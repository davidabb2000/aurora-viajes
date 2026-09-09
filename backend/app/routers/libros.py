from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.crud import libros as crud_libros
from app.dependencias import Bibliotecario, LibroDeRuta, PaginacionDep, SesionDep
from app.schemas.error import DetalleDeError
from app.schemas.libro import LibroActualizar, LibroCrear, LibroRespuesta

router = APIRouter(prefix='/libros', tags=['Libros'], responses={404: {'model': DetalleDeError}})


@router.get('', response_model=list[LibroRespuesta], summary='Listar el catálogo')
async def listar_libros(
    sesion: SesionDep,
    paginacion: PaginacionDep,
    categoria: Annotated[str | None, Query()] = None,
    anio_min: Annotated[int | None, Query(ge=1450, le=2100)] = None,
    buscar: Annotated[str | None, Query(min_length=3, max_length=80)] = None,
    solo_disponibles: Annotated[bool, Query()] = False,
):
    return await crud_libros.listar(
        sesion,
        categoria=categoria,
        anio_min=anio_min,
        buscar=buscar,
        solo_disponibles=solo_disponibles,
        limite=paginacion.limite,
        desplazamiento=paginacion.desplazamiento,
    )


@router.get('/disponibles', response_model=list[LibroRespuesta], summary='Listar solo libros disponibles')
async def listar_disponibles(sesion: SesionDep, paginacion: PaginacionDep):
    return await crud_libros.listar(
        sesion,
        solo_disponibles=True,
        limite=paginacion.limite,
        desplazamiento=paginacion.desplazamiento,
    )


@router.get('/{libro_id}', response_model=LibroRespuesta, summary='Consultar un libro')
async def obtener_libro(libro: LibroDeRuta):
    return libro


@router.post(
    '',
    response_model=LibroRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary='Registrar un libro',
    responses={409: {'model': DetalleDeError}},
)
async def crear_libro(sesion: SesionDep, datos: LibroCrear, bibliotecario: Bibliotecario):
    return await crud_libros.crear(sesion, datos.model_dump(exclude_none=True))


@router.patch('/{libro_id}', response_model=LibroRespuesta, summary='Actualizar parcialmente un libro')
async def actualizar_libro(
    sesion: SesionDep,
    libro: LibroDeRuta,
    datos: LibroActualizar,
    bibliotecario: Bibliotecario,
):
    return await crud_libros.actualizar(sesion, libro, datos.model_dump(exclude_unset=True))


@router.delete(
    '/{libro_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Eliminar un libro',
    responses={409: {'model': DetalleDeError}},
)
async def eliminar_libro(sesion: SesionDep, libro: LibroDeRuta, bibliotecario: Bibliotecario):
    await crud_libros.eliminar(sesion, libro)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
