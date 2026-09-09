from typing import Annotated
import re

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from app.dependencias import SesionDep, SocioActual
from app.models.biblioteca import Libro, Prestamo
from app.schemas.recomendacion import LibroRecomendado, RespuestaDeRecomendacion, SolicitudDeRecomendacion
from app.services.recomendaciones import ProveedorNoDisponible, ServicioDeRecomendaciones

router = APIRouter(prefix='/recomendaciones', tags=['Recomendaciones'])


def obtener_servicio(peticion: Request) -> ServicioDeRecomendaciones:
    return peticion.app.state.servicio_recomendaciones


ServicioIA = Annotated[ServicioDeRecomendaciones, Depends(obtener_servicio)]


async def _catalogo_disponible(sesion: SesionDep) -> list[dict]:
    consulta = select(Libro).where(Libro.ejemplares_disponibles > 0).limit(40)
    resultado = await sesion.scalars(consulta)
    return [
        {
            'libro_id': libro.id,
            'titulo': libro.titulo,
            'autor': libro.autor.nombre,
            'categoria': libro.categoria.nombre,
        }
        for libro in resultado.unique()
    ]


def _palabras_clave(texto: str) -> set[str]:
    return {palabra for palabra in re.findall(r'[\wáéíóúñ]+', texto.lower()) if len(palabra) >= 3}


def _puntaje_local(intereses: str, libro: dict, categoria_popular: int | None) -> int:
    palabras = _palabras_clave(intereses)
    texto_libro = f"{libro['titulo']} {libro['autor']} {libro['categoria']}".lower()

    puntaje = 0
    if libro['categoria'] == categoria_popular:
        puntaje += 3

    for palabra in palabras:
        if palabra in texto_libro:
            puntaje += 4

    coincidencias_categoria = {
        'novela': {'novela', 'ficcion', 'ficción', 'misterio', 'suspenso', 'romance', 'aventura'},
        'memorias': {'memoria', 'memorias', 'autobiografia', 'autobiografía', 'biografia', 'biografía', 'ensayo', 'historia'},
        'tecnica': {'tecnica', 'técnica', 'tecnologia', 'tecnología', 'programacion', 'programación', 'algoritmo', 'computacion', 'computación'},
        'infantil': {'infantil', 'niños', 'niñas', 'cuento', 'cuentos'},
        'referencia': {'referencia', 'consulta', 'manual', 'enciclopedia'},
    }
    for categoria, palabras_categoria in coincidencias_categoria.items():
        if libro['categoria'] == categoria and palabras.intersection(palabras_categoria):
            puntaje += 6

    return puntaje


async def _respaldo_local(sesion: SesionDep, intereses: str) -> list[LibroRecomendado]:
    categoria_popular = await sesion.scalar(
        select(Libro.categoria_id)
        .join(Prestamo, Prestamo.libro_id == Libro.id)
        .group_by(Libro.categoria_id)
        .order_by(func.count().desc())
        .limit(1)
    )
    resultado = await sesion.scalars(
        select(Libro).where(Libro.ejemplares_disponibles > 0).limit(40)
    )
    libros = list(resultado.unique())
    libros.sort(
        key=lambda libro: (
            -_puntaje_local(
                intereses,
                {
                    'libro_id': libro.id,
                    'titulo': libro.titulo,
                    'categoria': libro.categoria.nombre,
                    'autor': libro.autor.nombre,
                },
                categoria_popular,
            ),
            libro.titulo,
            libro.id,
        )
    )

    return [
        LibroRecomendado(
            libro_id=libro.id,
            titulo=libro.titulo,
            motivo=f'Coincide con tus intereses y está disponible en {libro.categoria.nombre}.',
        )
        for libro in libros[:3]
    ]


@router.post(
    '',
    response_model=RespuestaDeRecomendacion,
    summary='Recomendar tres libros a partir de los intereses del socio',
)
async def recomendar(sesion: SesionDep, datos: SolicitudDeRecomendacion, servicio: ServicioIA, socio: SocioActual):
    catalogo = await _catalogo_disponible(sesion)
    titulos_validos = {libro['libro_id'] for libro in catalogo}

    try:
        crudas = await servicio.recomendar(datos.intereses, catalogo)
    except ProveedorNoDisponible:
        return RespuestaDeRecomendacion(
            recomendaciones=await _respaldo_local(sesion, datos.intereses),
            generada_por='catalogo_local',
            aviso='El asistente no está disponible en este momento; estas sugerencias vienen del catálogo.',
        )

    validas = [LibroRecomendado(**item) for item in crudas if item.get('libro_id') in titulos_validos]
    if not validas:
        return RespuestaDeRecomendacion(
            recomendaciones=await _respaldo_local(sesion, datos.intereses),
            generada_por='catalogo_local',
            aviso='El asistente sugirió libros que no están en el catálogo.',
        )

    return RespuestaDeRecomendacion(recomendaciones=validas, generada_por='modelo_externo')