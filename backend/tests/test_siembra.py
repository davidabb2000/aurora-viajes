"""Datos de ejemplo: la programación de vuelos se renueva sola y el arranque no pisa lo ya guardado."""
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

RAIZ = Path(__file__).resolve().parent.parent


def opciones_de(api, destino):
    return api.get(f"/api/catalogos/destinos/{destino['id']}/opciones").json()


def test_todos_los_destinos_tienen_salidas_de_ida_y_de_regreso_futuras(api):
    destinos = api.get("/api/catalogos/destinos").json()
    assert len(destinos) == 10
    for destino in destinos:
        opciones = opciones_de(api, destino)
        assert len(opciones["vuelosIda"]) >= 4, destino["nombre"]
        assert len(opciones["vuelosRegreso"]) >= 4, destino["nombre"]
        assert all(datetime.fromisoformat(v["fechaSalida"]) > datetime.now() for v in opciones["vuelosIda"])
        # Cada salida tiene un vuelo de regreso entre 6 y 8 noches después.
        primera = datetime.fromisoformat(opciones["vuelosIda"][0]["fechaSalida"]).date()
        regresos = {datetime.fromisoformat(v["fechaSalida"]).date() - primera for v in opciones["vuelosRegreso"]}
        assert regresos & {timedelta(days=d) for d in (6, 7, 8)}, destino["nombre"]


def test_los_paquetes_de_ejemplo_apuntan_a_la_proxima_salida_con_su_regreso(api):
    for destino in api.get("/api/catalogos/destinos").json():
        paquetes = [p for p in opciones_de(api, destino)["paquetes"] if p["nombre"].startswith("Aurora ")]
        assert len(paquetes) == 1, destino["nombre"]
        paquete = paquetes[0]
        assert paquete["vueloRegreso"] is not None
        assert date.fromisoformat(paquete["fechaSalida"]) > date.today()
        assert paquete["noches"] == (date.fromisoformat(paquete["fechaRegreso"]) - date.fromisoformat(paquete["fechaSalida"])).days
        assert len(paquete["excursiones"]) == 3


def test_cada_destino_ofrece_hoteles_y_tres_excursiones_de_su_ciudad(api):
    for destino in api.get("/api/catalogos/destinos").json():
        opciones = opciones_de(api, destino)
        assert len(opciones["hoteles"]) >= 2 and len(opciones["excursiones"]) >= 3, destino["nombre"]
        # Todo lo que se ofrece en un destino es de su ciudad, por identificador y no por texto.
        assert {h["ciudadId"] for h in opciones["hoteles"]} == {destino["ciudadId"]}
        assert {e["ciudadId"] for e in opciones["excursiones"]} == {destino["ciudadId"]}


def test_los_hoteles_de_nueva_york_se_pueden_reservar(api, crear_cliente):
    """Regresión: el hotel de Nueva York decía «EE. UU.» y el destino «Estados Unidos»; al comparar
    textos nunca coincidían y no se podía reservar hotel en ese destino."""
    destino = next(d for d in api.get("/api/catalogos/destinos").json() if d["nombre"].startswith("Nueva York"))
    assert destino["nombre"] == "Nueva York, Estados Unidos"
    opciones = opciones_de(api, destino)
    assert "Manhattan Skyline Hotel" in [h["nombre"] for h in opciones["hoteles"]]

    ida = next(v for v in opciones["vuelosIda"] if v["numeroVuelo"] == "AUR309")
    regreso = next(v for v in opciones["vuelosRegreso"] if v["fechaSalida"] > ida["fechaLlegada"])
    cliente = crear_cliente()
    cuerpo = {
        "destinoId": destino["id"], "vueloId": ida["id"], "vueloRegresoId": regreso["id"], "hotelId": opciones["hoteles"][0]["id"],
        "excursiones": [{"id": opciones["excursiones"][0]["id"]}], "pasajeros": 2,
    }
    cotizacion = api.post("/api/reservas/cotizar", headers=cliente.headers, json=cuerpo)
    assert cotizacion.status_code == 200, cotizacion.text
    assert cotizacion.json()["desglose"]["hotel"] > 0


