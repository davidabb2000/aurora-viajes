"""Servicio centralizado de correo transaccional de Aurora Viajes."""

import base64
import html
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

import aiosmtplib
import httpx

from app.core.configuracion import configuracion

logger = logging.getLogger("aurora-viajes.correos")

# Colombia no tiene horario de verano: la hora local es siempre UTC-5.
HORA_DE_COLOMBIA = timezone(timedelta(hours=-5), "COT")
_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")
_METODOS_DE_PAGO = {
    "stripe": "Tarjeta en línea (Stripe)",
    "efectivo": "Efectivo",
    "transferencia": "Transferencia bancaria",
    "tarjeta": "Tarjeta (datáfono)",
}


@dataclass(frozen=True)
class Adjunto:
    nombre: str
    contenido: bytes
    tipo: str = "application/pdf"


def _texto(valor: object) -> str:
    return html.escape(str(valor))


def _mensaje(asunto: str, destinatario: str, texto: str, cuerpo_html: str, adjuntos: list[Adjunto]) -> MIMEMultipart:
    alternativa = MIMEMultipart("alternative")
    alternativa.attach(MIMEText(texto, "plain", "utf-8"))
    alternativa.attach(MIMEText(cuerpo_html, "html", "utf-8"))
    if adjuntos:
        mensaje = MIMEMultipart("mixed")
        mensaje.attach(alternativa)
        for adjunto in adjuntos:
            parte = MIMEApplication(adjunto.contenido, _subtype=adjunto.tipo.split("/")[-1])
            parte.add_header("Content-Disposition", "attachment", filename=adjunto.nombre)
            mensaje.attach(parte)
    else:
        mensaje = alternativa
    mensaje["Subject"] = asunto
    mensaje["From"] = formataddr((configuracion.smtp_from_nombre, configuracion.smtp_from), charset="utf-8")
    mensaje["To"] = destinatario
    return mensaje


async def _enviar_por_sendgrid(asunto: str, destinatario: str, texto: str, cuerpo_html: str, adjuntos: list[Adjunto]) -> bool:
    """Envía por la API HTTPS de SendGrid (202 = aceptado). Nunca escribe la clave en el log."""
    carga = {
        "personalizations": [{"to": [{"email": destinatario}]}],
        "from": {"email": configuracion.smtp_from, "name": configuracion.smtp_from_nombre},
        "subject": asunto,
        "content": [{"type": "text/plain", "value": texto}, {"type": "text/html", "value": cuerpo_html}],
    }
    if adjuntos:
        carga["attachments"] = [
            {
                "content": base64.b64encode(adjunto.contenido).decode("ascii"),
                "filename": adjunto.nombre,
                "type": adjunto.tipo,
                "disposition": "attachment",
            }
            for adjunto in adjuntos
        ]
    try:
        async with httpx.AsyncClient(timeout=15) as cliente:
            respuesta = await cliente.post(
                configuracion.sendgrid_api_url, json=carga, headers={"Authorization": f"Bearer {configuracion.clave_sendgrid}"}
            )
    except httpx.HTTPError:
        logger.exception("No se pudo llegar a SendGrid al enviar correo a %s: %s", destinatario, asunto)
        return False
    if respuesta.status_code != 202:
        logger.error("SendGrid rechazó el correo para %s (HTTP %s): %s", destinatario, respuesta.status_code, respuesta.text[:300])
        return False
    logger.info("Correo transaccional enviado a %s por SendGrid: %s", destinatario, asunto)
    return True


async def _enviar(asunto: str, destinatario: str, texto: str, cuerpo_html: str, adjuntos: list[Adjunto] | None = None) -> bool:
    adjuntos = adjuntos or []
    if configuracion.clave_sendgrid:
        return await _enviar_por_sendgrid(asunto, destinatario, texto, cuerpo_html, adjuntos)
    if not configuracion.smtp_host or not configuracion.smtp_user or not configuracion.smtp_password:
        logger.warning("SMTP no configurado. Correo para %s no enviado.", destinatario)
        return False
    mensaje = _mensaje(asunto, destinatario, texto, cuerpo_html, adjuntos)
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


