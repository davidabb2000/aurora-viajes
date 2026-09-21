"""Autenticación, roles, recomendaciones y manejo de errores."""

import logging

from app.core.seguridad import crear_token
from tests.conftest import CLAVE_ADMIN, CLAVE_CLIENTE, cuerpo_de_vuelo


def test_login_correcto_devuelve_token_y_usuario(api):
    respuesta = api.post("/api/auth/login", json={"correo": "admin@auroraviajes.com", "contrasena": CLAVE_ADMIN})
    assert respuesta.status_code == 200
    assert respuesta.json()["token"]
    assert respuesta.json()["usuario"]["rol"] == "administrador"


def test_login_con_contrasena_incorrecta(api):
    respuesta = api.post("/api/auth/login", json={"correo": "admin@auroraviajes.com", "contrasena": "incorrecta"})
    assert respuesta.status_code == 401
    assert respuesta.json()["codigo"] == "no_autenticado"


def test_login_de_cuenta_inactiva(api, admin, crear_cliente):
    cliente = crear_cliente()
    api.patch(f"/api/usuarios/{cliente.id}/estado", headers=admin, json={"activo": False})
    respuesta = api.post("/api/auth/login", json={"correo": cliente.correo, "contrasena": CLAVE_CLIENTE})
    assert respuesta.status_code == 401


def test_endpoint_protegido_sin_token(api):
    respuesta = api.get("/api/usuarios")
    assert respuesta.status_code == 401
    assert respuesta.headers["www-authenticate"] == "Bearer"


def test_un_cliente_no_accede_a_recursos_de_administrador(api, crear_cliente):
    respuesta = api.get("/api/usuarios", headers=crear_cliente().headers)
    assert respuesta.status_code == 403
    assert respuesta.json()["codigo"] == "permiso_denegado"


def test_un_token_de_recuperacion_no_abre_sesion(api, crear_cliente):
    cliente = crear_cliente()
    token = crear_token(cliente.id, "cliente", purpose="recuperacion", expiracion_minutos=60)
    assert api.get("/api/reservas/mias", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_invalido(api):
    assert api.get("/api/reservas/mias", headers={"Authorization": "Bearer token-inventado"}).status_code == 401


def test_recomendaciones_usan_el_catalogo_cuando_no_hay_ia(api, crear_cliente):
    respuesta = api.post("/api/destinos/recomendaciones", headers=crear_cliente().headers, json={"intereses": "playa, sol y descanso en el Caribe"})
    datos = respuesta.json()
    assert respuesta.status_code == 200
    assert datos["generada_por"] == "catalogo_local"
    assert len(datos["recomendaciones"]) == 3


def test_un_error_inesperado_registra_la_traza_completa(api, admin, catalogo, monkeypatch, caplog):
    """Regresión: el manejador era síncrono y el log decía «NoneType: None» en lugar de la excepción."""
    def falla(*_):
        raise RuntimeError("fallo de prueba")

    async def falla_async(*_):
        falla()

    monkeypatch.setattr("app.routers.viajes.generar_numero_vuelo", falla_async)
    with caplog.at_level(logging.ERROR):
        respuesta = api.post("/api/vuelos", headers=admin, json=cuerpo_de_vuelo(catalogo, catalogo.bogota, catalogo.paris, "2040-01-01T08:00:00"))
    assert respuesta.status_code == 500
    assert respuesta.json()["codigo"] == "error_interno"
    assert "RuntimeError: fallo de prueba" in caplog.text
