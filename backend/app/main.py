"""Aurora Viajes API: punto de entrada.

Aquí solo se ensambla la aplicación: ciclo de vida, middlewares, formato de
errores y routers. La lógica vive en `routers/`, `services/` y `schemas/`.
"""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.base_datos import motor
from app.core import estado_arranque as arranque
from app.core.configuracion import configuracion
from app.core.estado_arranque import es_error_de_conexion, estado_de_arranque
from app.errores import (
    ConflictoDeNegocio,
    DemasiadasPeticiones,
    ErrorDeDominio,
    NoAutenticado,
    PermisoDenegado,
    RecursoNoEncontrado,
    ServicioNoDisponible,
)
from app.middlewares import cabeceras_de_seguridad, exigir_base_lista, limitar_tamano_del_cuerpo, registrar_peticion
from app.routers import auth, catalogo, clientes, comercial, contacto, pagos, pasajeros, recomendaciones, reservas, usuarios, viajes
from app.services.migraciones import MigracionPendiente
from app.services.siembra import asegurar_base_inicial

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("aurora-viajes")


async def _reintentar_preparacion_de_la_base() -> None:
    """Vuelve a preparar la base, con espera creciente, hasta que responda. Los fallos que no son de conexión no se reintentan."""
    espera = arranque.ESPERA_INICIAL
    while True:
        await asyncio.sleep(espera)
        estado_de_arranque.intentos += 1
        try:
            await asegurar_base_inicial()
        except MigracionPendiente as pendiente:
            logger.critical("%s La API responde 503 hasta entonces.", pendiente)
            estado_de_arranque.migracion_pendiente = True
            return
        except Exception as error:  # noqa: BLE001 - se clasifica justo debajo
            if es_error_de_conexion(error):
                estado_de_arranque.ultimo_error = type(error).__name__
                logger.warning("La base de datos sigue sin responder (intento %s: %s). Reintento en %.0f s.", estado_de_arranque.intentos, type(error).__name__, min(espera * 2, arranque.ESPERA_MAXIMA))
                espera = min(espera * 2, arranque.ESPERA_MAXIMA)
                continue
            logger.critical("La preparación de la base falló y no se reintentará; la API seguirá respondiendo 503.", exc_info=True)
            estado_de_arranque.fallo_definitivo = True
            return
        estado_de_arranque.esperando_base = False
        estado_de_arranque.ultimo_error = ""
        logger.info("La base de datos ya responde: la API está lista.")
        return


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    if len(configuracion.secret_key) < 32:
        logger.warning("SECRET_KEY tiene menos de 32 caracteres: genera una más larga (python -c \"import secrets; print(secrets.token_urlsafe(48))\").")
    reintentos = None
    try:
        await asegurar_base_inicial()
    except MigracionPendiente as pendiente:
        # No es un fallo: es una pausa pedida a propósito. Reintentar no serviría (la variable no cambia sola): la API se
        # queda respondiendo 503 y avisando hasta que se active la migración y se reinicie.
        estado_de_arranque.esperando_base = True
        estado_de_arranque.migracion_pendiente = True
        logger.critical("%s La API responde 503 hasta entonces.", pendiente)
    except Exception as error:
        if not es_error_de_conexion(error):
            # Un fallo de la migración o de los datos no se arregla esperando: se cae, y la plataforma conserva la versión anterior.
            logger.critical("No se pudo preparar la base de datos.", exc_info=True)
            raise
        # Sin base la API no puede servir nada, pero se levanta igual: contesta 503 con un mensaje claro y se recupera
        # sola cuando la base vuelva (antes se caía, y la plataforma solo enseñaba un 502 sin explicación).
        estado_de_arranque.esperando_base = True
        estado_de_arranque.ultimo_error = type(error).__name__
        logger.critical(
            "No se pudo conectar con la base de datos (%s). La API responde 503 y reintenta sola. Si es un servicio gestionado "
            "(Aiven, Clever Cloud...), comprueba que esté encendido y que DATABASE_URL sea la correcta.",
            type(error).__name__,
        )
        reintentos = asyncio.create_task(_reintentar_preparacion_de_la_base())
    yield
    if reintentos is not None:
        reintentos.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reintentos
    await motor.dispose()


