from typing import Annotated

import jwt
from fastapi import Depends, Path, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.base_datos import obtener_sesion
from app.core.seguridad import decodificar_token
from app.errores import NoAutenticado, PermisoDenegado, RecursoNoEncontrado
from app.models.dominio import Destino, Reserva, User


SesionDep = Annotated[AsyncSession, Depends(obtener_sesion)]
esquema_oauth2 = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


async def usuario_actual(
    sesion: SesionDep,
    token: Annotated[str | None, Depends(esquema_oauth2)],
) -> User:
    if not token:
        raise NoAutenticado("Credenciales ausentes o inválidas.")
    try:
        carga = decodificar_token(token)
    except jwt.ExpiredSignatureError:
        raise NoAutenticado("El token expiró. Inicie sesión de nuevo.")
    except jwt.InvalidTokenError:
        raise NoAutenticado("El token no es válido.")
    # Un token de recuperacion viaja en la URL del correo y solo debe servir
    # para restablecer la contrasena; sin esta comprobacion abriria sesion
    # completa en toda la API.
    if carga.get("purpose", "login") != "login":
        raise NoAutenticado("El token no habilita el acceso a la API.")
    usuario_id = carga.get("id") or carga.get("sub")
    try:
        usuario_id = int(usuario_id)
    except (TypeError, ValueError):
        raise NoAutenticado("El token no es válido.")
    usuario = await sesion.get(User, usuario_id, options=[selectinload(User.role), selectinload(User.tipo_documento_catalogo)])
    if usuario is None or not usuario.activo:
        raise NoAutenticado("La cuenta no existe o está inactiva.")
    return usuario


async def exigir_administrador(usuario: Annotated[User, Depends(usuario_actual)]) -> User:
    if usuario.role.nombre != "administrador":
        raise PermisoDenegado("No tiene permiso para realizar esta operación.")
    return usuario


async def exigir_empleado_o_admin(usuario: Annotated[User, Depends(usuario_actual)]) -> User:
    if usuario.role.nombre not in {"administrador", "empleado"}:
        raise PermisoDenegado("No tiene permiso para realizar esta operación.")
    return usuario


UsuarioActual = Annotated[User, Depends(usuario_actual)]
Administrador = Annotated[User, Depends(exigir_administrador)]
EmpleadoOAdmin = Annotated[User, Depends(exigir_empleado_o_admin)]


class Paginacion:
    def __init__(
        self,
        limite: Annotated[int, Query(ge=1, le=100)] = 10,
        desplazamiento: Annotated[int, Query(ge=0)] = 0,
    ):
        self.limite = limite
        self.desplazamiento = desplazamiento


PaginacionDep = Annotated[Paginacion, Depends(Paginacion)]


async def usuario_de_ruta(sesion: SesionDep, usuario_id: Annotated[int, Path(ge=1)]) -> User:
    usuario = await sesion.get(User, usuario_id, options=[selectinload(User.role), selectinload(User.tipo_documento_catalogo)])
    if usuario is None:
        raise RecursoNoEncontrado("un usuario", usuario_id)
    return usuario


UsuarioDeRuta = Annotated[User, Depends(usuario_de_ruta)]


async def reserva_de_ruta(sesion: SesionDep, reserva_id: Annotated[int, Path(ge=1)]) -> Reserva:
    reserva = await sesion.get(
        Reserva,
        reserva_id,
        options=[
            selectinload(Reserva.usuario).selectinload(User.role),
            selectinload(Reserva.usuario).selectinload(User.tipo_documento_catalogo),
            selectinload(Reserva.destino_rel).selectinload(Destino.pais),
            selectinload(Reserva.vuelo_rel),
            selectinload(Reserva.hotel_rel),
            selectinload(Reserva.excursiones),
            selectinload(Reserva.estado_rel),
            selectinload(Reserva.estado_pago_rel),
            selectinload(Reserva.metodo_pago_rel),
        ],
    )
    if reserva is None:
        raise RecursoNoEncontrado("una reserva", reserva_id)
    return reserva


ReservaDeRuta = Annotated[Reserva, Depends(reserva_de_ruta)]


def exigir_acceso_a_reserva(usuario: User, reserva: Reserva) -> None:
    """El personal ve todas las reservas; un cliente, solo las suyas."""
    if usuario.role.nombre not in {"administrador", "empleado"} and reserva.usuario_id != usuario.id:
        raise PermisoDenegado("No tiene permiso para realizar esta operación.")
