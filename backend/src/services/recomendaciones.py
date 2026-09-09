from __future__ import annotations
import asyncio
import json
import logging
import httpx
from src.core.configuracion import configuracion

logger = logging.getLogger('aurora-viajes.ia')

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
            f"Intereses del viajero: {intereses}\n\n"
            f"Catálogo de paquetes disponibles:\n{json.dumps(catalogo, ensure_ascii=False)}"
        )

    async def recomendar(self, intereses: str, catalogo: list[dict]) -> list[dict]:
        if not self.configurado:
            raise ProveedorNoDisponible('No hay clave de Groq configurada.')

        instruccion = (
            "Eres un experto agente de viajes de Aurora Viajes. Analiza los intereses del cliente "
            "y elige exactamente 3 paquetes turísticos del catálogo proporcionado. "
            "Responde ÚNICAMENTE con un arreglo JSON de objetos con las claves: "
            "id, titulo y motivo. El motivo debe explicar por qué es ideal para el cliente en máximo 25 palabras."
        )

        cuerpo = {
            "model": configuracion.proveedor_ia_modelo,
            "messages": [
                {"role": "system", "content": instruccion},
                {"role": "user", "content": self._construir_mensaje(intereses, catalogo)}
            ],
            "temperature": 0.2,
            "max_tokens": 700
        }
        
        cabeceras = {
            "Authorization": f"Bearer {self._clave}",
            "Content-Type": "application/json"
        }

        for intento in range(3):
            ultimo_intento = intento == 2
            try:
                respuesta = await self._cliente.post(
                    configuracion.proveedor_ia_url,
                    json=cuerpo,
                    headers=cabeceras,
                    timeout=12.0
                )
                if 400 <= respuesta.status_code < 500 and respuesta.status_code != 429:
                    raise _RechazoDefinitivo(f"El proveedor respondió {respuesta.status_code}.")
                
                respuesta.raise_for_status()
                return self._extraer_recomendaciones(respuesta.json())
                
            except _RechazoDefinitivo:
                raise
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError, ProveedorNoDisponible) as exc:
                if ultimo_intento:
                    if isinstance(exc, ProveedorNoDisponible):
                        raise
                    raise ProveedorNoDisponible('El proveedor no respondió tras varios intentos.') from exc
                await asyncio.sleep(2**intento)
                
        raise ProveedorNoDisponible('El proveedor no respondió.')

    @staticmethod
    def _extraer_recomendaciones(carga: dict) -> list[dict]:
        try:
            texto = carga['choices'][0]['message']['content'].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ProveedorNoDisponible('Respuesta del proveedor ilegible.') from exc
            
        if texto.startswith('```'):
            texto = texto.split('```')[1].removeprefix('json').strip()
            
        try:
            datos = json.loads(texto)
        except json.JSONDecodeError as exc:
            raise ProveedorNoDisponible('El proveedor no devolvió JSON válido.') from exc
            
        if not isinstance(datos, list) or not datos:
            raise ProveedorNoDisponible('El proveedor devolvió una lista vacía.')
            
        return datos[:3]

    def respaldo_local(self, intereses: str, catalogo: list[dict]) -> list[dict]:
        recomendaciones = []
        for paquete in catalogo[:3]:
            recomendaciones.append({
                "id": paquete["id"],
                "titulo": paquete["titulo"],
                "motivo": "Recomendación destacada de nuestro catálogo local."
            })
        return recommendations if 'recommendations' in locals() else recomendaciones