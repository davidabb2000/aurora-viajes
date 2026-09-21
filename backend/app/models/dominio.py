"""Modelo de datos de Aurora Viajes, normalizado hasta la tercera forma normal.

Decisiones que conviene conocer antes de tocar una tabla:

* Un lugar se escribe una sola vez. `paises` -> `ciudades`; los destinos, los
  hoteles, las excursiones y los vuelos apuntan a una ciudad en lugar de repetir
  un texto («París», «Francia»). Antes cada tabla guardaba su propio texto y un
  hotel de «EE. UU.» no coincidía con un destino de «Estados Unidos».
* Lo que depende de otra cosa vive en la tabla de esa cosa: la capacidad física
  depende del modelo de avión, no del vuelo (`modelos_avion`), y el nombre de
  la aerolínea vive en `aerolineas`.
* Una reserva puede llevar varias excursiones y cada una con su cantidad y el
  precio del día en que se compró (`reserva_excursiones`), de modo que un
  cambio de tarifa no altere lo ya facturado.
* Se guardan a propósito unas pocas cifras derivadas y siempre protegidas por
  una restricción CHECK: los importes del desglose de la reserva y su total
  (documentos ya emitidos no deben cambiar si mañana cambia una tarifa) y las
  fechas del viaje (definen las noches de hotel aunque la aerolínea reprograme
  la hora del vuelo).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import INTEGER as MySQLInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_datos import Base


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


rol_permisos = Table(
    "rol_permisos",
    Base.metadata,
    Column("rol_id", ForeignKey("roles.id"), primary_key=True),
    Column("permiso_id", ForeignKey("permisos.id"), primary_key=True),
)

paquete_excursiones = Table(
    "paquete_excursiones",
    Base.metadata,
    Column("paquete_id", Integer, ForeignKey("paquetes.id"), primary_key=True),
    Column("excursion_id", Integer, ForeignKey("excursiones.id"), primary_key=True),
)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="role")
    permisos: Mapped[list["Permiso"]] = relationship(secondary=rol_permisos, back_populates="roles")


class Permiso(Base):
    __tablename__ = "permisos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)

    roles: Mapped[list[Role]] = relationship(secondary=rol_permisos, back_populates="permisos")


class TipoDocumento(Base):
    __tablename__ = "tipos_documento"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(5), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(40), nullable=False)

    usuarios: Mapped[list["User"]] = relationship(back_populates="tipo_documento_catalogo")


class Pais(Base):
    __tablename__ = "paises"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)

    ciudades: Mapped[list["Ciudad"]] = relationship(back_populates="pais")


class Ciudad(Base):
    """Un lugar del mundo. Es la única tabla que guarda el nombre de una ciudad."""

    __tablename__ = "ciudades"
    __table_args__ = (UniqueConstraint("pais_id", "nombre", name="uq_ciudad_pais_nombre"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pais_id: Mapped[int] = mapped_column(ForeignKey("paises.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)

    pais: Mapped[Pais] = relationship(back_populates="ciudades", lazy="joined")

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre}, {self.pais.nombre}"


class Destino(Base):
    """Una ciudad que la agencia vende como destino, con su tarifa aérea por pasajero."""

    __tablename__ = "destinos"
    __table_args__ = (CheckConstraint("precio_base >= 0", name="ck_destino_precio"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ciudad_id: Mapped[int] = mapped_column(ForeignKey("ciudades.id"), unique=True, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    precio_base: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    imagen_slug: Mapped[str | None] = mapped_column(String(80), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    ciudad: Mapped[Ciudad] = relationship(lazy="joined")
    reservas: Mapped[list["Reserva"]] = relationship(back_populates="destino_rel")

    @property
    def nombre(self) -> str:
        """«Ciudad, País»: se deriva, no se guarda."""
        return self.ciudad.nombre_completo

    @property
    def pais(self) -> Pais:
        return self.ciudad.pais


class EstadoReserva(Base):
    __tablename__ = "estados_reserva"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(40), nullable=False)

    reservas: Mapped[list["Reserva"]] = relationship(back_populates="estado_rel")


class EstadoPago(Base):
    __tablename__ = "estados_pago"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(40), nullable=False)

    reservas: Mapped[list["Reserva"]] = relationship(back_populates="estado_pago_rel")


class MetodoPago(Base):
    __tablename__ = "metodos_pago"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(40), nullable=False)

    reservas: Mapped[list["Reserva"]] = relationship(back_populates="metodo_pago_rel")


class User(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(40), nullable=False)
    apellido: Mapped[str] = mapped_column(String(40), nullable=False)
    tipo_documento_id: Mapped[int] = mapped_column(ForeignKey("tipos_documento.id"), nullable=False)
    numero_documento: Mapped[str] = mapped_column(String(12), unique=True, index=True, nullable=False)
    direccion: Mapped[str] = mapped_column(String(80), nullable=False)
    telefono: Mapped[str] = mapped_column(String(10), nullable=False)
    correo: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    contrasena_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rol_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    # Se incrementa al cambiar la contraseña, el rol o pedir «cerrar todas las sesiones»:
    # los tokens emitidos con una versión anterior dejan de valer al instante.
    sesion_version: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    # Cuentas creadas con una clave provisional (o con la clave por defecto del administrador).
    debe_cambiar_contrasena: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"), nullable=False)
    acepto_datos_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora, nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora, onupdate=_ahora, nullable=False)

    role: Mapped[Role] = relationship(back_populates="users", lazy="joined")
    tipo_documento_catalogo: Mapped[TipoDocumento] = relationship(back_populates="usuarios", lazy="joined")


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    precio: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Servicio(Base):
    __tablename__ = "servicios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    precio: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Hotel(Base):
    __tablename__ = "hoteles"
    __table_args__ = (
        UniqueConstraint("ciudad_id", "nombre", name="uq_hotel_ciudad_nombre"),
        CheckConstraint("estrellas >= 1 AND estrellas <= 5", name="ck_hotel_estrellas"),
        CheckConstraint("precio_noche >= 0", name="ck_hotel_precio"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    ciudad_id: Mapped[int] = mapped_column(ForeignKey("ciudades.id"), nullable=False, index=True)
    estrellas: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_noche: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    ciudad: Mapped[Ciudad] = relationship(lazy="joined")

    @property
    def pais(self) -> str:
        return self.ciudad.pais.nombre


class Excursion(Base):
    __tablename__ = "excursiones"
    __table_args__ = (
        UniqueConstraint("ciudad_id", "nombre", name="uq_excursion_ciudad_nombre"),
        CheckConstraint("duracion_horas >= 1 AND duracion_horas <= 48", name="ck_excursion_duracion"),
        CheckConstraint("precio >= 0", name="ck_excursion_precio"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    ciudad_id: Mapped[int] = mapped_column(ForeignKey("ciudades.id"), nullable=False, index=True)
    duracion_horas: Mapped[int] = mapped_column(Integer, nullable=False)
    precio: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    ciudad: Mapped[Ciudad] = relationship(lazy="joined")

    @property
    def pais(self) -> str:
        return self.ciudad.pais.nombre


class Aerolinea(Base):
    __tablename__ = "aerolineas"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(4), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)


class ModeloAvion(Base):
    """La capacidad física es del modelo de avión, no del vuelo: por eso vive aquí."""

    __tablename__ = "modelos_avion"
    __table_args__ = (CheckConstraint("capacidad >= 1", name="ck_modelo_capacidad"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    capacidad: Mapped[int] = mapped_column(Integer, nullable=False)


class Vuelo(Base):
    """Una salida concreta: el mismo número de vuelo se repite en fechas distintas."""

    __tablename__ = "vuelos"
    __table_args__ = (
        UniqueConstraint("numero_vuelo", "fecha_salida", name="uq_vuelo_numero_fecha"),
        CheckConstraint("origen_id <> destino_id", name="ck_vuelo_ruta"),
        CheckConstraint("fecha_llegada > fecha_salida", name="ck_vuelo_horario"),
        CheckConstraint("capacidad_maxima >= 1", name="ck_vuelo_capacidad"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    numero_vuelo: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    aerolinea_id: Mapped[int] = mapped_column(ForeignKey("aerolineas.id"), nullable=False, index=True)
    modelo_avion_id: Mapped[int] = mapped_column(ForeignKey("modelos_avion.id"), nullable=False)
    origen_id: Mapped[int] = mapped_column(ForeignKey("ciudades.id"), nullable=False, index=True)
    destino_id: Mapped[int] = mapped_column(ForeignKey("ciudades.id"), nullable=False, index=True)
    fecha_salida: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    fecha_llegada: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Plazas que la agencia puede vender; nunca más que las del modelo de avión.
    capacidad_maxima: Mapped[int] = mapped_column(Integer, nullable=False)
    puerta: Mapped[str | None] = mapped_column(String(10), nullable=True)
    terminal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    estado: Mapped[str] = mapped_column(String(20), default="programado", nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    aerolinea_rel: Mapped[Aerolinea] = relationship(lazy="joined")
    modelo_avion_rel: Mapped[ModeloAvion] = relationship(lazy="joined")
    origen_rel: Mapped[Ciudad] = relationship(foreign_keys=[origen_id], lazy="joined")
    destino_rel: Mapped[Ciudad] = relationship(foreign_keys=[destino_id], lazy="joined")

    @property
    def aerolinea(self) -> str:
        return self.aerolinea_rel.nombre

    @property
    def avion(self) -> str:
        return self.modelo_avion_rel.nombre

    @property
    def origen(self) -> str:
        return self.origen_rel.nombre

    @property
    def destino(self) -> str:
        return self.destino_rel.nombre


class Paquete(Base):
    """Oferta cerrada con precio fijo por pasajero. Sus fechas salen de sus vuelos."""

    __tablename__ = "paquetes"
    __table_args__ = (
        CheckConstraint("noches >= 1", name="ck_paquete_noches"),
        CheckConstraint("precio_base >= 0", name="ck_paquete_precio"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(140), nullable=False)
    destino_id: Mapped[int] = mapped_column(ForeignKey("destinos.id"), nullable=False)
    vuelo_id: Mapped[int] = mapped_column(ForeignKey("vuelos.id"), nullable=False)
    vuelo_regreso_id: Mapped[int | None] = mapped_column(ForeignKey("vuelos.id"), nullable=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hoteles.id"), nullable=False)
    noches: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_base: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    destino_rel: Mapped[Destino] = relationship(lazy="joined")
    vuelo_rel: Mapped[Vuelo] = relationship(foreign_keys=[vuelo_id], lazy="joined")
    vuelo_regreso_rel: Mapped[Vuelo | None] = relationship(foreign_keys=[vuelo_regreso_id], lazy="joined")
    hotel_rel: Mapped[Hotel] = relationship(lazy="joined")
    excursiones: Mapped[list[Excursion]] = relationship(secondary=paquete_excursiones, lazy="selectin")

    @property
    def fecha_salida(self) -> date:
        return self.vuelo_rel.fecha_salida.date()

    @property
    def fecha_regreso(self) -> date:
        return self.fecha_salida + timedelta(days=self.noches)


class ReservaExcursion(Base):
    """Una excursión dentro de una reserva: cuántas personas van y a qué precio se vendió."""

    __tablename__ = "reserva_excursiones"
    __table_args__ = (
        CheckConstraint("cantidad >= 1", name="ck_reserva_excursion_cantidad"),
        CheckConstraint("precio_unitario >= 0", name="ck_reserva_excursion_precio"),
    )

    reserva_id: Mapped[int] = mapped_column(ForeignKey("reservas.id", ondelete="CASCADE"), primary_key=True)
    excursion_id: Mapped[int] = mapped_column(ForeignKey("excursiones.id"), primary_key=True)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    excursion: Mapped[Excursion] = relationship(lazy="joined")


class Reserva(Base):
    __tablename__ = "reservas"
    __table_args__ = (
        CheckConstraint("pasajeros >= 1 AND pasajeros <= 9", name="ck_reserva_pasajeros"),
        CheckConstraint("fecha_regreso >= fecha_salida", name="ck_reserva_fechas"),
        # El total nunca puede desviarse de la suma del desglose (tolerancia de medio centavo por los redondeos de SQLite).
        CheckConstraint(
            "monto_vuelo >= 0 AND monto_hotel >= 0 AND monto_excursiones >= 0 "
            "AND ABS(monto_total - (monto_vuelo + monto_hotel + monto_excursiones)) < 0.005",
            name="ck_reserva_monto",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    # Quién la registró: el propio cliente (nulo) o alguien del personal.
    creada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    destino_id: Mapped[int] = mapped_column(ForeignKey("destinos.id"), nullable=False, index=True)
    vuelo_id: Mapped[int | None] = mapped_column(ForeignKey("vuelos.id"), nullable=True, index=True)
    vuelo_regreso_id: Mapped[int | None] = mapped_column(ForeignKey("vuelos.id"), nullable=True, index=True)
    paquete_id: Mapped[int | None] = mapped_column(ForeignKey("paquetes.id"), nullable=True, index=True)
    hotel_id: Mapped[int | None] = mapped_column(ForeignKey("hoteles.id"), nullable=True, index=True)
    fecha_salida: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_regreso: Mapped[date] = mapped_column(Date, nullable=False)
    pasajeros: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    telefono_contacto: Mapped[str] = mapped_column(String(10), nullable=False)
    notas: Mapped[str | None] = mapped_column(String(300), nullable=True)
    estado_id: Mapped[int] = mapped_column(ForeignKey("estados_reserva.id"), nullable=False)
    estado_pago_id: Mapped[int] = mapped_column(ForeignKey("estados_pago.id"), nullable=False)
    metodo_pago_id: Mapped[int | None] = mapped_column(ForeignKey("metodos_pago.id"), nullable=True)
    monto_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    # Desglose guardado al crear la reserva: permite que la factura detalle
    # cada concepto y que el total no dependa de precios que cambien despues.
    monto_vuelo: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    monto_hotel: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    monto_excursiones: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    stripe_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Pago en mostrador: comprobante y quién lo registró. En pagos por Stripe queda vacío.
    pago_referencia: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pago_registrado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    pagado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora, nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora, onupdate=_ahora, nullable=False)

    usuario: Mapped[User] = relationship(foreign_keys=[usuario_id], lazy="joined")
    # El personal se carga aparte: en una sola consulta el número de tablas unidas rozaría el
    # límite de 61 de MySQL, y una reserva solo trae estos datos cuando la registró alguien del equipo.
    creada_por: Mapped[User | None] = relationship(foreign_keys=[creada_por_id], lazy="selectin")
    pago_registrado_por: Mapped[User | None] = relationship(foreign_keys=[pago_registrado_por_id], lazy="selectin")
    destino_rel: Mapped[Destino] = relationship(back_populates="reservas", lazy="joined")
    vuelo_rel: Mapped[Vuelo | None] = relationship(foreign_keys=[vuelo_id], lazy="joined")
    vuelo_regreso_rel: Mapped[Vuelo | None] = relationship(foreign_keys=[vuelo_regreso_id], lazy="joined")
    paquete_rel: Mapped[Paquete | None] = relationship(lazy="selectin")
    hotel_rel: Mapped[Hotel | None] = relationship(lazy="joined")
    lineas_excursion: Mapped[list[ReservaExcursion]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="ReservaExcursion.excursion_id"
    )
    estado_rel: Mapped[EstadoReserva] = relationship(back_populates="reservas", lazy="joined")
    estado_pago_rel: Mapped[EstadoPago] = relationship(back_populates="reservas", lazy="joined")
    metodo_pago_rel: Mapped[MetodoPago | None] = relationship(back_populates="reservas", lazy="joined")

    @property
    def excursiones(self) -> list[Excursion]:
        return [linea.excursion for linea in self.lineas_excursion]

    @property
    def noches(self) -> int:
        return max(0, (self.fecha_regreso - self.fecha_salida).days)


class MensajeContacto(Base):
    __tablename__ = "mensajes_contacto"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    correo: Mapped[str] = mapped_column(String(100), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora, nullable=False)


class Venta(Base):
    __tablename__ = "ventas"

    id: Mapped[int] = mapped_column(MySQLInteger(unsigned=True), primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    # Enlace con la reserva que originó la venta (nulo en ventas de mostrador y en las anteriores a esta columna).
    reserva_id: Mapped[int | None] = mapped_column(ForeignKey("reservas.id", ondelete="SET NULL"), unique=True, nullable=True)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    descuento: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    impuestos: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    estado: Mapped[str] = mapped_column(String(30), default="completada", nullable=False, index=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora, nullable=False, index=True)

    cliente: Mapped[User] = relationship(foreign_keys=[cliente_id], lazy="joined")
    operador: Mapped[User | None] = relationship(foreign_keys=[usuario_id], lazy="joined")
    detalles: Mapped[list["DetalleVenta"]] = relationship(back_populates="venta", cascade="all, delete-orphan", lazy="selectin")
    factura: Mapped["Factura | None"] = relationship(back_populates="venta", uselist=False, cascade="all, delete-orphan", lazy="joined")


class DetalleVenta(Base):
    __tablename__ = "detalle_ventas"

    id: Mapped[int] = mapped_column(MySQLInteger(unsigned=True), primary_key=True)
    venta_id: Mapped[int] = mapped_column(MySQLInteger(unsigned=True), ForeignKey("ventas.id", ondelete="CASCADE"), nullable=False, index=True)
    producto_id: Mapped[int | None] = mapped_column(ForeignKey("productos.id"), nullable=True)
    servicio_id: Mapped[int | None] = mapped_column(ForeignKey("servicios.id"), nullable=True)
    nombre: Mapped[str] = mapped_column(String(140), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    venta: Mapped[Venta] = relationship(back_populates="detalles")
    producto: Mapped[Producto | None] = relationship(foreign_keys=[producto_id], lazy="joined")
    servicio: Mapped[Servicio | None] = relationship(foreign_keys=[servicio_id], lazy="joined")


class Factura(Base):
    __tablename__ = "facturas"

    id: Mapped[int] = mapped_column(MySQLInteger(unsigned=True), primary_key=True)
    venta_id: Mapped[int] = mapped_column(MySQLInteger(unsigned=True), ForeignKey("ventas.id", ondelete="CASCADE"), unique=True, nullable=False)
    numero: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    estado: Mapped[str] = mapped_column(String(30), default="emitida", nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora, nullable=False)

    venta: Mapped[Venta] = relationship(back_populates="factura")
    detalles: Mapped[list["DetalleFactura"]] = relationship(back_populates="factura", cascade="all, delete-orphan", lazy="selectin")


class DetalleFactura(Base):
    __tablename__ = "detalle_facturas"

    id: Mapped[int] = mapped_column(MySQLInteger(unsigned=True), primary_key=True)
    factura_id: Mapped[int] = mapped_column(MySQLInteger(unsigned=True), ForeignKey("facturas.id", ondelete="CASCADE"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(140), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_unitario: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    factura: Mapped[Factura] = relationship(back_populates="detalles")


class PQR(Base):
    __tablename__ = "pqr"

    id: Mapped[int] = mapped_column(MySQLInteger(unsigned=True), primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    asunto: Mapped[str] = mapped_column(String(140), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    respuesta: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado: Mapped[str] = mapped_column(String(30), default="pendiente", nullable=False, index=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora, nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora, onupdate=_ahora, nullable=False)

    cliente: Mapped[User] = relationship(lazy="joined")


class Conversacion(Base):
    __tablename__ = "conversaciones"

    id: Mapped[int] = mapped_column(MySQLInteger(unsigned=True), primary_key=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora, nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora, onupdate=_ahora, nullable=False)

    cliente: Mapped[User | None] = relationship(lazy="joined")
    mensajes: Mapped[list["Mensaje"]] = relationship(back_populates="conversacion", cascade="all, delete-orphan", lazy="selectin")


class Mensaje(Base):
    __tablename__ = "mensajes"

    id: Mapped[int] = mapped_column(MySQLInteger(unsigned=True), primary_key=True)
    conversacion_id: Mapped[int] = mapped_column(MySQLInteger(unsigned=True), ForeignKey("conversaciones.id", ondelete="CASCADE"), nullable=False, index=True)
    rol: Mapped[str] = mapped_column(String(20), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora, nullable=False)

    conversacion: Mapped[Conversacion] = relationship(back_populates="mensajes")
