import logging
import re
import secrets
import unicodedata
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
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
from app.services.correos import enviar_correo_recuperacion, enviar_correo_bienvenida, enviar_correo_reserva
from app.dependencias import Administrador, EmpleadoOAdmin, ReservaDeRuta, SesionDep, UsuarioActual, UsuarioDeRuta
from app.errores import ConflictoDeNegocio, ErrorDeDominio, NoAutenticado, PermisoDenegado, RecursoNoEncontrado
from app.middlewares import cabeceras_de_seguridad, registrar_peticion
from app.models.biblioteca import (
    Destino,
    DetalleFactura,
    DetalleVenta,
    EstadoPago,
    EstadoReserva,
    Excursion,
    Hotel,
    MensajeContacto,
    MetodoPago,
    Factura,
    Pais,
    Permiso,
    Producto,
    Paquete,
    Reserva,
    Role,
    Servicio,
    TipoDocumento,
    User,
    Venta,
    Vuelo,
)
from app.routers.comercial import router as router_comercial
from app.routers.recomendaciones import router as router_recomendaciones


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

VUELOS_SEMILLA = [
    ("AV101", "Aurora Airlines", "Airbus A320", "Bogotá", "París", datetime(2026, 10, 5, 8, 30), datetime(2026, 10, 5, 23, 15), 180, "A12", "1"),
    ("AV202", "Aurora Airlines", "Boeing 787", "Bogotá", "Tokio", datetime(2026, 10, 12, 10, 0), datetime(2026, 10, 13, 8, 30), 260, "B04", "2"),
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


ESTADOS_VUELO_VALIDOS = {"programado", "abordando", "en_vuelo", "aterrizado", "cancelado"}
AEROLINEAS_DISPONIBLES = {"Aurora Airlines", "Avianca", "LATAM", "Copa Airlines", "Iberia"}
AVIONES_DISPONIBLES = {"Airbus A320", "Airbus A330", "Boeing 737", "Boeing 787", "Embraer E195"}
CAPACIDAD_POR_AVION = {
    "Airbus A320": 180,
    "Airbus A330": 300,
    "Boeing 737": 189,
    "Boeing 787": 330,
    "Embraer E195": 132,
}
ORIGENES_DISPONIBLES = {"Bogotá", "Medellín", "Cali", "Cartagena", "Barranquilla", "Lima", "Madrid"}


class VueloCreate(BaseModel):
    numeroVuelo: str | None = Field(default=None, min_length=2, max_length=20)
    aerolinea: str = Field(..., min_length=2, max_length=80)
    avion: str = Field(..., min_length=2, max_length=80)
    origen: str = Field(..., min_length=2, max_length=120)
    destino: str = Field(..., min_length=2, max_length=120)
    fechaSalida: datetime
    fechaLlegada: datetime
    capacidadMaxima: int | None = Field(default=None, ge=1, le=1000)
    puerta: str | None = Field(default=None, max_length=10)
    terminal: str | None = Field(default=None, max_length=20)
    estado: str = "programado"
    activo: bool = True

    @field_validator("aerolinea", "avion", "origen", "destino")
    @classmethod
    def validar_texto(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Este campo es obligatorio.")
        return value

    @field_validator("aerolinea")
    @classmethod
    def validar_aerolinea(cls, value: str) -> str:
        if value not in AEROLINEAS_DISPONIBLES:
            raise ValueError("Selecciona una aerolínea válida.")
        return value

    @field_validator("avion")
    @classmethod
    def validar_avion(cls, value: str) -> str:
        if value not in AVIONES_DISPONIBLES:
            raise ValueError("Selecciona un avión válido.")
        return value

    @field_validator("origen")
    @classmethod
    def validar_origen(cls, value: str) -> str:
        if value not in ORIGENES_DISPONIBLES:
            raise ValueError("Selecciona un origen válido del catálogo.")
        return value

    @field_validator("estado")
    @classmethod
    def validar_estado(cls, value: str) -> str:
        if value not in ESTADOS_VUELO_VALIDOS:
            raise ValueError("Estado de vuelo no válido.")
        return value

    @model_validator(mode="after")
    def validar_horario(self):
        if self.fechaLlegada <= self.fechaSalida:
            raise ValueError("La llegada debe ser posterior a la salida.")
        self.capacidadMaxima = CAPACIDAD_POR_AVION[self.avion]
        return self


class HotelCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=120)
    ciudad: str = Field(..., min_length=2, max_length=120)
    pais: str = Field(..., min_length=2, max_length=120)
    estrellas: int = Field(..., ge=1, le=5)
    precioNoche: float = Field(default=0, ge=0)
    descripcion: str | None = Field(default=None, max_length=1000)
    activo: bool = True


class ExcursionCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=120)
    ciudad: str = Field(..., min_length=2, max_length=120)
    pais: str = Field(..., min_length=2, max_length=120)
    duracionHoras: int = Field(..., ge=1, le=48)
    precio: float = Field(default=0, ge=0)
    descripcion: str | None = Field(default=None, max_length=1000)
    activo: bool = True


