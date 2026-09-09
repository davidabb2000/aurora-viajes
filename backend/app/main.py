import logging
import re
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import urlencode

import jwt
import httpx
from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, field_validator
from pydantic import model_validator
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import selectinload

from app.core.base_datos import Base, FabricaDeSesiones, motor
from app.core.configuracion import configuracion
from app.core.seguridad import crear_token, hashear_contrasena, verificar_contrasena
from app.dependencias import Administrador, EmpleadoOAdmin, ReservaDeRuta, SesionDep, UsuarioActual, UsuarioDeRuta
from app.errores import ConflictoDeNegocio, ErrorDeDominio, NoAutenticado, PermisoDenegado, RecursoNoEncontrado
from app.middlewares import cabeceras_de_seguridad, registrar_peticion
from app.models.biblioteca import (
    Destino,
    EstadoPago,
    EstadoReserva,
    MensajeContacto,
    MetodoPago,
    Pais,
    Permiso,
    Producto,
    Reserva,
    Role,
    Servicio,
    TipoDocumento,
    User,
)
from app.services.recomendaciones import ProveedorNoDisponible, ServicioDeRecomendaciones


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("aurora-viajes")

TIPOS_DOCUMENTO_VALIDOS = {"CC", "TI", "CE", "PA"}
ROLES_VALIDOS = {"administrador", "empleado", "cliente"}
REGEX_CONTRASENA = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,20}$")
REGEX_DIRECCION = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ0-9#\-.,\s]+$")

PERMISOS_POR_ROL = {
    "administrador": ["usuarios:gestionar", "productos:gestionar", "servicios:gestionar", "reservas:gestionar", "mensajes:leer"],
    "empleado": ["reservas:gestionar"],
    "cliente": ["reservas:crear"],
}

TIPOS_DOCUMENTO_SEMILLA = [
    ("CC", "Cédula de ciudadanía"),
    ("TI", "Tarjeta de identidad"),
    ("CE", "Cédula de extranjería"),
    ("PA", "Pasaporte"),
]

PAISES_Y_DESTINOS_SEMILLA = [
    ("Francia", "París, Francia", "Recorre el Sena al atardecer y descubre por qué la Ciudad Luz sigue inspirando a viajeros de todo el mundo.", "paris", Decimal("6900000")),
    ("Japón", "Kioto, Japón", "Templos centenarios, jardines de piedra y la calma de los bosques de bambú te esperan en el antiguo Japón.", "kioto", Decimal("8400000")),
    ("Indonesia", "Bali, Indonesia", "Playas volcánicas, arrozales en terraza y una cultura espiritual que transforma cada visita en un ritual.", "bali", Decimal("7600000")),
    ("Colombia", "Cartagena, Colombia", "Murallas coloniales, calles de colores y el Caribe a un paso: la joya histórica de Colombia.", "cartagena", Decimal("1200000")),
    ("Grecia", "Santorini, Grecia", "Casas blancas suspendidas sobre el mar Egeo y atardeceres que se han vuelto leyenda.", "santorini", Decimal("9800000")),
    ("Perú", "Cusco, Perú", "Puerta de entrada a Machu Picchu y corazón del imperio inca, entre montañas y terrazas ancestrales.", "cusco", Decimal("2500000")),
    ("Marruecos", "Marrakech, Marruecos", "Zocos bulliciosos, palacios ocultos y el aroma a especias en cada esquina de la medina.", "marrakech", Decimal("8900000")),
    ("Islandia", "Reikiavik, Islandia", "Auroras boreales, fuentes termales y paisajes volcánicos al borde del Atlántico Norte.", "reikiavik", Decimal("10800000")),
    ("Estados Unidos", "Nueva York, EE. UU.", "Rascacielos icónicos, parques urbanos y una energía que nunca duerme.", "nueva-york", Decimal("7200000")),
    ("Egipto", "El Cairo, Egipto", "Las pirámides de Giza y el Nilo milenario te acercan a una de las civilizaciones más fascinantes de la historia.", "cairo", Decimal("9300000")),
]

ESTADOS_RESERVA_SEMILLA = [
    ("pendiente", "Pendiente"),
    ("confirmada", "Confirmada"),
    ("cancelada", "Cancelada"),
]

ESTADOS_PAGO_SEMILLA = [
    ("pendiente", "Pendiente"),
    ("pagado", "Pagado"),
    ("fallido", "Fallido"),
]

METODOS_PAGO_SEMILLA = [
    ("stripe", "Stripe"),
    ("transferencia", "Transferencia"),
]

FACTOR_STRIPE_MONEDA = Decimal("100")
INSTRUCCION_DESTINOS = (
    "Eres el asistente de una agencia de viajes. A partir de los intereses "
    "del usuario y del catálogo disponible, elige exactamente 3 destinos. "
    "Responde ÚNICAMENTE con un arreglo JSON de objetos con las claves "
    "destino_id, nombre, pais y motivo. El motivo debe tener máximo 25 palabras. "
    "No recomiendes destinos que no estén en el catálogo."
)


class UserCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=40)
    apellido: str = Field(..., min_length=2, max_length=40)
    tipoDocumento: str = Field(..., min_length=2, max_length=5)
    numeroDocumento: str = Field(..., min_length=6, max_length=12)
    direccion: str = Field(..., min_length=5, max_length=80)
    telefono: str = Field(..., min_length=7, max_length=10)
    correo: str
    contrasena: str = Field(..., min_length=8, max_length=20)

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


class UserLogin(BaseModel):
    correo: str
    contrasena: str = Field(..., min_length=1)

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, value: str) -> str:
        return UserCreate.validar_correo(value)


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


class ProductoCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    descripcion: str | None = None
    precio: float = Field(default=0, ge=0)
    activo: bool = True


class ServicioCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    descripcion: str | None = None
    precio: float = Field(default=0, ge=0)
    activo: bool = True


