from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.core.base_datos import Base

# --- TABLAS PARAMÉTRICAS (Evitan redundancias de texto) ---

class Rol(Base):
    __tablename__ = 'roles'
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True)
    usuarios: Mapped[list['Usuario']] = relationship(back_populates='rol')

class Pais(Base):
    __tablename__ = 'paises'
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True)
    destinos: Mapped[list['Destino']] = relationship(back_populates='pais')

class TipoTurismo(Base):
    __tablename__ = 'tipos_turismo'
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True)
    paquetes: Mapped[list['Paquete']] = relationship(back_populates='tipo_turismo')

class EstadoReserva(Base):
    __tablename__ = 'estados_reserva'
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True)  # Ej: Pendiente_Pago, Pagada
    reservas: Mapped[list['Reserva']] = relationship(back_populates='estado')

# --- ENTIDADES PRINCIPALES ---

class Usuario(Base):
    __tablename__ = 'usuarios'
    id: Mapped[int] = mapped_column(primary_key=True)
    documento: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(120), unique=True)
    contrasena_hash: Mapped[str] = mapped_column(String(255))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    rol_id: Mapped[int] = mapped_column(ForeignKey('roles.id'))
    
    rol: Mapped['Rol'] = relationship(back_populates='usuarios', lazy='joined')
    reservas: Mapped[list['Reserva']] = relationship(back_populates='usuario')

class Destino(Base):
    __tablename__ = 'destinos'
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    pais_id: Mapped[int] = mapped_column(ForeignKey('paises.id'))
    
    pais: Mapped['Pais'] = relationship(back_populates='destinos', lazy='joined')
    paquetes: Mapped[list['Paquete']] = relationship(back_populates='destino')

class Paquete(Base):
    """El catálogo del viaje, independiente de cuándo se realice."""
    __tablename__ = 'paquetes'
    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200), index=True)
    precio_base: Mapped[int] = mapped_column(Integer)
    destino_id: Mapped[int] = mapped_column(ForeignKey('destinos.id'))
    tipo_turismo_id: Mapped[int] = mapped_column(ForeignKey('tipos_turismo.id'))
    
    destino: Mapped['Destino'] = relationship(back_populates='paquetes', lazy='joined')
    tipo_turismo: Mapped['TipoTurismo'] = relationship(back_populates='paquetes', lazy='joined')
    salidas: Mapped[list['Salida']] = relationship(back_populates='paquete')

class Salida(Base):
    """Fechas específicas y cupos para un paquete turístico."""
    __tablename__ = 'salidas'
    id: Mapped[int] = mapped_column(primary_key=True)
    paquete_id: Mapped[int] = mapped_column(ForeignKey('paquetes.id'), index=True)
    fecha_salida: Mapped[date] = mapped_column(Date)
    fecha_retorno: Mapped[date] = mapped_column(Date)
    cupos_totales: Mapped[int] = mapped_column(Integer)
    cupos_disponibles: Mapped[int] = mapped_column(Integer)
    
    paquete: Mapped['Paquete'] = relationship(back_populates='salidas', lazy='joined')
    reservas: Mapped[list['Reserva']] = relationship(back_populates='salida')

class Reserva(Base):
    __tablename__ = 'reservas'
    __table_args__ = (UniqueConstraint('usuario_id', 'salida_id', name='uq_reserva_unica'),)
    
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey('usuarios.id'), index=True)
    salida_id: Mapped[int] = mapped_column(ForeignKey('salidas.id'), index=True)
    estado_id: Mapped[int] = mapped_column(ForeignKey('estados_reserva.id'))
    fecha_reserva: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Datos transaccionales de la pasarela de pagos
    transaccion_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    monto_pagado: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    usuario: Mapped['Usuario'] = relationship(back_populates='reservas', lazy='joined')
    salida: Mapped['Salida'] = relationship(back_populates='reservas', lazy='joined')
    estado: Mapped['EstadoReserva'] = relationship(back_populates='reservas', lazy='joined')

class RegistroAuditoria(Base):
    __tablename__ = 'auditoria'
    id: Mapped[int] = mapped_column(primary_key=True)
    momento: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    accion: Mapped[str] = mapped_column(String(60), index=True)
    recurso: Mapped[str] = mapped_column(String(60))
    recurso_id: Mapped[int] = mapped_column(Integer)
    usuario_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    detalle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)