def _plantilla(titulo: str, saludo: str, contenido: str, boton: tuple[str, str] | None = None, despues_del_boton: str = "") -> str:
    accion = ""
    if boton:
        texto_boton, enlace = boton
        accion = f'<p style="text-align:center;margin:28px 0"><a href="{_texto(enlace)}" style="background:#0f3d3e;color:#fff;padding:12px 24px;text-decoration:none;border-radius:5px;font-weight:600">{_texto(texto_boton)}</a></p>'
    return f'''<!doctype html><html lang="es"><body style="margin:0;background:#f7f4ee;font-family:Arial,sans-serif;color:#21201c"><div style="max-width:600px;margin:24px auto;background:#fff;padding:28px;border:1px solid #e4ddcb;border-radius:8px"><h2 style="color:#0f3d3e;margin-top:0">✦ Aurora Viajes</h2><h3 style="color:#0f3d3e">{_texto(titulo)}</h3><p>Hola <strong>{_texto(saludo)}</strong>,</p>{contenido}{accion}{despues_del_boton}<hr style="border:0;border-top:1px solid #e4ddcb;margin-top:28px"><small style="color:#777">Este correo fue enviado automáticamente por Aurora Viajes.</small></div></body></html>'''


async def enviar_correo_recuperacion(destinatario: str, nombre_usuario: str, token: str) -> bool:
    enlace = f"{configuracion.frontend_url.rstrip('/')}/restablecer?token={token}"
    texto = f"Aurora Viajes - Recuperar contraseña\n\nHola {nombre_usuario},\n\nUsa este enlace para crear una nueva contraseña:\n{enlace}\n\nEl enlace expira en 1 hora. Si no solicitaste el cambio, ignora este correo."
    contenido = (
        "<p>Recibimos una solicitud para cambiar tu contraseña.</p>"
        "<p>El enlace expira en <strong>1 hora</strong> y solo sirve una vez. Si no fuiste tú, puedes ignorar este mensaje: tu contraseña no cambia.</p>"
    )
    # El enlace va también en texto: algunos clientes de correo no muestran el botón o bloquean sus enlaces.
    respaldo = f'<p style="font-size:12px;color:#777;word-break:break-all">Si el botón no funciona, copia y pega este enlace en tu navegador:<br>{_texto(enlace)}</p>'
    cuerpo = _plantilla("Recuperar contraseña", nombre_usuario, contenido, ("Crear nueva contraseña", enlace), despues_del_boton=respaldo)
    return await _enviar("Recupera tu contraseña - Aurora Viajes", destinatario, texto, cuerpo)


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


# --------------------------------------------------------------------------- confirmación de pago


def pesos(valor: object) -> str:
    """Importe en pesos con el formato colombiano: $ 34.048.000 o $ 1.234,50."""
    numero = round(float(valor or 0), 2)
    if numero == int(numero):
        return "$ " + f"{int(numero):,}".replace(",", ".")
    entero, decimales = f"{numero:,.2f}".split(".")
    return "$ " + entero.replace(",", ".") + "," + decimales


def fecha_larga(valor: str | date) -> str:
    dia = valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])
    return f"{_DIAS[dia.weekday()]} {dia.day} de {_MESES[dia.month - 1]} de {dia.year}"


def _fecha_hora(valor: str) -> str:
    """Hora de un vuelo, tal como la programó la aerolínea (hora local del aeropuerto)."""
    momento = datetime.fromisoformat(str(valor))
    return f"{momento.day} de {_MESES[momento.month - 1]} de {momento.year}, {momento:%H:%M}"


def _momento_en_colombia(valor: str) -> str:
    """Un instante guardado en UTC (con o sin zona) mostrado en hora de Colombia."""
    momento = datetime.fromisoformat(str(valor))
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    local = momento.astimezone(HORA_DE_COLOMBIA)
    return f"{local.day} de {_MESES[local.month - 1]} de {local.year}, {local:%H:%M} (hora de Colombia)"


def _documento_oculto(numero: str | None) -> str:
    """Un correo no es un canal seguro: del documento solo se muestran los últimos cuatro dígitos."""
    numero = (numero or "").strip()
    return f"•••• {numero[-4:]}" if len(numero) > 4 else numero


def _en_texto(fragmento: str) -> str:
    """Un fragmento de HTML de estas plantillas (solo usan <strong> y <br>) como texto plano."""
    return html.unescape(fragmento.replace("<br>", " / ").replace("<strong>", "").replace("</strong>", ""))