class ReservaCreate(BaseModel):
    destino: str | None = Field(default=None, min_length=1, max_length=120)
    destinoId: int | None = Field(default=None, ge=1)
    fechaSalida: date
    fechaRegreso: date
    pasajeros: int = Field(..., ge=1, le=9)
    telefonoContacto: str = Field(..., min_length=7, max_length=10)
    notas: str | None = Field(None, max_length=300)

    @model_validator(mode="after")
    def validar_destino(self):
        if self.destino is None and self.destinoId is None:
            raise ValueError("Selecciona un destino válido.")
        return self

    @field_validator("telefonoContacto")
    @classmethod
    def validar_telefono(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("Solo se permiten números.")
        return value


class ReservaUpdate(ReservaCreate):
    destino: str | None = None
    destinoId: int | None = None

    @model_validator(mode="after")
    def validar_destino_update(self):
        if self.destino is None and self.destinoId is None:
            raise ValueError("Selecciona un destino válido.")
        return self


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


class SolicitudDeRecomendacionDestino(BaseModel):
    intereses: str = Field(..., min_length=10, max_length=500)


class DestinoRecomendado(BaseModel):
    destino_id: int
    nombre: str
    pais: str
    motivo: str
    descripcion: str | None = None
    precio_estimado: float | None = None
    imagen_slug: str | None = None


class RespuestaDeRecomendacionDestino(BaseModel):
    recomendaciones: list[DestinoRecomendado]
    generada_por: str
    aviso: str | None = None


def _usuario_a_dict(usuario: User) -> dict:
    return {
        "id": usuario.id,
        "nombre": usuario.nombre,
        "apellido": usuario.apellido,
        "tipoDocumento": usuario.tipo_documento_catalogo.codigo if usuario.tipo_documento_catalogo else "CC",
        "numeroDocumento": usuario.numero_documento,
        "direccion": usuario.direccion,
        "telefono": usuario.telefono,
        "correo": usuario.correo,
        "rol": usuario.role.nombre if usuario.role else "cliente",
        "activo": usuario.activo,
    }


def _usuario_sesion_a_dict(usuario: User) -> dict:
    return {
        "id": usuario.id,
        "nombre": usuario.nombre,
        "apellido": usuario.apellido,
        "correo": usuario.correo,
        "rol": usuario.role.nombre if usuario.role else "cliente",
        "activo": usuario.activo,
    }


def _producto_a_dict(producto: Producto) -> dict:
    return {
        "id": producto.id,
        "nombre": producto.nombre,
        "descripcion": producto.descripcion,
        "precio": float(producto.precio or 0),
        "activo": producto.activo,
    }


def _servicio_a_dict(servicio: Servicio) -> dict:
    return {
        "id": servicio.id,
        "nombre": servicio.nombre,
        "descripcion": servicio.descripcion,
        "precio": float(servicio.precio or 0),
        "activo": servicio.activo,
    }


def _reserva_a_dict(reserva: Reserva) -> dict:
    return {
        "id": reserva.id,
        "cliente": f"{reserva.usuario.nombre} {reserva.usuario.apellido}" if reserva.usuario else "",
        "destinoId": reserva.destino_id,
        "destino": reserva.destino_rel.nombre if reserva.destino_rel else "",
        "pais": reserva.destino_rel.pais.nombre if reserva.destino_rel and reserva.destino_rel.pais else "",
        "fechaSalida": reserva.fecha_salida.isoformat(),
        "fechaRegreso": reserva.fecha_regreso.isoformat(),
        "pasajeros": reserva.pasajeros,
        "telefonoContacto": reserva.telefono_contacto,
        "notas": reserva.notas,
        "estado": reserva.estado_rel.codigo if reserva.estado_rel else "pendiente",
        "estadoPago": reserva.estado_pago_rel.codigo if reserva.estado_pago_rel else "pendiente",
        "metodoPago": reserva.metodo_pago_rel.codigo if reserva.metodo_pago_rel else None,
        "montoTotal": float(reserva.monto_total or 0),
        "stripeSessionId": reserva.stripe_session_id,
    }


def _clausula_no_duplicados(sesion: SesionDep) -> str:
    return "INSERT IGNORE" if sesion.bind and sesion.bind.dialect.name == "mysql" else "INSERT OR IGNORE"


async def _asegurar_base_inicial() -> None:
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    async with FabricaDeSesiones() as sesion:
        clausula = _clausula_no_duplicados(sesion)

        tipos_documento_cache: dict[str, TipoDocumento] = {}
        for codigo, nombre in TIPOS_DOCUMENTO_SEMILLA:
            tipo_documento = await sesion.scalar(select(TipoDocumento).where(TipoDocumento.codigo == codigo))
            if tipo_documento is None:
                tipo_documento = TipoDocumento(codigo=codigo, nombre=nombre)
                sesion.add(tipo_documento)
                await sesion.flush()
            tipos_documento_cache[codigo] = tipo_documento

        paises_cache: dict[str, Pais] = {}
        for pais_nombre, *_resto in PAISES_Y_DESTINOS_SEMILLA:
            pais = await sesion.scalar(select(Pais).where(Pais.nombre == pais_nombre))
            if pais is None:
                pais = Pais(nombre=pais_nombre)
                sesion.add(pais)
                await sesion.flush()
            paises_cache[pais_nombre] = pais

        destinos_cache: dict[str, Destino] = {}
        for pais_nombre, nombre, descripcion, slug, precio_base in PAISES_Y_DESTINOS_SEMILLA:
            destino = await sesion.scalar(select(Destino).where(Destino.nombre == nombre))
            if destino is None:
                destino = Destino(
                    pais_id=paises_cache[pais_nombre].id,
                    nombre=nombre,
                    descripcion=descripcion,
                    precio_base=precio_base,
                    imagen_slug=slug,
                    activo=True,
                )
                sesion.add(destino)
                await sesion.flush()
            else:
                destino.pais_id = paises_cache[pais_nombre].id
                destino.descripcion = descripcion
                destino.precio_base = precio_base
                destino.imagen_slug = slug
                destino.activo = True
            destinos_cache[nombre] = destino

        estados_reserva_cache: dict[str, EstadoReserva] = {}
        for codigo, nombre in ESTADOS_RESERVA_SEMILLA:
            estado = await sesion.scalar(select(EstadoReserva).where(EstadoReserva.codigo == codigo))
            if estado is None:
                estado = EstadoReserva(codigo=codigo, nombre=nombre)
                sesion.add(estado)
                await sesion.flush()
            estados_reserva_cache[codigo] = estado

        estados_pago_cache: dict[str, EstadoPago] = {}
        for codigo, nombre in ESTADOS_PAGO_SEMILLA:
            estado = await sesion.scalar(select(EstadoPago).where(EstadoPago.codigo == codigo))
            if estado is None:
                estado = EstadoPago(codigo=codigo, nombre=nombre)
                sesion.add(estado)
                await sesion.flush()
            estados_pago_cache[codigo] = estado

        metodos_pago_cache: dict[str, MetodoPago] = {}
        for codigo, nombre in METODOS_PAGO_SEMILLA:
            metodo = await sesion.scalar(select(MetodoPago).where(MetodoPago.codigo == codigo))
            if metodo is None:
                metodo = MetodoPago(codigo=codigo, nombre=nombre)
                sesion.add(metodo)
                await sesion.flush()
            metodos_pago_cache[codigo] = metodo

        await _migrar_esquema_legacy(sesion)

        roles_cache: dict[str, Role] = {}
        for rol_nombre in PERMISOS_POR_ROL:
            rol = await sesion.scalar(select(Role).where(Role.nombre == rol_nombre))
            if rol is None:
                rol = Role(nombre=rol_nombre)
                sesion.add(rol)
                await sesion.flush()
            roles_cache[rol_nombre] = rol

        permisos_cache: dict[str, Permiso] = {}
        for permisos in PERMISOS_POR_ROL.values():
            for permiso_nombre in permisos:
                permiso = await sesion.scalar(select(Permiso).where(Permiso.nombre == permiso_nombre))
                if permiso is None:
                    permiso = Permiso(nombre=permiso_nombre)
                    sesion.add(permiso)
                    await sesion.flush()
                permisos_cache[permiso_nombre] = permiso

        for rol_nombre, permisos in PERMISOS_POR_ROL.items():
            rol = roles_cache[rol_nombre]
            for permiso_nombre in permisos:
                permiso = permisos_cache[permiso_nombre]
                await sesion.execute(
                    text(
                        f"{clausula} INTO rol_permisos (rol_id, permiso_id) VALUES (:rol_id, :permiso_id)"
                    ),
                    {"rol_id": rol.id, "permiso_id": permiso.id},
                )

        admin_role = roles_cache.get("administrador")
        if admin_role is not None:
            admin_email = configuracion.admin_email.lower()
            admin_user = await sesion.scalar(select(User).where(User.correo == admin_email))
            if admin_user is None:
                sesion.add(
                    User(
                        nombre="Administrador",
                        apellido="Aurora",
                        tipo_documento_id=tipos_documento_cache["CC"].id,
                        numero_documento="1000000000",
                        direccion="Oficina principal Aurora Viajes",
                        telefono="3000000000",
                        correo=configuracion.admin_email.lower(),
                        contrasena_hash=hashear_contrasena(configuracion.admin_password),
                        rol_id=admin_role.id,
                        activo=True,
                    )
                )
            else:
                admin_user.nombre = admin_user.nombre or "Administrador"
                admin_user.apellido = admin_user.apellido or "Aurora"
                admin_user.tipo_documento_id = tipos_documento_cache["CC"].id
                admin_user.rol_id = admin_role.id
                admin_user.activo = True
                try:
                    if not verificar_contrasena(configuracion.admin_password, admin_user.contrasena_hash):
                        admin_user.contrasena_hash = hashear_contrasena(configuracion.admin_password)
                except Exception:
                    admin_user.contrasena_hash = hashear_contrasena(configuracion.admin_password)

        await sesion.commit()


async def _resolver_tipo_documento_id(sesion: SesionDep, codigo: str) -> int:
    tipo_documento = await sesion.scalar(select(TipoDocumento).where(TipoDocumento.codigo == codigo))
    if tipo_documento is None:
        raise ErrorDeDominio("Selecciona un tipo de documento válido.")
    return tipo_documento.id


async def _resolver_estado_reserva_id(sesion: SesionDep, codigo: str) -> int:
    estado = await sesion.scalar(select(EstadoReserva).where(EstadoReserva.codigo == codigo))
    if estado is None:
        raise ErrorDeDominio("Estado de reserva no válido.")
    return estado.id


async def _resolver_estado_pago_id(sesion: SesionDep, codigo: str) -> int:
    estado = await sesion.scalar(select(EstadoPago).where(EstadoPago.codigo == codigo))
    if estado is None:
        raise ErrorDeDominio("Estado de pago no válido.")
    return estado.id


async def _resolver_metodo_pago_id(sesion: SesionDep, codigo: str) -> int:
    metodo = await sesion.scalar(select(MetodoPago).where(MetodoPago.codigo == codigo))
    if metodo is None:
        raise ErrorDeDominio("Método de pago no válido.")
    return metodo.id


async def _resolver_destino(sesion: SesionDep, destino: str | None = None, destino_id: int | None = None) -> Destino:
    if destino_id is not None:
        destino_obj = await sesion.get(Destino, destino_id, options=[selectinload(Destino.pais)])
        if destino_obj is not None:
            return destino_obj
    if destino:
        destino_obj = await sesion.scalar(
            select(Destino)
            .where(func.lower(Destino.nombre) == destino.strip().lower())
            .options(selectinload(Destino.pais))
        )
        if destino_obj is not None:
            return destino_obj
    raise ErrorDeDominio("Selecciona un destino válido.")


def _stripe_configurado() -> bool:
    return bool(configuracion.stripe_secret_key and configuracion.stripe_secret_key.strip())


def _url_frontend(ruta: str) -> str:
    return f"{configuracion.frontend_url.rstrip('/')}/{ruta.lstrip('/')}"


def _calcular_monto_reserva(destino: Destino, fecha_salida: date, fecha_regreso: date, pasajeros: int) -> Decimal:
    dias = (fecha_regreso - fecha_salida).days
    if dias < 1:
        dias = 1
    return Decimal(destino.precio_base or 0) * Decimal(str(pasajeros)) * Decimal(str(dias))


def _palabras_clave(texto: str) -> set[str]:
    return {palabra for palabra in re.findall(r"[\wáéíóúñ]+", texto.lower()) if len(palabra) >= 3}


def _puntaje_destino(intereses: str, destino: dict) -> int:
    palabras = _palabras_clave(intereses)
    texto_destino = " ".join(
        str(destino.get(campo, "")).lower()
        for campo in ("nombre", "pais", "descripcion")
    )

    puntaje = 0
    for palabra in palabras:
        if palabra in texto_destino:
            puntaje += 3

    coincidencias = {
        "playa": {"playa", "mar", "sol", "arena", "caribe", "isla", "snorkel", "descanso"},
        "cultural": {"cultura", "cultural", "historia", "museo", "patrimonio", "colonial"},
        "aventura": {"aventura", "montaña", "senderismo", "naturaleza", "ecoturismo"},
        "urbano": {"urbano", "ciudad", "noche", "modernas", "eventos", "gastronomía"},
        "romantico": {"romantico", "romántico", "pareja", "escapada", "tranquilo"},
    }
    for grupo in coincidencias.values():
        if palabras.intersection(grupo) and any(palabra in texto_destino for palabra in grupo):
            puntaje += 5

    return puntaje


async def _catalogo_destinos_recomendacion(sesion: SesionDep) -> list[dict]:
    destinos = await sesion.scalars(
        select(Destino)
        .options(selectinload(Destino.pais))
        .where(Destino.activo.is_(True))
        .where(Destino.precio_base > 0)
        .order_by(Destino.nombre.asc())
    )
    return [
        {
            "destino_id": destino.id,
            "nombre": destino.nombre,
            "pais": destino.pais.nombre if destino.pais else "",
            "descripcion": destino.descripcion,
            "precio_estimado": float(destino.precio_base or 0),
            "imagen_slug": destino.imagen_slug,
        }
        for destino in destinos
    ]


def _respaldo_destinos_local(intereses: str, catalogo: list[dict]) -> list[dict]:
    destinos_ordenados = sorted(
        catalogo,
        key=lambda destino: (
            -_puntaje_destino(intereses, destino),
            destino.get("precio_estimado", 0) or 0,
            destino.get("nombre", ""),
            destino.get("destino_id", 0),
        ),
    )
    resultados: list[dict] = []
    for destino in destinos_ordenados[:3]:
        resultados.append(
            {
                "destino_id": destino["destino_id"],
                "nombre": destino["nombre"],
                "pais": destino["pais"],
                "motivo": f"Coincide con tus intereses y encaja con un viaje a {destino['pais']}.",
                "descripcion": destino.get("descripcion"),
                "precio_estimado": destino.get("precio_estimado"),
                "imagen_slug": destino.get("imagen_slug"),
            }
        )
    return resultados


def _normalizar_recomendaciones_destinos(crudas: list[dict]) -> list[DestinoRecomendado]:
    return [DestinoRecomendado(**item) for item in crudas]


async def _stripe_crear_checkout(reserva: Reserva) -> dict:
    if not _stripe_configurado():
        raise ErrorDeDominio("Stripe no está configurado. Define STRIPE_SECRET_KEY para habilitar pagos reales.")

    monto = int((Decimal(reserva.monto_total or 0) * FACTOR_STRIPE_MONEDA).to_integral_value())
    if monto <= 0:
        raise ErrorDeDominio("La reserva no tiene un monto válido para cobrar.")

    data = {
        "mode": "payment",
        "success_url": _url_frontend(f"reservas/pago-exitoso?reserva_id={reserva.id}&session_id={{CHECKOUT_SESSION_ID}}"),
        "cancel_url": _url_frontend(f"reservas/pago/{reserva.id}"),
        "customer_email": reserva.usuario.correo if reserva.usuario else None,
        "metadata[reserva_id]": str(reserva.id),
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "cop",
        "line_items[0][price_data][unit_amount]": str(monto),
        "line_items[0][price_data][product_data][name]": f"Reserva a {reserva.destino_rel.nombre if reserva.destino_rel else reserva.destino_id}",
    }
    payload = {clave: valor for clave, valor in data.items() if valor is not None}

    async with httpx.AsyncClient(timeout=30.0) as cliente:
        respuesta = await cliente.post(
            "https://api.stripe.com/v1/checkout/sessions",
            data=payload,
            auth=(configuracion.stripe_secret_key, ""),
            headers={"Stripe-Version": "2024-06-20"},
        )

    if respuesta.status_code >= 400:
        logger.error("Stripe checkout falló: %s", respuesta.text)
        raise ErrorDeDominio("No se pudo crear la sesión de pago con Stripe.")

    datos = respuesta.json()
    url = datos.get("url")
    session_id = datos.get("id")
    if not url or not session_id:
        raise ErrorDeDominio("Stripe no devolvió una sesión válida.")
    return {"checkoutUrl": url, "sessionId": session_id}


async def _stripe_verificar_pago(session_id: str) -> dict:
    if not _stripe_configurado():
        raise ErrorDeDominio("Stripe no está configurado. Define STRIPE_SECRET_KEY para habilitar pagos reales.")

    async with httpx.AsyncClient(timeout=30.0) as cliente:
        respuesta = await cliente.get(
            f"https://api.stripe.com/v1/checkout/sessions/{session_id}",
            auth=(configuracion.stripe_secret_key, ""),
            headers={"Stripe-Version": "2024-06-20"},
        )
    if respuesta.status_code >= 400:
        logger.error("Stripe confirmación falló: %s", respuesta.text)
        raise ErrorDeDominio("No se pudo validar el pago con Stripe.")
    return respuesta.json()


async def _columna_existe(sesion: SesionDep, tabla: str, columna: str) -> bool:
    if sesion.bind and sesion.bind.dialect.name == "mysql":
        consulta = text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :tabla AND column_name = :columna"
        )
        cantidad = await sesion.scalar(consulta, {"tabla": tabla, "columna": columna})
        return bool(cantidad)
    return False


