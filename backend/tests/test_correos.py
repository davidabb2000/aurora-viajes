"""Correo transaccional: por dónde sale (Railway bloquea el SMTP) y qué dicen los correos de recuperación y de pago."""

import asyncio
import base64

import httpx
import pytest

from app.core.configuracion import configuracion
from app.services import correos
from app.services.correos import Adjunto, contenido_de_pago, pesos
from tests.conftest import cuerpo_de_reserva


# --------------------------------------------------------------------------- por dónde sale el correo


@pytest.fixture
def smtp_de_sendgrid(monkeypatch):
    """La configuración que había en Railway: el SMTP de SendGrid, sin SENDGRID_API_KEY."""
    monkeypatch.setattr(configuracion, "sendgrid_api_key", None)
    monkeypatch.setattr(configuracion, "smtp_host", "smtp.sendgrid.net")
    monkeypatch.setattr(configuracion, "smtp_user", "apikey")
    monkeypatch.setattr(configuracion, "smtp_password", "SG.clave-del-smtp")


@pytest.fixture
def peticiones_https(monkeypatch):
    capturadas = []

    async def falsa(self, url, **kwargs):
        capturadas.append((url, kwargs))
        return httpx.Response(202)

    monkeypatch.setattr(httpx.AsyncClient, "post", falsa)
    return capturadas


def test_la_contrasena_del_smtp_de_sendgrid_sirve_como_clave_de_su_api(smtp_de_sendgrid, monkeypatch):
    assert configuracion.clave_sendgrid == "SG.clave-del-smtp"
    monkeypatch.setattr(configuracion, "sendgrid_api_key", "SG.explicita")
    assert configuracion.clave_sendgrid == "SG.explicita"  # la variable propia manda


def test_con_otro_smtp_no_se_inventa_una_clave_de_sendgrid(monkeypatch):
    monkeypatch.setattr(configuracion, "sendgrid_api_key", None)
    monkeypatch.setattr(configuracion, "smtp_host", "smtp.gmail.com")
    monkeypatch.setattr(configuracion, "smtp_user", "alguien@gmail.com")
    monkeypatch.setattr(configuracion, "smtp_password", "clave-de-aplicacion")
    assert configuracion.clave_sendgrid is None


def test_con_el_smtp_de_sendgrid_el_correo_sale_por_https_y_no_por_el_puerto_587(smtp_de_sendgrid, peticiones_https, monkeypatch):
    """Regresión: en Railway todo correo acababa en «Timed out connecting to smtp.sendgrid.net on port 587»."""

    def smtp_prohibido(*args, **kwargs):
        raise AssertionError("No debe abrirse una conexión SMTP")

    monkeypatch.setattr(correos.aiosmtplib, "SMTP", smtp_prohibido)
    assert asyncio.run(correos._enviar("Asunto", "cliente@example.com", "Hola", "<p>Hola</p>")) is True
    (url, datos), = peticiones_https
    assert url == configuracion.sendgrid_api_url
    assert datos["headers"] == {"Authorization": "Bearer SG.clave-del-smtp"}
    assert datos["json"]["from"] == {"email": configuracion.smtp_from, "name": "Aurora Viajes"}
    assert "attachments" not in datos["json"]


def test_los_adjuntos_viajan_en_base64_por_la_api(smtp_de_sendgrid, peticiones_https):
    adjunto = Adjunto("AUR-1.pdf", b"%PDF-1.4 contenido")
    assert asyncio.run(correos._enviar("Asunto", "cliente@example.com", "Hola", "<p>Hola</p>", [adjunto])) is True
    (_, datos), = peticiones_https
    assert datos["json"]["attachments"] == [
        {"content": base64.b64encode(b"%PDF-1.4 contenido").decode(), "filename": "AUR-1.pdf", "type": "application/pdf", "disposition": "attachment"}
    ]


def test_por_smtp_el_adjunto_va_en_un_mensaje_mixto():
    mensaje = correos._mensaje("Asunto", "cliente@example.com", "Hola", "<p>Hola</p>", [Adjunto("AUR-1.pdf", b"%PDF-1.4")])
    assert mensaje.get_content_type() == "multipart/mixed"
    partes = [parte.get_content_type() for parte in mensaje.walk()]
    assert "text/plain" in partes and "text/html" in partes and "application/pdf" in partes
    assert "Aurora Viajes" in mensaje["From"]


# --------------------------------------------------------------------------- recuperación de contraseña


def test_el_correo_de_recuperacion_trae_el_enlace_en_el_boton_y_en_texto(buzon):
    asyncio.run(correos.enviar_correo_recuperacion("cliente@example.com", "Ana", "token-de-prueba"))
    (correo,) = buzon
    enlace = f"{configuracion.frontend_url.rstrip('/')}/restablecer?token=token-de-prueba"
    assert correo.para == "cliente@example.com"
    assert correo.html.count(enlace) == 2  # botón y respaldo en texto
    assert enlace in correo.texto


