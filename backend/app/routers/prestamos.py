from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select

from app.crud import prestamos as crud_prestamos
from app.crud import libros as crud_libros
from app.dependencias import Bibliotecario, PaginacionDep, PrestamoDeRuta, SesionDep, ServicioRiesgo, SocioActual
from app.errores import RecursoNoEncontrado
from app.models.biblioteca import Prestamo, Socio
from app.schemas.error import DetalleDeError
from app.schemas.prestamo import PrestamoCrear, PrestamoRespuesta
from app.schemas.riesgo import PrediccionDeRiesgo, SolicitudDeRiesgo
from app.services.auditoria import registrar_evento
from app.services.notificaciones import avisar_prestamo_registrado

router = APIRouter(
    prefix='/prestamos',
    tags=['Préstamos'],
    responses={
        404: {'model': DetalleDeError},
        409: {'model': DetalleDeError},
    },
)


@router.get(
    '',
    response_model=list[PrestamoRespuesta],
    summary='Listar préstamos',
)
async def listar_prestamos(
    sesion: SesionDep,
    solicitante: SocioActual,
    paginacion: PaginacionDep,
    estado: Annotated[str | None, Query(description='activo, devuelto o vencido.')] = None,
):
    consulta = select(Prestamo)
    if solicitante.rol != 'bibliotecario':
        consulta = consulta.where(Prestamo.socio_id == solicitante.id)
    resultado = await sesion.scalars(consulta)
    prestamos = list(resultado.unique())
    if estado is not None:
        prestamos = [p for p in prestamos if crud_prestamos._estado(p) == estado]
    return prestamos[paginacion.desplazamiento:paginacion.desplazamiento + paginacion.limite]


@router.post(
    '',
    response_model=PrestamoRespuesta,
    status_code=status.HTTP_201_CREATED,
    summary='Registrar un préstamo',
)
async def registrar_prestamo(
    sesion: SesionDep,
    datos: PrestamoCrear,
    tareas: BackgroundTasks,
    bibliotecario: Bibliotecario,
):
    prestamo = await crud_prestamos.registrar(
        sesion,
        libro_id=datos.libro_id,
        socio_id=datos.socio_id,
        dias_prestamo=datos.dias_prestamo,
    )

    libro = await crud_libros.obtener_o_fallar(sesion, datos.libro_id)
    socio = await sesion.get(Socio, datos.socio_id)

    tareas.add_task(
        registrar_evento,
        accion='prestamo_registrado',
        recurso='prestamo',
        recurso_id=prestamo.id,
        autor_id=getattr(bibliotecario, 'id', None),
        detalle=f'libro={prestamo.libro_id} socio={prestamo.socio_id} vence={prestamo.fecha_devolucion_esperada}',
    )
    tareas.add_task(
        avisar_prestamo_registrado,
        email=socio.email if socio is not None else '',
        titulo=libro.titulo,
        fecha_devolucion=str(prestamo.fecha_devolucion_esperada),
    )

    return prestamo


@router.post(
    '/{prestamo_id}/devolucion',
    response_model=PrestamoRespuesta,
    summary='Registrar la devolución de un préstamo',
)
async def registrar_devolucion(
    sesion: SesionDep,
    prestamo: PrestamoDeRuta,
    tareas: BackgroundTasks,
    bibliotecario: Bibliotecario,
):
    prestamo = await crud_prestamos.registrar_devolucion(sesion, prestamo)
    con_retraso = prestamo.fecha_devolucion_real > prestamo.fecha_devolucion_esperada
    tareas.add_task(
        registrar_evento,
        accion='devolucion_registrada',
        recurso='prestamo',
        recurso_id=prestamo.id,
        autor_id=getattr(bibliotecario, 'id', None),
        detalle=f'con_retraso={con_retraso}',
    )
    return prestamo


@router.post(
    '/riesgo',
    response_model=PrediccionDeRiesgo,
    summary='Estimar el riesgo de devolución con retraso',
    description='Devuelve una estimación estadística, no una decisión. El préstamo lo autoriza el bibliotecario.',
)
async def estimar_riesgo(
    sesion: SesionDep,
    datos: SolicitudDeRiesgo,
    servicio: ServicioRiesgo,
    bibliotecario: Bibliotecario,
):
    libro = await crud_libros.obtener_o_fallar(sesion, datos.libro_id)

    socio = await sesion.get(Socio, datos.socio_id)
    if socio is None:
        raise RecursoNoEncontrado('un socio', datos.socio_id)

    previos = await sesion.scalar(
        select(func.count()).select_from(Prestamo).where(Prestamo.socio_id == socio.id)
    )
    retrasos = await sesion.scalar(
        select(func.count()).select_from(Prestamo).where(
            Prestamo.socio_id == socio.id,
            Prestamo.fecha_devolucion_real.is_not(None),
            Prestamo.fecha_devolucion_real > Prestamo.fecha_devolucion_esperada,
        )
    )

    variables = {
        'dias_prestamo': datos.dias_prestamo,
        'prestamos_previos': previos or 0,
        'retrasos_previos': retrasos or 0,
        'ejemplares_disponibles': libro.ejemplares_disponibles,
        'categoria': libro.categoria.nombre,
    }

    probabilidad = await run_in_threadpool(servicio.predecir, variables)
    nivel, recomendacion = servicio.clasificar(probabilidad)

    return PrediccionDeRiesgo(
        probabilidad_retraso=round(probabilidad, 4),
        nivel=nivel,
        recomendacion=recomendacion,
        variables_usadas=variables,
        version_modelo=servicio.version,
    )
