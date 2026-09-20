"""Esquema del formulario de contacto."""
from pydantic import BaseModel, Field, field_validator


class ContactoCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=80)
    correo: str
    mensaje: str = Field(..., min_length=1, max_length=500)

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Correo electrónico inválido.")
        return value
