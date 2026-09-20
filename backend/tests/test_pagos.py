"""Pagos con Stripe: guardas del checkout, confirmación estricta y webhook firmado.

Nunca se llama a Stripe de verdad: las funciones que hablan con su API se sustituyen.
"""

import json

import pytest

from app.core.configuracion import configuracion
from tests.utiles import SECRETO_WEBHOOK, enviar_webhook, evento_de_pago, firmar, pagar_por_webhook


@pytest.fixture
def con_secreto_de_webhook(monkeypatch):
    monkeypatch.setattr(configuracion, "stripe_webhook_secret", SECRETO_WEBHOOK)


@pytest.fixture
def stripe_falso(monkeypatch):
    """Sustituye las llamadas a Stripe; `sesiones` es lo que Stripe "recuerda" por id."""
    estado = {"sesiones": {}, "creadas": 0}

    async def crear(reserva):
        estado["creadas"] += 1
        identificador = f"cs_test_{reserva.id}_{estado['creadas']}"
        estado["sesiones"][identificador] = {
            "id": identificador, "status": "open", "payment_status": "unpaid",
            "url": f"https://checkout.stripe.test/{identificador}",
            "amount_total": int(round(float(reserva.monto_total) * 100)), "currency": "cop",
            "metadata": {"reserva_id": str(reserva.id)},
        }
        return {"checkoutUrl": estado["sesiones"][identificador]["url"], "sessionId": identificador}

    async def obtener(identificador):
        from app.errores import ErrorDeDominio
        if identificador not in estado["sesiones"]:
            raise ErrorDeDominio("No se pudo validar el pago con Stripe.")
        return estado["sesiones"][identificador]

    monkeypatch.setattr("app.routers.pagos.crear_sesion", crear)
    monkeypatch.setattr("app.routers.pagos.obtener_sesion", obtener)
    return estado


def test_checkout_crea_un_enlace_y_lo_reutiliza(api, crear_cliente, viaje, reservar, stripe_falso):
    cliente = crear_cliente()
    reserva_id, _ = reservar(cliente, viaje)

    primero = api.post(f"/api/reservas/{reserva_id}/pago/checkout", headers=cliente.headers)
    segundo = api.post(f"/api/reservas/{reserva_id}/pago/checkout", headers=cliente.headers)
    assert primero.status_code == segundo.status_code == 200
    # Un solo enlace abierto por reserva: visitar la página de pago otra vez no abre un cobro nuevo.
    assert primero.json() == segundo.json()
    assert stripe_falso["creadas"] == 1


def test_checkout_abre_uno_nuevo_si_el_anterior_ya_no_esta_abierto(api, crear_cliente, viaje, reservar, stripe_falso):
    cliente = crear_cliente()
    reserva_id, _ = reservar(cliente, viaje)
    primero = api.post(f"/api/reservas/{reserva_id}/pago/checkout", headers=cliente.headers).json()
    stripe_falso["sesiones"][primero["sessionId"]]["status"] = "expired"

    nuevo = api.post(f"/api/reservas/{reserva_id}/pago/checkout", headers=cliente.headers).json()
    assert nuevo["sessionId"] != primero["sessionId"]
    assert stripe_falso["creadas"] == 2


def test_checkout_rechaza_una_reserva_ya_pagada(api, crear_cliente, viaje, reservar, stripe_falso, con_secreto_de_webhook):
    """Regresión: se podía abrir otro cobro (y pagar dos veces) aunque la reserva ya estuviera pagada."""
    cliente = crear_cliente()
    reserva_id, respuesta = reservar(cliente, viaje)
    pagar_por_webhook(api, reserva_id, respuesta["montoTotal"])

    resultado = api.post(f"/api/reservas/{reserva_id}/pago/checkout", headers=cliente.headers)
    assert resultado.status_code == 409
    assert "ya está pagada" in resultado.json()["mensaje"]
    assert stripe_falso["creadas"] == 0


