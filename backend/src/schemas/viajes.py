from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, EmailStr

# --- USUARIOS ---
class UsuarioCrear(BaseModel):
    documento: str = Field(pattern=r'^\d{6,15}$')
    nombre: str = Field(min_length=3, max_length=120)
    email: EmailStr
    contrasena: str = Field(min_length=8)
    rol_id: int = Field(default=1, description="ID del rol (ej. 1: viajero, 2: agente)")

class RolRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    nombre: str

class UsuarioRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    email: EmailStr
    activo: bool
    rol: RolRespuesta

# --- CATÁLOGO Y SALIDAS (3FN) ---
class DestinoRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    nombre: str

class PaqueteRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    titulo: str
    precio_base: int
    destino: DestinoRespuesta

class SalidaRespuesta(BaseModel):
    """Esquema para listar las fechas disponibles de un paquete"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    fecha_salida: date
    fecha_retorno: date
    cupos_disponibles: int
    paquete: PaqueteRespuesta

# --- RESERVAS ---
class EstadoReservaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    nombre: str

class ReservaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    salida_id: int
    usuario_id: int
    fecha_reserva: datetime
    transaccion_id: Optional[str]
    monto_pagado: Optional[int]
    estado: EstadoReservaRespuesta