"""Esquemas de autenticación y recuperación de contraseña."""
from pydantic import BaseModel, Field, field_validator

from app.schemas.usuarios import UserCreate, exigir_contrasena_robusta


class UserLogin(BaseModel):
    correo: str
    contrasena: str = Field(..., min_length=1)

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, value: str) -> str:
        return UserCreate.validar_correo(value)


class RecuperarContrasena(BaseModel):
    correo: str

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, value: str) -> str:
        return UserCreate.validar_correo(value)


class RestablecerContrasena(BaseModel):
    correo: str
    token: str = Field(..., min_length=10, max_length=2000)
    nuevaContrasena: str = Field(..., min_length=8, max_length=128)

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, value: str) -> str:
        return UserCreate.validar_correo(value)

    @field_validator("nuevaContrasena")
    @classmethod
    def validar_robustez(cls, value: str) -> str:
        return exigir_contrasena_robusta(value)
