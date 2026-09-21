from typing import Annotated

import jwt
from fastapi import Depends, Path, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_datos import obtener_sesion
from app.core.seguridad import decodificar_token
from app.errores import CambioDeContrasenaRequerido, NoAutenticado, PermisoDenegado, RecursoNoEncontrado
from app.models.dominio import Reserva, User


SesionDep = Annotated[AsyncSession, Depends(obtener_sesion)]
esquema_oauth2 = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

ROLES_DE_PERSONAL = {"administrador", "empleado"}


async def _usuario_del_token(sesion: AsyncSession, token: str | None) -> User:
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
    try:
        usuario_id = int(carga.get("id") or carga.get("sub"))
    except (TypeError, ValueError):
        raise NoAutenticado("El token no es válido.")
    usuario = await sesion.get(User, usuario_id)
    if usuario is None or not usuario.activo:
        raise NoAutenticado("La cuenta no existe o está inactiva.")
    # Cambiar la contraseña, el rol o cerrar todas las sesiones sube la versión del usuario y
    # deja sin efecto los tokens anteriores, aunque no hayan caducado.
    if int(carga.get("sv", 0)) != usuario.sesion_version:
        raise NoAutenticado("El token ya no es válido: la sesión fue cerrada. Inicia sesión de nuevo.")
    return usuario


async def usuario_autenticado(sesion: SesionDep, token: Annotated[str | None, Depends(esquema_oauth2)]) -> User:
    """El usuario de la sesión, incluso si aún debe cambiar su clave (solo para cambiarla)."""
    return await _usuario_del_token(sesion, token)


async def usuario_actual(usuario: Annotated[User, Depends(usuario_autenticado)]) -> User:
    """El usuario de la sesión. Con una clave provisional solo puede cambiarla, nada más."""
    if usuario.debe_cambiar_contrasena:
        raise CambioDeContrasenaRequerido()
    return usuario


async def exigir_administrador(usuario: Annotated[User, Depends(usuario_actual)]) -> User:
    if usuario.role.nombre != "administrador":
        raise PermisoDenegado("No tiene permiso para realizar esta operación.")
    return usuario


async def exigir_empleado_o_admin(usuario: Annotated[User, Depends(usuario_actual)]) -> User:
    if usuario.role.nombre not in ROLES_DE_PERSONAL:
        raise PermisoDenegado("No tiene permiso para realizar esta operación.")
    return usuario


UsuarioSinRestriccion = Annotated[User, Depends(usuario_autenticado)]
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
    usuario = await sesion.get(User, usuario_id)
    if usuario is None:
        raise RecursoNoEncontrado("un usuario", usuario_id)
    return usuario


UsuarioDeRuta = Annotated[User, Depends(usuario_de_ruta)]


async def reserva_de_ruta(sesion: SesionDep, reserva_id: Annotated[int, Path(ge=1)]) -> Reserva:
    reserva = await sesion.get(Reserva, reserva_id)
    if reserva is None:
        raise RecursoNoEncontrado("una reserva", reserva_id)
    return reserva


ReservaDeRuta = Annotated[Reserva, Depends(reserva_de_ruta)]


def es_personal(usuario: User) -> bool:
    return usuario.role.nombre in ROLES_DE_PERSONAL


def exigir_acceso_a_reserva(usuario: User, reserva: Reserva) -> None:
    """El personal ve todas las reservas; un cliente, solo las suyas.

    Para una reserva ajena se responde «no existe» en lugar de «prohibido»: así no se
    puede recorrer la numeración para averiguar cuáles existen.
    """
    if not es_personal(usuario) and reserva.usuario_id != usuario.id:
        raise RecursoNoEncontrado("una reserva", reserva.id)
