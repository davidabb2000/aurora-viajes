"""Esquemas de entrada de usuarios y validación de credenciales."""
import re

from pydantic import BaseModel, Field, field_validator


TIPOS_DOCUMENTO_VALIDOS = {"CC", "TI", "CE", "PA"}
ROLES_VALIDOS = {"administrador", "empleado", "cliente"}
REGEX_CONTRASENA = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,20}$")
REGEX_DIRECCION = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ0-9#\-.,\s]+$")


def exigir_contrasena_robusta(valor: str) -> str:
    """Rechaza contrasenas triviales: pide mayuscula, minuscula y digito."""
    if not any(c.islower() for c in valor) or not any(c.isupper() for c in valor) or not any(c.isdigit() for c in valor):
        raise ValueError("La contrasena debe incluir mayuscula, minuscula y al menos un numero.")
    return valor


class UserCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=40)
    apellido: str = Field(..., min_length=2, max_length=40)
    tipoDocumento: str = Field(..., min_length=2, max_length=5)
    numeroDocumento: str = Field(..., min_length=6, max_length=12)
    direccion: str = Field(..., min_length=5, max_length=80)
    telefono: str = Field(..., min_length=7, max_length=10)
    correo: str
    contrasena: str = Field(..., min_length=8, max_length=128)

    @field_validator("contrasena")
    @classmethod
    def validar_robustez_contrasena(cls, value: str) -> str:
        return exigir_contrasena_robusta(value)

    @field_validator("nombre", "apellido")
    @classmethod
    def validar_nombre(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Este campo es obligatorio.")
        return value

    @field_validator("tipoDocumento")
    @classmethod
    def validar_tipo_documento(cls, value: str) -> str:
        if value not in TIPOS_DOCUMENTO_VALIDOS:
            raise ValueError("Selecciona un tipo de documento válido (CC, TI, CE o PA).")
        return value

    @field_validator("numeroDocumento", "telefono")
    @classmethod
    def validar_numerico(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("Solo se permiten números.")
        return value

    @field_validator("direccion")
    @classmethod
    def validar_direccion(cls, value: str) -> str:
        value = value.strip()
        if not REGEX_DIRECCION.match(value):
            raise ValueError("La dirección contiene caracteres no permitidos.")
        return value

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Correo electrónico inválido.")
        return value

    @field_validator("contrasena")
    @classmethod
    def validar_contrasena(cls, value: str) -> str:
        if not REGEX_CONTRASENA.match(value):
            raise ValueError("Debe incluir mayúscula, minúscula, número y un carácter especial (8 a 20 caracteres).")
        return value


class UsuarioCreateAdmin(UserCreate):
    rol: str = Field(default="cliente")

    @field_validator("rol")
    @classmethod
    def validar_rol(cls, value: str) -> str:
        if value not in ROLES_VALIDOS:
            raise ValueError("Rol no válido.")
        return value


class UserUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=40)
    apellido: str | None = Field(default=None, min_length=2, max_length=40)
    tipoDocumento: str | None = None
    numeroDocumento: str | None = Field(default=None, min_length=6, max_length=12)
    direccion: str | None = Field(default=None, min_length=5, max_length=80)
    telefono: str | None = Field(default=None, min_length=7, max_length=10)
    correo: str | None = None
    rol: str | None = None

    @field_validator("tipoDocumento")
    @classmethod
    def validar_tipo_documento(cls, value: str | None) -> str | None:
        if value is not None and value not in TIPOS_DOCUMENTO_VALIDOS:
            raise ValueError("Selecciona un tipo de documento válido (CC, TI, CE o PA).")
        return value

    @field_validator("numeroDocumento", "telefono")
    @classmethod
    def validar_numerico(cls, value: str | None) -> str | None:
        if value is not None and not value.isdigit():
            raise ValueError("Solo se permiten números.")
        return value

    @field_validator("direccion")
    @classmethod
    def validar_direccion(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not REGEX_DIRECCION.match(value):
                raise ValueError("La dirección contiene caracteres no permitidos.")
        return value

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip().lower()
            if "@" not in value or "." not in value.split("@")[-1]:
                raise ValueError("Correo electrónico inválido.")
        return value

    @field_validator("rol")
    @classmethod
    def validar_rol(cls, value: str | None) -> str | None:
        if value is not None and value not in ROLES_VALIDOS:
            raise ValueError("Rol no válido.")
        return value


class EstadoUpdate(BaseModel):
    activo: bool
