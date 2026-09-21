"""Cobros con Stripe Checkout: sesiones, verificación del pago, firma del webhook y registro en la reserva."""

import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.configuracion import configuracion
from app.errores import ErrorDeDominio, ServicioNoDisponible
from app.models.dominio import EstadoPago, EstadoReserva, MetodoPago, Reserva
from app.services.reservas import sincronizar_venta

logger = logging.getLogger("aurora-viajes.pagos")

API_STRIPE = "https://api.stripe.com/v1"
VERSION_API_STRIPE = "2024-06-20"
MONEDA = "cop"
# El peso colombiano es una moneda de dos decimales en Stripe: se envía en centavos.
FACTOR_STRIPE_MONEDA = Decimal("100")
TOLERANCIA_WEBHOOK_SEGUNDOS = 300


def stripe_configurado() -> bool:
    return bool(configuracion.stripe_secret_key and configuracion.stripe_secret_key.strip())


def webhook_configurado() -> bool:
    return bool(configuracion.stripe_webhook_secret and configuracion.stripe_webhook_secret.strip())


def url_frontend(ruta: str) -> str:
    return f"{configuracion.frontend_url.rstrip('/')}/{ruta.lstrip('/')}"


def monto_esperado(reserva: Reserva) -> int:
    """Total de la reserva en la unidad mínima de cobro de Stripe."""
    return int((Decimal(reserva.monto_total or 0) * FACTOR_STRIPE_MONEDA).to_integral_value())


async def _llamar_stripe(metodo: str, ruta: str, mensaje_error: str, data: dict | None = None) -> dict:
    if not stripe_configurado():
        raise ErrorDeDominio("Stripe no está configurado. Define STRIPE_SECRET_KEY para habilitar pagos reales.")
    async with httpx.AsyncClient(timeout=30.0) as cliente:
        respuesta = await cliente.request(
            metodo,
            f"{API_STRIPE}{ruta}",
            data=data,
            auth=(configuracion.stripe_secret_key, ""),
            headers={"Stripe-Version": VERSION_API_STRIPE},
        )
    if respuesta.status_code >= 400:
        logger.error("Stripe %s %s falló: %s", metodo, ruta, respuesta.text)
        raise ErrorDeDominio(mensaje_error)
    return respuesta.json()


async def crear_sesion(reserva: Reserva) -> dict:
    monto = monto_esperado(reserva)
    if monto <= 0:
        raise ErrorDeDominio("La reserva no tiene un monto válido para cobrar.")
    datos = {
        "mode": "payment",
        "success_url": url_frontend(f"reservas/pago-exitoso?reserva_id={reserva.id}&session_id={{CHECKOUT_SESSION_ID}}"),
        "cancel_url": url_frontend(f"reservas/pago/{reserva.id}"),
        "customer_email": reserva.usuario.correo if reserva.usuario else None,
        "client_reference_id": str(reserva.id),
        "metadata[reserva_id]": str(reserva.id),
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": MONEDA,
        "line_items[0][price_data][unit_amount]": str(monto),
        "line_items[0][price_data][product_data][name]": f"Reserva a {reserva.destino_rel.nombre if reserva.destino_rel else reserva.destino_id}",
    }
    respuesta = await _llamar_stripe(
        "POST", "/checkout/sessions", "No se pudo crear la sesión de pago con Stripe.",
        {clave: valor for clave, valor in datos.items() if valor is not None},
    )
    if not respuesta.get("url") or not respuesta.get("id"):
        raise ErrorDeDominio("Stripe no devolvió una sesión válida.")
    return {"checkoutUrl": respuesta["url"], "sessionId": respuesta["id"]}


async def obtener_sesion(session_id: str) -> dict:
    return await _llamar_stripe("GET", f"/checkout/sessions/{session_id}", "No se pudo validar el pago con Stripe.")


async def expirar_sesion(session_id: str | None) -> None:
    """Cierra un enlace de pago que ya no debe usarse. Es un esfuerzo razonable, no una garantía."""
    if not session_id or not stripe_configurado():
        return
    try:
        await _llamar_stripe("POST", f"/checkout/sessions/{session_id}/expire", "No se pudo expirar la sesión de pago.")
    except (ErrorDeDominio, httpx.HTTPError):
        logger.info("La sesión %s no se pudo expirar (ya estaba pagada o cerrada).", session_id)


