import re
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

TIPOS_DOCUMENTO_VALIDOS = {"CC", "TI", "CE", "PA"}
ROLES_VALIDOS = {"administrador", "empleado", "cliente"}
# Mínimo 8 y máximo 20 caracteres, con mayúscula, minúscula, número y símbolo (igual que en el frontend).
REGEX_CONTRASENA = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,20}$")
REGEX_DIRECCION = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ0-9#\-.,\s]+$")


class UserCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=40)
    apellido: str = Field(..., min_length=2, max_length=40)
    tipoDocumento: str = Field(..., min_length=2, max_length=5)
    numeroDocumento: str = Field(..., min_length=6, max_length=12)
    direccion: str = Field(..., min_length=5, max_length=80)
    telefono: str = Field(..., min_length=7, max_length=10)
    correo: EmailStr
    contrasena: str = Field(..., min_length=8, max_length=20)

    @field_validator("nombre", "apellido")
    @classmethod
    def validate_names(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Este campo es obligatorio.")
        return value.strip()

    @field_validator("tipoDocumento")
    @classmethod
    def validate_tipo_documento(cls, value: str) -> str:
        if value not in TIPOS_DOCUMENTO_VALIDOS:
            raise ValueError("Selecciona un tipo de documento válido (CC, TI, CE o PA).")
        return value

    @field_validator("numeroDocumento", "telefono")
    @classmethod
    def validate_numeric(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("Solo se permiten números.")
        return value

    @field_validator("direccion")
    @classmethod
    def validate_direccion(cls, value: str) -> str:
        if not REGEX_DIRECCION.match(value.strip()):
            raise ValueError("La dirección contiene caracteres no permitidos.")
        return value.strip()

    @field_validator("contrasena")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not REGEX_CONTRASENA.match(value):
            raise ValueError("Debe incluir mayúscula, minúscula, número y un carácter especial (8 a 20 caracteres).")
        return value


class UsuarioCreateAdmin(UserCreate):
    rol: str = Field(default="cliente")

    @field_validator("rol")
    @classmethod
    def validate_rol(cls, value: str) -> str:
        if value not in ROLES_VALIDOS:
            raise ValueError("Rol no válido.")
        return value


class UserLogin(BaseModel):
    correo: EmailStr
    contrasena: str = Field(..., min_length=1)


class UserOut(BaseModel):
    id: int
    nombre: str
    apellido: str
    correo: str
    rol: str
    activo: bool


class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=2, max_length=40)
    apellido: Optional[str] = Field(None, min_length=2, max_length=40)
    tipoDocumento: Optional[str] = None
    numeroDocumento: Optional[str] = Field(None, min_length=6, max_length=12)
    direccion: Optional[str] = Field(None, min_length=5, max_length=80)
    telefono: Optional[str] = Field(None, min_length=7, max_length=10)
    correo: Optional[EmailStr] = None
    rol: Optional[str] = None

    @field_validator("tipoDocumento")
    @classmethod
    def validate_tipo_documento(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in TIPOS_DOCUMENTO_VALIDOS:
            raise ValueError("Selecciona un tipo de documento válido (CC, TI, CE o PA).")
        return value

    @field_validator("numeroDocumento", "telefono")
    @classmethod
    def validate_numeric(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.isdigit():
            raise ValueError("Solo se permiten números.")
        return value

    @field_validator("direccion")
    @classmethod
    def validate_direccion(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not REGEX_DIRECCION.match(value.strip()):
            raise ValueError("La dirección contiene caracteres no permitidos.")
        return value.strip() if value is not None else value

    @field_validator("rol")
    @classmethod
    def validate_rol(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in ROLES_VALIDOS:
            raise ValueError("Rol no válido.")
        return value


class EstadoUpdate(BaseModel):
    activo: bool


class ProductoCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    descripcion: Optional[str] = None
    precio: float = Field(default=0, ge=0)
    activo: bool = True


class ServicioCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    descripcion: Optional[str] = None
    precio: float = Field(default=0, ge=0)
    activo: bool = True


class ReservaCreate(BaseModel):
    destino: str = Field(..., min_length=1, max_length=120)
    fechaSalida: str
    fechaRegreso: str
    pasajeros: int = Field(..., ge=1, le=9)
    telefonoContacto: str = Field(..., min_length=7, max_length=10)
    notas: Optional[str] = Field(None, max_length=300)

    @field_validator("telefonoContacto")
    @classmethod
    def validate_telefono(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("Solo se permiten números.")
        return value


class ReservaUpdate(ReservaCreate):
    estado: Optional[str] = None


class ContactoCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=80)
    correo: EmailStr
    mensaje: str = Field(..., min_length=1, max_length=500)
