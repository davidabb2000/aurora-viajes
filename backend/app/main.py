"""Aurora Viajes API: punto de entrada.

Aquí solo se ensambla la aplicación: ciclo de vida, middlewares, formato de
errores y routers. La lógica vive en `routers/`, `services/` y `schemas/`.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.base_datos import motor
from app.core.configuracion import configuracion
from app.errores import (
    ConflictoDeNegocio,
    DemasiadasPeticiones,
    ErrorDeDominio,
    NoAutenticado,
    PermisoDenegado,
    RecursoNoEncontrado,
    ServicioNoDisponible,
)
from app.middlewares import cabeceras_de_seguridad, registrar_peticion
from app.routers import auth, catalogo, comercial, contacto, pagos, recomendaciones, reservas, usuarios, viajes
from app.services.siembra import asegurar_base_inicial

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("aurora-viajes")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    await asegurar_base_inicial()
    yield
    await motor.dispose()


app = FastAPI(
    title=configuracion.nombre_app,
    description="API de gestión de reservas y viajes.",
    version="1.0.0",
    docs_url="/docs" if configuracion.depuracion else None,
    redoc_url="/redoc" if configuracion.depuracion else None,
    lifespan=ciclo_de_vida,
)
app.middleware("http")(cabeceras_de_seguridad)
app.middleware("http")(registrar_peticion)
app.add_middleware(
    CORSMiddleware,
    allow_origins=configuracion.origenes_permitidos,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Peticion-Id", "X-Tiempo-Respuesta-ms"],
)

for modulo in (recomendaciones, comercial, auth, usuarios, catalogo, viajes, reservas, pagos, contacto):
    app.include_router(modulo.router)


def _respuesta_error(peticion: Request, estado: int, codigo: str, mensaje: str, detalles=None):
    return JSONResponse(status_code=estado, content={"codigo": codigo, "mensaje": mensaje, "ruta": peticion.url.path, "detalles": detalles})


# Los manejadores son `async` a propósito: uno síncrono corre en un hilo aparte, donde ya no hay
# excepción activa, y `logger.exception` acababa registrando «NoneType: None» en lugar de la traza.
@app.exception_handler(NoAutenticado)
async def manejar_no_autenticado(peticion: Request, exc: NoAutenticado):
    respuesta = _respuesta_error(peticion, status.HTTP_401_UNAUTHORIZED, exc.codigo, exc.mensaje)
    respuesta.headers["WWW-Authenticate"] = "Bearer"
    return respuesta


@app.exception_handler(PermisoDenegado)
async def manejar_permiso_denegado(peticion: Request, exc: PermisoDenegado):
    return _respuesta_error(peticion, status.HTTP_403_FORBIDDEN, exc.codigo, exc.mensaje)


@app.exception_handler(RecursoNoEncontrado)
async def manejar_no_encontrado(peticion: Request, exc: RecursoNoEncontrado):
    return _respuesta_error(peticion, status.HTTP_404_NOT_FOUND, exc.codigo, exc.mensaje)


@app.exception_handler(ConflictoDeNegocio)
async def manejar_conflicto(peticion: Request, exc: ConflictoDeNegocio):
    return _respuesta_error(peticion, status.HTTP_409_CONFLICT, exc.codigo, exc.mensaje)


@app.exception_handler(DemasiadasPeticiones)
async def manejar_demasiadas_peticiones(peticion: Request, exc: DemasiadasPeticiones):
    respuesta = _respuesta_error(peticion, status.HTTP_429_TOO_MANY_REQUESTS, exc.codigo, exc.mensaje)
    respuesta.headers["Retry-After"] = str(exc.segundos_restantes)
    return respuesta


@app.exception_handler(ServicioNoDisponible)
async def manejar_servicio_no_disponible(peticion: Request, exc: ServicioNoDisponible):
    return _respuesta_error(peticion, status.HTTP_503_SERVICE_UNAVAILABLE, exc.codigo, exc.mensaje)


@app.exception_handler(ErrorDeDominio)
async def manejar_error_dominio(peticion: Request, exc: ErrorDeDominio):
    return _respuesta_error(peticion, status.HTTP_400_BAD_REQUEST, exc.codigo, exc.mensaje)


@app.exception_handler(RequestValidationError)
async def manejar_validacion(peticion: Request, exc: RequestValidationError):
    detalles = [{"campo": ".".join(str(p) for p in error["loc"][1:]), "problema": error["msg"]} for error in exc.errors()]
    return _respuesta_error(peticion, status.HTTP_422_UNPROCESSABLE_ENTITY, "datos_invalidos", "Los datos enviados no cumplen el formato esperado.", detalles)


@app.exception_handler(Exception)
async def manejar_error_inesperado(peticion: Request, exc: Exception):
    logger.error("Error no controlado en %s", peticion.url.path, exc_info=exc)
    return _respuesta_error(peticion, status.HTTP_500_INTERNAL_SERVER_ERROR, "error_interno", "Ocurrio un error inesperado. Intente de nuevo mas tarde.")


@app.get("/")
def raiz():
    return {"servicio": configuracion.nombre_app, "version": app.version, "entorno": configuracion.entorno, "documentacion": "/docs"}


@app.get("/salud")
@app.get("/api/health")
def salud():
    return {"estado": "ok"}