async def _migrar_esquema_legacy(sesion: SesionDep) -> None:
    if not sesion.bind or sesion.bind.dialect.name != "mysql":
        return

    if await _columna_existe(sesion, "usuarios", "tipo_documento") and not await _columna_existe(sesion, "usuarios", "tipo_documento_id"):
        await sesion.execute(text("ALTER TABLE usuarios ADD COLUMN tipo_documento_id INT UNSIGNED NULL AFTER apellido"))
        tipos_legacy = await sesion.execute(
            text("SELECT DISTINCT tipo_documento FROM usuarios WHERE tipo_documento IS NOT NULL AND tipo_documento <> ''")
        )
        for fila in tipos_legacy:
            codigo = str(fila[0]).strip().upper()
            if codigo:
                await sesion.execute(
                    text("INSERT IGNORE INTO tipos_documento (codigo, nombre) VALUES (:codigo, :nombre)"),
                    {"codigo": codigo, "nombre": codigo},
                )
        await sesion.execute(
            text(
                "UPDATE usuarios u "
                "JOIN tipos_documento td ON td.codigo = u.tipo_documento "
                "SET u.tipo_documento_id = td.id"
            )
        )
        await sesion.execute(
            text(
                "UPDATE usuarios u "
                "JOIN tipos_documento td ON td.codigo = 'CC' "
                "SET u.tipo_documento_id = td.id "
                "WHERE u.tipo_documento_id IS NULL"
            )
        )
        await sesion.execute(text("ALTER TABLE usuarios MODIFY tipo_documento_id INT UNSIGNED NOT NULL"))
        await sesion.execute(text("ALTER TABLE usuarios DROP COLUMN tipo_documento"))

    if await _columna_existe(sesion, "reservas", "destino") and not await _columna_existe(sesion, "reservas", "destino_id"):
        await sesion.execute(text("ALTER TABLE reservas ADD COLUMN destino_id INT UNSIGNED NULL AFTER usuario_id"))
        await sesion.execute(text("ALTER TABLE reservas ADD COLUMN estado_id INT UNSIGNED NULL AFTER notas"))
        await sesion.execute(text("ALTER TABLE reservas ADD COLUMN estado_pago_id INT UNSIGNED NULL AFTER estado_id"))
        await sesion.execute(text("ALTER TABLE reservas ADD COLUMN metodo_pago_id INT UNSIGNED NULL AFTER estado_pago_id"))

        destinos_legacy = await sesion.execute(
            text("SELECT DISTINCT destino FROM reservas WHERE destino IS NOT NULL AND destino <> ''")
        )
        for fila in destinos_legacy:
            destino_nombre = str(fila[0]).strip()
            if not destino_nombre:
                continue
            destino = await sesion.scalar(select(Destino).where(Destino.nombre == destino_nombre))
            if destino is None:
                pais_nombre = destino_nombre.split(",")[-1].strip() if "," in destino_nombre else "Colombia"
                pais = await sesion.scalar(select(Pais).where(Pais.nombre == pais_nombre))
                if pais is None:
                    pais = Pais(nombre=pais_nombre)
                    sesion.add(pais)
                    await sesion.flush()
                destino = Destino(
                    pais_id=pais.id,
                    nombre=destino_nombre,
                    descripcion=destino_nombre,
                    precio_base=Decimal("0"),
                    imagen_slug=None,
                    activo=True,
                )
                sesion.add(destino)
                await sesion.flush()

        for codigo, nombre in ESTADOS_RESERVA_SEMILLA:
            estado = await sesion.scalar(select(EstadoReserva).where(EstadoReserva.codigo == codigo))
            if estado is None:
                estado = EstadoReserva(codigo=codigo, nombre=nombre)
                sesion.add(estado)
                await sesion.flush()
        for codigo, nombre in ESTADOS_PAGO_SEMILLA:
            estado = await sesion.scalar(select(EstadoPago).where(EstadoPago.codigo == codigo))
            if estado is None:
                estado = EstadoPago(codigo=codigo, nombre=nombre)
                sesion.add(estado)
                await sesion.flush()
        for codigo, nombre in METODOS_PAGO_SEMILLA:
            metodo = await sesion.scalar(select(MetodoPago).where(MetodoPago.codigo == codigo))
            if metodo is None:
                metodo = MetodoPago(codigo=codigo, nombre=nombre)
                sesion.add(metodo)
                await sesion.flush()

        await sesion.execute(
            text(
                "UPDATE reservas r "
                "JOIN destinos d ON d.nombre = r.destino "
                "SET r.destino_id = d.id"
            )
        )
        await sesion.execute(
            text(
                "UPDATE reservas r "
                "JOIN estados_reserva er ON er.codigo = r.estado "
                "SET r.estado_id = er.id"
            )
        )
        await sesion.execute(
            text(
                "UPDATE reservas r "
                "JOIN estados_pago ep ON ep.codigo = r.estado_pago "
                "SET r.estado_pago_id = ep.id"
            )
        )
        await sesion.execute(
            text(
                "UPDATE reservas r "
                "LEFT JOIN metodos_pago mp ON mp.codigo = r.metodo_pago "
                "SET r.metodo_pago_id = mp.id"
            )
        )
        await sesion.execute(
            text(
                "UPDATE reservas r "
                "JOIN destinos d ON d.id = r.destino_id "
                "JOIN estados_reserva er ON er.codigo = 'pendiente' "
                "JOIN estados_pago ep ON ep.codigo = 'pendiente' "
                "SET r.destino_id = d.id, r.estado_id = COALESCE(r.estado_id, er.id), r.estado_pago_id = COALESCE(r.estado_pago_id, ep.id) "
                "WHERE r.destino_id IS NULL OR r.estado_id IS NULL OR r.estado_pago_id IS NULL"
            )
        )
        await sesion.execute(text("ALTER TABLE reservas MODIFY destino_id INT UNSIGNED NOT NULL"))
        await sesion.execute(text("ALTER TABLE reservas MODIFY estado_id INT UNSIGNED NOT NULL"))
        await sesion.execute(text("ALTER TABLE reservas MODIFY estado_pago_id INT UNSIGNED NOT NULL"))
        await sesion.execute(text("ALTER TABLE reservas DROP COLUMN destino"))
        await sesion.execute(text("ALTER TABLE reservas DROP COLUMN estado"))
        await sesion.execute(text("ALTER TABLE reservas DROP COLUMN estado_pago"))
        await sesion.execute(text("ALTER TABLE reservas DROP COLUMN metodo_pago"))

    await sesion.commit()


