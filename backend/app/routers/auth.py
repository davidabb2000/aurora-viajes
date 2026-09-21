"""Inicio de sesión, cambio de contraseña y recuperación."""
import logging

import jwt
from fastapi import APIRouter, BackgroundTasks, Request
from sqlalchemy import select

from app.core.limitador import cliente_de, limitador, limitar
from app.core.politica_contrasena import validar_contrasena
from app.core.seguridad import crear_token, decodificar_token, hashear_contrasena, huella_de_contrasena, verificar_contrasena
from app.dependencias import SesionDep, UsuarioActual, UsuarioSinRestriccion
from app.errores import ErrorDeDominio, NoAutenticado
from app.models.dominio import User
from app.schemas.auth import CambiarContrasena, RecuperarContrasena, RestablecerContrasena, UserLogin
from app.services.correos import enviar_correo_recuperacion
from app.services.serializadores import usuario_sesion_a_dict

logger = logging.getLogger("aurora-viajes")
router = APIRouter(tags=["auth"])

MENSAJE_RECUPERACION = "Si el correo está registrado, recibirás instrucciones para recuperar tu contraseña."
ENLACE_INVALIDO = "El enlace de recuperación no es válido o ya expiró. Solicita uno nuevo."

# Hash de una contrasena que nadie usa. Sirve para gastar el mismo tiempo de
# verificacion cuando el correo no existe.
HASH_SENUELO = hashear_contrasena("contrasena-senuelo-sin-uso-real")


def _sesion_de(usuario: User) -> dict:
    return {
        "token": crear_token(usuario.id, usuario.role.nombre, sesion_version=usuario.sesion_version),
        "usuario": usuario_sesion_a_dict(usuario),
    }


def _exigir_contrasena_valida(usuario: User, nueva: str) -> None:
    try:
        validar_contrasena(nueva, usuario.correo, usuario.nombre, usuario.apellido)
    except ValueError as exc:
        raise ErrorDeDominio(str(exc)) from exc


@router.post("/api/auth/login")
async def login(payload: UserLogin, peticion: Request, sesion: SesionDep):
    # Tres límites que se complementan:
    #  - por IP: frena el barrido de muchas cuentas desde un mismo sitio;
    #  - por correo e IP: frena las pruebas de contraseñas contra una cuenta, y como lleva la IP, quien
    #    quiera bloquear a otra persona solo consigue bloquearse a sí mismo (ella entra desde su IP);
    #  - por correo: tope amplio para el ataque repartido entre muchas IP.
    ip = cliente_de(peticion)
    clave_ip = await limitar(peticion, "login-ip", maximo=10, ventana_segundos=300)
    clave_par = f"login-par:{payload.correo}:{ip}"
    await limitador.registrar(clave_par, maximo=5, ventana_segundos=300)
    clave_correo = f"login-correo:{payload.correo}"
    await limitador.registrar(clave_correo, maximo=20, ventana_segundos=900)

    usuario = await sesion.scalar(select(User).where(User.correo == payload.correo))
    try:
        if usuario is None:
            # Se verifica igualmente contra un hash de relleno para que la
            # respuesta tarde lo mismo exista o no la cuenta; si no, el tiempo
            # delata que correos estan registrados.
            verificar_contrasena(payload.contrasena, HASH_SENUELO)
            contrasena_valida = False
        else:
            contrasena_valida = verificar_contrasena(payload.contrasena, usuario.contrasena_hash) and usuario.activo
    except Exception as exc:
        logger.warning("No se pudo verificar la contraseña de un usuario: %s", exc)
        raise NoAutenticado("Credenciales inválidas o usuario inactivo.") from exc
    if not contrasena_valida:
        raise NoAutenticado("Credenciales inválidas o usuario inactivo.")
    for clave in (clave_ip, clave_par, clave_correo):
        await limitador.limpiar(clave)
    return _sesion_de(usuario)


@router.get("/api/auth/yo")
async def quien_soy(usuario: UsuarioSinRestriccion):
    """Datos vigentes de la sesión: el frontend los usa para saber si la cuenta cambió (rol, estado, clave provisional)."""
    return usuario_sesion_a_dict(usuario)


