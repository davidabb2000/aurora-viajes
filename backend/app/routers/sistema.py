import asyncio
import time

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from app.dependencias import SesionDep
from app.models.biblioteca import Destino
from app.schemas.diagnostico import Diagnostico, EstadoComponente

router = APIRouter(prefix='/sistema', tags=['Sistema'])

LIMITE_POR_COMPROBACION = 5.0


async def _medir(nombre: str, corrutina) -> EstadoComponente:
    inicio = time.perf_counter()
    detalle: str | None = None
    estado = 'ok'
    try:
        detalle = await asyncio.wait_for(corrutina, timeout=LIMITE_POR_COMPROBACION)
    except asyncio.TimeoutError:
        detalle, estado = 'No respondió dentro del límite.', 'caido'
    except Exception as exc:  # noqa: BLE001 — el diagnóstico nunca debe fallar
        detalle, estado = f'{type(exc).__name__}: {exc}', 'caido'

    return EstadoComponente(
        componente=nombre,
        estado=estado,
        latencia_ms=round((time.perf_counter() - inicio) * 1000, 1),
        detalle=detalle,
    )


async def _comprobar_base(sesion) -> str:
    total = await sesion.scalar(select(Destino.id).limit(1))
    return f'Consulta ejecutada (hay datos: {total is not None}).'


async def _comprobar_modelo(servicio) -> str:
    if servicio is None:
        raise RuntimeError('El modelo no está cargado.')
    variables = {
        'dias_viaje': 7,
        'viajes_previos': 2,
        'cancelaciones_previas': 0,
        'pasajeros': 2,
        'tipo_destino': 'playa',
    }
    probabilidad = await run_in_threadpool(servicio.predecir, variables)
    return f'Predicción de prueba: {probabilidad:.3f} ({servicio.version}).'


async def _comprobar_proveedor(servicio) -> str:
    if servicio is None or not servicio.configurado:
        raise RuntimeError('Sin clave de API configurada.')
    await servicio.recomendar(
        'me gustaría un viaje a una playa paradisíaca',
        [{'destino_id': 1, 'nombre': 'Prueba', 'pais': 'Desconocido', 'descripcion': 'Destino de prueba'}],
    )
    return 'El proveedor respondió correctamente.'


@router.get(
    '/diagnostico',
    response_model=Diagnostico,
    summary='Estado de la base de datos y de las integraciones de IA',
)
async def diagnostico(peticion: Request, sesion: SesionDep):
    estado = peticion.app.state

    componentes = await asyncio.gather(
        _medir('base_de_datos', _comprobar_base(sesion)),
        _medir('modelo_riesgo', _comprobar_modelo(getattr(estado, 'servicio_riesgo', None))),
        _medir('proveedor_ia', _comprobar_proveedor(getattr(estado, 'servicio_recomendaciones', None))),
    )

    base = componentes[0]
    if base.estado == 'caido':
        general = 'caido'
    elif any(componente.estado != 'ok' for componente in componentes):
        general = 'degradado'
    else:
        general = 'ok'

    return Diagnostico(estado_general=general, componentes=list(componentes))