def _seccion(titulo: str, filas: list[tuple[str, str]]) -> tuple[str, str]:
    """Una tabla de dos columnas (etiqueta, valor) en HTML y su versión en texto. Las celdas ya vienen escapadas."""
    celdas = "".join(
        f'<tr><td style="padding:6px 10px;color:#6b665b;width:38%;vertical-align:top;border-bottom:1px solid #f0ebdf">{etiqueta}</td>'
        f'<td style="padding:6px 10px;vertical-align:top;border-bottom:1px solid #f0ebdf">{valor}</td></tr>'
        for etiqueta, valor in filas
    )
    bloque = (
        f'<h4 style="color:#0f3d3e;margin:26px 0 6px;font-size:15px">{_texto(titulo)}</h4>'
        f'<table role="presentation" style="width:100%;border-collapse:collapse;font-size:14px">{celdas}</table>'
    )
    texto = f"\n{titulo.upper()}\n" + "\n".join(f"  {_en_texto(etiqueta)}: {_en_texto(valor)}" for etiqueta, valor in filas)
    return bloque, texto


def _vuelo(titulo: str, vuelo: dict) -> tuple[str, str]:
    filas = [
        ("Vuelo", f"{_texto(vuelo['aerolinea'])} · <strong>{_texto(vuelo['numeroVuelo'])}</strong>"),
        ("Ruta", f"{_texto(vuelo['origen'])} ({_texto(vuelo['origenPais'])}) → {_texto(vuelo['destino'])} ({_texto(vuelo['destinoPais'])})"),
        ("Salida", _texto(_fecha_hora(vuelo["fechaSalida"]))),
        ("Llegada", _texto(_fecha_hora(vuelo["fechaLlegada"]))),
    ]
    abordaje = " · ".join(parte for parte in (
        f"Terminal {vuelo['terminal']}" if vuelo.get("terminal") else "",
        f"Puerta {vuelo['puerta']}" if vuelo.get("puerta") else "",
    ) if parte)
    if abordaje:
        filas.append(("Abordaje", _texto(abordaje)))
    if vuelo.get("avion"):
        filas.append(("Avión", _texto(vuelo["avion"])))
    return _seccion(titulo, filas)


