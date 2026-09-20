"""Integración con el proveedor de IA para recomendaciones de viajes."""

from __future__ import annotations

import asyncio
import json
import logging

import httpx

from app.core.configuracion import configuracion

logger = logging.getLogger("aurora-viajes.ia")

INSTRUCCION_DESTINOS = (
    "Eres el asistente virtual de la agencia de viajes Aurora Viajes. A partir de las preferencias "
    "del viajero y del catálogo de destinos disponibles, selecciona exactamente 3 destinos ideales. "
    "Responde ÚNICAMENTE con un objeto JSON con una única clave 'recomendaciones', cuyo valor sea un "
    "arreglo de objetos con las claves: destino_id, nombre y motivo. "
    "El motivo debe explicar por qué encaja en máximo 25 palabras, en español, sin mezclar otros idiomas. "
    "Usa obligatoriamente el 'id' del catálogo como 'destino_id'. "
    "No agregues texto, comentarios ni explicaciones fuera del JSON. "
    "No recomiendes destinos que no estén en el catálogo."
)


class ProveedorNoDisponible(RuntimeError):
    """El proveedor externo no respondió de forma utilizable."""


class _RechazoDefinitivo(ProveedorNoDisponible):
    """Error del proveedor que no mejora con reintentos."""


class ServicioDeRecomendaciones:
    def __init__(self, cliente: httpx.AsyncClient):
        self._cliente = cliente
        self._clave = configuracion.proveedor_ia_api_key

    @property
    def configurado(self) -> bool:
        return self._clave is not None

    def _construir_mensaje(self, intereses: str, catalogo: list[dict]) -> str:
        return (
            f"Preferencias del viajero: {intereses}\n\n"
            f"Catálogo de destinos disponibles:\n{json.dumps(catalogo, ensure_ascii=False)}"
        )

    async def recomendar(
        self,
        intereses: str,
        catalogo: list[dict],
        instruccion: str = INSTRUCCION_DESTINOS,
    ) -> list[dict]:
        if not self.configurado:
            raise ProveedorNoDisponible("No hay clave de Groq configurada.")

        cuerpo = {
            "model": configuracion.proveedor_ia_modelo,
            "max_tokens": 800,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": instruccion},
                {
                    "role": "user",
                    "content": self._construir_mensaje(intereses, catalogo),
                },
            ],
        }
        cabeceras = {
            "authorization": f"Bearer {self._clave}",
            "content-type": "application/json",
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

                if (
                    400 <= respuesta.status_code < 500
                    and respuesta.status_code != 429
                ):
                    logger.error(
                        "El proveedor rechazó la petición: %s %s",
                        respuesta.status_code,
                        respuesta.text[:200],
                    )
                    raise _RechazoDefinitivo(
                        f"El proveedor respondió {respuesta.status_code}."
                    )

                respuesta.raise_for_status()
                return self._extraer_recomendaciones(respuesta.json())

            except _RechazoDefinitivo:
                raise
            except (
                httpx.TimeoutException,
                httpx.TransportError,
                httpx.HTTPStatusError,
                ProveedorNoDisponible,
            ) as exc:
                if ultimo_intento:
                    if isinstance(exc, ProveedorNoDisponible):
                        raise
                    raise ProveedorNoDisponible(
                        "El proveedor no respondió tras varios intentos."
                    ) from exc
                espera = 2**intento
                logger.warning(
                    "Intento %s fallido (%s: %s). Reintentando en %s s.",
                    intento + 1,
                    type(exc).__name__,
                    exc,
                    espera,
                )
                await asyncio.sleep(espera)

        raise ProveedorNoDisponible("El proveedor no respondió.")

    async def conversar(self, mensaje: str, historial: list[dict[str, str]] | None = None) -> str:
        """Genera una respuesta conversacional usando la misma integración Groq."""
        if not self.configurado:
            raise ProveedorNoDisponible("No hay clave de Groq configurada.")

        cuerpo = {
            "model": configuracion.proveedor_ia_modelo,
            "max_tokens": 600,
            "temperature": 0.3,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Eres Aurora, el asistente de Aurora Viajes. Responde en español, "
                        "orienta sobre destinos, reservas, viajes y PQR. No inventes precios, "
                        "disponibilidad ni estados de reservas. Sé claro y breve."
                    ),
                },
                *(historial or [])[-20:],
                {"role": "user", "content": mensaje},
            ],
        }
        cabeceras = {
            "authorization": f"Bearer {self._clave}",
            "content-type": "application/json",
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
                    raise _RechazoDefinitivo(f"El proveedor respondió {respuesta.status_code}.")
                respuesta.raise_for_status()
                texto = respuesta.json()["choices"][0]["message"]["content"]
                if not isinstance(texto, str) or not texto.strip():
                    raise ProveedorNoDisponible("El proveedor devolvió una respuesta vacía.")
                return texto.strip()
            except _RechazoDefinitivo:
                raise
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError, KeyError, IndexError, TypeError, ProveedorNoDisponible) as exc:
                if ultimo_intento:
                    raise ProveedorNoDisponible("El proveedor no respondió tras varios intentos.") from exc
                await asyncio.sleep(2**intento)

        raise ProveedorNoDisponible("El proveedor no respondió.")

    @staticmethod
    def _extraer_recomendaciones(carga: dict) -> list[dict]:
        try:
            texto = carga["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ProveedorNoDisponible(
                "Respuesta del proveedor ilegible."
            ) from exc

        # 1. Intentar parsear directo (esperado con response_format json_object)
        datos = None
        try:
            datos = json.loads(texto)
        except json.JSONDecodeError:
            pass

        # 2. Si falló, buscar el primer arreglo [...] balanceado dentro del texto
        if datos is None:
            datos = ServicioDeRecomendaciones._extraer_primer_json_balanceado(texto)

        if datos is None:
            logger.error("JSON inválido de Groq. Respuesta cruda: %s", texto)
            raise ProveedorNoDisponible(
                "El proveedor no devolvió JSON válido."
            )

        # Si devolvió un dict con una lista dentro, extraer la lista
        if isinstance(datos, dict):
            for valor in datos.values():
                if isinstance(valor, list):
                    datos = valor
                    break

        if not isinstance(datos, list) or not datos:
            logger.error("Groq devolvió una lista vacía. Texto: %s", texto)
            raise ProveedorNoDisponible(
                "El proveedor devolvió una lista vacía o formato inesperado."
            )

        return datos[:3]

    @staticmethod
    def _extraer_primer_json_balanceado(texto: str) -> list | dict | None:
        """Busca el primer objeto/arreglo JSON balanceado, ignorando texto
        alucinado que quede después de que el modelo ya cerró el JSON."""
        for apertura, cierre in (("[", "]"), ("{", "}")):
            inicio = texto.find(apertura)
            if inicio == -1:
                continue
            profundidad = 0
            for indice in range(inicio, len(texto)):
                caracter = texto[indice]
                if caracter == apertura:
                    profundidad += 1
                elif caracter == cierre:
                    profundidad -= 1
                    if profundidad == 0:
                        fragmento = texto[inicio : indice + 1]
                        try:
                            return json.loads(fragmento)
                        except json.JSONDecodeError:
                            break
        return None