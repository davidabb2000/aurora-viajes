from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PrestamoCrear(BaseModel):
    """Lo único que decide el cliente: qué libro, para qué socio y por cuántos días."""

    libro_id: int = Field(ge=1, description='Identificador del libro a prestar.')
    socio_id: int = Field(ge=1, description='Identificador del socio solicitante.')
    dias_prestamo: int = Field(
        default=15,
        ge=1,
        le=30,
        description='Días hasta la fecha de devolución esperada.',
    )


class PrestamoRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    libro_id: int
    socio_id: int
    fecha_prestamo: date
    fecha_devolucion_esperada: date
    fecha_devolucion_real: date | None
    estado: Literal['activo', 'devuelto', 'vencido']
