"""Notificaciones al socio. En clase se escriben al log; en producción irían
a un servicio de correo a través de una cola con reintentos."""

import logging

logger = logging.getLogger('biblioapi.notificaciones')


async def avisar_prestamo_registrado(email: str, titulo: str, fecha_devolucion: str) -> None:
    try:
        logger.info('Correo a %s: «%s» debe devolverse antes del %s.', email, titulo, fecha_devolucion)
    except Exception:
        logger.exception('Falló la notificación de préstamo a %s', email)