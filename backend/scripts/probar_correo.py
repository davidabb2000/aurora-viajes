"""Envía un correo de prueba con la configuración actual (API de SendGrid o SMTP).

    python -m scripts.probar_correo destinatario@ejemplo.com

Lee `backend/.env`, así que es la forma de comprobar, antes de desplegar, que las variables SENDGRID_API_KEY o
SMTP_* están bien. No imprime ninguna credencial. Sale con código 0 si el proveedor aceptó el mensaje.
"""
import asyncio
import sys

from app.core.configuracion import configuracion
from app.services.correos import enviar_correo_bienvenida


def proveedor() -> str:
    if configuracion.sendgrid_api_key:
        return "API HTTPS de SendGrid"
    if configuracion.smtp_host and configuracion.smtp_user and configuracion.smtp_password:
        return f"SMTP ({configuracion.smtp_host}:{configuracion.smtp_port})"
    return ""


async def principal(destinatario: str) -> int:
    via = proveedor()
    if not via:
        print("No hay ningún proveedor de correo configurado: define SENDGRID_API_KEY o SMTP_HOST, SMTP_USER y SMTP_PASSWORD.")
        return 1
    print(f"Enviando por {via} desde {configuracion.smtp_from} a {destinatario}...")
    if await enviar_correo_bienvenida(destinatario, "prueba"):
        print("Aceptado por el proveedor. Revisa la bandeja (y la carpeta de spam).")
        return 0
    print("El proveedor no lo aceptó: mira el log de arriba para ver el motivo.")
    return 2


if __name__ == "__main__":
    if len(sys.argv) != 2 or "@" not in sys.argv[1]:
        print("Uso: python -m scripts.probar_correo destinatario@ejemplo.com")
        raise SystemExit(64)
    raise SystemExit(asyncio.run(principal(sys.argv[1])))
