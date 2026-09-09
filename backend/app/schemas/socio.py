from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class SocioCrear(BaseModel):
    """La contraseña entra en claro y sale hasheada: nunca se almacena así."""

    documento: str = Field(pattern=r'^\d{6,15}$')
    nombre: str = Field(min_length=5, max_length=120)
    email: EmailStr
    contrasena: str = Field(min_length=8, max_length=128)
    rol: Literal['socio', 'bibliotecario'] = 'socio'

    @field_validator('contrasena')
    @classmethod
    def suficientemente_fuerte(cls, valor: str) -> str:
        if valor.isalpha() or valor.isdigit():
            raise ValueError('La contraseña debe combinar letras y números.')
        return valor


class SocioRespuesta(BaseModel):
    """Ni el documento ni el hash de la contraseña salen en la respuesta."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    email: EmailStr
    activo: bool
    rol: str
