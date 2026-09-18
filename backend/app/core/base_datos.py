from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.configuracion import configuracion

motor = create_async_engine(
    configuracion.url_base_datos,
    echo=configuracion.depuracion,
    pool_pre_ping=True,
    # Vacio en local; lleva el contexto TLS cuando la base es gestionada.
    connect_args=configuracion.argumentos_conexion,
    # Los hosts gestionados cierran conexiones ociosas: reciclarlas evita
    # el "MySQL server has gone away" tras periodos de inactividad.
    pool_recycle=280,
)

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
