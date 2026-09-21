"""Esquemas de entrada del catálogo: productos, servicios, lugares, vuelos, hoteles, excursiones y paquetes."""
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.reservas import limpiar_texto

ESTADOS_VUELO_VALIDOS = ("programado", "abordando", "en_vuelo", "aterrizado", "cancelado")
EstadoDeVuelo = Literal["programado", "abordando", "en_vuelo", "aterrizado", "cancelado"]


def _sin_zona(valor: datetime) -> datetime:
    """Las horas de los vuelos son la hora local del aeropuerto: se guardan sin zona horaria."""
    return valor.astimezone(timezone.utc).replace(tzinfo=None) if valor.tzinfo else valor


class ProductoCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    descripcion: str | None = None
    precio: float = Field(default=0, ge=0)
    activo: bool = True


class ServicioCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    descripcion: str | None = None
    precio: float = Field(default=0, ge=0)
    activo: bool = True


class CiudadCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=80)
    pais: str = Field(..., min_length=2, max_length=80)

    @field_validator("nombre", "pais")
    @classmethod
    def validar_texto(cls, value: str) -> str:
        limpio = limpiar_texto(value)
        if not limpio:
            raise ValueError("Este campo es obligatorio.")
        return limpio


class DestinoCreate(BaseModel):
    """Una ciudad que se vende como destino. `precioBase` es la tarifa aérea por pasajero: con 0 no se ofrece a los clientes."""

    ciudadId: int = Field(..., ge=1)
    descripcion: str | None = Field(default=None, max_length=2000)
    precioBase: float = Field(..., gt=0, le=1_000_000_000)
    # Nombre de la ilustración de la portada (por ejemplo «paris»). Sin ella se usa una genérica.
    imagenSlug: str | None = Field(default=None, max_length=80, pattern=r"^[a-z0-9-]+$")
    activo: bool = True

    @field_validator("descripcion")
    @classmethod
    def limpiar_descripcion(cls, value: str | None) -> str | None:
        return limpiar_texto(value)


class AerolineaCreate(BaseModel):
    codigo: str = Field(..., min_length=2, max_length=4, pattern=r"^[A-Za-z0-9]+$")
    nombre: str = Field(..., min_length=2, max_length=80)

    @field_validator("codigo")
    @classmethod
    def mayusculas(cls, value: str) -> str:
        return value.upper()

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, value: str) -> str:
        limpio = limpiar_texto(value)
        if not limpio:
            raise ValueError("Este campo es obligatorio.")
        return limpio


class ModeloAvionCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=80)
    capacidad: int = Field(..., ge=1, le=1000)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, value: str) -> str:
        limpio = limpiar_texto(value)
        if not limpio:
            raise ValueError("Este campo es obligatorio.")
        return limpio


class VueloCreate(BaseModel):
    numeroVuelo: str | None = Field(default=None, min_length=2, max_length=20, pattern=r"^[A-Za-z0-9-]+$")
    aerolineaId: int = Field(..., ge=1)
    modeloAvionId: int = Field(..., ge=1)
    origenId: int = Field(..., ge=1)
    destinoId: int = Field(..., ge=1)
    fechaSalida: datetime
    fechaLlegada: datetime
    # Plazas a la venta. Sin indicarlas se venden todas las del modelo de avión.
    capacidadMaxima: int | None = Field(default=None, ge=1, le=1000)
    puerta: str | None = Field(default=None, max_length=10)
    terminal: str | None = Field(default=None, max_length=20)
    estado: EstadoDeVuelo = "programado"
    activo: bool = True

    @field_validator("fechaSalida", "fechaLlegada")
    @classmethod
    def quitar_zona(cls, value: datetime) -> datetime:
        return _sin_zona(value)

    @field_validator("numeroVuelo")
    @classmethod
    def numero_en_mayusculas(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("puerta", "terminal")
    @classmethod
    def limpiar(cls, value: str | None) -> str | None:
        return limpiar_texto(value)

    @model_validator(mode="after")
    def validar_ruta_y_horario(self):
        if self.origenId == self.destinoId:
            raise ValueError("El origen y el destino del vuelo no pueden ser la misma ciudad.")
        if self.fechaLlegada <= self.fechaSalida:
            raise ValueError("La llegada debe ser posterior a la salida.")
        return self


class HotelCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=120)
    ciudadId: int = Field(..., ge=1)
    estrellas: int = Field(..., ge=1, le=5)
    precioNoche: float = Field(default=0, ge=0)
    descripcion: str | None = Field(default=None, max_length=1000)
    activo: bool = True

    @field_validator("nombre")
    @classmethod
    def limpiar_nombre(cls, value: str) -> str:
        limpio = limpiar_texto(value)
        if not limpio or len(limpio) < 2:
            raise ValueError("El nombre es demasiado corto.")
        return limpio

    @field_validator("descripcion")
    @classmethod
    def limpiar_descripcion(cls, value: str | None) -> str | None:
        return limpiar_texto(value)


class ExcursionCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=120)
    ciudadId: int = Field(..., ge=1)
    duracionHoras: int = Field(..., ge=1, le=48)
    precio: float = Field(default=0, ge=0)
    descripcion: str | None = Field(default=None, max_length=1000)
    activo: bool = True

    @field_validator("nombre")
    @classmethod
    def limpiar_nombre(cls, value: str) -> str:
        limpio = limpiar_texto(value)
        if not limpio or len(limpio) < 2:
            raise ValueError("El nombre es demasiado corto.")
        return limpio

    @field_validator("descripcion")
    @classmethod
    def limpiar_descripcion(cls, value: str | None) -> str | None:
        return limpiar_texto(value)


class PaqueteCreate(BaseModel):
    """Un paquete une un vuelo de ida, uno de regreso, un hotel y excursiones a un precio cerrado."""

    nombre: str = Field(..., min_length=3, max_length=140)
    destinoId: int = Field(..., ge=1)
    vueloId: int = Field(..., ge=1)
    vueloRegresoId: int | None = Field(default=None, ge=1)
    hotelId: int = Field(..., ge=1)
    excursionIds: list[int] = Field(default_factory=list, max_length=20)
    noches: int | None = Field(default=None, ge=1, le=90, description="Obligatorio si no hay vuelo de regreso")
    precioBase: float = Field(default=0, ge=0)
    activo: bool = True

    @field_validator("nombre")
    @classmethod
    def limpiar_nombre(cls, value: str) -> str:
        limpio = limpiar_texto(value)
        if not limpio or len(limpio) < 3:
            raise ValueError("El nombre es demasiado corto.")
        return limpio

    @field_validator("excursionIds")
    @classmethod
    def sin_repetidas(cls, value: list[int]) -> list[int]:
        if any(i < 1 for i in value):
            raise ValueError("Hay una excursión con identificador inválido.")
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validar_duracion(self):
        if self.vueloRegresoId is None and self.noches is None:
            raise ValueError("Indica las noches del paquete o elige un vuelo de regreso.")
        return self
