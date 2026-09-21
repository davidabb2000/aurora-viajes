"""Reglas de contraseña y de correo compartidas por el registro, el cambio y la recuperación.

El frontend repite estas reglas para avisar mientras se escribe, pero solo estas
cuentan: el servidor las aplica siempre.
"""

import re
import unicodedata

LONGITUD_MINIMA = 8
LONGITUD_MAXIMA = 128  # sin tope, una contraseña de megabytes se convierte en un ataque al hash

# Claves que aparecen en todos los listados de filtraciones. Cumplen las reglas de composición
# (mayúscula, número, símbolo), por eso hay que rechazarlas por nombre.
CONTRASENAS_COMUNES = frozenset(
    {
        "password1!", "password123!", "contrasena1!", "contraseña1!", "admin123!", "admin1234!",
        "qwerty123!", "qwerty12345!", "abc12345!", "abcd1234!", "welcome1!", "welcome123!",
        "passw0rd!", "p@ssw0rd", "p@ssword1", "p@ssw0rd1", "changeme1!", "letmein123!",
        "123456789a!", "colombia123!", "medellin123!", "aurora123!", "aurora2026!", "viajes123!",
        "iloveyou1!", "monkey123!", "dragon123!", "football1!", "sunshine1!", "princess1!",
    }
)

REGEX_CORREO = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def _simplificar(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", sin_acentos.lower())


def normalizar_correo(valor: str) -> str:
    """Correo en minúsculas y sin espacios, o ValueError si no tiene una forma válida.

    La expresión no admite espacios ni saltos de línea: es lo que evita colar
    cabeceras extra («a@b.com\\nBcc: ...») en el correo que se envía a esa dirección.
    """
    limpio = valor.strip().lower()
    if len(limpio) > 60 or not REGEX_CORREO.match(limpio):
        raise ValueError("Correo electrónico inválido.")
    return limpio


def validar_contrasena(contrasena: str, correo: str | None = None, nombre: str | None = None, apellido: str | None = None) -> str:
    """Devuelve la contraseña si es aceptable; si no, lanza ValueError con el motivo en español."""
    if len(contrasena) < LONGITUD_MINIMA:
        raise ValueError(f"La contraseña debe tener al menos {LONGITUD_MINIMA} caracteres.")
    if len(contrasena) > LONGITUD_MAXIMA:
        raise ValueError(f"La contraseña no puede superar {LONGITUD_MAXIMA} caracteres.")
    if contrasena != contrasena.strip():
        raise ValueError("La contraseña no puede empezar ni terminar con espacios.")
    if not any(c.islower() for c in contrasena) or not any(c.isupper() for c in contrasena):
        raise ValueError("La contraseña debe combinar mayúsculas y minúsculas.")
    if not any(c.isdigit() for c in contrasena):
        raise ValueError("La contraseña debe incluir al menos un número.")
    if not any(not c.isalnum() for c in contrasena):
        raise ValueError("La contraseña debe incluir al menos un carácter especial.")
    if contrasena.lower() in CONTRASENAS_COMUNES:
        raise ValueError("Esa contraseña es demasiado común. Elige otra.")
    simple = _simplificar(contrasena)
    if correo:
        parte_local = _simplificar(correo.split("@")[0])
        if len(parte_local) >= 4 and parte_local in simple:
            raise ValueError("La contraseña no puede contener tu correo.")
    for dato in (nombre, apellido):
        if dato and len(_simplificar(dato)) >= 4 and _simplificar(dato) in simple:
            raise ValueError("La contraseña no puede contener tu nombre.")
    return contrasena
