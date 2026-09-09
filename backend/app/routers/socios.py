from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.seguridad import hashear_contrasena
from app.dependencias import PaginacionDep, SesionDep, SocioDeRuta, exigir_bibliotecario
from app.errores import ConflictoDeNegocio
from app.models.biblioteca import Socio
from app.schemas.error import DetalleDeError
from app.schemas.socio import SocioCrear, SocioRespuesta

router = APIRouter(
    prefix='/socios',
    tags=['Socios'],
    dependencies=[Depends(exigir_bibliotecario)],
    responses={401: {'model': DetalleDeError}, 403: {'model': DetalleDeError}},
)


@router.get('', response_model=list[SocioRespuesta], summary='Listar socios')
async def listar_socios(
    sesion: SesionDep,
    paginacion: PaginacionDep,
    activo: Annotated[bool | None, Query()] = None,
):
    consulta = select(Socio)
    if activo is not None:
        consulta = consulta.where(Socio.activo.is_(activo))
    consulta = consulta.order_by(Socio.nombre).offset(paginacion.desplazamiento).limit(paginacion.limite)
    resultado = await sesion.scalars(consulta)
    return list(resultado)


@router.get('/{socio_id}', response_model=SocioRespuesta, summary='Consultar un socio')
async def obtener_socio(socio: SocioDeRuta):
    return socio


@router.post(
    '',
    response_model=SocioRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary='Registrar un socio',
    responses={409: {'model': DetalleDeError}},
)
async def crear_socio(sesion: SesionDep, datos: SocioCrear):
    valores = datos.model_dump()
    contrasena = valores.pop('contrasena')
    socio = Socio(**valores, contrasena_hash=hashear_contrasena(contrasena))
    sesion.add(socio)
    try:
        await sesion.commit()
    except IntegrityError:
        await sesion.rollback()
        raise ConflictoDeNegocio('Ya existe un socio con ese documento o correo electrónico.')
    await sesion.refresh(socio)
    return socio
