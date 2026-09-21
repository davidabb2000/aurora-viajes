"""Esquema del formulario de contacto."""
from pydantic import BaseModel, Field, field_validator

from app.core.politica_contrasena import normalizar_correo
from app.schemas.reservas import limpiar_texto


class ContactoCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=80)
    correo: str = Field(..., max_length=254)
    mensaje: str = Field(..., min_length=1, max_length=500)

    @field_validator("nombre", "mensaje")
    @classmethod
    def limpiar(cls, value: str) -> str:
        """Sin caracteres de control ni espacios sobrantes; un texto que queda vacío se rechaza."""
        limpio = limpiar_texto(value)
        if not limpio:
            raise ValueError("Este campo es obligatorio.")
        return limpio

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, value: str) -> str:
        return normalizar_correo(value)