@router.post("/api/auth/cambiar-contrasena")
async def cambiar_contrasena(payload: CambiarContrasena, peticion: Request, usuario: UsuarioSinRestriccion, sesion: SesionDep):
    await limitar(peticion, "cambiar-contrasena", maximo=10, ventana_segundos=900)
    await limitador.registrar(f"cambiar-contrasena:{usuario.id}", maximo=5, ventana_segundos=900)
    # Sin esta comprobación, un token robado bastaría para adueñarse de la cuenta cambiando su clave.
    if not verificar_contrasena(payload.contrasenaActual, usuario.contrasena_hash):
        raise ErrorDeDominio("La contraseña actual no es correcta.")
    if payload.nuevaContrasena == payload.contrasenaActual:
        raise ErrorDeDominio("La nueva contraseña debe ser distinta de la actual.")
    _exigir_contrasena_valida(usuario, payload.nuevaContrasena)
    usuario.contrasena_hash = hashear_contrasena(payload.nuevaContrasena)
    usuario.debe_cambiar_contrasena = False
    usuario.sesion_version += 1  # cierra las demás sesiones abiertas con la clave anterior
    await sesion.commit()
    return {"mensaje": "Contraseña actualizada correctamente.", **_sesion_de(usuario)}


@router.post("/api/auth/cerrar-sesiones")
async def cerrar_todas_las_sesiones(usuario: UsuarioActual, sesion: SesionDep):
    """Invalida todos los tokens emitidos hasta ahora (útil si se perdió un dispositivo)."""
    usuario.sesion_version += 1
    await sesion.commit()
    return {"mensaje": "Se cerraron todas las sesiones."}


@router.post("/api/auth/recuperar")
async def recuperar_contrasena(payload: RecuperarContrasena, peticion: Request, sesion: SesionDep, tareas: BackgroundTasks):
    # Sin limite, este endpoint es una ametralladora de correos hacia terceros: se limita por IP y
    # también por destinatario, para que nadie llene el buzón de una persona desde muchas IP.
    await limitar(peticion, "recuperar", maximo=5, ventana_segundos=900)
    await limitador.registrar(f"recuperar-correo:{payload.correo}", maximo=3, ventana_segundos=3600)
    usuario = await sesion.scalar(select(User).where(User.correo == payload.correo))
    if usuario is not None and usuario.activo:
        token = crear_token(
            usuario.id, usuario.role.nombre, purpose="recuperacion", expiracion_minutos=60,
            huella=huella_de_contrasena(usuario.contrasena_hash),
        )
        # El correo se envía después de responder: así la respuesta tarda igual exista o no la cuenta.
        tareas.add_task(enviar_correo_recuperacion, usuario.correo, usuario.nombre, token)
    return {"mensaje": MENSAJE_RECUPERACION}


@router.post("/api/auth/restablecer")
async def restablecer_contrasena(payload: RestablecerContrasena, peticion: Request, sesion: SesionDep):
    await limitar(peticion, "restablecer", maximo=10, ventana_segundos=900)
    try:
        carga = decodificar_token(payload.token.strip())
    except jwt.InvalidTokenError as exc:
        raise ErrorDeDominio(ENLACE_INVALIDO) from exc
    if carga.get("purpose") != "recuperacion":
        raise ErrorDeDominio(ENLACE_INVALIDO)
    try:
        usuario = await sesion.get(User, int(carga.get("id")))
    except (TypeError, ValueError) as exc:
        raise ErrorDeDominio(ENLACE_INVALIDO) from exc
    if usuario is None or not usuario.activo:
        raise ErrorDeDominio(ENLACE_INVALIDO)
    # El enlace lleva la huella de la contraseña vigente cuando se pidió: tras usarlo la clave cambia,
    # la huella ya no coincide y el mismo enlace no sirve dos veces.
    if carga.get("pwf") != huella_de_contrasena(usuario.contrasena_hash):
        raise ErrorDeDominio(ENLACE_INVALIDO)
    _exigir_contrasena_valida(usuario, payload.nuevaContrasena)
    usuario.contrasena_hash = hashear_contrasena(payload.nuevaContrasena)
    usuario.debe_cambiar_contrasena = False
    usuario.sesion_version += 1
    await sesion.commit()
    return {"mensaje": "Contraseña actualizada correctamente. Ya puedes iniciar sesión."}
