"""Fixtures compartidas por la batería de pruebas.

Las variables de entorno se fijan ANTES de importar la aplicación: los tests no
leen `backend/.env` (que puede traer credenciales reales de Aiven, SMTP, Stripe
o Groq) y trabajan sobre una SQLite temporal.
"""

import itertools
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

os.environ.update({
    "AURORA_ENV_FILE": "",
    "SECRET_KEY": "clave-de-pruebas-" + "x" * 32,
    "MOTOR_BD": "sqlite",
    "SQLITE_PATH": str(Path(tempfile.mkdtemp(prefix="aurora-tests-")) / "pruebas.db"),
    "DATABASE_URL": "",
    "DEPURACION": "false",
    "ADMIN_EMAIL": "admin@auroraviajes.com",
    "ADMIN_PASSWORD": "Admin123!",
    "SMTP_HOST": "",
    "SMTP_USER": "",
    "SMTP_PASSWORD": "",
    "STRIPE_SECRET_KEY": "",
    "STRIPE_WEBHOOK_SECRET": "",
    "PROVEEDOR_IA_API_KEY": "",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.configuracion import configuracion  # noqa: E402

# Salvaguarda: si la configuración apuntara a un servicio real, se aborta antes de arrancar la app.
assert configuracion.url_base_datos.startswith("sqlite"), "Los tests solo pueden usar SQLite"
assert not (configuracion.smtp_host or configuracion.stripe_secret_key or configuracion.proveedor_ia_api_key), (
    "Los tests no deben tener credenciales de SMTP, Stripe ni IA"
)

from app.core.limitador import limitador  # noqa: E402
from app.main import app  # noqa: E402

_contador = itertools.count(1)


@pytest.fixture(scope="session")
def api():
    with TestClient(app, raise_server_exceptions=False) as cliente:
        yield cliente


@pytest.fixture(autouse=True)
def _limitador_limpio():
    """Cada test parte sin intentos previos; el limitador vive en memoria y es global."""
    limitador._eventos.clear()
    yield


@pytest.fixture(scope="session")
def admin(api):
    respuesta = api.post("/api/auth/login", json={"correo": "admin@auroraviajes.com", "contrasena": "Admin123!"})
    assert respuesta.status_code == 200, respuesta.text
    return {"Authorization": f"Bearer {respuesta.json()['token']}"}


@pytest.fixture
def crear_cliente(api):
    """Registra un cliente nuevo y devuelve su id, correo y cabecera de sesión."""

    def _crear():
        n = next(_contador)
        datos = {
            "nombre": "Cliente", "apellido": f"Prueba{n}", "tipoDocumento": "CC",
            "numeroDocumento": str(2_000_000_000 + n), "direccion": "Calle 1 # 2", "telefono": "3001112233",
            "correo": f"cliente{n}@example.com", "contrasena": "Cliente1!",
        }
        assert api.post("/api/usuarios/registro", json=datos).status_code == 201
        respuesta = api.post("/api/auth/login", json={"correo": datos["correo"], "contrasena": datos["contrasena"]})
        assert respuesta.status_code == 200, respuesta.text
        return SimpleNamespace(
            id=respuesta.json()["usuario"]["id"], correo=datos["correo"],
            headers={"Authorization": f"Bearer {respuesta.json()['token']}"},
        )

    return _crear


@pytest.fixture
def viaje(api, admin):
    """Un vuelo, un hotel, excursiones y un paquete de París con fechas relativas a hoy.

    Los datos sembrados llevan fechas fijas que acaban en el pasado; así las
    pruebas no caducan.
    """
    destino = next(d for d in api.get("/api/catalogos/destinos").json() if d["nombre"].startswith("París"))
    salida = date.today() + timedelta(days=45 + next(_contador))
    vuelo = api.post("/api/vuelos", headers=admin, json={
        "aerolinea": "Aurora Airlines", "avion": "Airbus A320", "origen": "Bogotá", "destino": "París",
        "fechaSalida": f"{salida}T08:00:00", "fechaLlegada": f"{salida}T23:00:00",
    })
    assert vuelo.status_code == 201, vuelo.text
    opciones = api.get(f"/api/catalogos/destinos/{destino['id']}/opciones").json()
    hotel = opciones["hoteles"][0]
    excursiones = opciones["excursiones"][:2]
    paquete = api.post("/api/paquetes", headers=admin, json={
        "nombre": f"Paquete de prueba {salida}", "destinoId": destino["id"], "vueloId": vuelo.json()["id"],
        "hotelId": hotel["id"], "excursionIds": [e["id"] for e in excursiones],
        "fechaSalida": str(salida), "fechaRegreso": str(salida + timedelta(days=6)), "precioBase": 1_000_000,
    })
    assert paquete.status_code == 201, paquete.text
    return SimpleNamespace(destino=destino, vuelo=vuelo.json(), hotel=hotel, excursiones=excursiones, paquete=paquete.json(), salida=salida)


def cuerpo_de_reserva(viaje, modo="paquete", pasajeros=2, regreso=None):
    """Cuerpo de POST/PUT /api/reservas para un viaje: `paquete` o `carta`."""
    cuerpo = {
        "origen": "Bogotá", "destinoId": viaje.destino["id"], "vueloId": viaje.vuelo["id"],
        "fechaSalida": str(viaje.salida), "fechaRegreso": str(regreso or viaje.salida + timedelta(days=6)),
        "pasajeros": pasajeros, "telefonoContacto": "3001112233",
    }
    if modo == "paquete":
        cuerpo["paqueteId"] = viaje.paquete["id"]
    else:
        cuerpo["hotelId"] = viaje.hotel["id"]
        cuerpo["excursionIds"] = [e["id"] for e in viaje.excursiones]
    return cuerpo


@pytest.fixture
def reservar(api):
    """reservar(cliente, viaje, modo, pasajeros) -> (id, respuesta JSON)."""

    def _reservar(cliente, viaje, modo="paquete", pasajeros=2):
        respuesta = api.post("/api/reservas", headers=cliente.headers, json=cuerpo_de_reserva(viaje, modo, pasajeros))
        assert respuesta.status_code == 201, respuesta.text
        return respuesta.json()["id"], respuesta.json()

    return _reservar


@pytest.fixture
def venta_de(api, admin):
    """venta_de(reserva_id) -> la venta enlazada a esa reserva, o None."""

    def _venta(reserva_id):
        return next((v for v in api.get("/api/ventas", headers=admin).json() if v["reservaId"] == reserva_id), None)

    return _venta
