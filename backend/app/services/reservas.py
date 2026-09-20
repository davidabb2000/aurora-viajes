"""Reglas de negocio de las reservas: vuelo, hotel y excursiones válidos, precio, venta y factura."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errores import ConflictoDeNegocio, ErrorDeDominio
from app.models.dominio import (
    Destino,
    DetalleFactura,
    DetalleVenta,
    EstadoReserva,
    Excursion,
    Factura,
    Hotel,
    Paquete,
    Reserva,
    User,
    Venta,
    Vuelo,
)
from app.schemas.reservas import ReservaCreate
from app.services.catalogos import (
    esta_en_el_destino,
    normalizar_texto,
    resolver_destino,
    resolver_estado_pago_id,
    resolver_estado_reserva_id,
)
from app.services.precios import (
    DesgloseReserva,
    calcular_desglose_reserva,
    desglose_de_paquete,
    lineas_de_venta,
    noches_de_viaje,
)


async def resolver_vuelo_reserva(
    sesion: AsyncSession,
    payload: ReservaCreate,
    destino: Destino,
    reserva_id: int | None = None,
) -> Vuelo:
    vuelos = list(
        await sesion.scalars(
            select(Vuelo)
            .where(Vuelo.activo.is_(True), Vuelo.estado.in_({"programado", "abordando"}))
            .order_by(Vuelo.fecha_salida.asc())
        )
    )
    destino_normalizado = normalizar_texto(destino.nombre)
    candidatos = [
        vuelo
        for vuelo in vuelos
        if vuelo.fecha_salida.date() == payload.fechaSalida
        and normalizar_texto(vuelo.origen) == normalizar_texto(payload.origen)
        and (
            normalizar_texto(vuelo.destino) == destino_normalizado
            or normalizar_texto(vuelo.destino) in destino_normalizado
            or destino_normalizado in normalizar_texto(vuelo.destino)
        )
    ]
    if payload.vueloId is not None:
        candidatos = [vuelo for vuelo in candidatos if vuelo.id == payload.vueloId]
    if not candidatos:
        raise ErrorDeDominio("No hay un vuelo activo para ese destino y fecha de salida.")

    estado_cancelado_id = await resolver_estado_reserva_id(sesion, "cancelada")
    for vuelo in candidatos:
        condiciones = [
            Reserva.vuelo_id == vuelo.id,
            Reserva.estado_id != estado_cancelado_id,
        ]
        if reserva_id is not None:
            condiciones.append(Reserva.id != reserva_id)
        pasajeros_asignados = await sesion.scalar(
            select(func.coalesce(func.sum(Reserva.pasajeros), 0)).where(*condiciones)
        )
        if int(pasajeros_asignados or 0) + payload.pasajeros <= vuelo.capacidad_maxima:
            return vuelo

    raise ErrorDeDominio("El vuelo seleccionado no tiene capacidad para todos los pasajeros.")


async def _resolver_hotel_reserva(sesion: AsyncSession, hotel_id: int | None, destino: Destino) -> Hotel | None:
    if hotel_id is None:
        return None
    hotel = await sesion.get(Hotel, hotel_id)
    if hotel is None or not hotel.activo:
        raise ErrorDeDominio("El hotel seleccionado no está disponible.")
    # Sin esto se podia reservar un hotel de Santorini para un viaje a Cartagena.
    if not esta_en_el_destino(hotel.ciudad, hotel.pais, destino):
        raise ErrorDeDominio(f"El hotel {hotel.nombre} no está en {destino.nombre}.")
    return hotel


async def _resolver_excursiones_reserva(sesion: AsyncSession, ids: list[int], destino: Destino) -> list[Excursion]:
    if not ids:
        return []
    encontradas = (await sesion.scalars(select(Excursion).where(Excursion.id.in_(ids), Excursion.activo.is_(True)))).all()
    if len(encontradas) != len(ids):
        raise ErrorDeDominio("Alguna de las excursiones seleccionadas no está disponible.")
    for excursion in encontradas:
        if not esta_en_el_destino(excursion.ciudad, excursion.pais, destino):
            raise ErrorDeDominio(f"La excursión {excursion.nombre} no está en {destino.nombre}.")
    return list(encontradas)


def opciones_carga_reserva():
    return [
        selectinload(Reserva.usuario).selectinload(User.role),
        selectinload(Reserva.usuario).selectinload(User.tipo_documento_catalogo),
        selectinload(Reserva.destino_rel).selectinload(Destino.pais),
        selectinload(Reserva.vuelo_rel),
        selectinload(Reserva.paquete_rel).selectinload(Paquete.excursiones),
        selectinload(Reserva.hotel_rel),
        selectinload(Reserva.excursiones),
        selectinload(Reserva.estado_rel),
        selectinload(Reserva.estado_pago_rel),
        selectinload(Reserva.metodo_pago_rel),
    ]


@dataclass
class PlanDeReserva:
    """Todo lo que se decide antes de guardar una reserva: qué se reserva y cuánto cuesta."""

    destino: Destino
    vuelo: Vuelo
    paquete: Paquete | None
    hotel: Hotel | None
    excursiones: list[Excursion]
    desglose: DesgloseReserva
    noches: int
    lineas: list[dict]


async def preparar_reserva(sesion: AsyncSession, payload: ReservaCreate, reserva_id: int | None = None) -> PlanDeReserva:
    """Valida la petición contra el catálogo y calcula el precio.

    La usan tanto la creación como la edición, de modo que una reserva se
    valida y se cobra igual en ambos casos.
    """
    paquete: Paquete | None = None
    hotel: Hotel | None = None
    excursiones: list[Excursion] = []

    if payload.paqueteId is not None:
        paquete = await sesion.get(
            Paquete, payload.paqueteId, options=[selectinload(Paquete.destino_rel), selectinload(Paquete.vuelo_rel)]
        )
        if paquete is None or not paquete.activo:
            raise ErrorDeDominio("El paquete seleccionado no está disponible.")
        if payload.fechaSalida != paquete.fecha_salida or payload.origen.strip().lower() != paquete.vuelo_rel.origen.strip().lower():
            raise ErrorDeDominio("Los datos de la reserva no coinciden con el paquete seleccionado.")
        destino = paquete.destino_rel
        vuelo = await resolver_vuelo_reserva(sesion, payload, destino, reserva_id)
        if vuelo.id != paquete.vuelo_id:
            raise ErrorDeDominio("El vuelo del paquete ya no está disponible.")
        # El paquete ya trae hotel y excursiones: se copian a la reserva para
        # que la factura los detalle igual que en una reserva a la carta.
        hotel = paquete.hotel_rel
        excursiones = list(paquete.excursiones)
        desglose = desglose_de_paquete(paquete, payload.pasajeros)
    else:
        destino = await resolver_destino(sesion, payload.destino, payload.destinoId)
        vuelo = await resolver_vuelo_reserva(sesion, payload, destino, reserva_id)
        hotel = await _resolver_hotel_reserva(sesion, payload.hotelId, destino)
        excursiones = await _resolver_excursiones_reserva(sesion, payload.excursionIds, destino)
        desglose = calcular_desglose_reserva(
            destino, hotel, excursiones, payload.fechaSalida, payload.fechaRegreso, payload.pasajeros
        )

    noches = noches_de_viaje(payload.fechaSalida, payload.fechaRegreso)
    lineas = lineas_de_venta(destino, hotel, excursiones, desglose, payload.pasajeros, noches, paquete)
    return PlanDeReserva(destino, vuelo, paquete, hotel, excursiones, desglose, noches, lineas)


async def registrar_reserva(sesion: AsyncSession, usuario: User, payload: ReservaCreate) -> tuple[Reserva, PlanDeReserva]:
    """Crea la reserva junto con su venta y su factura en una sola transacción."""
    plan = await preparar_reserva(sesion, payload)
    total = plan.desglose.total
    reserva = Reserva(
        usuario_id=usuario.id,
        destino_id=plan.destino.id,
        vuelo_id=plan.vuelo.id,
        paquete_id=plan.paquete.id if plan.paquete else None,
        hotel_id=plan.hotel.id if plan.hotel else None,
        excursiones=plan.excursiones,
        fecha_salida=payload.fechaSalida,
        fecha_regreso=payload.fechaRegreso,
        pasajeros=payload.pasajeros,
        telefono_contacto=payload.telefonoContacto,
        notas=payload.notas,
        estado_id=await resolver_estado_reserva_id(sesion, "pendiente"),
        estado_pago_id=await resolver_estado_pago_id(sesion, "pendiente"),
        monto_total=total,
        monto_vuelo=plan.desglose.vuelo,
        monto_hotel=plan.desglose.hotel,
        monto_excursiones=plan.desglose.excursiones,
    )
    sesion.add(reserva)
    await sesion.flush()
    venta = Venta(
        cliente_id=usuario.id,
        usuario_id=usuario.id,
        reserva_id=reserva.id,
        subtotal=total,
        descuento=Decimal("0"),
        impuestos=Decimal("0"),
        total=total,
        estado="pendiente",
        detalles=[DetalleVenta(**linea) for linea in plan.lineas],
    )
    sesion.add(venta)
    await sesion.flush()
    sesion.add(Factura(
        venta_id=venta.id,
        numero=f"AUR-{datetime.now(timezone.utc):%Y%m%d}-{venta.id:06d}",
        estado="emitida",
        detalles=[DetalleFactura(**linea) for linea in plan.lineas],
    ))
    # Un unico commit: si algo falla, no queda una reserva sin venta ni factura.
    await sesion.commit()
    return reserva, plan


async def actualizar_reserva_existente(
    sesion: AsyncSession, reserva: Reserva, payload: ReservaCreate
) -> tuple[PlanDeReserva, str | None]:
    """Aplica los cambios de una edición y deja venta y factura al día.

    Devuelve el plan y, si el precio cambió mientras había un pago abierto, el
    id de esa sesión de Stripe para que quien llama la expire.
    """
    if reserva.estado_rel.codigo == "cancelada":
        raise ConflictoDeNegocio("Una reserva cancelada no se puede modificar.")
    plan = await preparar_reserva(sesion, payload, reserva_id=reserva.id)
    precio_cambia = plan.desglose.total != Decimal(reserva.monto_total or 0)
    if reserva.estado_pago_rel.codigo == "pagado" and precio_cambia:
        raise ConflictoDeNegocio("La reserva ya está pagada y no se puede cambiar su precio. Cancélala y crea una nueva.")

    reserva.destino_id = plan.destino.id
    reserva.vuelo_id = plan.vuelo.id
    reserva.paquete_id = plan.paquete.id if plan.paquete else None
    reserva.hotel_id = plan.hotel.id if plan.hotel else None
    reserva.excursiones = plan.excursiones
    reserva.fecha_salida = payload.fechaSalida
    reserva.fecha_regreso = payload.fechaRegreso
    reserva.pasajeros = payload.pasajeros
    reserva.telefono_contacto = payload.telefonoContacto
    reserva.notas = payload.notas
    reserva.monto_total = plan.desglose.total
    reserva.monto_vuelo = plan.desglose.vuelo
    reserva.monto_hotel = plan.desglose.hotel
    reserva.monto_excursiones = plan.desglose.excursiones

    sesion_obsoleta = None
    if precio_cambia and reserva.stripe_session_id:
        # El enlace de pago que ya se entregó cobraría el importe anterior.
        sesion_obsoleta, reserva.stripe_session_id = reserva.stripe_session_id, None

    venta = await venta_de_reserva(sesion, reserva.id)
    if venta is not None:
        total = plan.desglose.total
        venta.subtotal = total
        venta.total = total
        venta.detalles = [DetalleVenta(**linea) for linea in plan.lineas]
        if venta.factura is not None:
            venta.factura.detalles = [DetalleFactura(**linea) for linea in plan.lineas]
    await sesion.commit()
    return plan, sesion_obsoleta


async def venta_de_reserva(sesion: AsyncSession, reserva_id: int) -> Venta | None:
    return await sesion.scalar(select(Venta).where(Venta.reserva_id == reserva_id))


async def sincronizar_venta(sesion: AsyncSession, reserva: Reserva) -> None:
    """Deriva el estado de la venta y de su factura del estado de la reserva.

    Antes la venta se quedaba siempre en «pendiente»: pagar o cancelar la
    reserva no la tocaba, y los reportes contaban dinero que no existía.
    """
    venta = await venta_de_reserva(sesion, reserva.id)
    if venta is None:
        return  # reservas anteriores al enlace, o ventas de mostrador
    cancelada = reserva.estado_rel.codigo == "cancelada"
    pagada = reserva.estado_pago_rel.codigo == "pagado"
    venta.estado = "cancelada" if cancelada else "completada" if pagada else "pendiente"
    if venta.factura is not None:
        venta.factura.estado = "anulada" if cancelada else "emitida"


async def cambiar_estado_reserva(sesion: AsyncSession, reserva: Reserva, codigo: str) -> None:
    estado = await sesion.scalar(select(EstadoReserva).where(EstadoReserva.codigo == codigo))
    if estado is None:
        raise ErrorDeDominio("Estado de reserva no válido.")
    reserva.estado_rel = estado
    await sincronizar_venta(sesion, reserva)


async def anular_venta_de_reserva(sesion: AsyncSession, reserva: Reserva) -> None:
    """Antes de borrar una reserva: la venta y la factura se conservan como anuladas."""
    venta = await venta_de_reserva(sesion, reserva.id)
    if venta is None:
        return
    venta.reserva_id = None
    venta.estado = "cancelada"
    if venta.factura is not None:
        venta.factura.estado = "anulada"
