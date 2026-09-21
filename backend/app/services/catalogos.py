"""Búsquedas de filas de catálogo y utilidades compartidas por los routers y los servicios."""
import secrets
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errores import ErrorDeDominio
from app.models.dominio import Destino, EstadoPago, EstadoReserva, MetodoPago, TipoDocumento, Vuelo


def ahora() -> datetime:
    """Hora actual como fecha «ingenua» en UTC, comparable con las que devuelve la base de datos.

    Las horas de los vuelos se guardan como hora local del aeropuerto, sin zona; compararlas con
    la hora UTC adelanta el cierre de ventas unas horas, que es el lado seguro para no vender un
    vuelo que ya salió.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def sin_zona(momento: datetime) -> datetime:
    """Quita la zona horaria de una fecha para poder compararla con las de la base de datos."""
    return momento.replace(tzinfo=None) if momento.tzinfo else momento


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


async def resolver_destino(sesion: AsyncSession, destino_id: int) -> Destino:
    """Un destino activo por su id. La ciudad y el país se cargan junto con él."""
    destino = await sesion.get(Destino, destino_id)
    if destino is None or not destino.activo:
        raise ErrorDeDominio("Selecciona un destino válido.")
    return destino


def normalizar_texto(value: str) -> str:
    """Minúsculas, sin tildes y con espacios simples: para comparar nombres escritos de formas distintas."""
    texto = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.lower().split())


def escapar_like(texto: str) -> str:
    """Escapa los comodines de LIKE para que una búsqueda literal no se comporte como patrón."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


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