async def _actualizar_pago_stripe(sesion: SesionDep, reserva: Reserva, session_id: str | None = None) -> None:
    reserva.estado_pago_id = await _resolver_estado_pago_id(sesion, "pagado")
    reserva.estado_id = await _resolver_estado_reserva_id(sesion, "confirmada")
    reserva.metodo_pago_id = await _resolver_metodo_pago_id(sesion, "stripe")
    if session_id:
        reserva.stripe_session_id = session_id
    await sesion.commit()


def _opciones_carga_reserva():
    return [
        selectinload(Reserva.usuario).selectinload(User.role),
        selectinload(Reserva.usuario).selectinload(User.tipo_documento_catalogo),
        selectinload(Reserva.destino_rel).selectinload(Destino.pais),
        selectinload(Reserva.estado_rel),
        selectinload(Reserva.estado_pago_rel),
        selectinload(Reserva.metodo_pago_rel),
    ]


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    await _asegurar_base_inicial()
    yield
    await motor.dispose()


app = FastAPI(
    title=configuracion.nombre_app,
    description="API de gestión de reservas y viajes.",
    version="1.0.0",
    docs_url="/docs" if configuracion.depuracion else None,
    redoc_url="/redoc" if configuracion.depuracion else None,
    lifespan=ciclo_de_vida,
)
app.middleware("http")(cabeceras_de_seguridad)
app.middleware("http")(registrar_peticion)
app.add_middleware(
    CORSMiddleware,
    allow_origins=configuracion.origenes_permitidos,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Peticion-Id", "X-Tiempo-Respuesta-ms"],
)


