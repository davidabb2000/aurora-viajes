from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from src.core.configuracion import configuracion

# Argon2id es el estándar actual recomendado frente a bcrypt
gestor_de_hash = PasswordHash.recommended()

def hashear_contrasena(contrasena: str) -> str:
    return gestor_de_hash.hash(contrasena)

def verificar_contrasena(contrasena: str, hash_almacenado: str) -> bool:
    return gestor_de_hash.verify(contrasena, hash_almacenado)

def crear_token(usuario_id: int, nombre_rol: str) -> str:
    """Emite un JWT firmado con el ID y el nombre del rol del usuario."""
    ahora = datetime.now(timezone.utc)
    carga = {
        'sub': str(usuario_id),
        'rol': nombre_rol,
        'iat': ahora,
        'exp': ahora + timedelta(minutes=configuracion.minutos_expiracion_token),
    }
    return jwt.encode(
        carga,
        configuracion.secret_key,
        algorithm=configuracion.algoritmo_jwt,
    )

def decodificar_token(token: str) -> dict:
    """Verifica la firma y la expiración del JWT."""
    return jwt.decode(
        token,
        configuracion.secret_key,
        algorithms=[configuracion.algoritmo_jwt],
    )