def test_se_reserva_el_paquete_sembrado_de_extremo_a_extremo(api, crear_cliente):
    destino = api.get("/api/catalogos/destinos").json()[0]
    paquete = next(p for p in opciones_de(api, destino)["paquetes"] if p["nombre"].startswith("Aurora "))
    cliente = crear_cliente()
    cuerpo = {"destinoId": destino["id"], "paqueteId": paquete["id"], "pasajeros": 2, "telefonoContacto": "3001112233"}
    reserva = api.post("/api/reservas", headers=cliente.headers, json=cuerpo)
    assert reserva.status_code == 201, reserva.text
    assert reserva.json()["montoTotal"] == paquete["precioBase"] * 2


def _entorno_de(ruta_base: Path, **extra) -> dict:
    entorno = {
        "PATH": "", "SYSTEMROOT": "C:\\Windows", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(RAIZ),
        "AURORA_ENV_FILE": "", "SECRET_KEY": "x" * 40, "MOTOR_BD": "sqlite", "SQLITE_PATH": str(ruta_base),
        "DATABASE_URL": "", "DEPURACION": "false", "ADMIN_PASSWORD": "Admin-Pruebas#2026",
    }
    entorno.update(extra)
    return entorno


def test_el_arranque_es_idempotente_y_no_pisa_lo_guardado():
    """Arrancar dos veces sobre la misma base no duplica nada ni deshace las ediciones del administrador."""
    guion = textwrap.dedent(
        """
        import os, sqlite3, sys
        from fastapi.testclient import TestClient
        from app.main import app

        ruta = os.environ["SQLITE_PATH"]
        TABLAS = ("paises", "ciudades", "destinos", "hoteles", "excursiones", "vuelos", "paquetes", "aerolineas",
                  "modelos_avion", "roles", "permisos", "rol_permisos", "usuarios")

        def contar():
            con = sqlite3.connect(ruta)
            datos = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLAS}
            con.close()
            return datos

        with TestClient(app):
            primero = contar()
            con = sqlite3.connect(ruta)
            con.execute("UPDATE destinos SET precio_base = 12345, activo = 0 WHERE id = 1")
            con.commit()
            con.close()
        with TestClient(app):
            segundo = contar()
        con = sqlite3.connect(ruta)
        editado = con.execute("SELECT precio_base, activo FROM destinos WHERE id = 1").fetchone()
        con.close()
        print(primero == segundo, editado, primero, segundo)
        sys.exit(0 if primero == segundo and tuple(editado) == (12345, 0) else 1)
        """
    )
    with tempfile.TemporaryDirectory() as carpeta:
        resultado = subprocess.run(
            [sys.executable, "-c", guion], env=_entorno_de(Path(carpeta) / "idempotencia.db"),
            cwd=carpeta, capture_output=True, text=True, timeout=240,
        )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr[-2000:]


def test_una_sqlite_de_una_version_anterior_pide_recrearse():
    """La base local antigua no se migra: se avisa con un mensaje claro en lugar de fallar más adelante."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / "antigua.db"
        con = sqlite3.connect(ruta)
        con.execute("CREATE TABLE hoteles (id INTEGER PRIMARY KEY, nombre TEXT, ciudad TEXT, pais TEXT)")
        con.commit()
        con.close()
        guion = "from fastapi.testclient import TestClient\nfrom app.main import app\nwith TestClient(app): pass\n"
        resultado = subprocess.run(
            [sys.executable, "-c", guion], env=_entorno_de(ruta), cwd=carpeta, capture_output=True, text=True, timeout=240,
        )
    assert resultado.returncode != 0
    assert "versión anterior" in resultado.stderr


@pytest.mark.parametrize("fallo", [OSError("Name or service not known"), OperationalError("SELECT 1", {}, Exception("caída"))])
def test_si_la_base_no_responde_el_arranque_lo_explica_y_falla(monkeypatch, caplog, fallo):
    """Sin base de datos la app no arranca, pero el log dice por qué en lugar de dejar solo un 502 en la plataforma."""
    from app.main import app

    async def caida():
        raise fallo

    monkeypatch.setattr("app.main.asegurar_base_inicial", caida)
    with caplog.at_level(logging.CRITICAL, logger="aurora-viajes"):
        with pytest.raises(type(fallo)):
            with TestClient(app):
                pass
    assert "No se pudo conectar con la base de datos" in caplog.text and "DATABASE_URL" in caplog.text
