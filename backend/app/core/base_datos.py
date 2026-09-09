from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.configuracion import configuracion

motor = create_async_engine(
    configuracion.url_base_datos,
    echo=configuracion.depuracion,
    pool_pre_ping=True,
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
