from typing import Literal

from pydantic import BaseModel


class EstadoComponente(BaseModel):
    componente: str
    estado: Literal['ok', 'degradado', 'caido']
    latencia_ms: float | None = None
    detalle: str | None = None


class Diagnostico(BaseModel):
    estado_general: Literal['ok', 'degradado', 'caido']
    componentes: list[EstadoComponente]