def test_checkout_rechaza_una_reserva_cancelada(api, admin, crear_cliente, viaje, reservar, stripe_falso):
    cliente = crear_cliente()
    reserva_id, _ = reservar(cliente, viaje)
    api.patch(f"/api/reservas/{reserva_id}/estado", headers=admin, json={"estado": "cancelada"})

    resultado = api.post(f"/api/reservas/{reserva_id}/pago/checkout", headers=cliente.headers)
    assert resultado.status_code == 409
    assert stripe_falso["creadas"] == 0


def test_checkout_de_la_reserva_de_otro_cliente_esta_prohibido(api, crear_cliente, viaje, reservar, stripe_falso):
    dueno, intruso = crear_cliente(), crear_cliente()
    reserva_id, _ = reservar(dueno, viaje)
    assert api.post(f"/api/reservas/{reserva_id}/pago/checkout", headers=intruso.headers).status_code == 403


@pytest.mark.parametrize(
    "cambios, motivo",
    [
        ({"metadata": {}}, "sin reserva_id en la metadata"),
        ({"metadata": {"reserva_id": "999999"}}, "metadata de otra reserva"),
        ({"amount_total": 100}, "importe distinto del total"),
        ({"currency": "usd"}, "moneda distinta"),
        ({"payment_status": "unpaid"}, "sin pagar"),
    ],
)
def test_confirmar_pago_rechaza_sesiones_que_no_corresponden(api, crear_cliente, viaje, reservar, stripe_falso, cambios, motivo):
    cliente = crear_cliente()
    reserva_id, respuesta = reservar(cliente, viaje)
    abierta = api.post(f"/api/reservas/{reserva_id}/pago/checkout", headers=cliente.headers).json()
    sesion = stripe_falso["sesiones"][abierta["sessionId"]]
    sesion.update({"payment_status": "paid", "status": "complete", **cambios})

    resultado = api.post(f"/api/reservas/{reserva_id}/pago/confirmar", headers=cliente.headers, json={"sessionId": abierta["sessionId"]})
    assert resultado.status_code == 400, motivo
    assert api.get(f"/api/reservas/{reserva_id}", headers=cliente.headers).json()["estadoPago"] == "pendiente"


def test_confirmar_pago_acepta_una_sesion_correcta_y_es_idempotente(api, crear_cliente, viaje, reservar, stripe_falso, venta_de):
    cliente = crear_cliente()
    reserva_id, _ = reservar(cliente, viaje)
    abierta = api.post(f"/api/reservas/{reserva_id}/pago/checkout", headers=cliente.headers).json()
    stripe_falso["sesiones"][abierta["sessionId"]].update({"payment_status": "paid", "status": "complete"})

    cuerpo = {"sessionId": abierta["sessionId"]}
    assert api.post(f"/api/reservas/{reserva_id}/pago/confirmar", headers=cliente.headers, json=cuerpo).status_code == 200
    assert api.post(f"/api/reservas/{reserva_id}/pago/confirmar", headers=cliente.headers, json=cuerpo).status_code == 200
    assert api.get(f"/api/reservas/{reserva_id}", headers=cliente.headers).json()["estadoPago"] == "pagado"
    assert venta_de(reserva_id)["estado"] == "completada"


# ------------------------------------------------------------------ webhook


def test_webhook_sin_secreto_configurado_se_niega_a_operar(api):
    cuerpo = json.dumps(evento_de_pago(1, 1000)).encode()
    respuesta = api.post("/api/pagos/stripe/webhook", content=cuerpo, headers={"stripe-signature": firmar(cuerpo)})
    assert respuesta.status_code == 503


