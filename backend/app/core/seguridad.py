"""Hash de contraseñas y tokens de sesión."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.configuracion import configuracion


gestor_de_hash = PasswordHash.recommended()


def hashear_contrasena(contrasena: str) -> str:
    return gestor_de_hash.hash(contrasena)


def verificar_contrasena(contrasena: str, hash_almacenado: str) -> bool:
    return gestor_de_hash.verify(contrasena, hash_almacenado)


def contrasena_provisional() -> str:
    """Clave aleatoria para cuentas que crea el personal: nadie la conoce, el titular la cambia al entrar."""
    return secrets.token_urlsafe(18) + "aA1!"


def huella_de_contrasena(hash_almacenado: str) -> str:
    """Resumen corto del hash vigente.

    Va dentro del token de recuperación: en cuanto la contraseña cambia, la huella
    deja de coincidir y ese mismo enlace no sirve una segunda vez.
    """
    return hashlib.sha256(hash_almacenado.encode()).hexdigest()[:24]


def crear_token(
    usuario_id: int,
    nombre_rol: str,
    purpose: str = "login",
    expiracion_minutos: int | None = None,
    sesion_version: int = 0,
    huella: str | None = None,
) -> str:
    ahora = datetime.now(timezone.utc)
    minutos = expiracion_minutos if expiracion_minutos is not None else configuracion.minutos_expiracion_token
    carga = {
        "sub": str(usuario_id),
        "id": usuario_id,
        "rol": nombre_rol,
        "purpose": purpose,
        "sv": sesion_version,
        "jti": secrets.token_hex(8),
        "iat": ahora,
        "exp": ahora + timedelta(minutes=minutos),
    }
    if huella is not None:
        carga["pwf"] = huella
    return jwt.encode(carga, configuracion.secret_key, algorithm=configuracion.algoritmo_jwt)


def decodificar_token(token: str) -> dict:
    # `algorithms` fijo: un token con `alg: none` o firmado con otro algoritmo se rechaza.
    return jwt.decode(
        token,
        configuracion.secret_key,
        algorithms=[configuracion.algoritmo_jwt],
        options={"require": ["exp", "iat", "sub"]},
    )