def _respuesta_error(peticion: Request, estado: int, codigo: str, mensaje: str, detalles=None):
    return JSONResponse(status_code=estado, content={"codigo": codigo, "mensaje": mensaje, "ruta": peticion.url.path, "detalles": detalles})


@app.exception_handler(NoAutenticado)
def manejar_no_autenticado(peticion: Request, exc: NoAutenticado):
    respuesta = _respuesta_error(peticion, status.HTTP_401_UNAUTHORIZED, exc.codigo, exc.mensaje)
    respuesta.headers["WWW-Authenticate"] = "Bearer"
    return respuesta


@app.exception_handler(PermisoDenegado)
def manejar_permiso_denegado(peticion: Request, exc: PermisoDenegado):
    return _respuesta_error(peticion, status.HTTP_403_FORBIDDEN, exc.codigo, exc.mensaje)


@app.exception_handler(RecursoNoEncontrado)
def manejar_no_encontrado(peticion: Request, exc: RecursoNoEncontrado):
    return _respuesta_error(peticion, status.HTTP_404_NOT_FOUND, exc.codigo, exc.mensaje)


@app.exception_handler(ConflictoDeNegocio)
def manejar_conflicto(peticion: Request, exc: ConflictoDeNegocio):
    return _respuesta_error(peticion, status.HTTP_409_CONFLICT, exc.codigo, exc.mensaje)


@app.exception_handler(ErrorDeDominio)
def manejar_error_dominio(peticion: Request, exc: ErrorDeDominio):
    return _respuesta_error(peticion, status.HTTP_400_BAD_REQUEST, exc.codigo, exc.mensaje)


@app.exception_handler(RequestValidationError)
def manejar_validacion(peticion: Request, exc: RequestValidationError):
    detalles = [{"campo": ".".join(str(p) for p in error["loc"][1:]), "problema": error["msg"]} for error in exc.errors()]
    return _respuesta_error(peticion, status.HTTP_422_UNPROCESSABLE_ENTITY, "datos_invalidos", "Los datos enviados no cumplen el formato esperado.", detalles)


@app.exception_handler(Exception)
def manejar_error_inesperado(peticion: Request, exc: Exception):
    logger.exception("Error no controlado en %s", peticion.url.path)
    return _respuesta_error(peticion, status.HTTP_500_INTERNAL_SERVER_ERROR, "error_interno", "Ocurrio un error inesperado. Intente de nuevo mas tarde.")


@app.get("/")
def raiz():
    return {"servicio": configuracion.nombre_app, "version": app.version, "entorno": configuracion.entorno, "documentacion": "/docs"}


@app.get("/salud")
@app.get("/api/health")
def salud():
    return {"estado": "ok"}


