from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SolicitudDeRiesgo(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={'examples': [{'libro_id': 4, 'socio_id': 1, 'dias_prestamo': 30}]}
    )

    libro_id: int = Field(ge=1)
    socio_id: int = Field(ge=1)
    dias_prestamo: int = Field(default=15, ge=1, le=30)


class PrediccionDeRiesgo(BaseModel):
    probabilidad_retraso: float = Field(ge=0, le=1)
    nivel: Literal['bajo', 'medio', 'alto']
    recomendacion: str
    variables_usadas: dict
    version_modelo: str