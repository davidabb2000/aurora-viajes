"""Servicio centralizado de correo transaccional de Aurora Viajes."""

import html
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.core.configuracion import configuracion

logger = logging.getLogger("aurora-viajes.correos")


def _texto(valor: object) -> str:
    return html.escape(str(valor))


def _mensaje(asunto: str, destinatario: str, texto: str, cuerpo_html: str) -> MIMEMultipart:
    mensaje = MIMEMultipart("alternative")
    mensaje["Subject"] = asunto
    mensaje["From"] = configuracion.smtp_from
    mensaje["To"] = destinatario
    mensaje.attach(MIMEText(texto, "plain", "utf-8"))
    mensaje.attach(MIMEText(cuerpo_html, "html", "utf-8"))
    return mensaje


async def _enviar(asunto: str, destinatario: str, texto: str, cuerpo_html: str) -> bool:
    if not configuracion.smtp_host or not configuracion.smtp_user or not configuracion.smtp_password:
        logger.warning("SMTP no configurado. Correo para %s no enviado.", destinatario)
        return False
    mensaje = _mensaje(asunto, destinatario, texto, cuerpo_html)
    try:
        cliente = aiosmtplib.SMTP(
            hostname=configuracion.smtp_host,
            port=configuracion.smtp_port,
            use_tls=configuracion.smtp_port == 465,
            start_tls=False,
            timeout=15,
        )
        await cliente.connect()
        if configuracion.smtp_port != 465 and configuracion.smtp_use_tls:
            await cliente.starttls()
        await cliente.login(configuracion.smtp_user, configuracion.smtp_password)
        await cliente.send_message(mensaje)
        await cliente.quit()
        logger.info("Correo transaccional enviado a %s: %s", destinatario, asunto)
        return True
    except Exception:
        logger.exception("Error SMTP al enviar correo a %s: %s", destinatario, asunto)
        return False


def _plantilla(titulo: str, saludo: str, contenido: str, boton: tuple[str, str] | None = None) -> str:
    accion = ""
    if boton:
        texto_boton, enlace = boton
        accion = f'<p style="text-align:center;margin:28px 0"><a href="{_texto(enlace)}" style="background:#0f3d3e;color:#fff;padding:12px 24px;text-decoration:none;border-radius:5px;font-weight:600">{_texto(texto_boton)}</a></p>'
    return f'''<!doctype html><html lang="es"><body style="margin:0;background:#f7f4ee;font-family:Arial,sans-serif;color:#21201c"><div style="max-width:600px;margin:24px auto;background:#fff;padding:28px;border:1px solid #e4ddcb;border-radius:8px"><h2 style="color:#0f3d3e;margin-top:0">✦ Aurora Viajes</h2><h3 style="color:#0f3d3e">{_texto(titulo)}</h3><p>Hola <strong>{_texto(saludo)}</strong>,</p>{contenido}{accion}<hr style="border:0;border-top:1px solid #e4ddcb;margin-top:28px"><small style="color:#777">Este correo fue enviado automáticamente por Aurora Viajes.</small></div></body></html>'''


async def enviar_correo_recuperacion(destinatario: str, nombre_usuario: str, token: str) -> bool:
    enlace = f"{configuracion.frontend_url.rstrip('/')}/login?token={token}&vista=recuperar"
    texto = f"Aurora Viajes - Recuperar contraseña\n\nHola {nombre_usuario},\n\nUsa este enlace para crear una nueva contraseña:\n{enlace}\n\nEl enlace expira en 1 hora. Si no solicitaste el cambio, ignora este correo."
    contenido = "<p>Recibimos una solicitud para cambiar tu contraseña.</p><p>El enlace expira en <strong>1 hora</strong>. Si no fuiste tú, puedes ignorar este mensaje.</p>"
    return await _enviar("Recupera tu contraseña - Aurora Viajes", destinatario, texto, _plantilla("Recuperar contraseña", nombre_usuario, contenido, ("Crear nueva contraseña", enlace)))


async def enviar_correo_bienvenida(destinatario: str, nombre_usuario: str) -> bool:
    texto = f"Aurora Viajes - Bienvenido\n\nHola {nombre_usuario}, tu cuenta fue creada correctamente."
    contenido = "<p>Tu cuenta fue creada correctamente. Ya puedes explorar destinos y reservar tu próximo viaje.</p>"
    return await _enviar("Bienvenido a Aurora Viajes", destinatario, texto, _plantilla("¡Bienvenido a Aurora Viajes!", nombre_usuario, contenido, ("Explorar viajes", configuracion.frontend_url)))


async def enviar_correo_reserva(destinatario: str, nombre_usuario: str, reserva: dict) -> bool:
    estado = reserva.get("estado", "pendiente")
    destino = reserva.get("destino", "tu destino seleccionado")
    fecha_salida = reserva.get("fechaSalida", "")
    fecha_regreso = reserva.get("fechaRegreso", "")
    total = reserva.get("montoTotal", 0)
    texto = f"Aurora Viajes - Reserva registrada\n\nHola {nombre_usuario},\n\nDestino: {destino}\nSalida: {fecha_salida}\nRegreso: {fecha_regreso}\nPasajeros: {reserva.get('pasajeros', 1)}\nTotal: ${total}\nEstado: {estado}"
    contenido = f"<p>Registramos tu solicitud de viaje:</p><ul><li><strong>Destino:</strong> {_texto(destino)}</li><li><strong>Salida:</strong> {_texto(fecha_salida)}</li><li><strong>Regreso:</strong> {_texto(fecha_regreso)}</li><li><strong>Pasajeros:</strong> {_texto(reserva.get('pasajeros', 1))}</li><li><strong>Total:</strong> ${_texto(total)}</li><li><strong>Estado:</strong> {_texto(estado)}</li></ul><p>Te avisaremos cuando el estado de la reserva cambie.</p>"
    return await _enviar("Hemos recibido tu reserva - Aurora Viajes", destinatario, texto, _plantilla("Reserva registrada", nombre_usuario, contenido, ("Ver mis reservas", f"{configuracion.frontend_url.rstrip('/')}/panel")))