def validar_sesion_pagada(sesion_stripe: dict, reserva: Reserva) -> None:
    """La sesión debe estar pagada, ser de esta reserva y cobrar exactamente su total.

    Antes se aceptaba una sesión sin `reserva_id` en la metadata y nunca se
    comparaba el importe cobrado con el de la reserva.
    """
    if sesion_stripe.get("payment_status") != "paid":
        raise ErrorDeDominio("El pago aún no está confirmado en Stripe.")
    metadata = sesion_stripe.get("metadata") or {}
    if str(metadata.get("reserva_id", "")) != str(reserva.id):
        raise ErrorDeDominio("La sesión de Stripe no coincide con la reserva.")
    if sesion_stripe.get("amount_total") != monto_esperado(reserva) or str(sesion_stripe.get("currency", "")).lower() != MONEDA:
        raise ErrorDeDominio("El monto pagado no coincide con el total de la reserva.")


def verificar_firma_webhook(cuerpo: bytes, cabecera: str | None, ahora: float | None = None) -> None:
    """Comprueba la cabecera Stripe-Signature (esquema v1: HMAC-SHA256 de "marca.cuerpo").

    Sin esta comprobación cualquiera podría avisar de un pago que nunca ocurrió,
    así que sin secreto configurado el endpoint se niega a operar.
    """
    if not webhook_configurado():
        raise ServicioNoDisponible("El webhook de Stripe no está configurado (falta STRIPE_WEBHOOK_SECRET).")
    if not cabecera:
        raise ErrorDeDominio("Falta la cabecera Stripe-Signature.")
    partes = [trozo.strip().split("=", 1) for trozo in cabecera.split(",") if "=" in trozo]
    marcas = [valor for clave, valor in partes if clave == "t"]
    firmas = [valor for clave, valor in partes if clave == "v1"]
    if not marcas or not firmas:
        raise ErrorDeDominio("La cabecera Stripe-Signature no es válida.")
    esperada = hmac.new(
        configuracion.stripe_webhook_secret.strip().encode(), f"{marcas[0]}.".encode() + cuerpo, hashlib.sha256
    ).hexdigest()
    if not any(hmac.compare_digest(esperada, firma) for firma in firmas):
        raise ErrorDeDominio("La firma del webhook no es válida.")
    try:
        marca = int(marcas[0])
    except ValueError as exc:
        raise ErrorDeDominio("La marca de tiempo del webhook no es válida.") from exc
    if abs((ahora if ahora is not None else time.time()) - marca) > TOLERANCIA_WEBHOOK_SEGUNDOS:
        raise ErrorDeDominio("El webhook llegó fuera del margen de tiempo permitido.")


async def registrar_pago(sesion: AsyncSession, reserva: Reserva, session_id: str | None) -> bool:
    """Marca la reserva como pagada y confirmada. Devuelve False si ya lo estaba.

    Es idempotente a propósito: el navegador y el webhook pueden avisar del mismo
    pago, en cualquier orden y varias veces.
    """
    if reserva.estado_pago_rel.codigo == "pagado":
        return False
    reserva.estado_pago_rel = await sesion.scalar(select(EstadoPago).where(EstadoPago.codigo == "pagado"))
    reserva.metodo_pago_rel = await sesion.scalar(select(MetodoPago).where(MetodoPago.codigo == "stripe"))
    reserva.stripe_session_id = session_id or reserva.stripe_session_id
    reserva.pagado_en = datetime.now(timezone.utc)
    if reserva.estado_rel.codigo == "pendiente":
        reserva.estado_rel = await sesion.scalar(select(EstadoReserva).where(EstadoReserva.codigo == "confirmada"))
    elif reserva.estado_rel.codigo == "cancelada":
        logger.warning("Pago recibido para la reserva cancelada %s: requiere un reembolso manual.", reserva.id)
    await sincronizar_venta(sesion, reserva)
    await sesion.commit()
    return True
