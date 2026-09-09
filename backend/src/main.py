import logging
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.configuracion import configuracion
from src.core.base_datos import motor, Base
from src.routers import auth, reservas, inteligencia, paquetes, auditoria
from src.services.recomendaciones import ServicioDeRecomendaciones
from src.services.riesgo import ServicioDeRiesgo

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s | %(message)s')
logger = logging.getLogger('aurora-viajes')

@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    logger.info("Verificando base de datos...")
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    
    app.state.cliente_http = httpx.AsyncClient()
    app.state.ia = ServicioDeRecomendaciones(app.state.cliente_http)
    app.state.riesgo = ServicioDeRiesgo()
    
    yield
    
    logger.info("Apagando servicios y motor de base de datos...")
    await app.state.cliente_http.aclose()
    await motor.dispose()

# 1. PRIMERO SE CREA LA INSTANCIA DE LA APLICACIÓN
app = FastAPI(
    title=configuracion.nombre_app,
    description="API para gestión de reservas y viajes con IA.",
    version="1.0.0",
    lifespan=ciclo_de_vida
)

# 2. SE CONFIGURAN LOS MIDDLEWARES
app.add_middleware(
    CORSMiddleware,
    allow_origins=configuracion.origenes_permitidos,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def cabeceras_seguridad(request, call_next):
    respuesta = await call_next(request)
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    return respuesta

# 3. DESPUÉS SE REGISTRAN LOS ROUTERS USANDO 'app'
app.include_router(auth.router)
app.include_router(reservas.router)
app.include_router(inteligencia.router)
app.include_router(paquetes.router)
app.include_router(auditoria.router)

@app.get("/salud", tags=['Sistema'])
async def estado_del_servicio():
    return {"estado": "ok", "entorno": configuracion.entorno}