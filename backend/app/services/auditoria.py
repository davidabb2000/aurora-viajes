"""Registro de auditoría. Se ejecuta en segundo plano, con su propia sesión."""

import logging

from app.core.base_datos import FabricaDeSesiones
from app.models.biblioteca import RegistroAuditoria

logger = logging.getLogger('biblioapi.auditoria')


async def registrar_evento(
    accion: str,
    recurso: str,
    recurso_id: int,
    autor_id: int | None = None,
    detalle: str | None = None,
) -> None:
    try:
        async with FabricaDeSesiones() as sesion:
            sesion.add(
                RegistroAuditoria(
                    accion=accion,
                    recurso=recurso,
                    recurso_id=recurso_id,
                    autor_id=autor_id,
                    detalle=detalle,
                )
            )
            await sesion.commit()
    except Exception:
        logger.exception('No se pudo registrar la auditoría de %s %s', accion, recurso_id)