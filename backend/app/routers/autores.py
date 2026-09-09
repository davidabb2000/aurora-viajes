from fastapi import APIRouter, Response, status

from app.crud import autores as crud_autores
from app.dependencias import AutorDeRuta, PaginacionDep, SesionDep
from app.schemas.autor import AutorActualizar, AutorCrear, AutorRespuesta
from app.schemas.error import DetalleDeError

router = APIRouter(prefix='/autores', tags=['Autores'], responses={404: {'model': DetalleDeError}})


@router.get('', response_model=list[AutorRespuesta], summary='Listar autores')
async def listar_autores(sesion: SesionDep, paginacion: PaginacionDep):
    return await crud_autores.listar(sesion, limite=paginacion.limite, desplazamiento=paginacion.desplazamiento)


@router.get('/{autor_id}', response_model=AutorRespuesta, summary='Consultar un autor')
async def obtener_autor(autor: AutorDeRuta):
    return autor


@router.post('', response_model=AutorRespuesta, status_code=status.HTTP_201_CREATED, summary='Registrar un autor', responses={409: {'model': DetalleDeError}})
async def crear_autor(sesion: SesionDep, datos: AutorCrear):
    return await crud_autores.crear(sesion, datos.model_dump())


@router.patch('/{autor_id}', response_model=AutorRespuesta, summary='Actualizar parcialmente un autor', responses={409: {'model': DetalleDeError}})
async def actualizar_autor(sesion: SesionDep, autor: AutorDeRuta, datos: AutorActualizar):
    cambios = datos.model_dump(exclude_unset=True)
    return await crud_autores.actualizar(sesion, autor, cambios)


@router.delete('/{autor_id}', status_code=status.HTTP_204_NO_CONTENT, summary='Eliminar un autor', responses={409: {'model': DetalleDeError}})
async def eliminar_autor(sesion: SesionDep, autor: AutorDeRuta):
    await crud_autores.eliminar(sesion, autor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
