"""Esquemas de autenticación y recuperación de contraseña."""
from pydantic import BaseModel, Field, field_validator

from app.core.politica_contrasena import normalizar_correo


class UserLogin(BaseModel):
    correo: str = Field(..., max_length=254)
    contrasena: str = Field(..., min_length=1, max_length=128)

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, value: str) -> str:
        return normalizar_correo(value)


class RecuperarContrasena(BaseModel):
    correo: str = Field(..., max_length=254)

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, value: str) -> str:
        return normalizar_correo(value)


class RestablecerContrasena(BaseModel):
    """El token del correo ya identifica a la persona: no hace falta volver a pedir el correo."""

    token: str = Field(..., min_length=10, max_length=2000)
    nuevaContrasena: str = Field(..., min_length=8, max_length=128)


class CambiarContrasena(BaseModel):
    contrasenaActual: str = Field(..., min_length=1, max_length=128)
    nuevaContrasena: str = Field(..., min_length=8, max_length=128)
