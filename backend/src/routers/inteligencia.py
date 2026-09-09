from typing import Annotated
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from pydantic import BaseModel

from src.dependencias import SesionDep, UsuarioLogueado, AgenteLogueado
from src.models.viajes import Paquete
from src.services.recomendaciones import ProveedorNoDisponible, ServicioDeRecomendaciones

router = APIRouter(prefix='/ia', tags=['Inteligencia Artificial'])

class SolicitudRecomendacion(BaseModel):
    intereses: str

class SolicitudRiesgo(BaseModel):
    dias_antelacion: int
    precio_paquete: int
    reservas_previas: int
    cancelaciones_previas: int

@router.post('/recomendaciones', summary="Recomendar paquetes turísticos con LLM")
async def obtener_recomendaciones(
    datos: SolicitudRecomendacion, 
    sesion: SesionDep, 
    usuario: UsuarioLogueado, 
    peticion: Request
):
    servicio_ia: ServicioDeRecomendaciones = peticion.app.state.ia
    
    consulta = select(Paquete).options(joinedload(Paquete.destino)).limit(20)
    resultado = await sesion.scalars(consulta)
    catalogo = [
        {"id": p.id, "titulo": p.titulo, "precio": p.precio_base, "destino": p.destino.nombre}
        for p in resultado.unique()
    ]
    
    try:
        sugerencias = await servicio_ia.recomendar(datos.intereses, catalogo)
        origen = "modelo_externo"
    except ProveedorNoDisponible:
        sugerencias = servicio_ia.respaldo_local(datos.intereses, catalogo)
        origen = "catalogo_local"
        
    return {"generada_por": origen, "recomendaciones": sugerencias}

@router.post('/riesgo', summary="Evaluar riesgo de cancelación (Solo Agentes)")
async def evaluar_riesgo(
    datos: SolicitudRiesgo, 
    agente: AgenteLogueado, 
    peticion: Request
):
    servicio_riesgo = peticion.app.state.riesgo
    probabilidad = await run_in_threadpool(servicio_riesgo.predecir, datos.model_dump())
    nivel, recomendacion = servicio_riesgo.clasificar(probabilidad)
    
    return {
        "probabilidad_cancelacion": round(probabilidad, 4),
        "nivel": nivel,
        "recomendacion": recomendacion,
        "version_modelo": servicio_riesgo.version
    }