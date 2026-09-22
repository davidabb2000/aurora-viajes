"""Arranque sin base de datos: la API se levanta, contesta 503 con un mensaje claro y se recupera sola."""
import asyncio
import socket
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core import estado_arranque
from app.core.configuracion import configuracion
from app.core.estado_arranque import es_error_de_conexion, estado_de_arranque
from app.main import app
from app.services import migraciones
from app.services.migraciones import MigracionPendiente, migrar_esquema
from tests.test_siembra import _entorno_de


def sin_conexion() -> OperationalError:
    """Lo que SQLAlchemy lanza cuando aiomysql no llega al servidor (código 2003 de MySQL)."""
    return OperationalError("SELECT 1", {}, Exception(2003, "Can't connect to MySQL server"))


@pytest.fixture(autouse=True)
def _espera_corta_y_estado_limpio(monkeypatch):
    monkeypatch.setattr(estado_arranque, "ESPERA_INICIAL", 0.02)
    monkeypatch.setattr(estado_arranque, "ESPERA_MAXIMA", 0.05)
    yield
    estado_de_arranque.esperando_base = False
    estado_de_arranque.fallo_definitivo = False
    estado_de_arranque.migracion_pendiente = False
    estado_de_arranque.ultimo_error = ""
    estado_de_arranque.intentos = 0


def esperar_a(condicion, limite=10.0):
    import time

    fin = time.monotonic() + limite
    while time.monotonic() < fin:
        if condicion():
            return True
        time.sleep(0.03)
    return False


@pytest.mark.parametrize(
    ("error", "esperado"),
    [
        (OSError("Name or service not known"), True),
        (socket.gaierror(-2, "Name or service not known"), True),
        (sin_conexion(), True),
        (OperationalError("SELECT 1", {}, Exception(2006, "MySQL server has gone away")), True),
        (OperationalError("SELECT x", {}, Exception(1054, "Unknown column 'x'")), False),
        (OperationalError("SELECT 1", {}, Exception("caída")), False),
        (RuntimeError("La base de datos es de una versión muy antigua"), False),
        (ValueError("dato inválido"), False),
    ],
)
def test_solo_los_fallos_de_conexion_se_consideran_pasajeros(error, esperado):
    assert es_error_de_conexion(error) is esperado


def test_el_detalle_del_error_cuenta_lo_que_dijo_el_controlador_y_no_la_consulta():
    del_controlador = Exception(2003, "Can't connect to MySQL server on 'db.ejemplo'")
    del_controlador.__cause__ = socket.gaierror(-2, "Name or service not known")
    envuelto = OperationalError("SELECT secreto FROM tabla WHERE clave = %s", {"clave": "hunter2"}, del_controlador)

    detalle = estado_arranque.detalle_del_error(envuelto)
    assert "2003" in detalle and "Can't connect to MySQL server on 'db.ejemplo'" in detalle
    assert "Name or service not known" in detalle
    assert "SELECT" not in detalle and "hunter2" not in detalle
    assert estado_arranque.detalle_del_error(ValueError("dato inválido")) == "ValueError('dato inválido',)"
    assert len(estado_arranque.detalle_del_error(OSError("x" * 2000))) <= 400


