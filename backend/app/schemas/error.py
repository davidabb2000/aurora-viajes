from pydantic import BaseModel, Field


class DetalleDeError(BaseModel):
    codigo: str = Field(description='Identificador estable del tipo de error.')
    mensaje: str = Field(description='Explicacion legible para una persona.')
    ruta: str
    detalles: list[dict] | None = Field(default=None, description='Errores por campo.')