@app.get("/api/catalogos/destinos")
async def catalogo_destinos(sesion: SesionDep):
    destinos = await sesion.scalars(
        select(Destino)
        .options(selectinload(Destino.pais))
        .where(Destino.activo.is_(True))
        .where(Destino.precio_base > 0)
        .order_by(Destino.nombre.asc())
    )
    return [
        {
            "id": destino.id,
            "nombre": destino.nombre,
            "pais": destino.pais.nombre if destino.pais else "",
            "descripcion": destino.descripcion,
            "precioBase": float(destino.precio_base or 0),
            "imagenSlug": destino.imagen_slug,
        }
        for destino in destinos
    ]


@app.post("/api/destinos/recomendaciones", response_model=RespuestaDeRecomendacionDestino)
async def recomendar_destinos(payload: SolicitudDeRecomendacionDestino, sesion: SesionDep, _usuario: UsuarioActual):
    catalogo = await _catalogo_destinos_recomendacion(sesion)
    if not catalogo:
        raise ErrorDeDominio("No hay destinos disponibles para recomendar.")

    try:
        async with httpx.AsyncClient(timeout=configuracion.proveedor_ia_timeout) as cliente:
            servicio = ServicioDeRecomendaciones(cliente)
            crudas = await servicio.recomendar(payload.intereses, catalogo, instruccion=INSTRUCCION_DESTINOS)
        recomendaciones = _normalizar_recomendaciones_destinos(
            [item for item in crudas if item.get("destino_id") in {destino["destino_id"] for destino in catalogo}]
        )
        if not recomendaciones:
            raise ProveedorNoDisponible("El proveedor devolvió destinos que no están en el catálogo.")
        return RespuestaDeRecomendacionDestino(recomendaciones=recomendaciones[:3], generada_por="modelo_externo")
    except (ProveedorNoDisponible, ValidationError):
        return RespuestaDeRecomendacionDestino(
            recomendaciones=[DestinoRecomendado(**item) for item in _respaldo_destinos_local(payload.intereses, catalogo)],
            generada_por="catalogo_local",
            aviso="El asistente no está disponible en este momento; estas sugerencias vienen del catálogo.",
        )


@app.post("/api/auth/login")
async def login(payload: UserLogin, sesion: SesionDep):
    usuario = await sesion.scalar(select(User).where(User.correo == payload.correo.lower()).options(selectinload(User.role)))
    try:
        contrasena_valida = usuario is not None and usuario.activo and verificar_contrasena(payload.contrasena, usuario.contrasena_hash)
    except Exception as exc:
        logger.warning("No se pudo verificar la contraseña de %s: %s", payload.correo.lower(), exc)
        raise NoAutenticado("Credenciales inválidas o usuario inactivo.") from exc
    if not contrasena_valida:
        raise NoAutenticado("Credenciales inválidas o usuario inactivo.")
    return {"token": crear_token(usuario.id, usuario.role.nombre if usuario.role else "cliente"), "usuario": _usuario_sesion_a_dict(usuario)}


@app.post("/api/auth/recuperar")
async def recuperar_contrasena(payload: dict, sesion: SesionDep):
    correo = str(payload.get("correo", "")).strip().lower()
    if not correo:
        raise ErrorDeDominio("Ingresa un correo electrónico válido.")
    usuario = await sesion.scalar(select(User).where(User.correo == correo).options(selectinload(User.role)))
    if usuario is None:
        return {"mensaje": "Si el correo está registrado, recibirás instrucciones para recuperar tu contraseña."}
    return {"mensaje": "Se generó un enlace de recuperación válido para tu cuenta.", "token": crear_token(usuario.id, usuario.role.nombre if usuario.role else "cliente", purpose="recuperacion")}


@app.post("/api/auth/restablecer")
async def restablecer_contrasena(payload: dict, sesion: SesionDep):
    correo = str(payload.get("correo", "")).strip().lower()
    token = str(payload.get("token", "")).strip()
    nueva_contrasena = str(payload.get("nuevaContrasena", "")).strip()
    if not correo or not token or not nueva_contrasena:
        raise ErrorDeDominio("Correo, token y nueva contraseña son obligatorios.")
    if len(nueva_contrasena) < 8 or len(nueva_contrasena) > 20:
        raise ErrorDeDominio("La contraseña debe tener entre 8 y 20 caracteres.")
    try:
        decoded = jwt.decode(token, configuracion.secret_key, algorithms=[configuracion.algoritmo_jwt])
    except jwt.ExpiredSignatureError as exc:
        raise NoAutenticado("El token de recuperación no es válido o expiró.") from exc
    except jwt.InvalidTokenError as exc:
        raise NoAutenticado("El token de recuperación no es válido o expiró.") from exc
    if decoded.get("purpose") != "recuperacion":
        raise NoAutenticado("El token no corresponde a recuperación de contraseña.")
    usuario = await sesion.scalar(select(User).where(User.id == decoded.get("id"), User.correo == correo))
    if usuario is None:
        raise RecursoNoEncontrado("un usuario", correo)
    usuario.contrasena_hash = hashear_contrasena(nueva_contrasena)
    await sesion.commit()
    return {"mensaje": "Contraseña actualizada correctamente."}


@app.post("/api/usuarios/registro", status_code=status.HTTP_201_CREATED)
async def registrar_usuario(payload: UserCreate, sesion: SesionDep):
    existente = await sesion.scalar(select(User).where(or_(User.correo == payload.correo.lower(), User.numero_documento == payload.numeroDocumento)))
    if existente is not None:
        raise ConflictoDeNegocio("El correo o documento ya está registrado.")
    rol = await sesion.scalar(select(Role).where(Role.nombre == "cliente"))
    if rol is None:
        rol = Role(nombre="cliente")
        sesion.add(rol)
        await sesion.flush()
    tipo_documento_id = await _resolver_tipo_documento_id(sesion, payload.tipoDocumento)
    usuario = User(
        nombre=payload.nombre.strip(),
        apellido=payload.apellido.strip(),
        tipo_documento_id=tipo_documento_id,
        numero_documento=payload.numeroDocumento,
        direccion=payload.direccion.strip(),
        telefono=payload.telefono,
        correo=payload.correo.lower(),
        contrasena_hash=hashear_contrasena(payload.contrasena),
        rol_id=rol.id,
        activo=True,
    )
    sesion.add(usuario)
    await sesion.commit()
    return {"mensaje": "Cuenta creada correctamente."}


@app.get("/api/usuarios")
async def listar_usuarios(admin: Administrador, sesion: SesionDep):
    usuarios = await sesion.scalars(
        select(User).options(selectinload(User.role), selectinload(User.tipo_documento_catalogo)).order_by(User.id.desc())
    )
    return [_usuario_a_dict(usuario) for usuario in usuarios]