def test_sin_base_la_api_se_levanta_y_contesta_503(monkeypatch, caplog):
    async def caida():
        raise socket.gaierror(-2, "Name or service not known")

    monkeypatch.setattr("app.main.asegurar_base_inicial", caida)
    with TestClient(app) as cliente:
        salud = cliente.get("/api/health")
        assert salud.status_code == 200
        assert salud.json() == {"estado": "ok", "baseDeDatos": "sin conexion"}

        bloqueada = cliente.get("/api/catalogos/destinos", headers={"Origin": "http://localhost:5173"})
        assert bloqueada.status_code == 503
        assert bloqueada.json()["codigo"] == "servicio_no_disponible"
        assert "no está disponible" in bloqueada.json()["mensaje"]
        assert bloqueada.headers["retry-after"] == "30"
        # El navegador debe poder leer el 503 (si no, el frontend solo vería un fallo de CORS) y la respuesta lleva las cabeceras de siempre.
        assert bloqueada.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert bloqueada.headers["x-content-type-options"] == "nosniff"
        # También se rechazan las escrituras y las rutas con sesión, sin llegar a tocar la base.
        assert cliente.post("/api/auth/login", json={"correo": "a@b.com", "contrasena": "x"}).status_code == 503
        # La comprobación previa de CORS (OPTIONS) no depende de la base.
        assert cliente.options("/api/auth/login", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"}).status_code == 200
    assert "No se pudo conectar con la base de datos" in caplog.text and "DATABASE_URL" in caplog.text


def test_un_fallo_que_no_es_de_conexion_sigue_tumbando_el_arranque(monkeypatch):
    """Una migración fallida o unos datos que no cuadran no se arreglan esperando: la app se cae y la plataforma conserva la versión anterior."""
    async def rota():
        raise RuntimeError("La base de datos es de una versión muy antigua")

    monkeypatch.setattr("app.main.asegurar_base_inicial", rota)
    with pytest.raises(RuntimeError, match="muy antigua"):
        with TestClient(app):
            pass
    assert estado_de_arranque.esperando_base is False


def test_si_al_reintentar_falla_algo_que_no_es_la_conexion_no_se_sigue_reintentando(monkeypatch):
    llamadas = []

    async def primero_cae_la_red_luego_los_datos():
        llamadas.append(1)
        raise sin_conexion() if len(llamadas) == 1 else ValueError("los datos no cuadran")

    monkeypatch.setattr("app.main.asegurar_base_inicial", primero_cae_la_red_luego_los_datos)
    with TestClient(app) as cliente:
        assert esperar_a(lambda: cliente.get("/api/health").json()["baseDeDatos"] == "error")
        assert cliente.get("/api/catalogos/destinos").status_code == 503
    assert len(llamadas) == 2


def test_la_api_se_recupera_sola_cuando_la_base_vuelve():
    """Con una base real (SQLite temporal): tres intentos sin conexión, el cuarto la encuentra, y todo funciona sin reiniciar."""
    guion = textwrap.dedent(
        """
        import json, sys, time
        from fastapi.testclient import TestClient
        from sqlalchemy.exc import OperationalError
        from app.core import estado_arranque
        from app.main import app
        import app.main as principal

        estado_arranque.ESPERA_INICIAL = 0.02
        estado_arranque.ESPERA_MAXIMA = 0.05
        real = principal.asegurar_base_inicial
        llamadas = []

        async def intermitente():
            llamadas.append(1)
            if len(llamadas) <= 3:
                raise OperationalError("SELECT 1", {}, Exception(2003, "Can't connect to MySQL server"))
            await real()

        principal.asegurar_base_inicial = intermitente
        resultado = {}
        with TestClient(app) as cliente:
            resultado["antes"] = [cliente.get("/api/health").json()["baseDeDatos"], cliente.get("/api/catalogos/destinos").status_code]
            fin = time.monotonic() + 30
            while cliente.get("/api/health").json()["baseDeDatos"] != "lista" and time.monotonic() < fin:
                time.sleep(0.05)
            resultado["despues"] = [cliente.get("/api/health").json()["baseDeDatos"], cliente.get("/api/catalogos/destinos").status_code, len(cliente.get("/api/catalogos/destinos").json())]
        resultado["llamadas"] = len(llamadas)
        print("RESULTADO", json.dumps(resultado))
        """
    )
    with tempfile.TemporaryDirectory() as carpeta:
        proceso = subprocess.run(
            [sys.executable, "-c", guion], env=_entorno_de(Path(carpeta) / "recuperacion.db"),
            cwd=carpeta, capture_output=True, text=True, timeout=240,
        )
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr[-2000:]
    linea = next(l for l in proceso.stdout.splitlines() if l.startswith("RESULTADO"))
    import json

    resultado = json.loads(linea.removeprefix("RESULTADO "))
    assert resultado["antes"] == ["sin conexion", 503]
    assert resultado["despues"] == ["lista", 200, 10]
    assert resultado["llamadas"] == 4


# --------------------------------------------------------------------------------------
# MIGRACION_AUTOMATICA: pausa para hacer una copia antes de migrar una base real
# --------------------------------------------------------------------------------------


class SesionMySQLFalsa:
    """Lo mínimo de una sesión que `migrar_esquema` toca hasta llegar a la puerta: MySQL, versión aplicada y si hay datos."""

    def __init__(self, version=0, hay_datos=True):
        self.bind = SimpleNamespace(dialect=SimpleNamespace(name="mysql"))
        self.info = {}
        self._respuestas = [version, 1 if hay_datos else 0]

    async def scalar(self, consulta, parametros=None):
        return self._respuestas.pop(0)


def correr(sesion):
    return asyncio.run(migrar_esquema(sesion))


@pytest.fixture
def primer_paso_de_la_migracion(monkeypatch):
    """Sustituye el primer paso real de la migración por una señal, para saber si se llegó a él."""
    async def senal(sesion):
        raise RuntimeError("se empezó a migrar")

    monkeypatch.setattr(migraciones, "_migrar_a_v1", senal)


def test_con_la_migracion_automatica_apagada_una_base_con_datos_no_se_toca(monkeypatch):
    monkeypatch.setattr(configuracion, "migracion_automatica", False)
    with pytest.raises(MigracionPendiente, match="MIGRACION_AUTOMATICA"):
        correr(SesionMySQLFalsa(version=0, hay_datos=True))


def test_una_base_sin_datos_se_migra_aunque_la_migracion_automatica_este_apagada(monkeypatch, primer_paso_de_la_migracion):
    monkeypatch.setattr(configuracion, "migracion_automatica", False)
    with pytest.raises(RuntimeError, match="se empezó a migrar"):
        correr(SesionMySQLFalsa(version=0, hay_datos=False))


def test_con_la_migracion_automatica_encendida_se_migra_una_base_con_datos(monkeypatch, primer_paso_de_la_migracion):
    monkeypatch.setattr(configuracion, "migracion_automatica", True)
    with pytest.raises(RuntimeError, match="se empezó a migrar"):
        correr(SesionMySQLFalsa(version=0, hay_datos=True))


def test_una_base_ya_migrada_no_se_toca_ni_se_consulta_de_mas(monkeypatch, primer_paso_de_la_migracion):
    monkeypatch.setattr(configuracion, "migracion_automatica", False)
    sesion = SesionMySQLFalsa(version=migraciones.VERSION_DEL_ESQUEMA, hay_datos=True)
    correr(sesion)  # no lanza nada: con la marca puesta no hay nada que migrar
    assert sesion._respuestas == [1]  # solo se preguntó por la versión


def test_la_api_espera_la_migracion_sin_reintentar_y_lo_dice(monkeypatch, caplog):
    llamadas = []

    async def pendiente():
        llamadas.append(1)
        raise MigracionPendiente("La base necesita migrarse, pero MIGRACION_AUTOMATICA está en false.")

    monkeypatch.setattr("app.main.asegurar_base_inicial", pendiente)
    with TestClient(app) as cliente:
        assert cliente.get("/api/health").json() == {"estado": "ok", "baseDeDatos": "migracion pendiente"}
        assert cliente.get("/api/catalogos/destinos").status_code == 503
        esperar_a(lambda: False, limite=0.3)  # da tiempo a un reintento, que no debe ocurrir
    assert len(llamadas) == 1
    assert "MIGRACION_AUTOMATICA" in caplog.text


def test_si_la_migracion_pendiente_aparece_al_reintentar_tambien_se_queda_en_espera(monkeypatch):
    llamadas = []

    async def primero_sin_red_luego_pendiente():
        llamadas.append(1)
        raise sin_conexion() if len(llamadas) == 1 else MigracionPendiente("Falta hacer la copia.")

    monkeypatch.setattr("app.main.asegurar_base_inicial", primero_sin_red_luego_pendiente)
    with TestClient(app) as cliente:
        assert esperar_a(lambda: cliente.get("/api/health").json()["baseDeDatos"] == "migracion pendiente")
        assert cliente.get("/api/catalogos/destinos").status_code == 503
    assert len(llamadas) == 2
