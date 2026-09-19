"""Limitador de peticiones por ventana deslizante.

Protege los endpoints sensibles (login, registro, recuperacion de contrasena,
contacto) de ataques de fuerza bruta y de abuso automatizado.

El estado vive en memoria del proceso. Con una sola replica, que es como corre
este proyecto, basta. Si algun dia se escala a varias replicas cada una llevara
su propia cuenta, y habria que mover el contador a Redis.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from fastapi import Request

from app.errores import DemasiadasPeticiones


def cliente_de(peticion: Request) -> str:
    """Identifica al cliente detras del proxy de la plataforma.

    Railway y Cloudflare anteponen la IP real en X-Forwarded-For. Se toma la
    primera entrada, que es la del cliente; las siguientes son proxies
    intermedios. Si la cabecera no viene, se usa la conexion directa.
    """
    reenviada = peticion.headers.get("x-forwarded-for", "")
    if reenviada:
        primera = reenviada.split(",")[0].strip()
        if primera:
            return primera
    return peticion.client.host if peticion.client else "desconocido"


class Limitador:
    def __init__(self):
        self._eventos: dict[str, deque[float]] = defaultdict(deque)
        self._candado = asyncio.Lock()

    async def registrar(self, clave: str, maximo: int, ventana_segundos: int) -> None:
        """Anota un intento y lanza DemasiadasPeticiones si se paso del limite."""
        ahora = time.monotonic()
        corte = ahora - ventana_segundos
        async with self._candado:
            marcas = self._eventos[clave]
            while marcas and marcas[0] < corte:
                marcas.popleft()
            if len(marcas) >= maximo:
                restante = int(marcas[0] + ventana_segundos - ahora) + 1
                raise DemasiadasPeticiones(restante)
            marcas.append(ahora)
            # Evita que el diccionario crezca sin limite con claves ya vencidas.
            if len(self._eventos) > 10_000:
                for otra in [k for k, v in self._eventos.items() if not v or v[-1] < corte]:
                    del self._eventos[otra]

    async def limpiar(self, clave: str) -> None:
        """Olvida los intentos de una clave; se usa tras un login correcto."""
        async with self._candado:
            self._eventos.pop(clave, None)


limitador = Limitador()


async def limitar(peticion: Request, bucket: str, maximo: int, ventana_segundos: int) -> str:
    """Aplica el limite a la IP del cliente y devuelve la clave usada."""
    clave = f"{bucket}:{cliente_de(peticion)}"
    await limitador.registrar(clave, maximo, ventana_segundos)
    return clave
