"""Búsquedas de filas de catálogo y utilidades de texto compartidas por los routers."""
import secrets
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errores import ErrorDeDominio
from app.models.dominio import Destino, EstadoPago, EstadoReserva, MetodoPago, TipoDocumento, Vuelo


async def resolver_tipo_documento_id(sesion: AsyncSession, codigo: str) -> int:
    tipo_documento = await sesion.scalar(select(TipoDocumento).where(TipoDocumento.codigo == codigo))
    if tipo_documento is None:
        raise ErrorDeDominio("Selecciona un tipo de documento válido.")
    return tipo_documento.id


async def resolver_estado_reserva_id(sesion: AsyncSession, codigo: str) -> int:
    estado = await sesion.scalar(select(EstadoReserva).where(EstadoReserva.codigo == codigo))
    if estado is None:
        raise ErrorDeDominio("Estado de reserva no válido.")
    return estado.id


async def resolver_estado_pago_id(sesion: AsyncSession, codigo: str) -> int:
    estado = await sesion.scalar(select(EstadoPago).where(EstadoPago.codigo == codigo))
    if estado is None:
        raise ErrorDeDominio("Estado de pago no válido.")
    return estado.id


async def resolver_metodo_pago_id(sesion: AsyncSession, codigo: str) -> int:
    metodo = await sesion.scalar(select(MetodoPago).where(MetodoPago.codigo == codigo))
    if metodo is None:
        raise ErrorDeDominio("Método de pago no válido.")
    return metodo.id


async def resolver_destino(sesion: AsyncSession, destino: str | None = None, destino_id: int | None = None) -> Destino:
    if destino_id is not None:
        destino_obj = await sesion.get(Destino, destino_id, options=[selectinload(Destino.pais)])
        if destino_obj is not None:
            return destino_obj
    if destino:
        destino_obj = await sesion.scalar(
            select(Destino)
            .where(func.lower(Destino.nombre) == destino.strip().lower())
            .options(selectinload(Destino.pais))
        )
        if destino_obj is not None:
            return destino_obj
    raise ErrorDeDominio("Selecciona un destino válido.")


def normalizar_texto(value: str) -> str:
    texto = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.lower().split())


def puerta_terminal_por_ruta(origen: str, destino: str) -> tuple[str, str]:
    codigo_origen = normalizar_texto(origen)[:3].upper()
    codigo_destino = normalizar_texto(destino)[:3].upper()
    numero_puerta = (sum(ord(caracter) for caracter in codigo_origen + codigo_destino) % 20) + 1
    terminal = "A" if codigo_destino < "M" else "B"
    return f"{terminal}{numero_puerta:02d}", terminal


async def generar_numero_vuelo(sesion: AsyncSession) -> str:
    while True:
        numero = f"AV-{secrets.randbelow(1_000_000):06d}"
        if await sesion.scalar(select(Vuelo.id).where(Vuelo.numero_vuelo == numero)) is None:
            return numero


def ciudad_del_destino(destino: Destino) -> str:
    """Los destinos se nombran "Ciudad, Pais"; devuelve solo la ciudad."""
    return normalizar_texto(destino.nombre.split(",")[0])


def esta_en_el_destino(ciudad: str, pais: str, destino: Destino) -> bool:
    """Comprueba que un hotel o excursion pertenezca al destino del viaje."""
    pais_destino = normalizar_texto(destino.pais.nombre) if destino.pais else ""
    if pais_destino and normalizar_texto(pais) != pais_destino:
        return False
    return normalizar_texto(ciudad) == ciudad_del_destino(destino)
