from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import libros as crud_libros
from app.errores import (
    ConflictoDeNegocio,
    LimiteDePrestamosSuperado,
    PrestamoYaDevuelto,
    RecursoNoEncontrado,
    SinEjemplaresDisponibles,
    SocioInactivo,
)
from app.models.biblioteca import Prestamo, Socio

LIMITE_PRESTAMOS_ACTIVOS = 3


def _estado(prestamo: Prestamo) -> str:
    return prestamo.estado


async def registrar(sesion: AsyncSession, libro_id: int, socio_id: int, dias_prestamo: int) -> Prestamo:
    socio = await sesion.get(Socio, socio_id)
    if socio is None:
        raise RecursoNoEncontrado('un socio', socio_id)
    if not socio.activo:
        raise SocioInactivo(socio_id)

    activos = await sesion.scalar(
        select(func.count()).select_from(Prestamo)
        .where(Prestamo.socio_id == socio_id, Prestamo.fecha_devolucion_real.is_(None))
    )
    if activos >= LIMITE_PRESTAMOS_ACTIVOS:
        raise LimiteDePrestamosSuperado(socio_id, LIMITE_PRESTAMOS_ACTIVOS)

    libro = await crud_libros.obtener_o_fallar(sesion, libro_id)
    if libro.ejemplares_disponibles <= 0:
        raise SinEjemplaresDisponibles(libro_id)

    hoy = date.today()
    prestamo = Prestamo(
        libro_id=libro_id,
        socio_id=socio_id,
        fecha_prestamo=hoy,
        fecha_devolucion_esperada=hoy + timedelta(days=dias_prestamo),
        fecha_devolucion_real=None,
    )
    libro.ejemplares_disponibles -= 1
    sesion.add(prestamo)

    try:
        await sesion.commit()
    except IntegrityError:
        await sesion.rollback()
        raise ConflictoDeNegocio('El socio ya tiene registrado hoy un préstamo de ese libro.')
    except Exception:
        await sesion.rollback()
        raise

    await sesion.refresh(prestamo)
    return prestamo


async def registrar_devolucion(sesion: AsyncSession, prestamo: Prestamo) -> Prestamo:
    if prestamo.fecha_devolucion_real is not None:
        raise PrestamoYaDevuelto(prestamo.id)
    prestamo.fecha_devolucion_real = date.today()
    prestamo.libro.ejemplares_disponibles += 1
    await sesion.commit()
    await sesion.refresh(prestamo)
    return prestamo
