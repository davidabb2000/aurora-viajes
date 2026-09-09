from pydantic import BaseModel, Field


class SolicitudDeRecomendacion(BaseModel):
    intereses: str = Field(
        min_length=10,
        max_length=500,
        description='Qué le apetece leer al socio, en sus propias palabras.',
    )


class LibroRecomendado(BaseModel):
    libro_id: int
    titulo: str
    motivo: str


class RespuestaDeRecomendacion(BaseModel):
    recomendaciones: list[LibroRecomendado]
    generada_por: str = Field(description='modelo_externo o catalogo_local si hubo degradación.')
    aviso: str | None = None