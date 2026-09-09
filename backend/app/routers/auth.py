from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.core.configuracion import configuracion
from app.core.seguridad import crear_token, verificar_contrasena
from app.dependencias import SesionDep, SocioActual
from app.errores import NoAutenticado
from app.models.biblioteca import Socio
from app.schemas.auth import SocioAutenticado, Token
from app.schemas.error import DetalleDeError

router = APIRouter(
    prefix='/auth',
    tags=['Autenticación'],
    responses={401: {'model': DetalleDeError}},
)


@router.post(
    '/token',
    response_model=Token,
    summary='Obtener un token de acceso',
    description=(
        'Flujo OAuth2 con contraseña. El campo username corresponde al '
        'número de documento del socio.'
    ),
)
async def iniciar_sesion(
    sesion: SesionDep,
    formulario: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    socio = await sesion.scalar(select(Socio).where(Socio.documento == formulario.username))
    if socio is None or not verificar_contrasena(formulario.password, socio.contrasena_hash):
        raise NoAutenticado('Documento o contraseña incorrectos.')
    if not socio.activo:
        raise NoAutenticado('La cuenta está inactiva.')
    return Token(
        acceso=crear_token(socio_id=socio.id, rol=socio.rol),
        expira_en_segundos=configuracion.minutos_expiracion_token * 60,
    )


@router.get(
    '/yo',
    response_model=SocioAutenticado,
    summary='Datos del socio autenticado',
)
def socio_autenticado(socio: SocioActual):
    return socio
