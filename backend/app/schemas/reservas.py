"""Esquemas de entrada de reservas y pagos."""
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

METODOS_DE_MOSTRADOR = ("efectivo", "transferencia", "tarjeta")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def limpiar_texto(valor: str | None) -> str | None:
    """Quita caracteres de control y espacios sobrantes; una cadena vacía pasa a None."""
    if valor is None:
        return None
    limpio = _CONTROL.sub("", valor).strip()
    return limpio or None


class ExcursionElegida(BaseModel):
    """Una excursión de la reserva. Sin `cantidad`, la hacen todos los pasajeros."""

    id: int = Field(..., ge=1)
    cantidad: int | None = Field(default=None, ge=1, le=9)


class SolicitudDeViaje(BaseModel):
    """Todo lo que define un viaje: es lo que se cotiza y lo que se reserva.

    Las fechas de salida y de regreso no las escribe quien reserva: salen de los
    vuelos elegidos. Solo con un regreso «abierto» (sin vuelo de vuelta) se pide
    la fecha, que define las noches de hotel.
    """

    destinoId: int = Field(..., ge=1)
    paqueteId: int | None = Field(default=None, ge=1)
    vueloId: int | None = Field(default=None, ge=1, description="Vuelo de ida (a la carta)")
    vueloRegresoId: int | None = Field(default=None, ge=1)
    fechaRegreso: date | None = None
    hotelId: int | None = Field(default=None, ge=1)
    excursiones: list[ExcursionElegida] = Field(default_factory=list, max_length=10)
    pasajeros: int = Field(..., ge=1, le=9)

    @model_validator(mode="after")
    def validar_combinacion(self):
        if self.paqueteId is not None:
            if any((self.vueloId, self.vueloRegresoId, self.hotelId, self.fechaRegreso, self.excursiones)):
                raise ValueError("Un paquete ya incluye los vuelos, el hotel y las excursiones: no se pueden elegir aparte.")
        else:
            if self.vueloId is None:
                raise ValueError("Elige el vuelo de ida.")
            if self.vueloRegresoId is not None and self.fechaRegreso is not None:
                raise ValueError("Con vuelo de regreso la fecha de regreso es la de ese vuelo.")
            if self.vueloRegresoId is None and self.fechaRegreso is None:
                raise ValueError("Elige el vuelo de regreso o indica la fecha en que regresas por tu cuenta.")
        identificadores = [excursion.id for excursion in self.excursiones]
        if len(identificadores) != len(set(identificadores)):
            raise ValueError("Hay una excursión repetida.")
        for excursion in self.excursiones:
            if excursion.cantidad is not None and excursion.cantidad > self.pasajeros:
                raise ValueError("Una excursión no puede tener más personas que pasajeros.")
        return self


class SolicitudDeCotizacion(SolicitudDeViaje):
    """Un viaje que se cotiza. Con `reservaId` (al editar una reserva) se aplican las reglas de la edición:
    precios ya vendidos, vuelos que no cambian y piezas que el catálogo retiró después de la venta."""

    reservaId: int | None = Field(default=None, ge=1)


class ReservaDatos(SolicitudDeViaje):
    telefonoContacto: str = Field(..., min_length=7, max_length=10)
    notas: str | None = Field(default=None, max_length=300)

    @field_validator("telefonoContacto")
    @classmethod
    def validar_telefono(cls, value: str) -> str:
        if not value.isascii() or not value.isdigit():
            raise ValueError("Solo se permiten números.")
        return value

    @field_validator("notas")
    @classmethod
    def validar_notas(cls, value: str | None) -> str | None:
        return limpiar_texto(value)


class PagoInmediato(BaseModel):
    """Cobro registrado por el personal en el mostrador al crear la reserva."""

    metodo: Literal["efectivo", "transferencia", "tarjeta"]
    referencia: str | None = Field(default=None, max_length=80)

    @field_validator("referencia")
    @classmethod
    def validar_referencia(cls, value: str | None) -> str | None:
        return limpiar_texto(value)


class ReservaCreate(ReservaDatos):
    # Solo el personal puede reservar a nombre de otro cliente y cobrar en el momento.
    clienteId: int | None = Field(default=None, ge=1)
    pago: PagoInmediato | None = None


class ReservaUpdate(ReservaDatos):
    pass


class ConfirmacionDePago(BaseModel):
    sessionId: str | None = Field(default=None, max_length=255)


class PagoDeMostrador(PagoInmediato):
    pass


class EstadoDeReserva(BaseModel):
    estado: Literal["pendiente", "confirmada", "cancelada"]
