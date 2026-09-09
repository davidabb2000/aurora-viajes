from pydantic import BaseModel, ConfigDict


class Token(BaseModel):
    acceso: str
    tipo: str = 'bearer'
    expira_en_segundos: int


class SocioAutenticado(BaseModel):
    """Datos del socio que sí pueden devolverse: sin documento ni hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    rol: str
    activo: bool
