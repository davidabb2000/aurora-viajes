from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from pydantic import BaseModel

from src.dependencias import SesionDep, UsuarioLogueado
from src.core.seguridad import crear_token, verificar_contrasena
from src.models.viajes import Usuario

router = APIRouter(prefix='/auth', tags=['Autenticación'])

class TokenRespuesta(BaseModel):
    acceso: str
    tipo: str = 'bearer'

@router.post('/token', response_model=TokenRespuesta, summary="Iniciar sesión")
async def iniciar_sesion(
    sesion: SesionDep, 
    formulario: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    # En OAuth2 el campo por defecto se llama 'username', pero nosotros usamos el 'documento'
    consulta = select(Usuario).options(joinedload(Usuario.rol)).where(Usuario.documento == formulario.username)
    usuario = await sesion.scalar(consulta)
    
    if not usuario or not verificar_contrasena(formulario.password, usuario.contrasena_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Documento o contraseña incorrectos."
        )
    
    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="La cuenta está inactiva."
        )
        
    token = crear_token(usuario_id=usuario.id, nombre_rol=usuario.rol.nombre)
    return TokenRespuesta(acceso=token)

@router.get('/yo', summary="Ver perfil actual")
async def perfil_usuario(usuario: UsuarioLogueado):
    return usuario