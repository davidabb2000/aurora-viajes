from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.configuracion import configuracion


gestor_de_hash = PasswordHash.recommended()


def hashear_contrasena(contrasena: str) -> str:
    return gestor_de_hash.hash(contrasena)


def verificar_contrasena(contrasena: str, hash_almacenado: str) -> bool:
    return gestor_de_hash.verify(contrasena, hash_almacenado)


def crear_token(usuario_id: int, nombre_rol: str, purpose: str = "login", expiracion_minutos: int | None = None) -> str:
    ahora = datetime.now(timezone.utc)
    minutos = expiracion_minutos if expiracion_minutos is not None else configuracion.minutos_expiracion_token
    carga = {
        "sub": str(usuario_id),
        "id": usuario_id,
        "rol": nombre_rol,
        "purpose": purpose,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=minutos),
    }
    return jwt.encode(carga, configuracion.secret_key, algorithm=configuracion.algoritmo_jwt)


def decodificar_token(token: str) -> dict:
    return jwt.decode(token, configuracion.secret_key, algorithms=[configuracion.algoritmo_jwt])
