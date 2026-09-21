"""Datos de las personas que viajan en una reserva."""
from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.usuarios import TIPOS_DOCUMENTO_VALIDOS, _validar_nombre_propio


class PasajeroEntrada(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=40)
    apellido: str = Field(..., min_length=2, max_length=40)
    tipoDocumento: str = Field(..., min_length=2, max_length=5)
    # Los pasaportes llevan letras: por eso no se exige que sean solo números como en las cuentas.
    numeroDocumento: str = Field(..., min_length=5, max_length=20, pattern=r"^[A-Za-z0-9]+$")

    @field_validator("nombre", "apellido")
    @classmethod
    def validar_nombre(cls, value: str) -> str:
        return _validar_nombre_propio(value)

    @field_validator("tipoDocumento")
    @classmethod
    def validar_tipo(cls, value: str) -> str:
        if value not in TIPOS_DOCUMENTO_VALIDOS:
            raise ValueError("Selecciona un tipo de documento válido (CC, TI, CE o PA).")
        return value

    @field_validator("numeroDocumento")
    @classmethod
    def normalizar_numero(cls, value: str) -> str:
        return value.upper()


class DatosDePasajeros(BaseModel):
    """La lista completa de pasajeros con datos: reemplaza a la anterior. Puede ser menor que el número de plazas."""

    pasajeros: list[PasajeroEntrada] = Field(default_factory=list, max_length=9)

    @model_validator(mode="after")
    def sin_documentos_repetidos(self):
        documentos = [(p.tipoDocumento, p.numeroDocumento) for p in self.pasajeros]
        if len(documentos) != len(set(documentos)):
            raise ValueError("Hay un pasajero repetido: cada persona figura una sola vez en la reserva.")
        return self