# --------------------------------------------------------------------------- confirmación de pago


def test_pesos_con_formato_colombiano():
    assert pesos(34048000) == "$ 34.048.000"
    assert pesos(1234.5) == "$ 1.234,50"
    assert pesos(None) == "$ 0"


def test_el_detalle_del_pago_escapa_lo_que_escribio_el_cliente_y_oculta_documentos():
    reserva = {
        "id": 7, "ciudad": "París", "pais": "Francia", "fechaSalida": "2026-10-02", "fechaRegreso": "2026-10-08", "noches": 6,
        "pasajeros": 1, "paquete": None, "telefonoContacto": "3001112233", "notas": "<script>alert(1)</script>",
        "vuelo": None, "vueloRegreso": None, "hotel": None, "excursiones": [],
        "datosDePasajeros": [{"nombre": "Ana", "apellido": "Ruiz", "tipoDocumento": "CC", "numeroDocumento": "1020304050"}],
        "metodoPago": "stripe", "pagadoEn": "2026-09-22T17:28:29", "pagoReferencia": None,
    }
    cobro = {"lineas": [{"nombre": "Vuelo", "cantidad": 1, "precioUnitario": 900000, "subtotal": 900000}],
             "subtotal": 900000, "descuento": 0, "impuestos": 0, "total": 900000, "factura": "AUR-20260922-000009"}
    cuerpo_html, cuerpo_texto = contenido_de_pago(reserva, cobro)
    assert "<script>" not in cuerpo_html and "&lt;script&gt;" in cuerpo_html
    assert "1020304050" not in cuerpo_html and "•••• 4050" in cuerpo_html
    assert "viernes 2 de octubre de 2026" in cuerpo_html
    assert "22 de septiembre de 2026, 12:28 (hora de Colombia)" in cuerpo_html  # 17:28 UTC
    assert "Tarjeta en línea (Stripe)" in cuerpo_html
    assert "AUR-20260922-000009" in cuerpo_texto and "$ 900.000" in cuerpo_texto
    assert "<strong>" not in cuerpo_texto


def test_al_cobrar_en_mostrador_el_cliente_recibe_la_confirmacion_con_todo_el_detalle(api, admin, crear_cliente, viaje, reservar, venta_de, buzon):
    cliente = crear_cliente()
    reserva_id, creada = reservar(cliente, viaje, "carta", 2)
    buzon.clear()  # el acuse de la solicitud no interesa aquí

    cobro = api.post(f"/api/reservas/{reserva_id}/pago/manual", headers=admin, json={"metodo": "transferencia", "referencia": "TRX-2026-77"})
    assert cobro.status_code == 200, cobro.text

    (correo,) = buzon
    factura = venta_de(reserva_id)["factura"]["numero"]
    assert correo.para == cliente.correo
    assert f"Reserva #{reserva_id}" in correo.asunto and "Pago confirmado" in correo.asunto
    for dato in (
        viaje.ida["numeroVuelo"], viaje.vuelta["numeroVuelo"], viaje.hotel["nombre"], viaje.excursiones[0]["nombre"],
        "París", "Transferencia bancaria", "TRX-2026-77", factura, pesos(creada["montoTotal"]),
    ):
        assert dato in correo.html, dato
        assert dato in correo.texto, dato
    (pdf,) = correo.adjuntos
    assert pdf.nombre == f"{factura}.pdf" and pdf.contenido.startswith(b"%PDF")

    # Un segundo cobro se rechaza y no manda otro correo.
    assert api.post(f"/api/reservas/{reserva_id}/pago/manual", headers=admin, json={"metodo": "efectivo"}).status_code == 409
    assert len(buzon) == 1


def test_una_reserva_cobrada_al_registrarla_manda_solo_la_confirmacion_de_pago(api, admin, crear_cliente, viaje, buzon):
    cliente = crear_cliente()
    buzon.clear()  # el de bienvenida
    cuerpo = cuerpo_de_reserva(viaje, "paquete", 1, clienteId=cliente.id, pago={"metodo": "efectivo"})
    respuesta = api.post("/api/reservas", headers=admin, json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    (correo,) = buzon
    assert correo.para == cliente.correo and correo.asunto.startswith("Pago confirmado")
    assert viaje.paquete["nombre"] in correo.html


def test_una_reserva_sin_pagar_manda_el_acuse_y_no_la_confirmacion(crear_cliente, viaje, reservar, buzon):
    cliente = crear_cliente()
    buzon.clear()  # el de bienvenida
    reservar(cliente, viaje)
    (correo,) = buzon
    assert correo.para == cliente.correo and correo.asunto.startswith("Hemos recibido tu reserva")
