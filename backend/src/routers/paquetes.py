from typing import Annotated
from datetime import date
from fastapi import APIRouter, Query, Response, status, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.dependencias import SesionDep, AgenteLogueado
from src.models.viajes import Paquete, Salida, Destino

router = APIRouter(prefix='/paquetes', tags=['Paquetes Turísticos'])

@router.get('', summary="Listar catálogo de paquetes turísticos")
async def listar_paquetes(
    sesion: SesionDep,
    destino_id: Annotated[int | None, Query()] = None,
    precio_max: Annotated[int | None, Query(ge=0)] = None,
    limite: Annotated[int, Query(ge=1, le=50)] = 10,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
):
    consulta = select(Paquete).options(joinedload(Paquete.destino), joinedload(Paquete.tipo_turismo))
    
    if destino_id is not None:
        consulta = consulta.where(Paquete.destino_id == destino_id)
    if precio_max is not None:
        consulta = consulta.where(Paquete.precio_base <= precio_max)
        
    consulta = consulta.offset(desplazamiento).limit(limite)
    resultado = await sesion.scalars(consulta)
    return list(resultado.unique())

@router.get('/{paquete_id}', summary="Obtener detalle de un paquete")
async def obtener_paquete(paquete_id: int, sesion: SesionDep):
    paquete = await sesion.get(Paquete, paquete_id, options=[joinedload(Paquete.destino), joinedload(Paquete.tipo_turismo), joinedload(Paquete.salidas)])
    if not paquete:
        raise HTTPException(status_code=404, detail="Paquete turístico no encontrado.")
    return paquete

@router.post('', status_code=status.HTTP_201_CREATED, summary="Registrar paquete (Solo Agentes)")
async def crear_paquete(datos: dict, sesion: SesionDep, agente: AgenteLogueado):
    # Validar que el destino exista
    destino = await sesion.get(Destino, datos.get('destino_id'))
    if not destino:
        raise HTTPException(status_code=404, detail="El destino especificado no existe.")
        
    nuevo_paquete = Paquete(
        titulo=datos.get('titulo'),
        precio_base=datos.get('precio_base'),
        destino_id=datos.get('destino_id'),
        tipo_turismo_id=datos.get('tipo_turismo_id')
    )
    sesion.add(nuevo_paquete)
    await sesion.commit()
    await sesion.refresh(nuevo_paquete)
    return nuevo_paquete

@router.delete('/{paquete_id}', status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar paquete (Solo Agentes)")
async def eliminar_paquete(paquete_id: int, sesion: SesionDep, agente: AgenteLogueado):
    paquete = await sesion.get(Paquete, paquete_id)
    if not paquete:
        raise HTTPException(status_code=404, detail="Paquete no encontrado.")
        
    await sesion.delete(paquete)
    await sesion.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)