@app.post("/api/usuarios", status_code=status.HTTP_201_CREATED)
async def crear_usuario_admin(payload: UsuarioCreateAdmin, admin: Administrador, sesion: SesionDep):
    existente = await sesion.scalar(select(User).where(or_(User.correo == payload.correo.lower(), User.numero_documento == payload.numeroDocumento)))
    if existente is not None:
        raise ConflictoDeNegocio("El correo o documento ya está registrado.")
    rol = await sesion.scalar(select(Role).where(Role.nombre == payload.rol))
    if rol is None:
        raise ErrorDeDominio("Rol no válido.")
    tipo_documento_id = await _resolver_tipo_documento_id(sesion, payload.tipoDocumento)
    usuario = User(
        nombre=payload.nombre.strip(),
        apellido=payload.apellido.strip(),
        tipo_documento_id=tipo_documento_id,
        numero_documento=payload.numeroDocumento,
        direccion=payload.direccion.strip(),
        telefono=payload.telefono,
        correo=payload.correo.lower(),
        contrasena_hash=hashear_contrasena(payload.contrasena),
        rol_id=rol.id,
        activo=True,
    )
    sesion.add(usuario)
    await sesion.commit()
    return {"id": usuario.id, "mensaje": "Usuario creado correctamente."}


@app.get("/api/usuarios/{usuario_id}")
async def obtener_usuario(usuario: UsuarioDeRuta, admin: Administrador):
    return _usuario_a_dict(usuario)


@app.put("/api/usuarios/{usuario_id}")
async def actualizar_usuario(usuario: UsuarioDeRuta, payload: UserUpdate, admin: Administrador, sesion: SesionDep):
    if payload.correo is not None or payload.numeroDocumento is not None:
        correo = payload.correo.lower() if payload.correo is not None else usuario.correo
        documento = payload.numeroDocumento if payload.numeroDocumento is not None else usuario.numero_documento
        duplicado = await sesion.scalar(select(User).where(User.id != usuario.id, or_(User.correo == correo, User.numero_documento == documento)))
        if duplicado is not None:
            raise ConflictoDeNegocio("El correo o documento ya está registrado.")
    if payload.nombre is not None:
        usuario.nombre = payload.nombre.strip()
    if payload.apellido is not None:
        usuario.apellido = payload.apellido.strip()
    if payload.tipoDocumento is not None:
        usuario.tipo_documento_id = await _resolver_tipo_documento_id(sesion, payload.tipoDocumento)
    if payload.numeroDocumento is not None:
        usuario.numero_documento = payload.numeroDocumento
    if payload.direccion is not None:
        usuario.direccion = payload.direccion.strip()
    if payload.telefono is not None:
        usuario.telefono = payload.telefono
    if payload.correo is not None:
        usuario.correo = payload.correo.lower()
    if payload.rol is not None:
        rol = await sesion.scalar(select(Role).where(Role.nombre == payload.rol))
        if rol is None:
            raise ErrorDeDominio("Rol no válido.")
        usuario.rol_id = rol.id
    await sesion.commit()
    return {"mensaje": "Usuario actualizado."}


@app.patch("/api/usuarios/{usuario_id}/estado")
async def actualizar_estado_usuario(usuario: UsuarioDeRuta, payload: EstadoUpdate, admin: Administrador, sesion: SesionDep):
    usuario.activo = payload.activo
    await sesion.commit()
    return {"mensaje": "Estado actualizado."}


@app.delete("/api/usuarios/{usuario_id}")
async def eliminar_usuario(usuario: UsuarioDeRuta, admin: Administrador, sesion: SesionDep):
    await sesion.delete(usuario)
    await sesion.commit()
    return {"mensaje": "Usuario eliminado."}


@app.get("/api/productos")
async def listar_productos(sesion: SesionDep):
    productos = await sesion.scalars(select(Producto).order_by(Producto.id.desc()))
    return [_producto_a_dict(producto) for producto in productos]


@app.get("/api/productos/{producto_id}")
async def obtener_producto(producto_id: int, sesion: SesionDep):
    producto = await sesion.get(Producto, producto_id)
    if producto is None:
        raise RecursoNoEncontrado("un producto", producto_id)
    return _producto_a_dict(producto)


@app.post("/api/productos", status_code=status.HTTP_201_CREATED)
async def crear_producto(payload: ProductoCreate, admin: Administrador, sesion: SesionDep):
    producto = Producto(nombre=payload.nombre, descripcion=payload.descripcion, precio=payload.precio, activo=payload.activo)
    sesion.add(producto)
    await sesion.commit()
    await sesion.refresh(producto)
    return {"id": producto.id, "mensaje": "Producto creado."}


@app.put("/api/productos/{producto_id}")
async def actualizar_producto(producto_id: int, payload: ProductoCreate, admin: Administrador, sesion: SesionDep):
    producto = await sesion.get(Producto, producto_id)
    if producto is None:
        raise RecursoNoEncontrado("un producto", producto_id)
    producto.nombre = payload.nombre
    producto.descripcion = payload.descripcion
    producto.precio = payload.precio
    producto.activo = payload.activo
    await sesion.commit()
    return {"mensaje": "Producto actualizado."}


@app.delete("/api/productos/{producto_id}")
async def eliminar_producto(producto_id: int, admin: Administrador, sesion: SesionDep):
    producto = await sesion.get(Producto, producto_id)
    if producto is None:
        raise RecursoNoEncontrado("un producto", producto_id)
    await sesion.delete(producto)
    await sesion.commit()
    return {"mensaje": "Producto eliminado."}


@app.get("/api/servicios")
async def listar_servicios(sesion: SesionDep):
    servicios = await sesion.scalars(select(Servicio).order_by(Servicio.id.desc()))
    return [_servicio_a_dict(servicio) for servicio in servicios]


@app.get("/api/servicios/{servicio_id}")
async def obtener_servicio(servicio_id: int, sesion: SesionDep):
    servicio = await sesion.get(Servicio, servicio_id)
    if servicio is None:
        raise RecursoNoEncontrado("un servicio", servicio_id)
    return _servicio_a_dict(servicio)


@app.post("/api/servicios", status_code=status.HTTP_201_CREATED)
async def crear_servicio(payload: ServicioCreate, admin: Administrador, sesion: SesionDep):
    servicio = Servicio(nombre=payload.nombre, descripcion=payload.descripcion, precio=payload.precio, activo=payload.activo)
    sesion.add(servicio)
    await sesion.commit()
    await sesion.refresh(servicio)
    return {"id": servicio.id, "mensaje": "Servicio creado."}


@app.put("/api/servicios/{servicio_id}")
async def actualizar_servicio(servicio_id: int, payload: ServicioCreate, admin: Administrador, sesion: SesionDep):
    servicio = await sesion.get(Servicio, servicio_id)
    if servicio is None:
        raise RecursoNoEncontrado("un servicio", servicio_id)
    servicio.nombre = payload.nombre
    servicio.descripcion = payload.descripcion
    servicio.precio = payload.precio
    servicio.activo = payload.activo
    await sesion.commit()
    return {"mensaje": "Servicio actualizado."}


@app.delete("/api/servicios/{servicio_id}")
async def eliminar_servicio(servicio_id: int, admin: Administrador, sesion: SesionDep):
    servicio = await sesion.get(Servicio, servicio_id)
    if servicio is None:
        raise RecursoNoEncontrado("un servicio", servicio_id)
    await sesion.delete(servicio)
    await sesion.commit()
    return {"mensaje": "Servicio eliminado."}


