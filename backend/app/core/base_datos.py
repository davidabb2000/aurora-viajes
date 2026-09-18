from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.configuracion import configuracion

_opciones_motor: dict = {
    "echo": configuracion.depuracion,
    "pool_pre_ping": True,
    # Vacio en local; lleva el contexto TLS cuando la base es gestionada.
    "connect_args": configuracion.argumentos_conexion,
}

if configuracion.bd_sin_pool:
    # NullPool abre y cierra la conexion en cada peticion. Sin conexiones
    # ociosas el servicio deja de emitir trafico y puede dormirse.
    _opciones_motor["poolclass"] = NullPool
else:
    # Los hosts gestionados cierran conexiones ociosas: reciclarlas evita
    # el "MySQL server has gone away" tras periodos de inactividad.
    _opciones_motor["pool_recycle"] = 280

motor = create_async_engine(configuracion.url_base_datos, **_opciones_motor)

FabricaDeSesiones = async_sessionmaker(
    bind=motor,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def obtener_sesion() -> AsyncGenerator[AsyncSession, None]:
    async with FabricaDeSesiones() as sesion:
        yield sesion
