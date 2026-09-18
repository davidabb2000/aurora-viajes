"""Router de recomendaciones de destinos asistidas por IA (con fallback local)."""

from __future__ import annotations

import re

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.configuracion import configuracion
from app.dependencias import SesionDep, UsuarioActual
from app.errores import ErrorDeDominio
from app.models.biblioteca import Destino
from app.services.recomendaciones import (
    INSTRUCCION_DESTINOS,
    ProveedorNoDisponible,
    ServicioDeRecomendaciones,
)

router = APIRouter(prefix="/api/destinos", tags=["Recomendaciones"])


class SolicitudDeRecomendacionDestino(BaseModel):
    intereses: str = Field(..., min_length=10, max_length=500)


class DestinoRecomendado(BaseModel):
    destino_id: int
    nombre: str
    pais: str
    motivo: str
    descripcion: str | None = None
    precio_estimado: float | None = None
    imagen_slug: str | None = None


class RespuestaDeRecomendacionDestino(BaseModel):
    recomendaciones: list[DestinoRecomendado]
    generada_por: str
    aviso: str | None = None


def _palabras_clave(texto: str) -> set[str]:
    return {palabra for palabra in re.findall(r"[\wáéíóúñ]+", texto.lower()) if len(palabra) >= 3}


def _puntaje_destino(intereses: str, destino: dict) -> int:
    palabras = _palabras_clave(intereses)
    texto_destino = " ".join(
        str(destino.get(campo, "")).lower() for campo in ("nombre", "pais", "descripcion")
    )

    puntaje = 0
    for palabra in palabras:
        if palabra in texto_destino:
            puntaje += 3

    coincidencias = {
        "playa": {"playa", "mar", "sol", "arena", "caribe", "isla", "snorkel", "descanso"},
        "cultural": {"cultura", "cultural", "historia", "museo", "patrimonio", "colonial"},
        "aventura": {"aventura", "montaña", "senderismo", "naturaleza", "ecoturismo"},
        "urbano": {"urbano", "ciudad", "noche", "modernas", "eventos", "gastronomía"},
        "romantico": {"romantico", "romántico", "pareja", "escapada", "tranquilo"},
    }
    for grupo in coincidencias.values():
        if palabras.intersection(grupo) and any(palabra in texto_destino for palabra in grupo):
            puntaje += 5

    return puntaje


async def _catalogo_destinos_recomendacion(sesion: SesionDep) -> list[dict]:
    destinos = await sesion.scalars(
        select(Destino)
        .options(selectinload(Destino.pais))
        .where(Destino.activo.is_(True))
        .where(Destino.precio_base > 0)
        .order_by(Destino.nombre.asc())
    )
    return [
        {
            "destino_id": destino.id,
            "nombre": destino.nombre,
            "pais": destino.pais.nombre if destino.pais else "",
            "descripcion": destino.descripcion,
            "precio_estimado": float(destino.precio_base or 0),
            "imagen_slug": destino.imagen_slug,
        }
        for destino in destinos
    ]


def _respaldo_destinos_local(intereses: str, catalogo: list[dict]) -> list[dict]:
    destinos_ordenados = sorted(
        catalogo,
        key=lambda destino: (
            -_puntaje_destino(intereses, destino),
            destino.get("precio_estimado", 0) or 0,
            destino.get("nombre", ""),
            destino.get("destino_id", 0),
        ),
    )
    resultados: list[dict] = []
    for destino in destinos_ordenados[:3]:
        resultados.append(
            {
                "destino_id": destino["destino_id"],
                "nombre": destino["nombre"],
                "pais": destino["pais"],
                "motivo": f"Coincide con tus intereses y encaja con un viaje a {destino['pais']}.",
                "descripcion": destino.get("descripcion"),
                "precio_estimado": destino.get("precio_estimado"),
                "imagen_slug": destino.get("imagen_slug"),
            }
        )
    return resultados


@router.post("/recomendaciones", response_model=RespuestaDeRecomendacionDestino)
async def recomendar_destinos(
    payload: SolicitudDeRecomendacionDestino,
    sesion: SesionDep,
    _usuario: UsuarioActual,
):
    catalogo = await _catalogo_destinos_recomendacion(sesion)
    if not catalogo:
        raise ErrorDeDominio("No hay destinos disponibles para recomendar.")

    try:
        async with httpx.AsyncClient(timeout=configuracion.proveedor_ia_timeout) as cliente:
            servicio = ServicioDeRecomendaciones(cliente)
            crudas = await servicio.recomendar(payload.intereses, catalogo, instruccion=INSTRUCCION_DESTINOS)
        # Del modelo solo se toma el motivo. Los datos del destino (pais, precio,
        # imagen) salen del catalogo: DestinoRecomendado exige 'pais', que el
        # prompt nunca pide, y confiar en el modelo para cifras lo dejaria
        # inventarlas.
        por_id = {destino["destino_id"]: destino for destino in catalogo}
        recomendaciones = []
        for item in crudas:
            if not isinstance(item, dict):
                continue
            try:
                identificador = int(item.get("destino_id"))
            except (TypeError, ValueError):
                continue
            destino = por_id.get(identificador)
            if destino is None:
                continue
            motivo = str(item.get("motivo") or "").strip()
            if not motivo:
                continue
            recomendaciones.append(DestinoRecomendado(**{**destino, "motivo": motivo}))
        if not recomendaciones:
            raise ProveedorNoDisponible("El proveedor devolvió destinos que no están en el catálogo.")
        return RespuestaDeRecomendacionDestino(recomendaciones=recomendaciones[:3], generada_por="modelo_externo")
    except (ProveedorNoDisponible, ValidationError):
        return RespuestaDeRecomendacionDestino(
            recomendaciones=[DestinoRecomendado(**item) for item in _respaldo_destinos_local(payload.intereses, catalogo)],
            generada_por="catalogo_local",
            aviso="El asistente no está disponible en este momento; estas sugerencias vienen del catálogo.",
        )