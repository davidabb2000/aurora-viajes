from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AutorBase(BaseModel):
    nombre: str = Field(min_length=3, max_length=120)
    nacionalidad: str = Field(min_length=3, max_length=60)

    @field_validator('nombre', 'nacionalidad')
    @classmethod
    def normalizar(cls, valor: str) -> str:
        return ' '.join(valor.split()).title()


class AutorCrear(AutorBase):
    pass


class AutorActualizar(BaseModel):
    nombre: str | None = Field(default=None, min_length=3, max_length=120)
    nacionalidad: str | None = Field(default=None, min_length=3, max_length=60)

    @model_validator(mode='after')
    def al_menos_un_campo(self):
        if not self.model_dump(exclude_unset=True):
            raise ValueError('Debe enviarse al menos un campo para actualizar.')
        return self


class AutorRespuesta(AutorBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    libros_registrados: int = 0
