from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from src.dependencias import SesionDep, AgenteLogueado
from src.models.viajes import RegistroAuditoria

router = APIRouter(prefix='/auditoria', tags=['Auditoría'])

class EventoAuditoriaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    momento: datetime
    accion: str
    recurso: str
    recurso_id: int
    usuario_id: int | None
    detalle: str | None

@router.get('', response_model=list[EventoAuditoriaRespuesta], summary="Consultar registros de auditoría (Solo Agentes)")
async def listar_auditoria(
    sesion: SesionDep,
    agente: AgenteLogueado,
    limite: Annotated[int, Query(ge=1, le=100)] = 20
):
    consulta = select(RegistroAuditoria).order_by(RegistroAuditoria.momento.desc()).limit(limite)
    resultado = await sesion.scalars(consulta)
    return list(resultado)