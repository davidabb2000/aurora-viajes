"""Datos de los pasajeros de cada reserva y manifiesto de cada vuelo."""
from sqlalchemy import or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.errores import ConflictoDeNegocio, ErrorDeDominio
from app.models.dominio import EstadoReserva, PasajeroDeReserva, Reserva, TipoDocumento, User, Vuelo
from app.schemas.pasajeros import DatosDePasajeros
from app.services.catalogos import ahora, sin_zona
from app.services.disponibilidad import plazas_libres
from app.services.serializadores import pasajero_a_dict, vuelo_a_dict


def _vuelos_de(reserva: Reserva) -> list[int]:
    return [vuelo_id for vuelo_id in (reserva.vuelo_id, reserva.vuelo_regreso_id) if vuelo_id is not None]


async def _exigir_que_no_figuren_en_otra_reserva(sesion: AsyncSession, reserva: Reserva, pares: list[tuple[int, str]]) -> None:
    """Una persona no ocupa dos plazas del mismo vuelo: si ya viaja en otra reserva activa, se avisa cuál."""
    vuelos = _vuelos_de(reserva)
    if not pares or not vuelos:
        return
    repetido = (await sesion.execute(
        select(PasajeroDeReserva.nombre, PasajeroDeReserva.apellido, PasajeroDeReserva.reserva_id)
        .join(Reserva, Reserva.id == PasajeroDeReserva.reserva_id)
        .where(
            PasajeroDeReserva.reserva_id != reserva.id,
            tuple_(PasajeroDeReserva.tipo_documento_id, PasajeroDeReserva.numero_documento).in_(pares),
            or_(Reserva.vuelo_id.in_(vuelos), Reserva.vuelo_regreso_id.in_(vuelos)),
            Reserva.estado_rel.has(EstadoReserva.codigo != "cancelada"),
        )
        .limit(1)
    )).first()
    if repetido is not None:
        nombre, apellido, otra_reserva = repetido
        raise ConflictoDeNegocio(f"{nombre} {apellido} ya figura como pasajero en la reserva #{otra_reserva}, en el mismo vuelo.")


async def guardar_datos_de_pasajeros(sesion: AsyncSession, reserva: Reserva, datos: DatosDePasajeros, es_personal: bool) -> list[PasajeroDeReserva]:
    """Reemplaza los datos de los pasajeros de una reserva, con las reglas que evitan un manifiesto incoherente."""
    if reserva.estado_rel.codigo == "cancelada":
        raise ConflictoDeNegocio("Una reserva cancelada no admite cambios. Reactívala primero.")
    salida = reserva.vuelo_rel.fecha_salida if reserva.vuelo_rel is not None else None
    if not es_personal and salida is not None and sin_zona(salida) <= ahora():
        raise ConflictoDeNegocio("El vuelo de ida ya salió: para cambiar los datos de los pasajeros escríbenos desde la página de contacto.")
    if len(datos.pasajeros) > reserva.pasajeros:
        raise ErrorDeDominio(f"La reserva es para {reserva.pasajeros} pasajero{'s' if reserva.pasajeros != 1 else ''}: no se pueden registrar más.")

    tipos = {t.codigo: t for t in (await sesion.scalars(select(TipoDocumento))).all()}
    nuevos = [
        PasajeroDeReserva(
            nombre=p.nombre, apellido=p.apellido, tipo_documento_id=tipos[p.tipoDocumento].id, numero_documento=p.numeroDocumento
        )
        for p in datos.pasajeros
    ]
    await _exigir_que_no_figuren_en_otra_reserva(sesion, reserva, [(p.tipo_documento_id, p.numero_documento) for p in nuevos])

    # Primero se borran los anteriores y se confirma el borrado: si no, volver a guardar a la misma persona chocaría con su clave única.
    reserva.datos_pasajeros.clear()
    await sesion.flush()
    reserva.datos_pasajeros.extend(nuevos)
    await sesion.commit()
    for pasajero in nuevos:
        await sesion.refresh(pasajero)
    return nuevos


async def manifiesto_de_vuelo(sesion: AsyncSession, vuelo: Vuelo) -> dict:
    """Quién viaja en un vuelo: las reservas que no están canceladas, con los datos de sus pasajeros y lo que falta por completar."""
    reservas = (await sesion.scalars(
        select(Reserva).where(or_(Reserva.vuelo_id == vuelo.id, Reserva.vuelo_regreso_id == vuelo.id)).order_by(Reserva.id)
    )).unique().all()
    activas = [r for r in reservas if r.estado_rel.codigo != "cancelada"]
    libres = (await plazas_libres(sesion, [vuelo]))[vuelo.id]

    filas = []
    for reserva in activas:
        registrados = len(reserva.datos_pasajeros)
        filas.append({
            "reservaId": reserva.id,
            "tramo": "ida" if reserva.vuelo_id == vuelo.id else "regreso",
            "estado": reserva.estado_rel.codigo,
            "estadoPago": reserva.estado_pago_rel.codigo,
            "cliente": _nombre_de(reserva.usuario),
            "telefono": reserva.telefono_contacto,
            "pasajeros": reserva.pasajeros,
            "registrados": registrados,
            "faltan": reserva.pasajeros - registrados,
            "datosDePasajeros": [pasajero_a_dict(p) for p in reserva.datos_pasajeros],
        })
    plazas = sum(fila["pasajeros"] for fila in filas)
    registrados = sum(fila["registrados"] for fila in filas)
    return {
        "vuelo": vuelo_a_dict(vuelo, libres),
        "resumen": {"reservas": len(filas), "plazas": plazas, "conDatos": registrados, "faltanDatos": plazas - registrados},
        "reservas": filas,
    }


def _nombre_de(usuario: User) -> str:
    return f"{usuario.nombre} {usuario.apellido}"
