import logging
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.configuracion import configuracion
from app.core.estado_arranque import estado_de_arranque


logger = logging.getLogger("aurora-viajes.peticiones")


async def registrar_peticion(peticion: Request, call_next):
    identificador = str(uuid.uuid4())[:8]
    inicio = time.perf_counter()
    respuesta = await call_next(peticion)
    duracion_ms = (time.perf_counter() - inicio) * 1000
    respuesta.headers["X-Peticion-Id"] = identificador
    respuesta.headers["X-Tiempo-Respuesta-ms"] = f"{duracion_ms:.1f}"
    logger.info(
        "[%s] %s %s -> %s (%.1f ms)",
        identificador,
        peticion.method,
        peticion.url.path,
        respuesta.status_code,
        duracion_ms,
    )
    return respuesta


async def cabeceras_de_seguridad(peticion: Request, call_next):
    respuesta = await call_next(peticion)
    respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
    respuesta.headers.setdefault("X-Frame-Options", "DENY")
    respuesta.headers.setdefault("Referrer-Policy", "no-referrer")
    respuesta.headers.setdefault("Cache-Control", "no-store, no-cache, must-revalidate")
    # La API solo devuelve JSON y PDF: no necesita cargar nada de ningun sitio.
    respuesta.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
    )
    respuesta.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=()")
    respuesta.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
    # Solo tiene sentido sobre HTTPS; en desarrollo la peticion es http y se omite.
    if peticion.url.scheme == "https" or peticion.headers.get("x-forwarded-proto") == "https":
        respuesta.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return respuesta


async def limitar_tamano_del_cuerpo(peticion: Request, call_next):
    """Rechaza de entrada las peticiones con un cuerpo declarado mayor que el máximo.

    La API solo recibe JSON pequeño; un cuerpo de decenas de megabytes solo sirve para
    gastar memoria y tiempo de análisis.
    """
    largo = peticion.headers.get("content-length", "")
    if largo.isdigit() and int(largo) > configuracion.tamano_maximo_cuerpo:
        return JSONResponse(
            status_code=413,
            content={"codigo": "cuerpo_demasiado_grande", "mensaje": "La petición es demasiado grande.", "ruta": peticion.url.path, "detalles": None},
        )
    return await call_next(peticion)


# Lo que sigue respondiendo aunque la base no esté: la comprobación de salud de la plataforma y la portada de la API.
RUTAS_SIN_BASE = {"/", "/salud", "/api/health"}


async def exigir_base_lista(peticion: Request, call_next):
    """Mientras la base no responda, todo lo que la necesite contesta 503 en lugar de fallar con un error interno."""
    if estado_de_arranque.esperando_base and peticion.method != "OPTIONS" and peticion.url.path not in RUTAS_SIN_BASE:
        respuesta = JSONResponse(
            status_code=503,
            content={
                "codigo": "servicio_no_disponible",
                "mensaje": "El servicio no está disponible en este momento. Inténtalo de nuevo en unos minutos.",
                "ruta": peticion.url.path,
                "detalles": None,
            },
        )
        respuesta.headers["Retry-After"] = "30"
        return respuesta
    return await call_next(peticion)