app = FastAPI(
    title=configuracion.nombre_app,
    description="API de gestión de reservas y viajes.",
    version="1.0.0",
    # La documentación interactiva y el esquema OpenAPI describen toda la API: solo en desarrollo.
    docs_url="/docs" if configuracion.depuracion else None,
    redoc_url="/redoc" if configuracion.depuracion else None,
    openapi_url="/openapi.json" if configuracion.depuracion else None,
    lifespan=ciclo_de_vida,
)
# El último que se añade es el más externo: primero se registra, luego se ponen las cabeceras y por
# último se rechazan los cuerpos enormes (así también la respuesta 413 lleva cabeceras de seguridad).
app.middleware("http")(exigir_base_lista)
app.middleware("http")(limitar_tamano_del_cuerpo)
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

for modulo in (recomendaciones, comercial, auth, usuarios, clientes, catalogo, viajes, reservas, pasajeros, pagos, contacto):
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


def _problema_de(error: dict) -> str:
    """Redacta en español el problema de un campo; las reglas propias ya vienen redactadas."""
    tipo, contexto = str(error.get("type", "")), error.get("ctx") or {}
    if tipo == "value_error":
        return str(error.get("msg", "")).removeprefix("Value error, ")
    if tipo == "missing":
        return "Este campo es obligatorio."
    if tipo == "string_too_short":
        return f"Debe tener al menos {contexto.get('min_length')} caracteres."
    if tipo == "string_too_long":
        return f"No puede superar {contexto.get('max_length')} caracteres."
    if tipo in {"greater_than_equal", "greater_than"}:
        return f"Debe ser al menos {contexto.get('ge', contexto.get('gt'))}."
    if tipo in {"less_than_equal", "less_than"}:
        return f"No puede ser mayor que {contexto.get('le', contexto.get('lt'))}."
    if tipo == "too_long":
        return f"No puede tener más de {contexto.get('max_length')} elementos."
    if tipo in {"literal_error", "enum"}:
        return "Valor no permitido."
    if tipo == "string_pattern_mismatch":
        return "El formato no es válido."
    if tipo.endswith("_parsing") or tipo.endswith("_type") or tipo.startswith("json"):
        return "El valor no tiene el formato esperado."
    return "Valor no válido."


@app.exception_handler(RequestValidationError)
async def manejar_validacion(peticion: Request, exc: RequestValidationError):
    errores = exc.errors()
    detalles = [{"campo": ".".join(str(p) for p in error["loc"][1:]), "problema": _problema_de(error)} for error in errores]
    # Una regla propia (contraseña débil, correo inválido...) ya viene redactada para la persona: se muestra tal cual.
    propios = [detalle for error, detalle in zip(errores, detalles) if error.get("type") == "value_error"]
    if propios:
        mensaje = propios[0]["problema"]
    elif len(detalles) == 1 and detalles[0]["campo"]:
        mensaje = f"{detalles[0]['campo']}: {detalles[0]['problema']}"
    else:
        mensaje = "Los datos enviados no cumplen el formato esperado."
    return _respuesta_error(peticion, status.HTTP_422_UNPROCESSABLE_ENTITY, "datos_invalidos", mensaje, detalles)


@app.exception_handler(IntegrityError)
async def manejar_integridad(peticion: Request, exc: IntegrityError):
    # Una restricción de la base (duplicado, dato en uso) se explica como conflicto, no como error del servidor.
    logger.warning("Violación de integridad en %s: %s", peticion.url.path, exc.orig)
    return _respuesta_error(
        peticion, status.HTTP_409_CONFLICT, "conflicto_de_datos",
        "La operación choca con datos existentes: un duplicado o algo que ya está en uso.",
    )


@app.exception_handler(Exception)
async def manejar_error_inesperado(peticion: Request, exc: Exception):
    logger.error("Error no controlado en %s", peticion.url.path, exc_info=exc)
    return _respuesta_error(peticion, status.HTTP_500_INTERNAL_SERVER_ERROR, "error_interno", "Ocurrio un error inesperado. Intente de nuevo mas tarde.")


@app.get("/")
def raiz():
    datos = {"servicio": configuracion.nombre_app, "version": app.version}
    if configuracion.depuracion:
        datos.update(entorno=configuracion.entorno, documentacion="/docs")
    return datos


@app.get("/salud")
@app.get("/api/health")
def salud():
    """La API está viva. `baseDeDatos` dice si ya puede atender consultas (lista) o si aún espera a la base (sin conexion)."""
    return {"estado": "ok", "baseDeDatos": estado_de_arranque.descripcion}
