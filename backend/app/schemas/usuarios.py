"""Esquemas de entrada de usuarios."""
import re

from pydantic import BaseModel, Field, field_validator

from app.core.politica_contrasena import normalizar_correo, validar_contrasena

TIPOS_DOCUMENTO_VALIDOS = {"CC", "TI", "CE", "PA"}
ROLES_VALIDOS = {"administrador", "empleado", "cliente"}
REGEX_DIRECCION = re.compile(r"^[A-Za-zÁÉÍÓÚÜáéíóúüÑñ0-9#\-.,°\s]+$")
REGEX_NOMBRE = re.compile(r"^[A-Za-zÁÉÍÓÚÜáéíóúüÑñ][A-Za-zÁÉÍÓÚÜáéíóúüÑñ '\-]*$")


def _validar_nombre_propio(value: str) -> str:
    limpio = " ".join(value.split())
    if len(limpio) < 2:
        raise ValueError("Este campo es obligatorio.")
    if not REGEX_NOMBRE.match(limpio):
        raise ValueError("Solo se permiten letras, espacios, apóstrofes y guiones.")
    return limpio


class UserCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=40)
    apellido: str = Field(..., min_length=2, max_length=40)
    tipoDocumento: str = Field(..., min_length=2, max_length=5)
    numeroDocumento: str = Field(..., min_length=6, max_length=12)
    direccion: str = Field(..., min_length=5, max_length=80)
    telefono: str = Field(..., min_length=7, max_length=10)
    correo: str
    contrasena: str = Field(..., min_length=8, max_length=128)

    @field_validator("nombre", "apellido")
    @classmethod
    def validar_nombre(cls, value: str) -> str:
        return _validar_nombre_propio(value)

    @field_validator("tipoDocumento")
    @classmethod
    def validar_tipo_documento(cls, value: str) -> str:
        if value not in TIPOS_DOCUMENTO_VALIDOS:
            raise ValueError("Selecciona un tipo de documento válido (CC, TI, CE o PA).")
        return value

    @field_validator("numeroDocumento", "telefono")
    @classmethod
    def validar_numerico(cls, value: str) -> str:
        if not value.isascii() or not value.isdigit():
            raise ValueError("Solo se permiten números.")
        return value

    @field_validator("direccion")
    @classmethod
    def validar_direccion(cls, value: str) -> str:
        value = " ".join(value.split())
        if not REGEX_DIRECCION.match(value):
            raise ValueError("La dirección contiene caracteres no permitidos.")
        return value

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, value: str) -> str:
        return normalizar_correo(value)

    @field_validator("contrasena")
    @classmethod
    def validar_contrasena_completa(cls, value: str, info) -> str:
        # `info.data` ya trae el correo y el nombre validados: la clave no puede contenerlos.
        return validar_contrasena(value, info.data.get("correo"), info.data.get("nombre"), info.data.get("apellido"))


class RegistroPublico(UserCreate):
    """El registro desde la web exige aceptar el tratamiento de datos; la fecha se guarda."""

    aceptaTratamientoDatos: bool

    @field_validator("aceptaTratamientoDatos")
    @classmethod
    def exigir_aceptacion(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Debes autorizar el tratamiento de tus datos para crear la cuenta.")
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

    @field_validator("nombre", "apellido")
    @classmethod
    def validar_nombre(cls, value: str | None) -> str | None:
        return _validar_nombre_propio(value) if value is not None else None

    @field_validator("tipoDocumento")
    @classmethod
    def validar_tipo_documento(cls, value: str | None) -> str | None:
        if value is not None and value not in TIPOS_DOCUMENTO_VALIDOS:
            raise ValueError("Selecciona un tipo de documento válido (CC, TI, CE o PA).")
        return value

    @field_validator("numeroDocumento", "telefono")
    @classmethod
    def validar_numerico(cls, value: str | None) -> str | None:
        if value is not None and (not value.isascii() or not value.isdigit()):
            raise ValueError("Solo se permiten números.")
        return value

    @field_validator("direccion")
    @classmethod
    def validar_direccion(cls, value: str | None) -> str | None:
        if value is not None:
            value = " ".join(value.split())
            if not REGEX_DIRECCION.match(value):
                raise ValueError("La dirección contiene caracteres no permitidos.")
        return value

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, value: str | None) -> str | None:
        return normalizar_correo(value) if value is not None else None

    @field_validator("rol")
    @classmethod
    def validar_rol(cls, value: str | None) -> str | None:
        if value is not None and value not in ROLES_VALIDOS:
            raise ValueError("Rol no válido.")
        return value


class EstadoUpdate(BaseModel):
    activo: bool

