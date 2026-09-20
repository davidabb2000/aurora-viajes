"""Inicio de sesión y recuperación de contraseña."""
import logging

import jwt
from fastapi import APIRouter, Request
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.configuracion import configuracion
from app.core.limitador import limitador, limitar
from app.core.seguridad import crear_token, hashear_contrasena, verificar_contrasena
from app.dependencias import SesionDep
from app.errores import NoAutenticado, RecursoNoEncontrado
from app.models.dominio import User
from app.schemas.auth import RecuperarContrasena, RestablecerContrasena, UserLogin
from app.services.correos import enviar_correo_recuperacion
from app.services.serializadores import usuario_sesion_a_dict

logger = logging.getLogger("aurora-viajes")
router = APIRouter(tags=["auth"])


# Hash de una contrasena que nadie usa. Sirve para gastar el mismo tiempo de
# verificacion cuando el correo no existe.
HASH_SENUELO = hashear_contrasena("contrasena-senuelo-sin-uso-real")


@router.post("/api/auth/login")
async def login(payload: UserLogin, peticion: Request, sesion: SesionDep):
    # Dos ventanas: uNA por IP, para frenar el barrido de cuentas, y otra por
    # correo, para que no se pueda machacar una cuenta concreta desde varias IP.
    clave_ip = await limitar(peticion, "login-ip", maximo=10, ventana_segundos=300)
    clave_correo = f"login-correo:{payload.correo.lower()}"
    await limitador.registrar(clave_correo, maximo=5, ventana_segundos=300)

    usuario = await sesion.scalar(select(User).where(User.correo == payload.correo.lower()).options(selectinload(User.role)))
    try:
        if usuario is None:
            # Se verifica igualmente contra un hash de relleno para que la
            # respuesta tarde lo mismo exista o no la cuenta; si no, el tiempo
            # delata que correos estan registrados.
            verificar_contrasena(payload.contrasena, HASH_SENUELO)
            contrasena_valida = False
        else:
            contrasena_valida = usuario.activo and verificar_contrasena(payload.contrasena, usuario.contrasena_hash)
    except Exception as exc:
        logger.warning("No se pudo verificar la contraseña de %s: %s", payload.correo.lower(), exc)
        raise NoAutenticado("Credenciales inválidas o usuario inactivo.") from exc
    if not contrasena_valida:
        raise NoAutenticado("Credenciales inválidas o usuario inactivo.")
    await limitador.limpiar(clave_ip)
    await limitador.limpiar(clave_correo)
    return {"token": crear_token(usuario.id, usuario.role.nombre if usuario.role else "cliente"), "usuario": usuario_sesion_a_dict(usuario)}


@router.post("/api/auth/recuperar")
async def recuperar_contrasena(payload: RecuperarContrasena, peticion: Request, sesion: SesionDep):
    # Sin limite, este endpoint es una ametralladora de correos hacia terceros.
    await limitar(peticion, "recuperar", maximo=3, ventana_segundos=900)
    correo = payload.correo.lower()
    usuario = await sesion.scalar(select(User).where(User.correo == correo).options(selectinload(User.role)))
    if usuario is None:
        return {"mensaje": "Si el correo está registrado, recibirás instrucciones para recuperar tu contraseña."}
    
    # Generar token de recuperación
    token_recuperacion = crear_token(usuario.id, usuario.role.nombre if usuario.role else "cliente", purpose="recuperacion", expiracion_minutos=60)
    
    # Enviar correo (async y no esperamos resultado)
    await enviar_correo_recuperacion(usuario.correo, usuario.nombre, token_recuperacion)
    
    return {"mensaje": "Si el correo está registrado, recibirás instrucciones para recuperar tu contraseña."}


@router.post("/api/auth/restablecer")
async def restablecer_contrasena(payload: RestablecerContrasena, peticion: Request, sesion: SesionDep):
    await limitar(peticion, "restablecer", maximo=5, ventana_segundos=900)
    correo = payload.correo.lower()
    token = payload.token.strip()
    nueva_contrasena = payload.nuevaContrasena
    try:
        decoded = jwt.decode(token, configuracion.secret_key, algorithms=[configuracion.algoritmo_jwt])
    except jwt.ExpiredSignatureError as exc:
        raise NoAutenticado("El token de recuperación no es válido o expiró.") from exc
    except jwt.InvalidTokenError as exc:
        raise NoAutenticado("El token de recuperación no es válido o expiró.") from exc
    if decoded.get("purpose") != "recuperacion":
        raise NoAutenticado("El token no corresponde a recuperación de contraseña.")
    usuario = await sesion.scalar(select(User).where(User.id == decoded.get("id"), User.correo == correo))
    if usuario is None:
        raise RecursoNoEncontrado("un usuario", correo)
    usuario.contrasena_hash = hashear_contrasena(nueva_contrasena)
    await sesion.commit()
    return {"mensaje": "Contraseña actualizada correctamente."}
