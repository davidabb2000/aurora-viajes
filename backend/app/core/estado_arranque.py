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
    migracion_pendiente: bool = False
    ultimo_error: str = ""
    intentos: int = 0

    @property
    def descripcion(self) -> str:
        if self.fallo_definitivo:
            return "error"
        if self.migracion_pendiente:
            return "migracion pendiente"
        return "sin conexion" if self.esperando_base else "lista"


estado_de_arranque = EstadoDeArranque()


def detalle_del_error(error: BaseException) -> str:
    """Lo que dijo de verdad el controlador (código y mensaje de MySQL) y el fallo de red que hay debajo, para el log.

    `OperationalError` a secas no distingue un nombre que no resuelve de una clave mala o de un certificado rechazado.
    Solo se cuenta el error del controlador (`orig`) y su cadena de causas, nunca el texto de SQLAlchemy, que lleva la
    consulta y sus parámetros; los mensajes de MySQL y del sistema nombran el servidor y el usuario, no la contraseña.
    """
    actual = getattr(error, "orig", None) or error
    partes = []
    while actual is not None and len(partes) < 4:
        argumentos = getattr(actual, "args", ())
        partes.append(f"{type(actual).__name__}{tuple(argumentos)!r}" if argumentos else type(actual).__name__)
        actual = actual.__cause__ or actual.__context__
    return " <- ".join(partes)[:400]


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
