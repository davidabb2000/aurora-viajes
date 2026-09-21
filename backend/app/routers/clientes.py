"""Clientes en el mostrador: el personal los busca o los da de alta al crear una reserva."""
import logging

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select

from app.core.politica_contrasena import normalizar_correo
from app.core.seguridad import contrasena_provisional, hashear_contrasena
from app.dependencias import EmpleadoOAdmin, SesionDep
from app.errores import ConflictoDeNegocio
from app.models.dominio import Role, User
from app.schemas.usuarios import TIPOS_DOCUMENTO_VALIDOS, REGEX_DIRECCION, _validar_nombre_propio
from app.services.catalogos import escapar_like, resolver_tipo_documento_id
from app.services.serializadores import cliente_resumido_a_dict

logger = logging.getLogger("aurora-viajes")
router = APIRouter(tags=["clientes"])


class ClienteRapido(BaseModel):
    """Lo mínimo para reservar a nombre de alguien que llega al mostrador."""

    nombre: str = Field(..., min_length=2, max_length=40)
    apellido: str = Field(..., min_length=2, max_length=40)
    tipoDocumento: str = Field(default="CC", min_length=2, max_length=5)
    numeroDocumento: str = Field(..., min_length=6, max_length=12)
    telefono: str = Field(..., min_length=7, max_length=10)
    correo: str
    direccion: str = Field(default="No registrada", min_length=3, max_length=80)

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

    @field_validator("numeroDocumento", "telefono")
    @classmethod
    def validar_numerico(cls, value: str) -> str:
        if not value.isascii() or not value.isdigit():
            raise ValueError("Solo se permiten números.")
        return value

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, value: str) -> str:
        return normalizar_correo(value)

    @field_validator("direccion")
    @classmethod
    def validar_direccion(cls, value: str) -> str:
        value = value.strip()
        if not REGEX_DIRECCION.match(value):
            raise ValueError("La dirección contiene caracteres no permitidos.")
        return value


@router.get("/api/clientes")
async def buscar_clientes(
    personal: EmpleadoOAdmin,
    sesion: SesionDep,
    q: str = Query(default="", max_length=80),
    limite: int = Query(default=15, ge=1, le=50),
):
    """Busca clientes activos por nombre, correo o documento. El texto se trata como literal, no como patrón."""
    consulta = select(User).join(Role, Role.id == User.rol_id).where(Role.nombre == "cliente", User.activo.is_(True))
    texto = q.strip().lower()
    if texto:
        patron = f"%{escapar_like(texto)}%"
        consulta = consulta.where(or_(
            func.lower(User.nombre + " " + User.apellido).like(patron, escape="\\"),
            func.lower(User.correo).like(patron, escape="\\"),
            User.numero_documento.like(patron, escape="\\"),
        ))
    clientes = await sesion.scalars(consulta.order_by(User.nombre, User.apellido).limit(limite))
    return [cliente_resumido_a_dict(cliente) for cliente in clientes.unique()]


@router.post("/api/clientes", status_code=status.HTTP_201_CREATED)
async def crear_cliente(payload: ClienteRapido, personal: EmpleadoOAdmin, sesion: SesionDep):
    """Alta rápida en el mostrador.

    La cuenta se crea con una clave aleatoria que nadie conoce: si el cliente quiere entrar a la web,
    usa «¿Olvidaste tu contraseña?» y elige la suya con un enlace enviado a su correo.
    """
    existente = await sesion.scalar(
        select(User.id).where(or_(User.correo == payload.correo, User.numero_documento == payload.numeroDocumento))
    )
    if existente is not None:
        raise ConflictoDeNegocio("Ya existe un cliente con ese correo o documento.")
    rol = await sesion.scalar(select(Role).where(Role.nombre == "cliente"))
    cliente = User(
        nombre=payload.nombre,
        apellido=payload.apellido,
        tipo_documento_id=await resolver_tipo_documento_id(sesion, payload.tipoDocumento),
        numero_documento=payload.numeroDocumento,
        direccion=payload.direccion,
        telefono=payload.telefono,
        correo=payload.correo,
        contrasena_hash=hashear_contrasena(contrasena_provisional()),
        rol_id=rol.id,
        activo=True,
    )
    sesion.add(cliente)
    await sesion.commit()
    await sesion.refresh(cliente)
    logger.info("Cliente %s creado en el mostrador por %s.", cliente.id, personal.id)
    return cliente_resumido_a_dict(cliente)
