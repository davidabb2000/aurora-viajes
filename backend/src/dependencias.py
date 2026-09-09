import jwt
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from src.core.base_datos import obtener_sesion
from src.core.seguridad import decodificar_token
from src.models.viajes import Usuario

SesionDep = Annotated[AsyncSession, Depends(obtener_sesion)]
esquema_oauth2 = OAuth2PasswordBearer(tokenUrl='auth/token')

async def usuario_actual(sesion: SesionDep, token: Annotated[str, Depends(esquema_oauth2)]) -> Usuario:
    try:
        carga = decodificar_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="El token ha expirado. Inicia sesión nuevamente.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="El token no es válido.")
    
    # Cargamos el usuario junto con su rol (Join) gracias a SQLAlchemy
    usuario = await sesion.get(Usuario, int(carga['sub']), options=[joinedload(Usuario.rol)])
    
    if usuario is None or not usuario.activo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="La cuenta no existe o está inactiva.")
    return usuario

async def exigir_agente(usuario: Annotated[Usuario, Depends(usuario_actual)]) -> Usuario:
    """Dependencia para proteger rutas administrativas"""
    if usuario.rol.nombre != 'agente':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso denegado. Esta operación es exclusiva para agentes de viaje.")
    return usuario

# Tipos anotados para inyectar fácilmente en los routers
UsuarioLogueado = Annotated[Usuario, Depends(usuario_actual)]
AgenteLogueado = Annotated[Usuario, Depends(exigir_agente)]