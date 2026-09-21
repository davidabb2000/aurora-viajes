"""Plazas de los vuelos: cuántas hay vendidas, cuántas quedan y cómo evitar venderlas dos veces."""

from collections.abc import Iterable

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errores import ErrorDeDominio
from app.models.dominio import Reserva, Vuelo
from app.services.catalogos import resolver_estado_reserva_id


async def bloquear_vuelos(sesion: AsyncSession, ids: Iterable[int]) -> None:
    """Toma el candado de fila de esos vuelos hasta el final de la transacción.

    Dos reservas simultáneas para el último asiento se ejecutaban a la vez, las
    dos veían una plaza libre y las dos se guardaban. Con el candado la segunda
    espera a que la primera termine y ve ya la plaza ocupada. Se piden siempre en
    orden de id para que dos reservas con los mismos vuelos no se bloqueen entre
    sí. Solo se selecciona el id: así el candado no se extiende a las tablas
    unidas (aerolíneas, ciudades) ni exige `FOR UPDATE OF`, que MariaDB no tiene.
    SQLite no tiene candados de fila y SQLAlchemy omite la cláusula.
    """
    ordenados = sorted(set(ids))
    if ordenados:
        await sesion.execute(select(Vuelo.id).where(Vuelo.id.in_(ordenados)).order_by(Vuelo.id).with_for_update())


async def plazas_ocupadas(
    sesion: AsyncSession,
    ids: Iterable[int],
    excluir_reserva_id: int | None = None,
    bloquear: bool = False,
) -> dict[int, int]:
    """Pasajeros con reserva vigente en cada vuelo, sea como ida o como regreso.

    `bloquear` lee con candado: en MySQL una lectura normal usa la foto que la
    transacción tomó al empezar, y no vería reservas confirmadas mientras esperaba
    el candado del vuelo.
    """
    ordenados = sorted(set(ids))
    if not ordenados:
        return {}
    cancelada_id = await resolver_estado_reserva_id(sesion, "cancelada")
    condiciones = [Reserva.estado_id != cancelada_id]
    if excluir_reserva_id is not None:
        condiciones.append(Reserva.id != excluir_reserva_id)

    ocupadas = dict.fromkeys(ordenados, 0)
    if bloquear:
        for vuelo_id in ordenados:
            consulta = (
                select(Reserva.pasajeros)
                .where(or_(Reserva.vuelo_id == vuelo_id, Reserva.vuelo_regreso_id == vuelo_id), *condiciones)
                .with_for_update()
            )
            ocupadas[vuelo_id] = sum(int(p or 0) for p in (await sesion.scalars(consulta)).all())
        return ocupadas

    for columna in (Reserva.vuelo_id, Reserva.vuelo_regreso_id):
        filas = await sesion.execute(
            select(columna, func.coalesce(func.sum(Reserva.pasajeros), 0))
            .where(columna.in_(ordenados), *condiciones)
            .group_by(columna)
        )
        for vuelo_id, total in filas.all():
            ocupadas[vuelo_id] += int(total or 0)
    return ocupadas


async def plazas_libres(sesion: AsyncSession, vuelos: Iterable[Vuelo]) -> dict[int, int]:
    """Plazas que quedan a la venta en cada vuelo (lectura informativa, sin candado)."""
    lista = list(vuelos)
    ocupadas = await plazas_ocupadas(sesion, [v.id for v in lista])
    return {v.id: max(v.capacidad_maxima - ocupadas.get(v.id, 0), 0) for v in lista}


async def exigir_plazas(
    sesion: AsyncSession,
    tramos: list[tuple[Vuelo, str]],
    pasajeros: int,
    excluir_reserva_id: int | None = None,
    bloquear: bool = True,
) -> None:
    """Comprueba que cada vuelo tenga plazas para todos los pasajeros.

    Con `bloquear` (crear o editar una reserva) toma el candado de los vuelos; sin él
    (cotizar) solo lee, para no retener nada mientras alguien mira precios.
    """
    ids = {vuelo.id for vuelo, _ in tramos}
    if bloquear:
        await bloquear_vuelos(sesion, ids)
    ocupadas = await plazas_ocupadas(sesion, ids, excluir_reserva_id, bloquear=bloquear)
    for vuelo, tramo in tramos:
        libres = vuelo.capacidad_maxima - ocupadas.get(vuelo.id, 0)
        if pasajeros > libres:
            quedan = max(libres, 0)
            raise ErrorDeDominio(
                f"El vuelo {vuelo.numero_vuelo} ({tramo}) solo tiene {quedan} plaza{'s' if quedan != 1 else ''} "
                f"libre{'s' if quedan != 1 else ''} y la reserva necesita {pasajeros}."
            )
