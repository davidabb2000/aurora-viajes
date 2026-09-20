"""Esquemas de entrada de reservas y pagos."""
from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator


class ReservaCreate(BaseModel):
    origen: str = Field(..., min_length=2, max_length=120)
    destino: str | None = Field(default=None, min_length=1, max_length=120)
    destinoId: int | None = Field(default=None, ge=1)
    vueloId: int | None = Field(default=None, ge=1)
    paqueteId: int | None = Field(default=None, ge=1)
    hotelId: int | None = Field(default=None, ge=1)
    excursionIds: list[int] = Field(default_factory=list, max_length=10)
    fechaSalida: date
    fechaRegreso: date
    pasajeros: int = Field(..., ge=1, le=9)
    telefonoContacto: str = Field(..., min_length=7, max_length=10)
    notas: str | None = Field(None, max_length=300)

    @field_validator("excursionIds")
    @classmethod
    def validar_excursiones(cls, value: list[int]) -> list[int]:
        if any(identificador < 1 for identificador in value):
            raise ValueError("Hay una excursión con identificador inválido.")
        # Elegir dos veces la misma excursion no debe cobrarse dos veces.
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validar_destino(self):
        if self.destino is None and self.destinoId is None:
            raise ValueError("Selecciona un destino válido.")
        return self

    @model_validator(mode="after")
    def validar_fechas(self):
        if self.fechaRegreso < self.fechaSalida:
            raise ValueError("La fecha de regreso no puede ser anterior a la de salida.")
        if self.fechaSalida < date.today():
            raise ValueError("No se puede reservar un viaje con fecha de salida ya pasada.")
        if (self.fechaRegreso - self.fechaSalida).days > 365:
            raise ValueError("El viaje no puede durar más de un año.")
        return self

    @field_validator("telefonoContacto")
    @classmethod
    def validar_telefono(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("Solo se permiten números.")
        return value

    @field_validator("origen")
    @classmethod
    def validar_origen(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Selecciona un lugar de salida.")
        return value


class ReservaUpdate(ReservaCreate):
    destino: str | None = None
    destinoId: int | None = None

    @model_validator(mode="after")
    def validar_destino_update(self):
        if self.destino is None and self.destinoId is None:
            raise ValueError("Selecciona un destino válido.")
        return self


class ConfirmacionDePago(BaseModel):
    sessionId: str | None = Field(default=None, max_length=255)


class EstadoDeReserva(BaseModel):
    estado: str = Field(..., min_length=3, max_length=30)