@app.post("/api/reservas", status_code=status.HTTP_201_CREATED)
async def crear_reserva(payload: ReservaCreate, usuario: UsuarioActual, sesion: SesionDep):
    if payload.fechaRegreso < payload.fechaSalida:
        raise ErrorDeDominio("La fecha de regreso debe ser posterior a la fecha de salida.")
    destino = await _resolver_destino(sesion, payload.destino, payload.destinoId)
    reserva = Reserva(
        usuario_id=usuario.id,
        destino_id=destino.id,
        fecha_salida=payload.fechaSalida,
        fecha_regreso=payload.fechaRegreso,
        pasajeros=payload.pasajeros,
        telefono_contacto=payload.telefonoContacto,
        notas=payload.notas,
        estado_id=await _resolver_estado_reserva_id(sesion, "pendiente"),
        estado_pago_id=await _resolver_estado_pago_id(sesion, "pendiente"),
        monto_total=_calcular_monto_reserva(destino, payload.fechaSalida, payload.fechaRegreso, payload.pasajeros),
    )
    sesion.add(reserva)
    await sesion.commit()
    return {"id": reserva.id, "mensaje": "Solicitud registrada."}


@app.get("/api/reservas")
async def listar_reservas(personal: EmpleadoOAdmin, sesion: SesionDep):
    reservas = await sesion.scalars(select(Reserva).options(*_opciones_carga_reserva()).order_by(Reserva.id.desc()))
    return [_reserva_a_dict(reserva) for reserva in reservas]


@app.get("/api/reservas/mias")
async def mis_reservas(usuario: UsuarioActual, sesion: SesionDep):
    reservas = await sesion.scalars(
        select(Reserva).where(Reserva.usuario_id == usuario.id).options(*_opciones_carga_reserva()).order_by(Reserva.id.desc())
    )
    return [_reserva_a_dict(reserva) for reserva in reservas]


@app.get("/api/reservas/{reserva_id}")
async def obtener_reserva(reserva: ReservaDeRuta, usuario: UsuarioActual):
    if usuario.role.nombre not in {"administrador", "empleado"} and reserva.usuario_id != usuario.id:
        raise PermisoDenegado("No tiene permiso para realizar esta operación.")
    return _reserva_a_dict(reserva)


@app.put("/api/reservas/{reserva_id}")
async def actualizar_reserva(reserva: ReservaDeRuta, payload: ReservaUpdate, personal: EmpleadoOAdmin, sesion: SesionDep):
    if payload.fechaRegreso < payload.fechaSalida:
        raise ErrorDeDominio("La fecha de regreso debe ser posterior a la fecha de salida.")
    destino = await _resolver_destino(sesion, payload.destino, payload.destinoId)
    reserva.destino_id = destino.id
    reserva.fecha_salida = payload.fechaSalida
    reserva.fecha_regreso = payload.fechaRegreso
    reserva.pasajeros = payload.pasajeros
    reserva.telefono_contacto = payload.telefonoContacto
    reserva.notas = payload.notas
    reserva.monto_total = _calcular_monto_reserva(destino, payload.fechaSalida, payload.fechaRegreso, payload.pasajeros)
    await sesion.commit()
    return {"mensaje": "Solicitud actualizada correctamente."}


@app.post("/api/reservas/{reserva_id}/pago/checkout")
async def crear_checkout(reserva: ReservaDeRuta, usuario: UsuarioActual, sesion: SesionDep):
    if usuario.role.nombre not in {"administrador", "empleado"} and reserva.usuario_id != usuario.id:
        raise PermisoDenegado("No tiene permiso para realizar esta operación.")
    if not reserva.monto_total or reserva.monto_total == 0:
        reserva.monto_total = _calcular_monto_reserva(reserva.destino_rel, reserva.fecha_salida, reserva.fecha_regreso, reserva.pasajeros)
        await sesion.commit()
    session = await _stripe_crear_checkout(reserva)
    reserva.stripe_session_id = session["sessionId"]
    await sesion.commit()
    return {
        "checkoutUrl": session["checkoutUrl"],
        "sessionId": session["sessionId"],
    }


@app.post("/api/reservas/{reserva_id}/pago/confirmar")
async def confirmar_pago(reserva: ReservaDeRuta, usuario: UsuarioActual, payload: dict | None, sesion: SesionDep):
    if usuario.role.nombre not in {"administrador", "empleado"} and reserva.usuario_id != usuario.id:
        raise PermisoDenegado("No tiene permiso para realizar esta operación.")
    session_id = ""
    if payload:
        session_id = str(payload.get("sessionId", "")).strip()
    if not session_id:
        session_id = reserva.stripe_session_id or ""
    if not session_id:
        raise ErrorDeDominio("No se encontró la sesión de pago de Stripe.")
    sesion_stripe = await _stripe_verificar_pago(session_id)
    if sesion_stripe.get("payment_status") != "paid":
        raise ErrorDeDominio("El pago aún no está confirmado en Stripe.")
    metadata = sesion_stripe.get("metadata") or {}
    if str(metadata.get("reserva_id", "")) not in {"", str(reserva.id)}:
        raise ErrorDeDominio("La sesión de Stripe no coincide con la reserva.")
    await _actualizar_pago_stripe(sesion, reserva, session_id)
    return {"mensaje": "Pago confirmado correctamente."}


@app.patch("/api/reservas/{reserva_id}/estado")
async def actualizar_estado_reserva(reserva: ReservaDeRuta, payload: dict, personal: EmpleadoOAdmin, sesion: SesionDep):
    nuevo_estado = str(payload.get("estado", "")).strip()
    if not nuevo_estado:
        raise ErrorDeDominio("El estado es obligatorio.")
    reserva.estado_id = await _resolver_estado_reserva_id(sesion, nuevo_estado)
    await sesion.commit()
    return {"mensaje": "Estado actualizado."}


@app.delete("/api/reservas/{reserva_id}")
async def eliminar_reserva(reserva: ReservaDeRuta, usuario: UsuarioActual, sesion: SesionDep):
    if usuario.role.nombre not in {"administrador", "empleado"} and reserva.usuario_id != usuario.id:
        raise PermisoDenegado("No tiene permiso para realizar esta operación.")
    await sesion.delete(reserva)
    await sesion.commit()
    return {"mensaje": "Reserva eliminada."}


@app.post("/api/contacto")
async def crear_contacto(payload: ContactoCreate, sesion: SesionDep):
    mensaje = MensajeContacto(nombre=payload.nombre, correo=payload.correo.lower(), mensaje=payload.mensaje)
    sesion.add(mensaje)
    await sesion.commit()
    return {"mensaje": "Mensaje enviado correctamente."}


@app.get("/api/contacto")
async def listar_contactos(admin: Administrador, sesion: SesionDep):
    mensajes = await sesion.scalars(select(MensajeContacto).order_by(MensajeContacto.id.desc()))
    return [{"id": mensaje.id, "nombre": mensaje.nombre, "correo": mensaje.correo, "mensaje": mensaje.mensaje, "creadoEn": mensaje.creado_en.isoformat()} for mensaje in mensajes]
