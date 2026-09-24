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

CLAVE_ADMIN = "Admin-Pruebas#2026"
CLAVE_CLIENTE = "Viajero#2026x"

os.environ.update({
    "AURORA_ENV_FILE": "",
    "SECRET_KEY": "clave-de-pruebas-" + "x" * 32,
    "MOTOR_BD": "sqlite",
    "SQLITE_PATH": str(Path(tempfile.mkdtemp(prefix="aurora-tests-")) / "pruebas.db"),
    "DATABASE_URL": "",
    "DEPURACION": "false",
    "ADMIN_EMAIL": "admin@auroraviajes.com",
    "ADMIN_PASSWORD": CLAVE_ADMIN,
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


def cabecera(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def letras(n: int) -> str:
    """Un número escrito con letras (0 -> a, 1 -> b...): los apellidos no admiten dígitos."""
    return "".join(chr(97 + int(digito)) for digito in str(n))


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
    respuesta = api.post("/api/auth/login", json={"correo": "admin@auroraviajes.com", "contrasena": CLAVE_ADMIN})
    assert respuesta.status_code == 200, respuesta.text
    return cabecera(respuesta.json()["token"])


@pytest.fixture
def crear_cliente(api):
    """Registra un cliente nuevo y devuelve su id, correo y cabecera de sesión."""

    def _crear():
        n = next(_contador)
        datos = {
            "nombre": "Cliente", "apellido": f"Prueba{letras(n)}", "tipoDocumento": "CC",
            "numeroDocumento": str(2_000_000_000 + n), "direccion": "Calle 1 # 2", "telefono": "3001112233",
            "correo": f"cliente{n}@example.com", "contrasena": CLAVE_CLIENTE, "aceptaTratamientoDatos": True,
        }
        registro = api.post("/api/usuarios/registro", json=datos)
        assert registro.status_code == 201, registro.text
        respuesta = api.post("/api/auth/login", json={"correo": datos["correo"], "contrasena": datos["contrasena"]})
        assert respuesta.status_code == 200, respuesta.text
        return SimpleNamespace(
            id=respuesta.json()["usuario"]["id"], correo=datos["correo"], contrasena=datos["contrasena"],
            token=respuesta.json()["token"], headers=cabecera(respuesta.json()["token"]),
            documento=datos["numeroDocumento"], telefono=datos["telefono"],
        )

    return _crear


@pytest.fixture
def crear_empleado(api, admin):
    """Crea un empleado. El administrador le fija una clave provisional, así que debe cambiarla al entrar."""

    def _crear(rol="empleado"):
        n = next(_contador)
        correo = f"{rol}{n}@auroraviajes.com"
        provisional = "Provisional#2026a"
        creado = api.post("/api/usuarios", headers=admin, json={
            "nombre": "Personal", "apellido": f"Agencia{letras(n)}", "tipoDocumento": "CC", "numeroDocumento": str(3_000_000_000 + n),
            "direccion": "Oficina principal", "telefono": "3005550000", "correo": correo, "contrasena": provisional, "rol": rol,
        })
        assert creado.status_code == 201, creado.text
        entrada = api.post("/api/auth/login", json={"correo": correo, "contrasena": provisional}).json()
        assert entrada["usuario"]["debeCambiarContrasena"] is True
        definitiva = "Definitiva#2026b"
        cambio = api.post("/api/auth/cambiar-contrasena", headers=cabecera(entrada["token"]), json={
            "contrasenaActual": provisional, "nuevaContrasena": definitiva,
        })
        assert cambio.status_code == 200, cambio.text
        return SimpleNamespace(id=entrada["usuario"]["id"], correo=correo, contrasena=definitiva, headers=cabecera(cambio.json()["token"]))

    return _crear


@pytest.fixture(scope="session")
def catalogo(api, admin):
    """Identificadores de las piezas sembradas que las pruebas necesitan."""
    aerolineas = api.get("/api/aerolineas", headers=admin).json()
    modelos = api.get("/api/modelos-avion", headers=admin).json()
    ciudades = api.get("/api/ciudades", headers=admin).json()
    destinos = api.get("/api/catalogos/destinos").json()
    return SimpleNamespace(
        aerolinea=next(a for a in aerolineas if a["nombre"] == "Aurora Airlines"),
        avion=next(m for m in modelos if m["nombre"] == "Airbus A320"),
        bogota=next(c for c in ciudades if c["nombre"] == "Bogotá"),
        madrid=next(c for c in ciudades if c["nombre"] == "Madrid"),
        paris=next(c for c in ciudades if c["nombre"] == "París"),
        kioto=next(c for c in ciudades if c["nombre"] == "Kioto"),
        destino_paris=next(d for d in destinos if d["nombre"].startswith("París")),
        destino_kioto=next(d for d in destinos if d["nombre"].startswith("Kioto")),
    )


def cuerpo_de_vuelo(catalogo, origen, destino, salida, llegada=None, **cambios) -> dict:
    """Cuerpo de POST /api/vuelos. `salida` y `llegada` son fechas y horas ISO sin zona."""
    llegada = llegada or f"{salida[:10]}T23:30:00"
    cuerpo = {
        "aerolineaId": catalogo.aerolinea["id"], "modeloAvionId": catalogo.avion["id"],
        "origenId": origen["id"], "destinoId": destino["id"], "fechaSalida": salida, "fechaLlegada": llegada,
    }
    cuerpo.update(cambios)
    return cuerpo


@pytest.fixture
def viaje(api, admin, catalogo):
    """Vuelos de ida y de regreso, un hotel, excursiones y un paquete de París con fechas relativas a hoy.

    La programación sembrada llega a unos 70 días; estos vuelos salen más adelante y cada prueba usa
    fechas propias, así que nunca chocan entre sí ni con los datos de ejemplo.
    """
    n = next(_contador)
    salida = date.today() + timedelta(days=100 + n)
    regreso = salida + timedelta(days=6)
    ida = api.post("/api/vuelos", headers=admin, json=cuerpo_de_vuelo(catalogo, catalogo.bogota, catalogo.paris, f"{salida}T08:00:00"))
    assert ida.status_code == 201, ida.text
    vuelta = api.post("/api/vuelos", headers=admin, json=cuerpo_de_vuelo(catalogo, catalogo.paris, catalogo.bogota, f"{regreso}T11:00:00"))
    assert vuelta.status_code == 201, vuelta.text
    opciones = api.get(f"/api/catalogos/destinos/{catalogo.destino_paris['id']}/opciones").json()
    hotel = opciones["hoteles"][0]
    excursiones = opciones["excursiones"][:2]
    paquete = api.post("/api/paquetes", headers=admin, json={
        "nombre": f"Paquete de prueba {salida}", "destinoId": catalogo.destino_paris["id"], "vueloId": ida.json()["id"],
        "vueloRegresoId": vuelta.json()["id"], "hotelId": hotel["id"], "excursionIds": [e["id"] for e in excursiones],
        "precioBase": 1_000_000,
    })
    assert paquete.status_code == 201, paquete.text
    return SimpleNamespace(
        destino=catalogo.destino_paris, ida=ida.json(), vuelta=vuelta.json(), hotel=hotel, excursiones=excursiones,
        paquete=paquete.json(), salida=salida, regreso=regreso,
    )


def cuerpo_de_reserva(viaje, modo="paquete", pasajeros=2, **cambios):
    """Cuerpo de POST/PUT /api/reservas para un viaje: `paquete` o `carta`."""
    cuerpo = {"destinoId": viaje.destino["id"], "pasajeros": pasajeros, "telefonoContacto": "3001112233"}
    if modo == "paquete":
        cuerpo["paqueteId"] = viaje.paquete["id"]
    else:
        cuerpo.update(
            vueloId=viaje.ida["id"], vueloRegresoId=viaje.vuelta["id"], hotelId=viaje.hotel["id"],
            excursiones=[{"id": e["id"]} for e in viaje.excursiones],
        )
    cuerpo.update(cambios)
    return cuerpo


@pytest.fixture
def reservar(api):
    """reservar(cliente, viaje, modo, pasajeros) -> (id, respuesta JSON)."""

    def _reservar(cliente, viaje, modo="paquete", pasajeros=2, **cambios):
        respuesta = api.post("/api/reservas", headers=cliente.headers, json=cuerpo_de_reserva(viaje, modo, pasajeros, **cambios))
        assert respuesta.status_code == 201, respuesta.text
        return respuesta.json()["id"], respuesta.json()

    return _reservar


@pytest.fixture
def venta_de(api, admin):
    """venta_de(reserva_id) -> la venta enlazada a esa reserva, o None."""

    def _venta(reserva_id):
        return next((v for v in api.get("/api/ventas", headers=admin).json() if v["reservaId"] == reserva_id), None)

    return _venta


@pytest.fixture
def buzon(monkeypatch):
    """Captura cada correo que la app intenta enviar, en lugar de enviarlo.

    Devuelve la lista de correos como SimpleNamespace(asunto, para, texto, html, adjuntos). Las tareas en
    segundo plano ya terminaron cuando el TestClient devuelve la respuesta, así que se puede mirar enseguida.
    """
    from app.services import correos

    enviados = []

    async def falso(asunto, destinatario, texto, cuerpo_html, adjuntos=None):
        enviados.append(SimpleNamespace(asunto=asunto, para=destinatario, texto=texto, html=cuerpo_html, adjuntos=list(adjuntos or [])))
        return True

    monkeypatch.setattr(correos, "_enviar", falso)
    return enviados
