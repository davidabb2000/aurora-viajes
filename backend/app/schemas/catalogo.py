"""Esquemas de entrada del catálogo: productos, servicios, vuelos, hoteles, excursiones y paquetes."""
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator


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


ESTADOS_VUELO_VALIDOS = {"programado", "abordando", "en_vuelo", "aterrizado", "cancelado"}
AEROLINEAS_DISPONIBLES = {"Aurora Airlines", "Avianca", "LATAM", "Copa Airlines", "Iberia"}
AVIONES_DISPONIBLES = {"Airbus A320", "Airbus A330", "Boeing 737", "Boeing 787", "Embraer E195"}
CAPACIDAD_POR_AVION = {
    "Airbus A320": 180,
    "Airbus A330": 300,
    "Boeing 737": 189,
    "Boeing 787": 330,
    "Embraer E195": 132,
}
ORIGENES_DISPONIBLES = {"Bogotá", "Medellín", "Cali", "Cartagena", "Barranquilla", "Lima", "Madrid"}


class VueloCreate(BaseModel):
    numeroVuelo: str | None = Field(default=None, min_length=2, max_length=20)
    aerolinea: str = Field(..., min_length=2, max_length=80)
    avion: str = Field(..., min_length=2, max_length=80)
    origen: str = Field(..., min_length=2, max_length=120)
    destino: str = Field(..., min_length=2, max_length=120)
    fechaSalida: datetime
    fechaLlegada: datetime
    capacidadMaxima: int | None = Field(default=None, ge=1, le=1000)
    puerta: str | None = Field(default=None, max_length=10)
    terminal: str | None = Field(default=None, max_length=20)
    estado: str = "programado"
    activo: bool = True

    @field_validator("aerolinea", "avion", "origen", "destino")
    @classmethod
    def validar_texto(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Este campo es obligatorio.")
        return value

    @field_validator("aerolinea")
    @classmethod
    def validar_aerolinea(cls, value: str) -> str:
        if value not in AEROLINEAS_DISPONIBLES:
            raise ValueError("Selecciona una aerolínea válida.")
        return value

    @field_validator("avion")
    @classmethod
    def validar_avion(cls, value: str) -> str:
        if value not in AVIONES_DISPONIBLES:
            raise ValueError("Selecciona un avión válido.")
        return value

    @field_validator("origen")
    @classmethod
    def validar_origen(cls, value: str) -> str:
        if value not in ORIGENES_DISPONIBLES:
            raise ValueError("Selecciona un origen válido del catálogo.")
        return value

    @field_validator("estado")
    @classmethod
    def validar_estado(cls, value: str) -> str:
        if value not in ESTADOS_VUELO_VALIDOS:
            raise ValueError("Estado de vuelo no válido.")
        return value

    @model_validator(mode="after")
    def validar_horario(self):
        if self.fechaLlegada <= self.fechaSalida:
            raise ValueError("La llegada debe ser posterior a la salida.")
        self.capacidadMaxima = CAPACIDAD_POR_AVION[self.avion]
        return self


class HotelCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=120)
    ciudad: str = Field(..., min_length=2, max_length=120)
    pais: str = Field(..., min_length=2, max_length=120)
    estrellas: int = Field(..., ge=1, le=5)
    precioNoche: float = Field(default=0, ge=0)
    descripcion: str | None = Field(default=None, max_length=1000)
    activo: bool = True


class ExcursionCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=120)
    ciudad: str = Field(..., min_length=2, max_length=120)
    pais: str = Field(..., min_length=2, max_length=120)
    duracionHoras: int = Field(..., ge=1, le=48)
    precio: float = Field(default=0, ge=0)
    descripcion: str | None = Field(default=None, max_length=1000)
    activo: bool = True


class PaqueteCreate(BaseModel):
    nombre: str = Field(..., min_length=3, max_length=140)
    destinoId: int = Field(..., ge=1)
    vueloId: int | None = Field(default=None, ge=1)
    vuelo: VueloCreate | None = None
    hotelId: int = Field(..., ge=1)
    excursionIds: list[int] = Field(default_factory=list, max_length=20)
    fechaSalida: date
    fechaRegreso: date
    precioBase: float = Field(default=0, ge=0)
    activo: bool = True

    @model_validator(mode="after")
    def validar_fechas(self):
        if self.fechaRegreso < self.fechaSalida:
            raise ValueError("La fecha de regreso debe ser posterior a la salida.")
        if self.vueloId is None and self.vuelo is None:
            raise ValueError("Debes configurar el vuelo dentro de la reserva.")
        if self.vueloId is not None and self.vuelo is not None:
            raise ValueError("Usa un vuelo existente o configura uno nuevo, no ambos.")
        return self
