"""Estado de la puesta a punto de la base de datos.

Si la base no responde al arrancar (un servicio gestionado apagado, un corte de red), la API no se cae: se
levanta, contesta 503 con un mensaje claro y reintenta sola con espera creciente. Así, en cuanto la base vuelve,
la aplicación se recupera sin que nadie tenga que volver a desplegarla, y la plataforma no acumula reinicios
fallidos hasta rendirse.
"""
from dataclasses import dataclass

from sqlalchemy.exc import DBAPIError

# Segundos entre reintentos: empiezan cortos y se duplican hasta el máximo.
ESPERA_INICIAL = 5.0
ESPERA_MAXIMA = 60.0

# Códigos de MySQL que significan «no pude hablar con el servidor» y no «la consulta está mal».
CODIGOS_DE_CONEXION = {1040, 2002, 2003, 2005, 2006, 2013}


@dataclass
class EstadoDeArranque:
    esperando_base: bool = False
    fallo_definitivo: bool = False
    ultimo_error: str = ""
    intentos: int = 0

    @property
    def descripcion(self) -> str:
        if self.fallo_definitivo:
            return "error"
        return "sin conexion" if self.esperando_base else "lista"


estado_de_arranque = EstadoDeArranque()


def es_error_de_conexion(error: BaseException) -> bool:
    """¿El fallo es de conectividad (y por tanto pasajero) y no un error del código o de los datos?"""
    if isinstance(error, OSError):
        return True
    if isinstance(error, DBAPIError):
        if error.connection_invalidated:
            return True
        argumentos = getattr(error.orig, "args", ())
        return bool(argumentos) and argumentos[0] in CODIGOS_DE_CONEXION
    return False
