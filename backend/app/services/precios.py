"""Cálculo del precio de una reserva y de las líneas que se facturan."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.models.dominio import Destino, Excursion, Hotel, Paquete, Vuelo

CENTAVOS = Decimal("0.01")


def dinero(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(CENTAVOS)


def noches_de_viaje(fecha_salida: date, fecha_regreso: date) -> int:
    """Noches entre la salida y el regreso. Cero si son el mismo día."""
    return max(0, (fecha_regreso - fecha_salida).days)


def habitaciones_para(pasajeros: int) -> int:
    """Dos personas por habitacion, redondeando hacia arriba."""
    return (pasajeros + 1) // 2


@dataclass(frozen=True)
class LineaExcursion:
    """Una excursión elegida: cuántas personas van y a qué precio unitario."""

    excursion: Excursion
    cantidad: int
    precio_unitario: Decimal

    @property
    def subtotal(self) -> Decimal:
        return (self.precio_unitario * self.cantidad).quantize(CENTAVOS)


@dataclass
class TarifasCongeladas:
    """Tarifas con las que se vendió una reserva que se está editando.

    Cambiar el teléfono o las notas de una reserva pagada no debe reprecificarla
    con las tarifas de hoy: solo cambia el precio de aquello que el cliente
    realmente modificó (otro destino, otro hotel, otra excursión).
    """

    vuelo: Decimal | None = None  # por pasajero
    hotel: Decimal | None = None  # por noche y habitación
    excursiones: dict[int, Decimal] = field(default_factory=dict)  # excursion_id -> precio unitario


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


def tarifa_de_vuelo(destino: Destino, paquete: Paquete | None, congeladas: TarifasCongeladas | None) -> Decimal:
    """Precio por pasajero del vuelo (o del paquete completo, que manda sobre el del destino)."""
    if congeladas is not None and congeladas.vuelo is not None:
        return congeladas.vuelo
    return dinero(paquete.precio_base if paquete is not None else destino.precio_base)


def tarifa_de_hotel(hotel: Hotel | None, congeladas: TarifasCongeladas | None) -> Decimal:
    if hotel is None:
        return Decimal("0.00")
    if congeladas is not None and congeladas.hotel is not None:
        return congeladas.hotel
    return dinero(hotel.precio_noche)


def desglose_a_la_carta(
    tarifa_vuelo: Decimal, tarifa_hotel: Decimal, noches: int, pasajeros: int, extras: list[LineaExcursion]
) -> DesgloseReserva:
    """Vuelo por pasajero, hotel por noche y habitación, excursiones por persona que las hace."""
    monto_vuelo = (tarifa_vuelo * pasajeros).quantize(CENTAVOS)
    monto_hotel = (tarifa_hotel * noches * habitaciones_para(pasajeros)).quantize(CENTAVOS)
    monto_excursiones = sum((linea.subtotal for linea in extras), Decimal("0.00")).quantize(CENTAVOS)
    return DesgloseReserva(vuelo=monto_vuelo, hotel=monto_hotel, excursiones=monto_excursiones)


def desglose_de_paquete(tarifa_paquete: Decimal, pasajeros: int) -> DesgloseReserva:
    """El precio del paquete manda: es una oferta cerrada que ya incluye hotel y excursiones."""
    return DesgloseReserva(vuelo=(tarifa_paquete * pasajeros).quantize(CENTAVOS), hotel=Decimal("0.00"), excursiones=Decimal("0.00"))


def _linea_incluida(nombre: str) -> dict:
    return {"nombre": nombre, "cantidad": 1, "precio_unitario": Decimal("0.00"), "subtotal": Decimal("0.00")}


def _nombre_de_vuelos(ida: Vuelo, regreso: Vuelo | None) -> str:
    texto = f"Vuelo {ida.numero_vuelo} {ida.origen} - {ida.destino}"
    if regreso is not None:
        texto += f" y regreso {regreso.numero_vuelo}"
    return texto[:140]


def lineas_de_venta(
    destino: Destino,
    ida: Vuelo,
    regreso: Vuelo | None,
    hotel: Hotel | None,
    extras: list[LineaExcursion],
    desglose: DesgloseReserva,
    pasajeros: int,
    noches: int,
    tarifa_vuelo: Decimal,
    tarifa_hotel: Decimal,
    paquete: Paquete | None = None,
) -> list[dict]:
    """Una linea por concepto. La suma de los subtotales siempre iguala el total de la reserva.

    En un paquete el precio va en una sola linea y el hotel y las excursiones
    figuran como incluidos a valor cero. Los subtotales salen del mismo desglose
    que se cobra, así que factura y reserva no pueden diferir ni en un centavo.
    """
    if paquete is not None:
        lineas = [{
            "nombre": f"Paquete {paquete.nombre} - {destino.nombre}"[:140],
            "cantidad": pasajeros,
            "precio_unitario": tarifa_vuelo,
            "subtotal": desglose.vuelo,
        }]
        if hotel is not None:
            lineas.append(_linea_incluida(f"Hotel {hotel.nombre} ({hotel.estrellas}*) - incluido en el paquete"[:140]))
        for linea in extras:
            lineas.append(_linea_incluida(f"Excursión {linea.excursion.nombre} ({linea.excursion.duracion_horas}h) - incluida en el paquete"[:140]))
        return lineas

    lineas = [{
        "nombre": _nombre_de_vuelos(ida, regreso),
        "cantidad": pasajeros,
        "precio_unitario": tarifa_vuelo,
        "subtotal": desglose.vuelo,
    }]
    if hotel is not None and desglose.hotel > 0:
        unidades = noches * habitaciones_para(pasajeros)
        lineas.append({
            "nombre": f"Hotel {hotel.nombre} ({hotel.estrellas}*) - {noches} noche(s) x {habitaciones_para(pasajeros)} habitacion(es)"[:140],
            "cantidad": unidades,
            "precio_unitario": tarifa_hotel,
            "subtotal": desglose.hotel,
        })
    for linea in extras:
        lineas.append({
            "nombre": f"Excursión {linea.excursion.nombre} ({linea.excursion.duracion_horas}h)"[:140],
            "cantidad": linea.cantidad,
            "precio_unitario": linea.precio_unitario,
            "subtotal": linea.subtotal,
        })
    return lineas
