from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_datos import Base


rol_permisos = Table(
    "rol_permisos",
    Base.metadata,
    Column("rol_id", ForeignKey("roles.id"), primary_key=True),
    Column("permiso_id", ForeignKey("permisos.id"), primary_key=True),
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


class Reserva(Base):
    __tablename__ = "reservas"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    destino_id: Mapped[int] = mapped_column(ForeignKey("destinos.id"), nullable=False, index=True)
    fecha_salida: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_regreso: Mapped[date] = mapped_column(Date, nullable=False)
    pasajeros: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    telefono_contacto: Mapped[str] = mapped_column(String(10), nullable=False)
    notas: Mapped[str | None] = mapped_column(String(300), nullable=True)
    estado_id: Mapped[int] = mapped_column(ForeignKey("estados_reserva.id"), nullable=False)
    estado_pago_id: Mapped[int] = mapped_column(ForeignKey("estados_pago.id"), nullable=False)
    metodo_pago_id: Mapped[int | None] = mapped_column(ForeignKey("metodos_pago.id"), nullable=True)
    monto_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
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
