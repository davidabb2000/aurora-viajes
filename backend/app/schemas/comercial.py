from decimal import Decimal

from pydantic import BaseModel, Field


class DetalleVentaEntrada(BaseModel):
    tipo: str = Field(pattern="^(producto|servicio)$")
    id: int = Field(gt=0)
    cantidad: int = Field(gt=0, le=1000)


class VentaEntrada(BaseModel):
    cliente_id: int | None = Field(default=None, gt=0)
    descuento: Decimal = Field(default=0, ge=0)
    impuesto_porcentaje: Decimal = Field(default=0, ge=0, le=100)
    items: list[DetalleVentaEntrada] = Field(min_length=1)


class PQREntrada(BaseModel):
    tipo: str = Field(pattern="^(peticion|queja|reclamo)$")
    asunto: str = Field(min_length=3, max_length=140)
    descripcion: str = Field(min_length=5, max_length=4000)


class PQRActualizacion(BaseModel):
    estado: str = Field(pattern="^(pendiente|en_proceso|respondida|cerrada)$")
    respuesta: str | None = Field(default=None, max_length=4000)


class ChatEntrada(BaseModel):
    mensaje: str = Field(min_length=1, max_length=2000)
    historial: list[dict[str, str]] = Field(default_factory=list, max_length=20)
    conversacion_id: int | None = Field(default=None, gt=0)