class PaqueteCreate(BaseModel):
    nombre: str = Field(..., min_length=3, max_length=140)
    destinoId: int = Field(..., ge=1)
    vueloId: int | None = Field(default=None, ge=1)
    vuelo: VueloCreate | None = None
    hotelId: int = Field(..., ge=1)
    excursionIds: list[int] = Field(default_factory=list, max_length=20)
    fechaSalida: date
    fechaRegreso: date
    precioBase: float = Field(default=0, ge=0)
    activo: bool = True

    @model_validator(mode="after")
    def validar_fechas(self):
        if self.fechaRegreso < self.fechaSalida:
            raise ValueError("La fecha de regreso debe ser posterior a la salida.")
        if self.vueloId is None and self.vuelo is None:
            raise ValueError("Debes configurar el vuelo dentro de la reserva.")
        if self.vueloId is not None and self.vuelo is not None:
            raise ValueError("Usa un vuelo existente o configura uno nuevo, no ambos.")
        return self


class ReservaCreate(BaseModel):
    origen: str = Field(..., min_length=2, max_length=120)
    destino: str | None = Field(default=None, min_length=1, max_length=120)
    destinoId: int | None = Field(default=None, ge=1)
    vueloId: int | None = Field(default=None, ge=1)
    paqueteId: int | None = Field(default=None, ge=1)
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

    @field_validator("origen")
    @classmethod
    def validar_origen(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Selecciona un lugar de salida.")
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


def _vuelo_a_dict(vuelo: Vuelo) -> dict:
    return {
        "id": vuelo.id,
        "numeroVuelo": vuelo.numero_vuelo,
        "aerolinea": vuelo.aerolinea,
        "avion": vuelo.avion,
        "origen": vuelo.origen,
        "destino": vuelo.destino,
        "fechaSalida": vuelo.fecha_salida.isoformat(),
        "fechaLlegada": vuelo.fecha_llegada.isoformat(),
        "capacidadMaxima": vuelo.capacidad_maxima,
        "puerta": vuelo.puerta,
        "terminal": vuelo.terminal,
        "estado": vuelo.estado,
        "activo": vuelo.activo,
    }


def _hotel_a_dict(hotel: Hotel) -> dict:
    return {
        "id": hotel.id,
        "nombre": hotel.nombre,
        "ciudad": hotel.ciudad,
        "pais": hotel.pais,
        "estrellas": hotel.estrellas,
        "precioNoche": float(hotel.precio_noche or 0),
        "descripcion": hotel.descripcion,
        "activo": hotel.activo,
    }


def _excursion_a_dict(excursion: Excursion) -> dict:
    return {
        "id": excursion.id,
        "nombre": excursion.nombre,
        "ciudad": excursion.ciudad,
        "pais": excursion.pais,
        "duracionHoras": excursion.duracion_horas,
        "precio": float(excursion.precio or 0),
        "descripcion": excursion.descripcion,
        "activo": excursion.activo,
    }


def _paquete_a_dict(paquete: Paquete) -> dict:
    return {
        "id": paquete.id,
        "nombre": paquete.nombre,
        "destinoId": paquete.destino_id,
        "destino": paquete.destino_rel.nombre if paquete.destino_rel else "",
        "vueloId": paquete.vuelo_id,
        "vuelo": _vuelo_a_dict(paquete.vuelo_rel),
        "hotelId": paquete.hotel_id,
        "hotel": _hotel_a_dict(paquete.hotel_rel),
        "excursiones": [_excursion_a_dict(excursion) for excursion in paquete.excursiones],
        "fechaSalida": paquete.fecha_salida.isoformat(),
        "fechaRegreso": paquete.fecha_regreso.isoformat(),
        "precioBase": float(paquete.precio_base or 0),
        "activo": paquete.activo,
    }


def _reserva_a_dict(reserva: Reserva) -> dict:
    return {
        "id": reserva.id,
        "cliente": f"{reserva.usuario.nombre} {reserva.usuario.apellido}" if reserva.usuario else "",
        "destinoId": reserva.destino_id,
        "destino": reserva.destino_rel.nombre if reserva.destino_rel else "",
        "pais": reserva.destino_rel.pais.nombre if reserva.destino_rel and reserva.destino_rel.pais else "",
        "origen": reserva.vuelo_rel.origen if reserva.vuelo_rel else "",
        "vueloId": reserva.vuelo_id,
        "vuelo": _vuelo_a_dict(reserva.vuelo_rel) if reserva.vuelo_rel else None,
        "paqueteId": reserva.paquete_id,
        "paquete": _paquete_a_dict(reserva.paquete_rel) if reserva.paquete_rel else None,
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
        for tabla in ("hoteles", "excursiones"):
            if conexion.dialect.name == "mysql":
                columnas = await conexion.execute(text(f"SHOW COLUMNS FROM {tabla} LIKE 'pais'"))
                existe_pais = columnas.first() is not None
            else:
                columnas = await conexion.execute(text(f"PRAGMA table_info({tabla})"))
                existe_pais = any(columna[1] == "pais" for columna in columnas.fetchall())
            if not existe_pais:
                posicion = " AFTER ciudad" if conexion.dialect.name == "mysql" else ""
                await conexion.execute(text(f"ALTER TABLE {tabla} ADD COLUMN pais VARCHAR(120) NOT NULL DEFAULT ''{posicion}"))
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

        for numero, aerolinea, avion, origen, destino, salida, llegada, capacidad, puerta, terminal in VUELOS_SEMILLA:
            vuelo = await sesion.scalar(select(Vuelo).where(Vuelo.numero_vuelo == numero))
            if vuelo is None:
                sesion.add(
                    Vuelo(
                        numero_vuelo=numero,
                        aerolinea=aerolinea,
                        avion=avion,
                        origen=origen,
                        destino=destino,
                        fecha_salida=salida,
                        fecha_llegada=llegada,
                        capacidad_maxima=capacidad,
                        puerta=puerta,
                        terminal=terminal,
                        estado="programado",
                        activo=True,
                    )
                )

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


def _normalizar_texto(value: str) -> str:
    texto = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.lower().split())


def _puerta_terminal_por_ruta(origen: str, destino: str) -> tuple[str, str]:
    codigo_origen = _normalizar_texto(origen)[:3].upper()
    codigo_destino = _normalizar_texto(destino)[:3].upper()
    numero_puerta = (sum(ord(caracter) for caracter in codigo_origen + codigo_destino) % 20) + 1
    terminal = "A" if codigo_destino < "M" else "B"
    return f"{terminal}{numero_puerta:02d}", terminal


async def _generar_numero_vuelo(sesion: SesionDep) -> str:
    while True:
        numero = f"AV-{secrets.randbelow(1_000_000):06d}"
        if await sesion.scalar(select(Vuelo.id).where(Vuelo.numero_vuelo == numero)) is None:
            return numero


async def _resolver_vuelo_reserva(
    sesion: SesionDep,
    payload: ReservaCreate,
    destino: Destino,
    reserva_id: int | None = None,
) -> Vuelo:
    vuelos = list(
        await sesion.scalars(
            select(Vuelo)
            .where(Vuelo.activo.is_(True), Vuelo.estado.in_({"programado", "abordando"}))
            .order_by(Vuelo.fecha_salida.asc())
        )
    )
    destino_normalizado = _normalizar_texto(destino.nombre)
    candidatos = [
        vuelo
        for vuelo in vuelos
        if vuelo.fecha_salida.date() == payload.fechaSalida
        and _normalizar_texto(vuelo.origen) == _normalizar_texto(payload.origen)
        and (
            _normalizar_texto(vuelo.destino) == destino_normalizado
            or _normalizar_texto(vuelo.destino) in destino_normalizado
            or destino_normalizado in _normalizar_texto(vuelo.destino)
        )
    ]
    if payload.vueloId is not None:
        candidatos = [vuelo for vuelo in candidatos if vuelo.id == payload.vueloId]
    if not candidatos:
        raise ErrorDeDominio("No hay un vuelo activo para ese destino y fecha de salida.")

    estado_cancelado_id = await _resolver_estado_reserva_id(sesion, "cancelada")
    for vuelo in candidatos:
        condiciones = [
            Reserva.vuelo_id == vuelo.id,
            Reserva.estado_id != estado_cancelado_id,
        ]
        if reserva_id is not None:
            condiciones.append(Reserva.id != reserva_id)
        pasajeros_asignados = await sesion.scalar(
            select(func.coalesce(func.sum(Reserva.pasajeros), 0)).where(*condiciones)
        )
        if int(pasajeros_asignados or 0) + payload.pasajeros <= vuelo.capacidad_maxima:
            return vuelo

    raise ErrorDeDominio("El vuelo seleccionado no tiene capacidad para todos los pasajeros.")


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


async def _restriccion_existe(sesion: SesionDep, tabla: str, restriccion: str) -> bool:
    if sesion.bind and sesion.bind.dialect.name == "mysql":
        cantidad = await sesion.scalar(
            text(
                "SELECT COUNT(*) FROM information_schema.table_constraints "
                "WHERE table_schema = DATABASE() AND table_name = :tabla "
                "AND constraint_name = :restriccion"
            ),
            {"tabla": tabla, "restriccion": restriccion},
        )
        return bool(cantidad)
    return False


async def _migrar_esquema_legacy(sesion: SesionDep) -> None:
    if not sesion.bind or sesion.bind.dialect.name != "mysql":
        return

    if not await _columna_existe(sesion, "reservas", "paquete_id"):
        await sesion.execute(text("ALTER TABLE reservas ADD COLUMN paquete_id INT NULL AFTER vuelo_id"))
        await sesion.execute(
            text(
                "ALTER TABLE reservas ADD CONSTRAINT fk_reserva_paquete "
                "FOREIGN KEY (paquete_id) REFERENCES paquetes(id) ON DELETE RESTRICT"
            )
        )
    else:
        await sesion.execute(text("ALTER TABLE reservas MODIFY COLUMN paquete_id INT NULL"))
        if not await _restriccion_existe(sesion, "reservas", "fk_reserva_paquete"):
            await sesion.execute(
                text(
                    "ALTER TABLE reservas ADD CONSTRAINT fk_reserva_paquete "
                    "FOREIGN KEY (paquete_id) REFERENCES paquetes(id) ON DELETE RESTRICT"
                )
            )

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

    if not await _columna_existe(sesion, "reservas", "vuelo_id"):
        await sesion.execute(text("ALTER TABLE reservas ADD COLUMN vuelo_id INT UNSIGNED NULL AFTER destino_id"))
        await sesion.execute(
            text(
                "ALTER TABLE reservas ADD CONSTRAINT fk_reserva_vuelo "
                "FOREIGN KEY (vuelo_id) REFERENCES vuelos(id) ON DELETE RESTRICT"
            )
        )

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
        selectinload(Reserva.vuelo_rel),
        selectinload(Reserva.paquete_rel).selectinload(Paquete.excursiones),
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

app.include_router(router_recomendaciones)
app.include_router(router_comercial)


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
    
    # Generar token de recuperación
    token_recuperacion = crear_token(usuario.id, usuario.role.nombre if usuario.role else "cliente", purpose="recuperacion", expiracion_minutos=60)
    
    # Enviar correo (async y no esperamos resultado)
    await enviar_correo_recuperacion(usuario.correo, usuario.nombre, token_recuperacion)
    
    return {"mensaje": "Si el correo está registrado, recibirás instrucciones para recuperar tu contraseña."}


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
    await enviar_correo_bienvenida(usuario.correo, f"{usuario.nombre} {usuario.apellido}")
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


@app.get("/api/vuelos")
async def listar_vuelos(usuario: UsuarioActual, sesion: SesionDep):
    vuelos = await sesion.scalars(select(Vuelo).order_by(Vuelo.fecha_salida.asc()))
    estado_cancelado_id = await _resolver_estado_reserva_id(sesion, "cancelada")
    ocupacion = await sesion.execute(
        select(Reserva.vuelo_id, func.coalesce(func.sum(Reserva.pasajeros), 0))
        .where(Reserva.estado_id != estado_cancelado_id, Reserva.vuelo_id.is_not(None))
        .group_by(Reserva.vuelo_id)
    )
    ocupados = {vuelo_id: int(total or 0) for vuelo_id, total in ocupacion.all()}
    resultado = []
    for vuelo in vuelos:
        datos = _vuelo_a_dict(vuelo)
        datos["pasajerosDisponibles"] = max(vuelo.capacidad_maxima - ocupados.get(vuelo.id, 0), 0)
        resultado.append(datos)
    return resultado


@app.get("/api/vuelos/{vuelo_id}")
async def obtener_vuelo(vuelo_id: int, usuario: UsuarioActual, sesion: SesionDep):
    vuelo = await sesion.get(Vuelo, vuelo_id)
    if vuelo is None:
        raise RecursoNoEncontrado("un vuelo", vuelo_id)
    return _vuelo_a_dict(vuelo)


@app.post("/api/vuelos", status_code=status.HTTP_201_CREATED)
async def crear_vuelo(payload: VueloCreate, admin: Administrador, sesion: SesionDep):
    numero_vuelo = await _generar_numero_vuelo(sesion)
    puerta, terminal = payload.puerta, payload.terminal
    if not puerta or not terminal:
        puerta, terminal = _puerta_terminal_por_ruta(payload.origen, payload.destino)
    vuelo = Vuelo(
        numero_vuelo=numero_vuelo,
        aerolinea=payload.aerolinea,
        avion=payload.avion,
        origen=payload.origen,
        destino=payload.destino,
        fecha_salida=payload.fechaSalida,
        fecha_llegada=payload.fechaLlegada,
        capacidad_maxima=payload.capacidadMaxima,
        puerta=puerta,
        terminal=terminal,
        estado=payload.estado,
        activo=payload.activo,
    )
    sesion.add(vuelo)
    await sesion.commit()
    await sesion.refresh(vuelo)
    return _vuelo_a_dict(vuelo)


@app.put("/api/vuelos/{vuelo_id}")
async def actualizar_vuelo(vuelo_id: int, payload: VueloCreate, admin: Administrador, sesion: SesionDep):
    vuelo = await sesion.get(Vuelo, vuelo_id)
    if vuelo is None:
        raise RecursoNoEncontrado("un vuelo", vuelo_id)
    duplicado = await sesion.scalar(
        select(Vuelo).where(Vuelo.numero_vuelo == payload.numeroVuelo, Vuelo.id != vuelo_id)
    )
    if duplicado is not None:
        raise ConflictoDeNegocio("Ya existe un vuelo con ese número.")
    vuelo.numero_vuelo = payload.numeroVuelo
    vuelo.aerolinea = payload.aerolinea
    vuelo.avion = payload.avion
    vuelo.origen = payload.origen
    vuelo.destino = payload.destino
    vuelo.fecha_salida = payload.fechaSalida
    vuelo.fecha_llegada = payload.fechaLlegada
    vuelo.capacidad_maxima = payload.capacidadMaxima
    vuelo.puerta = payload.puerta
    vuelo.terminal = payload.terminal
    vuelo.estado = payload.estado
    vuelo.activo = payload.activo
    await sesion.commit()
    await sesion.refresh(vuelo)
    return _vuelo_a_dict(vuelo)


@app.delete("/api/vuelos/{vuelo_id}")
async def eliminar_vuelo(vuelo_id: int, admin: Administrador, sesion: SesionDep):
    vuelo = await sesion.get(Vuelo, vuelo_id)
    if vuelo is None:
        raise RecursoNoEncontrado("un vuelo", vuelo_id)
    await sesion.delete(vuelo)
    await sesion.commit()
    return {"mensaje": "Vuelo eliminado."}


async def _validar_paquete(sesion: SesionDep, payload: PaqueteCreate):
    destino = await sesion.get(Destino, payload.destinoId)
    vuelo = await sesion.get(Vuelo, payload.vueloId)
    hotel = await sesion.get(Hotel, payload.hotelId)
    if destino is None:
        raise RecursoNoEncontrado("un destino", payload.destinoId)
    if vuelo is None:
        raise RecursoNoEncontrado("un vuelo", payload.vueloId)
    if hotel is None or not hotel.activo:
        raise ErrorDeDominio("El hotel seleccionado no existe o está inactivo.")
    ubicacion_destino = [_normalizar_texto(parte) for parte in destino.nombre.split(",")]
    if _normalizar_texto(hotel.ciudad) not in ubicacion_destino or _normalizar_texto(hotel.pais) not in ubicacion_destino:
        raise ErrorDeDominio("El hotel debe pertenecer a la ciudad y país del destino seleccionado.")
    if not vuelo.activo or vuelo.estado in {"cancelado", "aterrizado"}:
        raise ErrorDeDominio("El vuelo seleccionado no está disponible.")
    if vuelo.fecha_salida.date() != payload.fechaSalida:
        raise ErrorDeDominio("La fecha del paquete debe coincidir con la salida del vuelo.")
    if _normalizar_texto(vuelo.destino) not in _normalizar_texto(destino.nombre) and _normalizar_texto(destino.nombre) not in _normalizar_texto(vuelo.destino):
        raise ErrorDeDominio("El destino del paquete no coincide con el destino del vuelo.")
    excursiones = list(await sesion.scalars(select(Excursion).where(Excursion.id.in_(set(payload.excursionIds))))) if payload.excursionIds else []
    if len(excursiones) != len(set(payload.excursionIds)) or any(not excursion.activo for excursion in excursiones):
        raise ErrorDeDominio("Una o más excursiones no existen o están inactivas.")
    if any(_normalizar_texto(excursion.ciudad) not in ubicacion_destino or _normalizar_texto(excursion.pais) not in ubicacion_destino for excursion in excursiones):
        raise ErrorDeDominio("Las excursiones deben pertenecer a la ciudad y país del destino seleccionado.")
    return destino, vuelo, hotel, excursiones


@app.get("/api/hoteles")
async def listar_hoteles(usuario: UsuarioActual, sesion: SesionDep):
    hoteles = await sesion.scalars(select(Hotel).order_by(Hotel.nombre.asc()))
    return [_hotel_a_dict(hotel) for hotel in hoteles]


@app.post("/api/hoteles", status_code=status.HTTP_201_CREATED)
async def crear_hotel(payload: HotelCreate, admin: Administrador, sesion: SesionDep):
    hotel = Hotel(nombre=payload.nombre.strip(), ciudad=payload.ciudad.strip(), pais=payload.pais.strip(), estrellas=payload.estrellas, precio_noche=payload.precioNoche, descripcion=payload.descripcion, activo=payload.activo)
    sesion.add(hotel)
    await sesion.commit()
    await sesion.refresh(hotel)
    return _hotel_a_dict(hotel)


@app.put("/api/hoteles/{hotel_id}")
async def actualizar_hotel(hotel_id: int, payload: HotelCreate, admin: Administrador, sesion: SesionDep):
    hotel = await sesion.get(Hotel, hotel_id)
    if hotel is None:
        raise RecursoNoEncontrado("un hotel", hotel_id)
    hotel.nombre, hotel.ciudad, hotel.pais, hotel.estrellas = payload.nombre.strip(), payload.ciudad.strip(), payload.pais.strip(), payload.estrellas
    hotel.precio_noche, hotel.descripcion, hotel.activo = payload.precioNoche, payload.descripcion, payload.activo
    await sesion.commit()
    return _hotel_a_dict(hotel)


@app.delete("/api/hoteles/{hotel_id}")
async def eliminar_hotel(hotel_id: int, admin: Administrador, sesion: SesionDep):
    hotel = await sesion.get(Hotel, hotel_id)
    if hotel is None:
        raise RecursoNoEncontrado("un hotel", hotel_id)
    hotel.activo = False
    await sesion.commit()
    return {"mensaje": "Hotel desactivado."}


@app.get("/api/excursiones")
async def listar_excursiones(usuario: UsuarioActual, sesion: SesionDep):
    excursiones = await sesion.scalars(select(Excursion).order_by(Excursion.nombre.asc()))
    return [_excursion_a_dict(excursion) for excursion in excursiones]


@app.post("/api/excursiones", status_code=status.HTTP_201_CREATED)
async def crear_excursion(payload: ExcursionCreate, admin: Administrador, sesion: SesionDep):
    excursion = Excursion(nombre=payload.nombre.strip(), ciudad=payload.ciudad.strip(), pais=payload.pais.strip(), duracion_horas=payload.duracionHoras, precio=payload.precio, descripcion=payload.descripcion, activo=payload.activo)
    sesion.add(excursion)
    await sesion.commit()
    await sesion.refresh(excursion)
    return _excursion_a_dict(excursion)


@app.put("/api/excursiones/{excursion_id}")
async def actualizar_excursion(excursion_id: int, payload: ExcursionCreate, admin: Administrador, sesion: SesionDep):
    excursion = await sesion.get(Excursion, excursion_id)
    if excursion is None:
        raise RecursoNoEncontrado("una excursión", excursion_id)
    excursion.nombre, excursion.ciudad, excursion.pais, excursion.duracion_horas = payload.nombre.strip(), payload.ciudad.strip(), payload.pais.strip(), payload.duracionHoras
    excursion.precio, excursion.descripcion, excursion.activo = payload.precio, payload.descripcion, payload.activo
    await sesion.commit()
    return _excursion_a_dict(excursion)


@app.delete("/api/excursiones/{excursion_id}")
async def eliminar_excursion(excursion_id: int, admin: Administrador, sesion: SesionDep):
    excursion = await sesion.get(Excursion, excursion_id)
    if excursion is None:
        raise RecursoNoEncontrado("una excursión", excursion_id)
    excursion.activo = False
    await sesion.commit()
    return {"mensaje": "Excursión desactivada."}


@app.get("/api/paquetes")
async def listar_paquetes(usuario: UsuarioActual, sesion: SesionDep):
    paquetes = await sesion.scalars(select(Paquete).where(Paquete.activo.is_(True)).order_by(Paquete.fecha_salida.asc()))
    estado_cancelado_id = await _resolver_estado_reserva_id(sesion, "cancelada")
    ocupacion = await sesion.execute(
        select(Reserva.vuelo_id, func.coalesce(func.sum(Reserva.pasajeros), 0))
        .where(Reserva.estado_id != estado_cancelado_id, Reserva.vuelo_id.is_not(None))
        .group_by(Reserva.vuelo_id)
    )
    ocupados = {vuelo_id: int(total or 0) for vuelo_id, total in ocupacion.all()}
    resultado = []
    for paquete in paquetes:
        datos = _paquete_a_dict(paquete)
        datos["vuelo"]["pasajerosDisponibles"] = max(paquete.vuelo_rel.capacidad_maxima - ocupados.get(paquete.vuelo_id, 0), 0)
        resultado.append(datos)
    return resultado


@app.post("/api/paquetes", status_code=status.HTTP_201_CREATED)
async def crear_paquete(payload: PaqueteCreate, admin: Administrador, sesion: SesionDep):
    if payload.vuelo is not None:
        numero_vuelo = await _generar_numero_vuelo(sesion)
        puerta, terminal = payload.vuelo.puerta, payload.vuelo.terminal
        if not puerta or not terminal:
            puerta, terminal = _puerta_terminal_por_ruta(payload.vuelo.origen, payload.vuelo.destino)
        vuelo_nuevo = Vuelo(
            numero_vuelo=numero_vuelo,
            aerolinea=payload.vuelo.aerolinea,
            avion=payload.vuelo.avion,
            origen=payload.vuelo.origen,
            destino=payload.vuelo.destino,
            fecha_salida=payload.vuelo.fechaSalida,
            fecha_llegada=payload.vuelo.fechaLlegada,
            capacidad_maxima=payload.vuelo.capacidadMaxima,
            puerta=puerta,
            terminal=terminal,
            estado=payload.vuelo.estado,
            activo=payload.vuelo.activo,
        )
        sesion.add(vuelo_nuevo)
        await sesion.flush()
        payload.vueloId = vuelo_nuevo.id
    destino, vuelo, hotel, excursiones = await _validar_paquete(sesion, payload)
    paquete = Paquete(nombre=payload.nombre.strip(), destino_id=destino.id, vuelo_id=vuelo.id, hotel_id=hotel.id, fecha_salida=payload.fechaSalida, fecha_regreso=payload.fechaRegreso, precio_base=payload.precioBase, activo=payload.activo, excursiones=excursiones)
    sesion.add(paquete)
    await sesion.commit()
    await sesion.refresh(paquete)
    return _paquete_a_dict(paquete)


@app.put("/api/paquetes/{paquete_id}")
async def actualizar_paquete(paquete_id: int, payload: PaqueteCreate, admin: Administrador, sesion: SesionDep):
    paquete = await sesion.get(Paquete, paquete_id, options=[selectinload(Paquete.excursiones)])
    if paquete is None:
        raise RecursoNoEncontrado("un paquete", paquete_id)
    destino, vuelo, hotel, excursiones = await _validar_paquete(sesion, payload)
    paquete.nombre, paquete.destino_id, paquete.vuelo_id, paquete.hotel_id = payload.nombre.strip(), destino.id, vuelo.id, hotel.id
    paquete.fecha_salida, paquete.fecha_regreso, paquete.precio_base, paquete.activo = payload.fechaSalida, payload.fechaRegreso, payload.precioBase, payload.activo
    paquete.excursiones = excursiones
    await sesion.commit()
    await sesion.refresh(paquete)
    return _paquete_a_dict(paquete)


@app.delete("/api/paquetes/{paquete_id}")
async def eliminar_paquete(paquete_id: int, admin: Administrador, sesion: SesionDep):
    paquete = await sesion.get(Paquete, paquete_id)
    if paquete is None:
        raise RecursoNoEncontrado("un paquete", paquete_id)
    paquete.activo = False
    await sesion.commit()
    return {"mensaje": "Paquete desactivado."}


@app.post("/api/reservas", status_code=status.HTTP_201_CREATED)
async def crear_reserva(payload: ReservaCreate, usuario: UsuarioActual, sesion: SesionDep):
    if payload.fechaRegreso < payload.fechaSalida:
        raise ErrorDeDominio("La fecha de regreso debe ser posterior a la fecha de salida.")
    paquete = None
    if payload.paqueteId is not None:
        paquete = await sesion.get(Paquete, payload.paqueteId, options=[selectinload(Paquete.destino_rel), selectinload(Paquete.vuelo_rel)])
        if paquete is None or not paquete.activo:
            raise ErrorDeDominio("El paquete seleccionado no está disponible.")
        if payload.fechaSalida != paquete.fecha_salida or payload.origen.strip().lower() != paquete.vuelo_rel.origen.strip().lower():
            raise ErrorDeDominio("Los datos de la reserva no coinciden con el paquete seleccionado.")
        destino = paquete.destino_rel
        vuelo = await _resolver_vuelo_reserva(sesion, payload, destino)
        if vuelo.id != paquete.vuelo_id:
            raise ErrorDeDominio("El vuelo del paquete ya no está disponible.")
    else:
        destino = await _resolver_destino(sesion, payload.destino, payload.destinoId)
        vuelo = await _resolver_vuelo_reserva(sesion, payload, destino)
    reserva = Reserva(
        usuario_id=usuario.id,
        destino_id=destino.id,
        vuelo_id=vuelo.id,
        paquete_id=paquete.id if paquete else None,
        fecha_salida=payload.fechaSalida,
        fecha_regreso=payload.fechaRegreso,
        pasajeros=payload.pasajeros,
        telefono_contacto=payload.telefonoContacto,
        notas=payload.notas,
        estado_id=await _resolver_estado_reserva_id(sesion, "pendiente"),
        estado_pago_id=await _resolver_estado_pago_id(sesion, "pendiente"),
        monto_total=(paquete.precio_base * payload.pasajeros if paquete else _calcular_monto_reserva(destino, payload.fechaSalida, payload.fechaRegreso, payload.pasajeros)),
    )
    sesion.add(reserva)
    await sesion.commit()
    monto_reserva = Decimal(str(reserva.monto_total or 0))
    precio_pasajero = (monto_reserva / payload.pasajeros).quantize(Decimal("0.01"))
    venta = Venta(
        cliente_id=usuario.id,
        usuario_id=usuario.id,
        subtotal=monto_reserva,
        descuento=Decimal("0"),
        impuestos=Decimal("0"),
        total=monto_reserva,
        estado="pendiente",
        detalles=[DetalleVenta(
            nombre=f"Reserva de viaje - {destino.nombre}",
            cantidad=payload.pasajeros,
            precio_unitario=precio_pasajero,
            subtotal=monto_reserva,
        )],
    )
    sesion.add(venta)
    await sesion.flush()
    sesion.add(Factura(
        venta_id=venta.id,
        numero=f"AUR-{datetime.now(timezone.utc):%Y%m%d}-{venta.id:06d}",
        estado="emitida",
        detalles=[DetalleFactura(
            nombre=f"Reserva de viaje - {destino.nombre}",
            cantidad=payload.pasajeros,
            precio_unitario=precio_pasajero,
            subtotal=monto_reserva,
        )],
    ))
    await sesion.commit()
    reserva_dict = {
        "destino": destino.nombre,
        "fechaSalida": payload.fechaSalida.isoformat(),
        "fechaRegreso": payload.fechaRegreso.isoformat(),
        "pasajeros": payload.pasajeros,
        "montoTotal": float(reserva.monto_total or 0),
        "estado": "pendiente",
    }
    correo_enviado = await enviar_correo_reserva(
        usuario.correo,
        f"{usuario.nombre} {usuario.apellido}",
        reserva_dict,
    )
    if not correo_enviado:
        logger.warning("Reserva %s creada, pero no se pudo enviar el correo a %s.", reserva.id, usuario.correo)
    return {"id": reserva.id, "mensaje": "Solicitud registrada. Recibirás la confirmación en tu correo."}


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
    paquete = None
    if payload.paqueteId is not None:
        paquete = await sesion.get(Paquete, payload.paqueteId, options=[selectinload(Paquete.destino_rel)])
        if paquete is None or not paquete.activo:
            raise ErrorDeDominio("El paquete seleccionado no está disponible.")
        destino = paquete.destino_rel
        payload.fechaSalida = paquete.fecha_salida
        payload.fechaRegreso = paquete.fecha_regreso
        payload.origen = paquete.vuelo_rel.origen
        vuelo = await _resolver_vuelo_reserva(sesion, payload, destino, reserva.id)
        reserva.paquete_id = paquete.id
    else:
        destino = await _resolver_destino(sesion, payload.destino, payload.destinoId)
        vuelo = await _resolver_vuelo_reserva(sesion, payload, destino, reserva.id)
    reserva.destino_id = destino.id
    reserva.vuelo_id = vuelo.id
    reserva.fecha_salida = payload.fechaSalida
    reserva.fecha_regreso = payload.fechaRegreso
    reserva.pasajeros = payload.pasajeros
    reserva.telefono_contacto = payload.telefonoContacto
    reserva.notas = payload.notas
    reserva.monto_total = paquete.precio_base * payload.pasajeros if paquete else _calcular_monto_reserva(destino, payload.fechaSalida, payload.fechaRegreso, payload.pasajeros)
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