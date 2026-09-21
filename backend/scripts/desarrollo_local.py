"""Arranca el backend para desarrollo con una SQLite local, sin tocar ningún servicio externo.

    python -m scripts.desarrollo_local          # http://127.0.0.1:8001

No lee `backend/.env`: así la base gestionada, el correo, Stripe y la IA no se usan aunque ese archivo tenga
credenciales reales (y el arranque no siembra ni migra la base de producción). La base queda en
`backend/aurora_dev.db`; se puede borrar para empezar de cero. Variables opcionales: PUERTO y ADMIN_PASSWORD.
"""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Todo lo que apunta fuera de esta máquina se vacía antes de importar la aplicación.
SERVICIOS_EXTERNOS = (
    "DATABASE_URL", "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SENDGRID_API_KEY",
    "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "PROVEEDOR_IA_API_KEY",
)


def preparar_entorno() -> None:
    os.environ["AURORA_ENV_FILE"] = ""
    for nombre in SERVICIOS_EXTERNOS:
        os.environ[nombre] = ""
    os.environ["MOTOR_BD"] = "sqlite"
    os.environ["SQLITE_PATH"] = str(RAIZ / "aurora_dev.db")
    os.environ.setdefault("SECRET_KEY", "clave-solo-para-desarrollo-local-" + "x" * 32)
    os.environ.setdefault("ENTORNO", "desarrollo")
    os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")
    # Sin proxy delante, X-Forwarded-For lo escribe cualquiera: se ignora.
    os.environ.setdefault("PROXIES_DE_CONFIANZA", "0")


if __name__ == "__main__":
    preparar_entorno()
    import uvicorn

    puerto = int(os.environ.get("PUERTO", "8001"))
    print(f"Backend de desarrollo (SQLite en {os.environ['SQLITE_PATH']}) en http://127.0.0.1:{puerto}")
    uvicorn.run("app.main:app", host="127.0.0.1", port=puerto)
