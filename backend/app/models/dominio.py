from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Table, Text
from sqlalchemy.dialects.mysql import INTEGER as MySQLInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_datos import Base


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

# Permite armar una reserva a la carta, sin depender de un paquete prearmado.
reserva_excursiones = Table(
    "reserva_excursiones",
    Base.metadata,
    Column("reserva_id", Integer, ForeignKey("reservas.id", ondelete="CASCADE"), primary_key=True),
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

    destinos: Mapped[list["Destino"]] = relationship(back_populates="pais")


class Destino(Base):
    __tablename__ = "destinos"

    id: Mapped[int] = mapped_column(primary_key=True)
    pais_id: Mapped[int] = mapped_column(ForeignKey("paises.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    precio_base: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    imagen_slug: Mapped[str | None] = mapped_column(String(80), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    pais: Mapped[Pais] = relationship(back_populates="destinos")
    reservas: Mapped[list["Reserva"]] = relationship(back_populates="destino_rel")


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
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    role: Mapped[Role] = relationship(back_populates="users", lazy="joined")
    tipo_documento_catalogo: Mapped[TipoDocumento] = relationship(back_populates="usuarios", lazy="joined")
    reservas: Mapped[list["Reserva"]] = relationship(back_populates="usuario")


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

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    ciudad: Mapped[str] = mapped_column(String(120), nullable=False)
    pais: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    estrellas: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_noche: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    paquetes: Mapped[list["Paquete"]] = relationship(back_populates="hotel_rel")


class Excursion(Base):
    __tablename__ = "excursiones"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    ciudad: Mapped[str] = mapped_column(String(120), nullable=False)
    pais: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    duracion_horas: Mapped[int] = mapped_column(Integer, nullable=False)
    precio: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    paquetes: Mapped[list["Paquete"]] = relationship(secondary=paquete_excursiones, back_populates="excursiones")


class Vuelo(Base):
    __tablename__ = "vuelos"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero_vuelo: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    aerolinea: Mapped[str] = mapped_column(String(80), nullable=False)
    avion: Mapped[str] = mapped_column(String(80), nullable=False)
    origen: Mapped[str] = mapped_column(String(120), nullable=False)
    destino: Mapped[str] = mapped_column(String(120), nullable=False)
    fecha_salida: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_llegada: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    capacidad_maxima: Mapped[int] = mapped_column(Integer, nullable=False)
    puerta: Mapped[str | None] = mapped_column(String(10), nullable=True)
    terminal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    estado: Mapped[str] = mapped_column(String(20), default="programado", nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    reservas: Mapped[list["Reserva"]] = relationship(back_populates="vuelo_rel")
    paquetes: Mapped[list["Paquete"]] = relationship(back_populates="vuelo_rel")


class Paquete(Base):
    __tablename__ = "paquetes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(140), nullable=False)
    destino_id: Mapped[int] = mapped_column(ForeignKey("destinos.id"), nullable=False)
    vuelo_id: Mapped[int] = mapped_column(ForeignKey("vuelos.id"), nullable=False)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hoteles.id"), nullable=False)
    fecha_salida: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_regreso: Mapped[date] = mapped_column(Date, nullable=False)
    precio_base: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    destino_rel: Mapped[Destino] = relationship(lazy="joined")
    vuelo_rel: Mapped[Vuelo] = relationship(back_populates="paquetes", lazy="joined")
    hotel_rel: Mapped[Hotel] = relationship(back_populates="paquetes", lazy="joined")
    excursiones: Mapped[list[Excursion]] = relationship(secondary=paquete_excursiones, back_populates="paquetes", lazy="selectin")
    reservas: Mapped[list["Reserva"]] = relationship(back_populates="paquete_rel")


class Reserva(Base):
    __tablename__ = "reservas"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    destino_id: Mapped[int] = mapped_column(ForeignKey("destinos.id"), nullable=False, index=True)
    vuelo_id: Mapped[int | None] = mapped_column(ForeignKey("vuelos.id"), nullable=True, index=True)
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
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    usuario: Mapped[User] = relationship(back_populates="reservas", lazy="joined")
    destino_rel: Mapped[Destino] = relationship(back_populates="reservas", lazy="joined")
    vuelo_rel: Mapped[Vuelo | None] = relationship(back_populates="reservas", lazy="joined")
    paquete_rel: Mapped[Paquete | None] = relationship(back_populates="reservas", lazy="joined")
    hotel_rel: Mapped["Hotel | None"] = relationship(lazy="joined")
    excursiones: Mapped[list["Excursion"]] = relationship(secondary=reserva_excursiones, lazy="selectin")
    estado_rel: Mapped[EstadoReserva] = relationship(back_populates="reservas", lazy="joined")
    estado_pago_rel: Mapped[EstadoPago] = relationship(back_populates="reservas", lazy="joined")
    metodo_pago_rel: Mapped[MetodoPago | None] = relationship(back_populates="reservas", lazy="joined")


class MensajeContacto(Base):
    __tablename__ = "mensajes_contacto"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    correo: Mapped[str] = mapped_column(String(100), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


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
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

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
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

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
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    cliente: Mapped[User] = relationship(lazy="joined")


class Conversacion(Base):
    __tablename__ = "conversaciones"

    id: Mapped[int] = mapped_column(MySQLInteger(unsigned=True), primary_key=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    cliente: Mapped[User | None] = relationship(lazy="joined")
    mensajes: Mapped[list["Mensaje"]] = relationship(back_populates="conversacion", cascade="all, delete-orphan", lazy="selectin")


class Mensaje(Base):
    __tablename__ = "mensajes"

    id: Mapped[int] = mapped_column(MySQLInteger(unsigned=True), primary_key=True)
    conversacion_id: Mapped[int] = mapped_column(MySQLInteger(unsigned=True), ForeignKey("conversaciones.id", ondelete="CASCADE"), nullable=False, index=True)
    rol: Mapped[str] = mapped_column(String(20), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    conversacion: Mapped[Conversacion] = relationship(back_populates="mensajes")
