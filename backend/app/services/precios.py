"""Cálculo del precio de una reserva y de las líneas que se facturan."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.models.dominio import Destino, Excursion, Hotel, Paquete

CENTAVOS = Decimal("0.01")


def noches_de_viaje(fecha_salida: date, fecha_regreso: date) -> int:
    return max(1, (fecha_regreso - fecha_salida).days)


def habitaciones_para(pasajeros: int) -> int:
    """Dos personas por habitacion, redondeando hacia arriba."""
    return (pasajeros + 1) // 2


class DesgloseReserva(BaseModel):
    """Precio de la reserva separado por concepto.

    Guardarlo permite que la factura detalle cada linea y que el total quede
    congelado: si manana sube el precio de un hotel, la reserva ya emitida no
    cambia.
    """

    vuelo: Decimal
    hotel: Decimal
    excursiones: Decimal

    @property
    def total(self) -> Decimal:
        return (self.vuelo + self.hotel + self.excursiones).quantize(CENTAVOS)


def calcular_desglose_reserva(
    destino: Destino,
    hotel: Hotel | None,
    excursiones: list[Excursion],
    fecha_salida: date,
    fecha_regreso: date,
    pasajeros: int,
) -> DesgloseReserva:
    """Precio por concepto: vuelo por pasajero, hotel por noche y habitacion,
    excursiones por pasajero."""
    noches = noches_de_viaje(fecha_salida, fecha_regreso)
    viajeros = Decimal(str(pasajeros))

    monto_vuelo = (Decimal(destino.precio_base or 0) * viajeros).quantize(CENTAVOS)

    monto_hotel = Decimal("0")
    if hotel is not None:
        habitaciones = Decimal(str(habitaciones_para(pasajeros)))
        monto_hotel = (Decimal(hotel.precio_noche or 0) * Decimal(str(noches)) * habitaciones).quantize(CENTAVOS)

    monto_excursiones = Decimal("0")
    for excursion in excursiones:
        monto_excursiones += Decimal(excursion.precio or 0) * viajeros
    monto_excursiones = monto_excursiones.quantize(CENTAVOS)

    return DesgloseReserva(vuelo=monto_vuelo, hotel=monto_hotel, excursiones=monto_excursiones)


def desglose_de_paquete(paquete: Paquete, pasajeros: int) -> DesgloseReserva:
    """El precio del paquete manda: es una oferta cerrada que ya incluye hotel y excursiones."""
    total = (Decimal(paquete.precio_base or 0) * Decimal(str(pasajeros))).quantize(CENTAVOS)
    return DesgloseReserva(vuelo=total, hotel=Decimal("0"), excursiones=Decimal("0"))


def _linea_incluida(nombre: str) -> dict:
    return {"nombre": nombre, "cantidad": 1, "precio_unitario": Decimal("0.00"), "subtotal": Decimal("0.00")}


def lineas_de_venta(
    destino: Destino,
    hotel: Hotel | None,
    excursiones: list[Excursion],
    desglose: DesgloseReserva,
    pasajeros: int,
    noches: int,
    paquete: Paquete | None = None,
) -> list[dict]:
    """Una linea por concepto. La suma de los subtotales siempre iguala el total de la reserva.

    En un paquete el precio va en una sola linea y el hotel y las excursiones
    figuran como incluidos a valor cero. Antes se sumaban tambien las
    excursiones, y la factura terminaba cobrando mas que la venta.
    """
    viajeros = Decimal(str(pasajeros))

    if paquete is not None:
        lineas = [{
            "nombre": f"Paquete {paquete.nombre} - {destino.nombre}",
            "cantidad": pasajeros,
            "precio_unitario": (desglose.total / viajeros).quantize(CENTAVOS),
            "subtotal": desglose.total,
        }]
        if hotel is not None:
            lineas.append(_linea_incluida(f"Hotel {hotel.nombre} ({hotel.estrellas}*) - incluido en el paquete"))
        for excursion in excursiones:
            lineas.append(_linea_incluida(f"Excursión {excursion.nombre} ({excursion.duracion_horas}h) - incluida en el paquete"))
        return lineas

    lineas = [{
        "nombre": f"Vuelo y traslados - {destino.nombre}",
        "cantidad": pasajeros,
        "precio_unitario": (desglose.vuelo / viajeros).quantize(CENTAVOS),
        "subtotal": desglose.vuelo,
    }]
    if hotel is not None and desglose.hotel > 0:
        habitaciones = habitaciones_para(pasajeros)
        unidades = noches * habitaciones
        lineas.append({
            "nombre": f"Hotel {hotel.nombre} ({hotel.estrellas}*) - {noches} noche(s) x {habitaciones} habitacion(es)",
            "cantidad": unidades,
            "precio_unitario": (desglose.hotel / Decimal(str(unidades))).quantize(CENTAVOS),
            "subtotal": desglose.hotel,
        })
    for excursion in excursiones:
        lineas.append({
            "nombre": f"Excursión {excursion.nombre} ({excursion.duracion_horas}h)",
            "cantidad": pasajeros,
            "precio_unitario": Decimal(excursion.precio or 0).quantize(CENTAVOS),
            "subtotal": (Decimal(excursion.precio or 0) * viajeros).quantize(CENTAVOS),
        })
    return lineas
