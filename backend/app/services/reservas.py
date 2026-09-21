"""Reglas de negocio de las reservas: qué se puede reservar, cuánto cuesta y cómo evoluciona.

Una reserva se decide siempre en `preparar_reserva`, tanto si se cotiza como si se crea o se
edita: así lo que se muestra, lo que se cobra y lo que se factura salen del mismo cálculo.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errores import ConflictoDeNegocio, ErrorDeDominio
from app.models.dominio import (
    Destino,
    DetalleFactura,
    DetalleVenta,
    EstadoPago,
    EstadoReserva,
    Excursion,
    Factura,
    Hotel,
    MetodoPago,
    Paquete,
    Reserva,
    ReservaExcursion,
    User,
    Venta,
    Vuelo,
)
from app.schemas.reservas import ExcursionElegida, PagoInmediato, ReservaCreate, ReservaUpdate, SolicitudDeViaje
from app.services.catalogos import ahora, resolver_destino, sin_zona
from app.services.disponibilidad import exigir_plazas
from app.services.precios import (
    CENTAVOS,
    DesgloseReserva,
    LineaExcursion,
    TarifasCongeladas,
    desglose_a_la_carta,
    desglose_de_paquete,
    habitaciones_para,
    lineas_de_venta,
    noches_de_viaje,
    tarifa_de_hotel,
    tarifa_de_vuelo,
)

DIAS_MAXIMOS_DE_VIAJE = 365


@dataclass
class PlanDeReserva:
    """Todo lo que se decide antes de guardar una reserva: qué se reserva y cuánto cuesta."""

    destino: Destino
    paquete: Paquete | None
    ida: Vuelo
    regreso: Vuelo | None
    hotel: Hotel | None
    extras: list[LineaExcursion]
    pasajeros: int
    fecha_salida: date
    fecha_regreso: date
    noches: int
    tarifa_vuelo: Decimal
    tarifa_hotel: Decimal
    desglose: DesgloseReserva
    lineas: list[dict]

    @property
    def total(self) -> Decimal:
        return self.desglose.total


# --------------------------------------------------------------------------------------
# Validación de las piezas del viaje
# --------------------------------------------------------------------------------------


async def _resolver_vuelo(sesion: AsyncSession, vuelo_id: int, tramo: str) -> Vuelo:
    vuelo = await sesion.get(Vuelo, vuelo_id)
    if vuelo is None:
        raise ErrorDeDominio(f"El vuelo de {tramo} no existe.")
    return vuelo


def _exigir_vuelo_vendible(vuelo: Vuelo, tramo: str) -> None:
    if not vuelo.activo or vuelo.estado != "programado":
        raise ErrorDeDominio(f"El vuelo {vuelo.numero_vuelo} ({tramo}) no está disponible.")
    if sin_zona(vuelo.fecha_salida) <= ahora():
        raise ErrorDeDominio(f"El vuelo {vuelo.numero_vuelo} ({tramo}) ya salió.")


def _validar_ruta(ida: Vuelo, regreso: Vuelo | None, destino: Destino) -> None:
    """Los vuelos tienen que llevar al destino elegido y, en el regreso, devolver al origen."""
    if ida.destino_id != destino.ciudad_id:
        raise ErrorDeDominio(f"El vuelo {ida.numero_vuelo} no llega a {destino.nombre}.")
    if regreso is None:
        return
    if regreso.origen_id != destino.ciudad_id or regreso.destino_id != ida.origen_id:
        raise ErrorDeDominio(
            f"El vuelo de regreso {regreso.numero_vuelo} debe salir de {destino.ciudad.nombre} hacia {ida.origen}."
        )
    if sin_zona(regreso.fecha_salida) <= sin_zona(ida.fecha_llegada):
        raise ErrorDeDominio("El vuelo de regreso sale antes de que llegue el de ida.")


async def _resolver_hotel(
    sesion: AsyncSession, hotel_id: int | None, destino: Destino, hotel_de_la_reserva: int | None = None
) -> Hotel | None:
    if hotel_id is None:
        return None
    hotel = await sesion.get(Hotel, hotel_id)
    # Al editar, el hotel que la reserva ya tenía se conserva aunque hoy esté desactivado del catálogo.
    if hotel is None or (not hotel.activo and hotel.id != hotel_de_la_reserva):
        raise ErrorDeDominio("El hotel seleccionado no está disponible.")
    if hotel.ciudad_id != destino.ciudad_id:
        raise ErrorDeDominio(f"El hotel {hotel.nombre} no está en {destino.nombre}.")
    return hotel


async def _resolver_excursiones(
    sesion: AsyncSession,
    elegidas: list[ExcursionElegida],
    destino: Destino,
    pasajeros: int,
    congeladas: TarifasCongeladas | None,
    ya_incluidas: frozenset[int] = frozenset(),
) -> list[LineaExcursion]:
    if not elegidas:
        return []
    ids = [excursion.id for excursion in elegidas]
    encontradas = {e.id: e for e in (await sesion.scalars(select(Excursion).where(Excursion.id.in_(ids)))).unique().all()}
    lineas: list[LineaExcursion] = []
    for elegida in elegidas:
        excursion = encontradas.get(elegida.id)
        # Igual que el hotel: lo que la reserva ya incluía no se pierde porque el catálogo lo haya desactivado.
        if excursion is None or (not excursion.activo and excursion.id not in ya_incluidas):
            raise ErrorDeDominio("Alguna de las excursiones seleccionadas no está disponible.")
        if excursion.ciudad_id != destino.ciudad_id:
            raise ErrorDeDominio(f"La excursión {excursion.nombre} no está en {destino.nombre}.")
        # Una excursión que ya estaba en la reserva conserva el precio con el que se vendió.
        precio = (congeladas.excursiones.get(excursion.id) if congeladas else None)
        precio = precio if precio is not None else Decimal(str(excursion.precio or 0)).quantize(CENTAVOS)
        lineas.append(LineaExcursion(excursion, elegida.cantidad or pasajeros, precio))
    return sorted(lineas, key=lambda linea: linea.excursion.id)


def _tarifas_congeladas(reserva: Reserva | None, destino: Destino, paquete: Paquete | None, hotel: Hotel | None) -> TarifasCongeladas | None:
    """Tarifas con las que se vendió la reserva, para no reprecificar lo que no se tocó."""
    if reserva is None:
        return None
    congeladas = TarifasCongeladas()
    mismo_producto = reserva.destino_id == destino.id and reserva.paquete_id == (paquete.id if paquete else None)
    if mismo_producto and reserva.pasajeros and Decimal(str(reserva.monto_vuelo or 0)) > 0:
        congeladas.vuelo = (Decimal(str(reserva.monto_vuelo)) / reserva.pasajeros).quantize(CENTAVOS)
    if paquete is None and hotel is not None and reserva.hotel_id == hotel.id:
        unidades = reserva.noches * habitaciones_para(reserva.pasajeros)
        if unidades and Decimal(str(reserva.monto_hotel or 0)) > 0:
            congeladas.hotel = (Decimal(str(reserva.monto_hotel)) / unidades).quantize(CENTAVOS)
    congeladas.excursiones = {
        linea.excursion_id: Decimal(str(linea.precio_unitario)) for linea in reserva.lineas_excursion if Decimal(str(linea.precio_unitario)) > 0
    }
    return congeladas


async def preparar_reserva(
    sesion: AsyncSession,
    datos: SolicitudDeViaje,
    reserva_actual: Reserva | None = None,
    bloquear: bool = True,
) -> PlanDeReserva:
    """Valida el viaje contra el catálogo, comprueba las plazas y calcula el precio.

    La usan la cotización, la creación y la edición. `bloquear=False` (cotizar)
    consulta las plazas sin tomar el candado del vuelo.
    """
    destino = await resolver_destino(sesion, datos.destinoId)
    pasajeros = datos.pasajeros
    hotel: Hotel | None = None
    paquete: Paquete | None = None

    if datos.paqueteId is not None:
        paquete = await sesion.get(Paquete, datos.paqueteId)
        paquete_de_la_reserva = reserva_actual.paquete_id if reserva_actual is not None else None
        if paquete is None or (not paquete.activo and paquete.id != paquete_de_la_reserva):
            raise ErrorDeDominio("El paquete seleccionado no está disponible.")
        if paquete.destino_id != destino.id:
            raise ErrorDeDominio("El paquete no corresponde al destino elegido.")
        ida, regreso = paquete.vuelo_rel, paquete.vuelo_regreso_rel
        hotel = paquete.hotel_rel
        fecha_salida = ida.fecha_salida.date()
        fecha_regreso = regreso.fecha_salida.date() if regreso is not None else paquete.fecha_regreso
        congeladas = _tarifas_congeladas(reserva_actual, destino, paquete, hotel)
        # El paquete ya trae sus excursiones: se copian a la reserva sin cobro aparte.
        extras = [LineaExcursion(e, pasajeros, Decimal("0.00")) for e in sorted(paquete.excursiones, key=lambda e: e.id)]
    else:
        ida = await _resolver_vuelo(sesion, datos.vueloId, "ida")
        regreso = await _resolver_vuelo(sesion, datos.vueloRegresoId, "regreso") if datos.vueloRegresoId else None
        fecha_salida = ida.fecha_salida.date()
        fecha_regreso = regreso.fecha_salida.date() if regreso is not None else datos.fechaRegreso
        hotel = await _resolver_hotel(sesion, datos.hotelId, destino, reserva_actual.hotel_id if reserva_actual else None)
        congeladas = _tarifas_congeladas(reserva_actual, destino, None, hotel)
        ya_incluidas = frozenset(linea.excursion_id for linea in reserva_actual.lineas_excursion) if reserva_actual else frozenset()
        extras = await _resolver_excursiones(sesion, datos.excursiones, destino, pasajeros, congeladas, ya_incluidas)

    _validar_ruta(ida, regreso, destino)
    if fecha_regreso < fecha_salida:
        raise ErrorDeDominio("La fecha de regreso no puede ser anterior a la de salida.")
    if (fecha_regreso - fecha_salida).days > DIAS_MAXIMOS_DE_VIAJE:
        raise ErrorDeDominio("El viaje no puede durar más de un año.")
    noches = noches_de_viaje(fecha_salida, fecha_regreso)
    if hotel is not None and paquete is None and noches < 1:
        raise ErrorDeDominio("Para reservar hotel, el regreso debe ser al menos un día después de la salida.")

    # Si el vuelo y los pasajeros no cambian en una edición, no se vuelve a exigir lo que ya se vendió.
    sin_cambios_de_vuelo = (
        reserva_actual is not None
        and reserva_actual.pasajeros == pasajeros
        and reserva_actual.vuelo_id == ida.id
        and reserva_actual.vuelo_regreso_id == (regreso.id if regreso is not None else None)
    )
    if not sin_cambios_de_vuelo:
        tramos = [(ida, "ida")] + ([(regreso, "regreso")] if regreso is not None else [])
        for vuelo, tramo in tramos:
            _exigir_vuelo_vendible(vuelo, tramo)
        await exigir_plazas(sesion, tramos, pasajeros, reserva_actual.id if reserva_actual else None, bloquear=bloquear)

    tarifa_vuelo = tarifa_de_vuelo(destino, paquete, congeladas)
    if paquete is not None:
        tarifa_hotel = Decimal("0.00")
        desglose = desglose_de_paquete(tarifa_vuelo, pasajeros)
    else:
        tarifa_hotel = tarifa_de_hotel(hotel, congeladas)
        desglose = desglose_a_la_carta(tarifa_vuelo, tarifa_hotel, noches, pasajeros, extras)
    lineas = lineas_de_venta(destino, ida, regreso, hotel, extras, desglose, pasajeros, noches, tarifa_vuelo, tarifa_hotel, paquete)
    return PlanDeReserva(
        destino, paquete, ida, regreso, hotel, extras, pasajeros, fecha_salida, fecha_regreso, noches,
        tarifa_vuelo, tarifa_hotel, desglose, lineas,
    )


# --------------------------------------------------------------------------------------
# Alta, edición y estados
# --------------------------------------------------------------------------------------


async def _estados(sesion: AsyncSession) -> SimpleNamespace:
    """Filas de los catálogos de estado y método de pago, por código."""
    reserva = {e.codigo: e for e in (await sesion.scalars(select(EstadoReserva))).all()}
    pago = {e.codigo: e for e in (await sesion.scalars(select(EstadoPago))).all()}
    metodo = {e.codigo: e for e in (await sesion.scalars(select(MetodoPago))).all()}
    return SimpleNamespace(reserva=reserva, pago=pago, metodo=metodo)


def _lineas_de_excursion(plan: PlanDeReserva) -> list[ReservaExcursion]:
    return [
        ReservaExcursion(excursion_id=linea.excursion.id, cantidad=linea.cantidad, precio_unitario=linea.precio_unitario)
        for linea in plan.extras
    ]


async def registrar_reserva(
    sesion: AsyncSession, cliente: User, datos: ReservaCreate, personal: User | None = None
) -> tuple[Reserva, PlanDeReserva]:
    """Crea la reserva con su venta y su factura en una sola transacción.

    Si la registra el personal puede además dejarla ya cobrada en el mostrador.
    """
    plan = await preparar_reserva(sesion, datos)
    estados = await _estados(sesion)
    reserva = Reserva(
        usuario_id=cliente.id,
        creada_por_id=personal.id if personal is not None and personal.id != cliente.id else None,
        destino_id=plan.destino.id,
        vuelo_id=plan.ida.id,
        vuelo_regreso_id=plan.regreso.id if plan.regreso else None,
        paquete_id=plan.paquete.id if plan.paquete else None,
        hotel_id=plan.hotel.id if plan.hotel else None,
        fecha_salida=plan.fecha_salida,
        fecha_regreso=plan.fecha_regreso,
        pasajeros=plan.pasajeros,
        telefono_contacto=datos.telefonoContacto,
        notas=datos.notas,
        estado_rel=estados.reserva["pendiente"],
        estado_pago_rel=estados.pago["pendiente"],
        monto_total=plan.total,
        monto_vuelo=plan.desglose.vuelo,
        monto_hotel=plan.desglose.hotel,
        monto_excursiones=plan.desglose.excursiones,
        lineas_excursion=_lineas_de_excursion(plan),
    )
    sesion.add(reserva)
    await sesion.flush()
    venta = Venta(
        cliente_id=cliente.id,
        usuario_id=(personal or cliente).id,
        reserva_id=reserva.id,
        subtotal=plan.total,
        descuento=Decimal("0"),
        impuestos=Decimal("0"),
        total=plan.total,
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
    if datos.pago is not None and personal is not None:
        await _cobrar_en_mostrador(sesion, reserva, datos.pago, personal, estados)
    # Un unico commit: si algo falla, no queda una reserva sin venta ni factura.
    await sesion.commit()
    return reserva, plan


def _sincronizar_lineas(reserva: Reserva, plan: PlanDeReserva) -> None:
    """Deja las excursiones de la reserva como las del plan, cambiando solo lo que difiere."""
    nuevas = {linea.excursion.id: linea for linea in plan.extras}
    for existente in list(reserva.lineas_excursion):
        if existente.excursion_id not in nuevas:
            reserva.lineas_excursion.remove(existente)
    actuales = {linea.excursion_id: linea for linea in reserva.lineas_excursion}
    for excursion_id, linea in nuevas.items():
        if excursion_id in actuales:
            actuales[excursion_id].cantidad = linea.cantidad
            actuales[excursion_id].precio_unitario = linea.precio_unitario
        else:
            reserva.lineas_excursion.append(
                ReservaExcursion(excursion_id=excursion_id, cantidad=linea.cantidad, precio_unitario=linea.precio_unitario)
            )


async def actualizar_reserva_existente(
    sesion: AsyncSession, reserva: Reserva, datos: ReservaUpdate
) -> tuple[PlanDeReserva, str | None]:
    """Aplica los cambios de una edición y deja venta y factura al día.

    Devuelve el plan y, si el precio cambió mientras había un pago abierto, el
    id de esa sesión de Stripe para que quien llama la expire.
    """
    if reserva.estado_rel.codigo == "cancelada":
        raise ConflictoDeNegocio("Una reserva cancelada no se puede modificar. Reactívala primero.")
    plan = await preparar_reserva(sesion, datos, reserva_actual=reserva)
    precio_cambia = plan.total != Decimal(str(reserva.monto_total or 0)).quantize(CENTAVOS)
    if reserva.estado_pago_rel.codigo == "pagado" and precio_cambia:
        raise ConflictoDeNegocio("La reserva ya está pagada y no se puede cambiar su precio. Cancélala y crea una nueva.")

    reserva.destino_id = plan.destino.id
    reserva.vuelo_id = plan.ida.id
    reserva.vuelo_regreso_id = plan.regreso.id if plan.regreso else None
    reserva.paquete_id = plan.paquete.id if plan.paquete else None
    reserva.hotel_id = plan.hotel.id if plan.hotel else None
    reserva.fecha_salida = plan.fecha_salida
    reserva.fecha_regreso = plan.fecha_regreso
    reserva.pasajeros = plan.pasajeros
    reserva.telefono_contacto = datos.telefonoContacto
    reserva.notas = datos.notas
    reserva.monto_total = plan.total
    reserva.monto_vuelo = plan.desglose.vuelo
    reserva.monto_hotel = plan.desglose.hotel
    reserva.monto_excursiones = plan.desglose.excursiones
    _sincronizar_lineas(reserva, plan)

    sesion_obsoleta = None
    if precio_cambia and reserva.stripe_session_id:
        # El enlace de pago que ya se entregó cobraría el importe anterior.
        sesion_obsoleta, reserva.stripe_session_id = reserva.stripe_session_id, None

    venta = await venta_de_reserva(sesion, reserva.id)
    if venta is not None:
        venta.subtotal = plan.total
        venta.total = plan.total
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


async def _exigir_plazas_de_reserva(sesion: AsyncSession, reserva: Reserva) -> None:
    """Al reactivar una reserva cancelada sus plazas pueden haberse vendido a otra persona."""
    tramos = [(v, t) for v, t in ((reserva.vuelo_rel, "ida"), (reserva.vuelo_regreso_rel, "regreso")) if v is not None]
    for vuelo, tramo in tramos:
        _exigir_vuelo_vendible(vuelo, tramo)
    await exigir_plazas(sesion, tramos, reserva.pasajeros, excluir_reserva_id=reserva.id)


async def cambiar_estado_reserva(sesion: AsyncSession, reserva: Reserva, codigo: str) -> None:
    """Cambia el estado respetando lo que ya ocurrió con el dinero y con las plazas.

    * «confirmada» exige el pago: se confirma cobrando, no a mano.
    * Una reserva pagada no vuelve a «pendiente».
    * Reactivar una cancelada vuelve a tomar sus plazas y falla si ya no quedan.
    """
    actual = reserva.estado_rel.codigo
    if codigo == actual:
        return
    pagada = reserva.estado_pago_rel.codigo == "pagado"
    if codigo == "confirmada" and not pagada:
        raise ConflictoDeNegocio("Registra el pago antes de confirmar la reserva.")
    if codigo == "pendiente" and pagada:
        raise ConflictoDeNegocio("La reserva ya está pagada: no puede volver a pendiente.")
    estado = await sesion.scalar(select(EstadoReserva).where(EstadoReserva.codigo == codigo))
    if estado is None:
        raise ErrorDeDominio("Estado de reserva no válido.")
    if actual == "cancelada":
        await _exigir_plazas_de_reserva(sesion, reserva)
    reserva.estado_rel = estado
    await sincronizar_venta(sesion, reserva)


async def _cobrar_en_mostrador(
    sesion: AsyncSession, reserva: Reserva, pago: PagoInmediato, personal: User, estados: SimpleNamespace | None = None
) -> None:
    """Marca la reserva como pagada con el método y comprobante que indique el personal (sin commit)."""
    if reserva.estado_rel.codigo == "cancelada":
        raise ConflictoDeNegocio("La reserva está cancelada y no se puede cobrar.")
    if reserva.estado_pago_rel.codigo == "pagado":
        raise ConflictoDeNegocio("Esta reserva ya está pagada.")
    estados = estados or await _estados(sesion)
    reserva.estado_pago_rel = estados.pago["pagado"]
    reserva.metodo_pago_rel = estados.metodo[pago.metodo]
    reserva.pago_referencia = pago.referencia
    reserva.pago_registrado_por = personal
    reserva.pagado_en = datetime.now(timezone.utc)
    if reserva.estado_rel.codigo == "pendiente":
        reserva.estado_rel = estados.reserva["confirmada"]
    await sincronizar_venta(sesion, reserva)


async def registrar_pago_de_mostrador(sesion: AsyncSession, reserva: Reserva, pago: PagoInmediato, personal: User) -> None:
    """Cobro en el mostrador de una reserva ya existente. Devuelve con la reserva confirmada y pagada."""
    await _cobrar_en_mostrador(sesion, reserva, pago, personal)
    await sesion.commit()


async def anular_venta_de_reserva(sesion: AsyncSession, reserva: Reserva) -> None:
    """Antes de borrar una reserva: la venta y la factura se conservan como anuladas."""
    venta = await venta_de_reserva(sesion, reserva.id)
    if venta is None:
        return
    venta.reserva_id = None
    venta.estado = "cancelada"
    if venta.factura is not None:
        venta.factura.estado = "anulada"


def resumen_para_correo(reserva: Reserva, plan: PlanDeReserva) -> dict:
    return {
        "destino": plan.destino.nombre,
        "fechaSalida": plan.fecha_salida.isoformat(),
        "fechaRegreso": plan.fecha_regreso.isoformat(),
        "pasajeros": plan.pasajeros,
        "montoTotal": float(plan.total),
        "estado": reserva.estado_rel.codigo,
        "hotel": plan.hotel.nombre if plan.hotel else None,
        "excursiones": [linea.excursion.nombre for linea in plan.extras],
    }


__all__ = [
    "PlanDeReserva",
    "actualizar_reserva_existente",
    "anular_venta_de_reserva",
    "cambiar_estado_reserva",
    "preparar_reserva",
    "registrar_pago_de_mostrador",
    "registrar_reserva",
    "resumen_para_correo",
    "sincronizar_venta",
]
