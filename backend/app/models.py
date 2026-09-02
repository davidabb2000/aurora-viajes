from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, String, Table, Text, func
from sqlalchemy.dialects.mysql import INTEGER as MySQLInteger
from sqlalchemy.orm import relationship

from app.database import Base

rol_permisos = Table(
    "rol_permisos",
    Base.metadata,
    Column("rol_id", MySQLInteger(unsigned=True), ForeignKey("roles.id"), primary_key=True),
    Column("permiso_id", MySQLInteger(unsigned=True), ForeignKey("permisos.id"), primary_key=True),
)


class Role(Base):
    __tablename__ = "roles"

    id = Column(MySQLInteger(unsigned=True), primary_key=True, index=True)
    nombre = Column(String(30), unique=True, nullable=False)

    users = relationship("User", back_populates="role")
    permisos = relationship("Permiso", secondary=rol_permisos, back_populates="roles")


class Permiso(Base):
    __tablename__ = "permisos"

    id = Column(MySQLInteger(unsigned=True), primary_key=True, index=True)
    nombre = Column(String(80), unique=True, nullable=False)

    roles = relationship("Role", secondary=rol_permisos, back_populates="permisos")


class User(Base):
    __tablename__ = "usuarios"

    id = Column(MySQLInteger(unsigned=True), primary_key=True, index=True)
    nombre = Column(String(40), nullable=False)
    apellido = Column(String(40), nullable=False)
    tipo_documento = Column(String(5), nullable=False)
    numero_documento = Column(String(12), nullable=False, unique=True, index=True)
    direccion = Column(String(80), nullable=False)
    telefono = Column(String(10), nullable=False)
    correo = Column(String(60), nullable=False, unique=True, index=True)
    contrasena_hash = Column(String(255), nullable=False)
    activo = Column(Boolean, default=True, nullable=False)
    rol_id = Column(MySQLInteger(unsigned=True), ForeignKey("roles.id"), nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    role = relationship("Role", back_populates="users")
    reservas = relationship("Reserva", back_populates="usuario")


class Producto(Base):
    __tablename__ = "productos"

    id = Column(MySQLInteger(unsigned=True), primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(Text, nullable=True)
    precio = Column(String(20), default="0", nullable=False)
    activo = Column(Boolean, default=True, nullable=False)


class Servicio(Base):
    __tablename__ = "servicios"

    id = Column(MySQLInteger(unsigned=True), primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(Text, nullable=True)
    precio = Column(String(20), default="0", nullable=False)
    activo = Column(Boolean, default=True, nullable=False)


class Reserva(Base):
    __tablename__ = "reservas"

    id = Column(MySQLInteger(unsigned=True), primary_key=True, index=True)
    usuario_id = Column(MySQLInteger(unsigned=True), ForeignKey("usuarios.id"), nullable=False)
    destino = Column(String(120), nullable=False)
    fecha_salida = Column(Date, nullable=False)
    fecha_regreso = Column(Date, nullable=False)
    pasajeros = Column(MySQLInteger(unsigned=True), default=1, nullable=False)
    telefono_contacto = Column(String(10), nullable=False)
    notas = Column(String(300), nullable=True)
    estado = Column(String(30), default="pendiente", nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    usuario = relationship("User", back_populates="reservas")


class MensajeContacto(Base):
    __tablename__ = "mensajes_contacto"

    id = Column(MySQLInteger(unsigned=True), primary_key=True, index=True)
    nombre = Column(String(80), nullable=False)
    correo = Column(String(100), nullable=False)
    mensaje = Column(Text, nullable=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