@pytest.mark.usefixtures("con_secreto_de_webhook")
class TestWebhookFirmado:
    def test_firma_invalida_es_rechazada(self, api, crear_cliente, viaje, reservar):
        cliente = crear_cliente()
        reserva_id, respuesta = reservar(cliente, viaje)
        resultado = enviar_webhook(api, evento_de_pago(reserva_id, respuesta["montoTotal"]), firma=firmar(b"otro cuerpo"))
        assert resultado.status_code == 400
        assert api.get(f"/api/reservas/{reserva_id}", headers=cliente.headers).json()["estadoPago"] == "pendiente"

    def test_sin_cabecera_de_firma_es_rechazado(self, api):
        cuerpo = json.dumps(evento_de_pago(1, 1000)).encode()
        assert api.post("/api/pagos/stripe/webhook", content=cuerpo).status_code == 400

    def test_firma_hecha_con_otro_secreto_es_rechazada(self, api):
        cuerpo = json.dumps(evento_de_pago(1, 1000)).encode()
        resultado = api.post("/api/pagos/stripe/webhook", content=cuerpo, headers={"stripe-signature": firmar(cuerpo, secreto="whsec_ajeno")})
        assert resultado.status_code == 400

    def test_marca_de_tiempo_antigua_es_rechazada(self, api):
        """Impide reenviar una petición firmada capturada hace tiempo."""
        cuerpo = json.dumps(evento_de_pago(1, 1000)).encode()
        vieja = firmar(cuerpo, marca=1_600_000_000)
        assert api.post("/api/pagos/stripe/webhook", content=cuerpo, headers={"stripe-signature": vieja}).status_code == 400

    def test_confirma_la_reserva_aunque_el_cliente_no_vuelva(self, api, crear_cliente, viaje, reservar, venta_de):
        cliente = crear_cliente()
        reserva_id, respuesta = reservar(cliente, viaje)

        resultado = enviar_webhook(api, evento_de_pago(reserva_id, respuesta["montoTotal"]))
        assert resultado.json() == {"recibido": True, "aplicado": True}
        reserva = api.get(f"/api/reservas/{reserva_id}", headers=cliente.headers).json()
        assert (reserva["estado"], reserva["estadoPago"]) == ("confirmada", "pagado")
        assert venta_de(reserva_id)["estado"] == "completada"

    def test_es_idempotente(self, api, crear_cliente, viaje, reservar):
        cliente = crear_cliente()
        reserva_id, respuesta = reservar(cliente, viaje)
        primero = enviar_webhook(api, evento_de_pago(reserva_id, respuesta["montoTotal"]))
        segundo = enviar_webhook(api, evento_de_pago(reserva_id, respuesta["montoTotal"]))
        assert primero.json()["aplicado"] is True
        assert segundo.status_code == 200 and segundo.json()["aplicado"] is False

    def test_no_aplica_un_pago_de_otro_importe(self, api, crear_cliente, viaje, reservar):
        cliente = crear_cliente()
        reserva_id, respuesta = reservar(cliente, viaje)
        resultado = enviar_webhook(api, evento_de_pago(reserva_id, respuesta["montoTotal"] - 1))
        # 200 para que Stripe no reintente; el caso queda en el log para revisarlo a mano.
        assert resultado.status_code == 200 and resultado.json()["aplicado"] is False
        assert api.get(f"/api/reservas/{reserva_id}", headers=cliente.headers).json()["estadoPago"] == "pendiente"

    def test_ignora_eventos_de_otro_tipo(self, api, crear_cliente, viaje, reservar):
        cliente = crear_cliente()
        reserva_id, respuesta = reservar(cliente, viaje)
        resultado = enviar_webhook(api, evento_de_pago(reserva_id, respuesta["montoTotal"], tipo="charge.refunded"))
        assert resultado.json()["aplicado"] is False

    def test_una_reserva_que_ya_no_existe_se_reconoce_sin_error(self, api):
        assert enviar_webhook(api, evento_de_pago(987654, 1000)).status_code == 200

    def test_un_pago_sobre_una_reserva_cancelada_no_la_reactiva(self, api, admin, crear_cliente, viaje, reservar, venta_de):
        cliente = crear_cliente()
        reserva_id, respuesta = reservar(cliente, viaje)
        api.patch(f"/api/reservas/{reserva_id}/estado", headers=admin, json={"estado": "cancelada"})

        enviar_webhook(api, evento_de_pago(reserva_id, respuesta["montoTotal"]))
        reserva = api.get(f"/api/reservas/{reserva_id}", headers=cliente.headers).json()
        assert reserva["estado"] == "cancelada"  # el cobro queda visible para reembolsarlo a mano
        assert reserva["estadoPago"] == "pagado"
        assert venta_de(reserva_id)["estado"] == "cancelada"