def contenido_de_pago(reserva: dict, cobro: dict) -> tuple[str, str]:
    """El detalle completo de una reserva pagada, en HTML y en texto plano.

    `reserva` es la de `reserva_a_dict`; `cobro` trae las líneas de la venta (lo que se facturó), sus totales
    y la factura. Se arma aparte del envío para poder probarlo sin enviar nada.
    """
    bloques: list[tuple[str, str]] = []

    pago = [
        ("Estado", "<strong>Pagado</strong> · reserva confirmada"),
        ("Total pagado", f"<strong>{_texto(pesos(cobro['total']))}</strong>"),
        ("Método de pago", _texto(_METODOS_DE_PAGO.get(reserva.get("metodoPago") or "", (reserva.get("metodoPago") or "—").capitalize()))),
    ]
    if reserva.get("pagadoEn"):
        pago.append(("Fecha del pago", _texto(_momento_en_colombia(reserva["pagadoEn"]))))
    if reserva.get("pagoReferencia"):
        pago.append(("Comprobante", _texto(reserva["pagoReferencia"])))
    if cobro.get("factura"):
        pago.append(("Factura", f"{_texto(cobro['factura'])} (adjunta en PDF)"))
    bloques.append(_seccion("Pago", pago))

    viaje = [
        ("Reserva", f"<strong>#{_texto(reserva['id'])}</strong>"),
        ("Destino", f"{_texto(reserva['ciudad'])}, {_texto(reserva['pais'])}"),
        ("Salida", _texto(fecha_larga(reserva["fechaSalida"]))),
        ("Regreso", _texto(fecha_larga(reserva["fechaRegreso"]))),
        ("Duración", f"{_texto(reserva['noches'])} noche(s)"),
        ("Pasajeros", _texto(reserva["pasajeros"])),
    ]
    if reserva.get("paquete"):
        viaje.append(("Paquete", _texto(reserva["paquete"]["nombre"])))
    if reserva.get("telefonoContacto"):
        viaje.append(("Teléfono de contacto", _texto(reserva["telefonoContacto"])))
    if reserva.get("notas"):
        viaje.append(("Notas", _texto(reserva["notas"])))
    bloques.append(_seccion("Tu viaje", viaje))

    if reserva.get("vuelo"):
        bloques.append(_vuelo("Vuelo de ida", reserva["vuelo"]))
    if reserva.get("vueloRegreso"):
        bloques.append(_vuelo("Vuelo de regreso", reserva["vueloRegreso"]))

    if reserva.get("hotel"):
        hotel = reserva["hotel"]
        bloques.append(_seccion("Hotel", [
            ("Hotel", f"<strong>{_texto(hotel['nombre'])}</strong> {'★' * int(hotel.get('estrellas') or 0)}"),
            ("Ciudad", f"{_texto(hotel['ciudad'])}, {_texto(hotel['pais'])}"),
            ("Estadía", f"{_texto(reserva['noches'])} noche(s), del día de salida al de regreso"),
        ]))

    if reserva.get("excursiones"):
        bloques.append(_seccion("Excursiones", [
            (_texto(excursion["nombre"]), f"{_texto(excursion['duracionHoras'])} h · {_texto(excursion['ciudad'])} · {_texto(excursion['cantidad'])} cupo(s)")
            for excursion in reserva["excursiones"]
        ]))

    if reserva.get("datosDePasajeros"):
        bloques.append(_seccion("Pasajeros registrados", [
            (f"Pasajero {numero}", f"{_texto(p['nombre'])} {_texto(p['apellido'])} · {_texto(p['tipoDocumento'])} {_texto(_documento_oculto(p['numeroDocumento']))}")
            for numero, p in enumerate(reserva["datosDePasajeros"], start=1)
        ]))

    lineas = [
        (_texto(linea["nombre"]), f"{_texto(linea['cantidad'])} × {_texto(pesos(linea['precioUnitario']))} = <strong>{_texto(pesos(linea['subtotal']))}</strong>")
        for linea in cobro["lineas"]
    ]
    lineas.append(("Subtotal", _texto(pesos(cobro["subtotal"]))))
    if float(cobro.get("descuento") or 0):
        lineas.append(("Descuento", "− " + _texto(pesos(cobro["descuento"]))))
    if float(cobro.get("impuestos") or 0):
        lineas.append(("Impuestos", _texto(pesos(cobro["impuestos"]))))
    lineas.append(("<strong>Total pagado</strong>", f"<strong>{_texto(pesos(cobro['total']))}</strong>"))
    bloques.append(_seccion("Detalle del cobro", lineas))

    introduccion = (
        f"<p>¡Recibimos tu pago! Tu reserva <strong>#{_texto(reserva['id'])}</strong> a <strong>{_texto(reserva['ciudad'])}, "
        f"{_texto(reserva['pais'])}</strong> quedó <strong>confirmada</strong>. Aquí tienes todos los detalles"
        f"{'; la factura va adjunta en PDF' if cobro.get('factura') else ''}.</p>"
    )
    cierre = "<p style=\"margin-top:24px\">Guarda este correo: te servirá como soporte durante el viaje. Si necesitas cambiar algo, respóndenos o escríbenos desde tu panel.</p>"
    cuerpo_html = introduccion + "".join(bloque for bloque, _ in bloques) + cierre
    cuerpo_texto = "".join(texto for _, texto in bloques)
    return cuerpo_html, cuerpo_texto


async def enviar_correo_pago_confirmado(destinatario: str, nombre_usuario: str, reserva: dict, cobro: dict, adjuntos: list[Adjunto] | None = None) -> bool:
    cuerpo_html, cuerpo_texto = contenido_de_pago(reserva, cobro)
    enlace = f"{configuracion.frontend_url.rstrip('/')}/reservas"
    texto = (
        f"Aurora Viajes - Pago confirmado\n\nHola {nombre_usuario},\n\n"
        f"Recibimos tu pago: la reserva #{reserva['id']} a {reserva['ciudad']}, {reserva['pais']} quedó confirmada.\n"
        f"{cuerpo_texto}\n\nVer mis reservas: {enlace}\n"
    )
    asunto = f"Pago confirmado · Reserva #{reserva['id']} a {reserva['ciudad']} - Aurora Viajes"
    return await _enviar(asunto, destinatario, texto, _plantilla("Pago confirmado", nombre_usuario, cuerpo_html, ("Ver mi reserva", enlace)), adjuntos)
