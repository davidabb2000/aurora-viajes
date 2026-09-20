"""Ayudas para los tests de pagos: eventos y firmas de Stripe."""

import hashlib
import hmac
import json
import time

from app.core.configuracion import configuracion

SECRETO_WEBHOOK = "whsec_de_pruebas"


def firmar(cuerpo: bytes, secreto: str = SECRETO_WEBHOOK, marca: int | None = None) -> str:
    """Cabecera Stripe-Signature válida para un cuerpo, igual que la genera Stripe."""
    marca = int(time.time()) if marca is None else marca
    firma = hmac.new(secreto.encode(), f"{marca}.".encode() + cuerpo, hashlib.sha256).hexdigest()
    return f"t={marca},v1={firma}"


def evento_de_pago(reserva_id, monto, session_id="cs_test_1", tipo="checkout.session.completed", **cambios) -> dict:
    """Evento de Stripe por una sesión pagada. `monto` está en pesos; Stripe lo cobra en centavos."""
    objeto = {
        "id": session_id,
        "payment_status": "paid",
        "amount_total": int(round(monto * 100)),
        "currency": "cop",
        "metadata": {"reserva_id": str(reserva_id)},
        "client_reference_id": str(reserva_id),
    }
    objeto.update(cambios)
    return {"id": "evt_prueba", "type": tipo, "data": {"object": objeto}}


def enviar_webhook(api, evento: dict, firma: str | None = None):
    cuerpo = json.dumps(evento).encode()
    cabeceras = {"content-type": "application/json", "stripe-signature": firma or firmar(cuerpo)}
    return api.post("/api/pagos/stripe/webhook", content=cuerpo, headers=cabeceras)


def pagar_por_webhook(api, reserva_id, monto, session_id="cs_test_1"):
    """Simula el aviso de Stripe de que la reserva se pagó. Configura el secreto solo durante la llamada."""
    anterior = configuracion.stripe_webhook_secret
    configuracion.stripe_webhook_secret = SECRETO_WEBHOOK
    try:
        respuesta = enviar_webhook(api, evento_de_pago(reserva_id, monto, session_id))
    finally:
        configuracion.stripe_webhook_secret = anterior
    assert respuesta.status_code == 200 and respuesta.json()["aplicado"] is True, respuesta.text
