"""Integración con el proveedor de IA. Aísla el detalle del proveedor."""

from __future__ import annotations

import asyncio
import json
import logging

import httpx

from app.core.configuracion import configuracion

logger = logging.getLogger('biblioapi.ia')

INSTRUCCION_LIBROS = (
    'Eres el asistente de una biblioteca pública. A partir de los intereses '
    'del socio y del catálogo disponible, elige exactamente 3 libros. '
    'Responde ÚNICAMENTE con un arreglo JSON de objetos con las claves '
    'libro_id, titulo y motivo. El motivo debe tener máximo 25 palabras. '
    'No recomiendes libros que no estén en el catálogo.'
)


class ProveedorNoDisponible(RuntimeError):
    """El proveedor externo no respondió de forma utilizable."""


class _RechazoDefinitivo(ProveedorNoDisponible):
    """Error del proveedor que no mejora con reintentos (clave inválida, modelo inexistente, etc.)."""


class ServicioDeRecomendaciones:
    def __init__(self, cliente: httpx.AsyncClient):
        self._cliente = cliente
        self._clave = configuracion.proveedor_ia_api_key

    @property
    def configurado(self) -> bool:
        return self._clave is not None

    def _construir_mensaje(self, intereses: str, catalogo: list[dict]) -> str:
        return (
            f'Intereses del socio: {intereses}\n\n'
            f'Catálogo disponible:\n{json.dumps(catalogo, ensure_ascii=False)}'
        )

    async def recomendar(self, intereses: str, catalogo: list[dict], instruccion: str = INSTRUCCION_LIBROS) -> list[dict]:
        if not self.configurado:
            raise ProveedorNoDisponible('No hay clave de Groq configurada.')

        cuerpo = {
            'model': configuracion.proveedor_ia_modelo,
            'max_tokens': 700,
            'temperature': 0.2,
            'messages': [
                {'role': 'system', 'content': instruccion},
                {'role': 'user', 'content': self._construir_mensaje(intereses, catalogo)},
            ],
        }
        cabeceras = {
            'authorization': f'Bearer {self._clave}',
            'content-type': 'application/json',
        }

        for intento in range(configuracion.proveedor_ia_reintentos + 1):
            ultimo_intento = intento == configuracion.proveedor_ia_reintentos
            try:
                respuesta = await self._cliente.post(
                    configuracion.proveedor_ia_url,
                    json=cuerpo,
                    headers=cabeceras,
                    timeout=configuracion.proveedor_ia_timeout,
                )

                if 400 <= respuesta.status_code < 500 and respuesta.status_code != 429:
                    logger.error(
                        'El proveedor rechazó la petición: %s %s',
                        respuesta.status_code,
                        respuesta.text[:200],
                    )
                    # Rechazo definitivo (clave inválida, modelo inexistente, etc.): no vale la pena reintentar.
                    raise _RechazoDefinitivo(f'El proveedor respondió {respuesta.status_code}.')

                respuesta.raise_for_status()
                # El modelo a veces "piensa" demasiado y devuelve un JSON vacío o truncado; se trata como fallo reintentable.
                return self._extraer_recomendaciones(respuesta.json())

            except _RechazoDefinitivo:
                raise
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError, ProveedorNoDisponible) as exc:
                if ultimo_intento:
                    if isinstance(exc, ProveedorNoDisponible):
                        raise
                    raise ProveedorNoDisponible('El proveedor no respondió tras varios intentos.') from exc
                espera = 2**intento
                logger.warning(
                    'Intento %s fallido (%s). Reintentando en %s s.',
                    intento + 1,
                    type(exc).__name__,
                    espera,
                )
                await asyncio.sleep(espera)

        raise ProveedorNoDisponible('El proveedor no respondió.')

    @staticmethod
    def _extraer_recomendaciones(carga: dict) -> list[dict]:
        try:
            texto = carga['choices'][0]['message']['content'].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ProveedorNoDisponible('Respuesta del proveedor ilegible.') from exc

        if texto.startswith('```'):
            texto = texto.split('```')[1]
            texto = texto.removeprefix('json').strip()

        try:
            datos = json.loads(texto)
        except json.JSONDecodeError as exc:
            raise ProveedorNoDisponible('El proveedor no devolvió JSON válido.') from exc

        if not isinstance(datos, list) or not datos:
            raise ProveedorNoDisponible('El proveedor devolvió una lista vacía.')
        return datos[:3]