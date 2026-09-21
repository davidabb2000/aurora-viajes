"""Pago de reservas con Stripe: enlace de cobro, confirmación desde el navegador y webhook."""

import json
import logging

from fastapi import APIRouter, Request

from app.dependencias import EmpleadoOAdmin, ReservaDeRuta, SesionDep, UsuarioActual, exigir_acceso_a_reserva
from app.errores import ConflictoDeNegocio, ErrorDeDominio
from app.models.dominio import Reserva
from app.schemas.reservas import ConfirmacionDePago, PagoDeMostrador
from app.services.pagos import (
    crear_sesion,
    expirar_sesion,
    monto_esperado,
    obtener_sesion,
    registrar_pago,
    validar_sesion_pagada,
    verificar_firma_webhook,
)
from app.services.reservas import registrar_pago_de_mostrador

logger = logging.getLogger("aurora-viajes.pagos")
router = APIRouter(tags=["pagos"])

EVENTOS_DE_PAGO = {"checkout.session.completed", "checkout.session.async_payment_succeeded"}


def _exigir_cobrable(reserva: Reserva) -> None:
    if reserva.estado_rel.codigo == "cancelada":
        raise ConflictoDeNegocio("La reserva está cancelada y no se puede pagar.")
    if reserva.estado_pago_rel.codigo == "pagado":
        raise ConflictoDeNegocio("Esta reserva ya está pagada.")


@router.post("/api/reservas/{reserva_id}/pago/checkout")
async def crear_checkout(reserva: ReservaDeRuta, usuario: UsuarioActual, sesion: SesionDep):
    exigir_acceso_a_reserva(usuario, reserva)
    # Sin estas guardas se podía abrir un cobro nuevo cada vez que se visitaba la
    # página de pago, incluso con la reserva ya pagada.
    _exigir_cobrable(reserva)

    if reserva.stripe_session_id:
        try:
            previa = await obtener_sesion(reserva.stripe_session_id)
        except ErrorDeDominio:
            previa = None
        if previa is not None:
            if previa.get("payment_status") == "paid":
                validar_sesion_pagada(previa, reserva)
                await registrar_pago(sesion, reserva, previa["id"])
                raise ConflictoDeNegocio("Esta reserva ya está pagada.")
            if previa.get("status") == "open" and previa.get("url") and previa.get("amount_total") == monto_esperado(reserva):
                # Un solo enlace abierto por reserva evita que se pague dos veces.
                return {"checkoutUrl": previa["url"], "sessionId": previa["id"]}

    nueva = await crear_sesion(reserva)
    reserva.stripe_session_id = nueva["sessionId"]
    await sesion.commit()
    return nueva


@router.post("/api/reservas/{reserva_id}/pago/confirmar")
async def confirmar_pago(reserva: ReservaDeRuta, usuario: UsuarioActual, sesion: SesionDep, payload: ConfirmacionDePago | None = None):
    """Respaldo cuando el cliente vuelve de Stripe; el webhook es la vía principal."""
    exigir_acceso_a_reserva(usuario, reserva)
    if reserva.estado_pago_rel.codigo == "pagado":
        return {"mensaje": "Pago confirmado correctamente."}
    session_id = (payload.sessionId.strip() if payload and payload.sessionId else "") or reserva.stripe_session_id or ""
    if not session_id:
        raise ErrorDeDominio("No se encontró la sesión de pago de Stripe.")
    datos = await obtener_sesion(session_id)
    validar_sesion_pagada(datos, reserva)
    await registrar_pago(sesion, reserva, session_id)
    return {"mensaje": "Pago confirmado correctamente."}


@router.post("/api/reservas/{reserva_id}/pago/manual")
async def cobrar_en_mostrador(reserva: ReservaDeRuta, payload: PagoDeMostrador, personal: EmpleadoOAdmin, sesion: SesionDep):
    """El personal registra un pago recibido en efectivo, por transferencia o con datáfono."""
    sesion_de_pago = reserva.stripe_session_id
    await registrar_pago_de_mostrador(sesion, reserva, payload, personal)
    # Si había un enlace de Stripe abierto se cierra: la reserva no debe poder pagarse dos veces.
    await expirar_sesion(sesion_de_pago)
    return {"mensaje": "Pago registrado. La reserva quedó confirmada."}


@router.post("/api/pagos/stripe/webhook")
async def webhook_stripe(peticion: Request, sesion: SesionDep):
    """Stripe avisa aquí de cada pago, aunque el cliente cierre el navegador antes de volver."""
    cuerpo = await peticion.body()
    verificar_firma_webhook(cuerpo, peticion.headers.get("stripe-signature"))
    try:
        evento = json.loads(cuerpo)
    except json.JSONDecodeError as exc:
        raise ErrorDeDominio("El cuerpo del webhook no es JSON válido.") from exc

    if evento.get("type") not in EVENTOS_DE_PAGO:
        return {"recibido": True, "aplicado": False}
    objeto = (evento.get("data") or {}).get("object") or {}
    try:
        reserva_id = int((objeto.get("metadata") or {}).get("reserva_id") or objeto.get("client_reference_id"))
    except (TypeError, ValueError):
        logger.warning("Webhook %s sin reserva identificable.", evento.get("id"))
        return {"recibido": True, "aplicado": False}

    reserva = await sesion.get(Reserva, reserva_id)
    if reserva is None:
        logger.warning("Webhook %s: la reserva %s ya no existe (¿pago de una reserva eliminada?).", evento.get("id"), reserva_id)
        return {"recibido": True, "aplicado": False}
    try:
        validar_sesion_pagada(objeto, reserva)
    except ErrorDeDominio as exc:
        # Se responde 200 para que Stripe no reintente: es un caso para revisar a mano.
        logger.error("Webhook %s no aplicado a la reserva %s: %s", evento.get("id"), reserva_id, exc.mensaje)
        return {"recibido": True, "aplicado": False}
    aplicado = await registrar_pago(sesion, reserva, objeto.get("id"))
    return {"recibido": True, "aplicado": aplicado}
