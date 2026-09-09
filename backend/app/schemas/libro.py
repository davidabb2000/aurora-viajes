from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Categoria = Literal['novela', 'memorias', 'tecnica', 'infantil', 'referencia']


class LibroBase(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    isbn: str = Field(pattern=r'^\d{13}$')
    anio_publicacion: int = Field(ge=1450, le=date.today().year)
    autor: str = Field(min_length=3, max_length=120)
    categoria: Categoria

    @field_validator('titulo', 'autor')
    @classmethod
    def sin_espacios_sobrantes(cls, valor: str) -> str:
        return ' '.join(valor.split())


class LibroCrear(LibroBase):
    ejemplares_totales: int = Field(ge=1, le=999)
    autor_id: int | None = Field(default=None, ge=1)
    categoria_id: int | None = Field(default=None, ge=1)

    model_config = ConfigDict(json_schema_extra={'examples': [{
        'titulo': 'Delirio', 'isbn': '9788483462744', 'anio_publicacion': 2004,
        'autor': 'Laura Restrepo', 'categoria': 'novela', 'ejemplares_totales': 4,
    }]})


class AutorRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    nacionalidad: str


class CategoriaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str


class LibroActualizar(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=200)
    autor: str | None = Field(default=None, min_length=3, max_length=120)
    categoria: Categoria | None = None
    ejemplares_totales: int | None = Field(default=None, ge=1, le=999)

    @model_validator(mode='after')
    def al_menos_un_campo(self):
        if not self.model_dump(exclude_unset=True):
            raise ValueError('Debe enviarse al menos un campo para actualizar.')
        return self


class LibroRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    titulo: str
    isbn: str
    anio_publicacion: int
    autor: AutorRespuesta
    categoria: CategoriaRespuesta
    id: int
    ejemplares_totales: int
    ejemplares_disponibles: int

    @model_validator(mode='after')
    def disponibles_no_superan_totales(self):
        if self.ejemplares_disponibles > self.ejemplares_totales:
            raise ValueError('Los ejemplares disponibles no pueden superar los totales.')
        return self
