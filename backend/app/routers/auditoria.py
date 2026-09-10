from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.dependencias import Bibliotecario, SesionDep
from app.models.biblioteca import RegistroAuditoria

router = APIRouter(prefix='/auditoria', tags=['Auditoría'])


class EventoRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    momento: datetime
    accion: str
    recurso: str
    recurso_id: int
    autor_id: int | None
    detalle: str | None


@router.get('', response_model=list[EventoRespuesta], summary='Consultar la auditoría')
async def listar_eventos(
    sesion: SesionDep,
    bibliotecario: Bibliotecario,
    accion: Annotated[str | None, Query()] = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
):
    consulta = select(RegistroAuditoria)
    if accion is not None:
        consulta = consulta.where(RegistroAuditoria.accion == accion)
    resultado = await sesion.scalars(consulta.order_by(RegistroAuditoria.momento.desc()).limit(limite))
    return list(resultado)