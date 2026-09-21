"""Seguridad: inyección SQL, tokens manipulados, suplantación de IP, cabeceras, tamaño de cuerpo, CORS y SQL estático."""
import ast
import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest

from app.core.configuracion import configuracion
from tests.conftest import CLAVE_CLIENTE, cabecera

RAIZ_APP = Path(__file__).resolve().parent.parent / "app"

CARGAS_SQL = [
    "' OR '1'='1",
    "' OR 1=1 --",
    '" OR ""="',
    "'; DROP TABLE usuarios; --",
    "1; DELETE FROM reservas",
    "' UNION SELECT contrasena_hash FROM usuarios --",
    "admin'--",
    "%' OR '1'='1",
    "\\",
    "'",
    "1' AND SLEEP(5) --",
    "') OR ('1'='1",
]


def b64(datos: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(datos).encode()).rstrip(b"=").decode()


def carga_de(usuario_id: int, **cambios) -> dict:
    ahora = datetime.now(timezone.utc)
    carga = {"sub": str(usuario_id), "id": usuario_id, "rol": "cliente", "purpose": "login", "sv": 0, "iat": ahora, "exp": ahora + timedelta(minutes=30)}
    carga.update(cambios)
    return carga


# --------------------------------------------------------------------------------------
# Inyección SQL
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("carga", CARGAS_SQL)
def test_las_cargas_sql_no_dan_acceso_por_el_login(api, carga):
    # En el correo: no es una dirección válida, ni siquiera llega a la base de datos.
    en_correo = api.post("/api/auth/login", json={"correo": f"admin@auroraviajes.com{carga}", "contrasena": "x"})
    assert en_correo.status_code in (401, 422), en_correo.text
    # En la contraseña: se compara con un hash, no se concatena en ninguna consulta.
    en_clave = api.post("/api/auth/login", json={"correo": "admin@auroraviajes.com", "contrasena": carga})
    assert en_clave.status_code == 401
    assert "token" not in en_clave.text


@pytest.mark.parametrize("carga", CARGAS_SQL)
def test_las_cargas_sql_en_busquedas_no_devuelven_datos_ni_rompen(api, admin, carga):
    for ruta, parametro in (("/api/clientes", "q"), ("/api/reservas", "q"), ("/api/facturas", "numero")):
        respuesta = api.get(ruta, headers=admin, params={parametro: carga})
        assert respuesta.status_code == 200, (ruta, respuesta.text)
        assert respuesta.json() == []  # ninguna coincidencia: el texto se busca literalmente
    for parametro in ("estado", "desde"):
        assert api.get("/api/ventas", headers=admin, params={parametro: carga}).status_code in (200, 422)


@pytest.mark.parametrize("carga", CARGAS_SQL)
def test_las_cargas_sql_en_el_registro_y_el_contacto_no_se_ejecutan(api, admin, carga):
    registro = api.post("/api/usuarios/registro", json={
        "nombre": carga, "apellido": "Prueba", "tipoDocumento": "CC", "numeroDocumento": "1234567890", "direccion": carga,
        "telefono": "3001112233", "correo": f"{carga}@example.com", "contrasena": "Amanecer#Andino7", "aceptaTratamientoDatos": True,
    })
    assert registro.status_code == 422
    contacto = api.post("/api/contacto", json={"nombre": "Persona Real", "correo": "persona@example.com", "mensaje": carga})
    assert contacto.status_code == 200
    # Se guarda tal cual, como texto: no se ejecuta y tampoco se altera.
    mensajes = api.get("/api/contacto", headers=admin).json()
    assert carga.strip() in [m["mensaje"] for m in mensajes]


def test_tras_los_intentos_las_tablas_siguen_intactas(api, admin, catalogo):
    assert len(api.get("/api/usuarios", headers=admin).json()) >= 1
    assert len(api.get("/api/catalogos/destinos").json()) == 10
    assert api.post("/api/auth/login", json={"correo": "admin@auroraviajes.com", "contrasena": "no"}).status_code == 401


@pytest.mark.parametrize("ruta", [
    "/api/reservas/1%20OR%201=1", "/api/reservas/1;DROP%20TABLE%20usuarios", "/api/usuarios/abc", "/api/vuelos/-1",
    "/api/facturas/1'%20OR%20'1'='1/pdf", "/api/catalogos/destinos/1%27/opciones",
])
def test_los_identificadores_de_ruta_solo_admiten_enteros(api, admin, ruta):
    respuesta = api.get(ruta, headers=admin)
    assert respuesta.status_code in (404, 422), (ruta, respuesta.status_code)


def test_ningun_archivo_construye_sql_con_texto_dinamico():
    """El código SQL que no usa el ORM solo se escribe con parámetros o con identificadores validados.

    Recorre el árbol sintáctico de toda la aplicación y falla si aparece una consulta armada con f-strings,
    `%` o `.format()`, salvo en los dos módulos de arranque y migración, donde cada texto dinámico es un
    identificador que pasa por `_q()` o una constante del propio archivo.
    """
    # Nombres que pueden ir dentro de un f-string de SQL: identificadores que pasan por `_q`, tipos de columna leídos de
    # information_schema y validados con una expresión regular, y textos escritos como constantes en el propio archivo.
    permitidos_por_archivo = {
        "services/migraciones.py": {"_q", "tipo", "tipo_id", "definicion", "condicion", "al_borrar"},
        "services/siembra.py": {"clausula"},
    }
    # Posición del argumento que contiene el SQL en cada función que lo ejecuta.
    posicion_del_sql = {"text": 0, "execute": 0, "scalar": 0, "scalars": 0, "_ejecutar": 1, "_intentar": 2}
    problemas = []
    for ruta in RAIZ_APP.rglob("*.py"):
        relativa = ruta.relative_to(RAIZ_APP).as_posix()
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call):
                nombre = getattr(nodo.func, "id", getattr(nodo.func, "attr", ""))
                posicion = posicion_del_sql.get(nombre)
                if posicion is not None and len(nodo.args) > posicion:
                    _revisar(nodo.args[posicion], relativa, permitidos_por_archivo, problemas, nodo.lineno)
    assert not problemas, "\n".join(problemas)


def _revisar(argumento, relativa, permitidos_por_archivo, problemas, linea):
    if isinstance(argumento, ast.JoinedStr):  # un f-string
        permitido = permitidos_por_archivo.get(relativa)
        for valor in argumento.values:
            if isinstance(valor, ast.FormattedValue):
                expresion = valor.value
                nombre = getattr(getattr(expresion, "func", None), "id", None) or getattr(expresion, "id", None)
                if permitido is None or nombre not in permitido:
                    problemas.append(f"{relativa}:{linea}: SQL con f-string y texto dinámico ({ast.unparse(expresion)})")
    elif isinstance(argumento, ast.BinOp) and isinstance(argumento.op, (ast.Mod, ast.Add)):
        if isinstance(argumento.left, ast.Constant) and isinstance(argumento.left.value, str) and any(
            palabra in argumento.left.value.upper() for palabra in ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "ALTER ")
        ):
            problemas.append(f"{relativa}:{linea}: SQL concatenado o formateado con %")
    elif isinstance(argumento, ast.Call) and getattr(argumento.func, "attr", "") == "format":
        problemas.append(f"{relativa}:{linea}: SQL con .format()")


# --------------------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------------------


def test_un_token_sin_firma_alg_none_se_rechaza(api):
    sin_firma = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': '1', 'id': 1, 'rol': 'administrador', 'purpose': 'login', 'exp': 4102444800, 'iat': 1})}."
    assert api.get("/api/usuarios", headers=cabecera(sin_firma)).status_code == 401
    assert api.get("/api/reservas/mias", headers=cabecera(sin_firma)).status_code == 401


def test_un_token_firmado_con_otra_clave_o_algoritmo_se_rechaza(api, crear_cliente):
    cliente = crear_cliente()
    ajeno = jwt.encode(carga_de(cliente.id), "una-clave-que-no-es-la-del-servidor-1234567890", algorithm="HS256")
    otro_algoritmo = jwt.encode(carga_de(cliente.id), configuracion.secret_key, algorithm="HS512")
    assert api.get("/api/reservas/mias", headers=cabecera(ajeno)).status_code == 401
    assert api.get("/api/reservas/mias", headers=cabecera(otro_algoritmo)).status_code == 401


def test_un_token_alterado_pierde_su_firma(api, crear_cliente, admin):
    cliente = crear_cliente()
    cabecera_jwt, carga, firma = cliente.token.split(".")
    datos = json.loads(base64.urlsafe_b64decode(carga + "=" * (-len(carga) % 4)))
    datos["id"], datos["sub"], datos["rol"] = 1, "1", "administrador"  # intenta hacerse pasar por el administrador
    alterado = f"{cabecera_jwt}.{b64(datos)}.{firma}"
    assert api.get("/api/usuarios", headers=cabecera(alterado)).status_code == 401


def test_un_token_caducado_o_sin_caducidad_se_rechaza(api, crear_cliente):
    cliente = crear_cliente()
    caducado = jwt.encode(carga_de(cliente.id, exp=datetime.now(timezone.utc) - timedelta(minutes=1)), configuracion.secret_key, algorithm="HS256")
    respuesta = api.get("/api/reservas/mias", headers=cabecera(caducado))
    assert respuesta.status_code == 401 and "expir" in respuesta.json()["mensaje"]
    eterno = carga_de(cliente.id)
    del eterno["exp"]
    assert api.get("/api/reservas/mias", headers=cabecera(jwt.encode(eterno, configuracion.secret_key, algorithm="HS256"))).status_code == 401


def test_el_rol_sale_de_la_base_de_datos_y_no_del_token(api, crear_cliente):
    cliente = crear_cliente()
    engañoso = jwt.encode(carga_de(cliente.id, rol="administrador"), configuracion.secret_key, algorithm="HS256")
    assert api.get("/api/usuarios", headers=cabecera(engañoso)).status_code == 403
    assert api.get("/api/reservas/mias", headers=cabecera(engañoso)).status_code == 200


def test_los_tokens_anteriores_a_las_versiones_de_sesion_siguen_valiendo_hasta_que_se_revoquen(api, crear_cliente):
    cliente = crear_cliente()
    sin_version = carga_de(cliente.id)
    del sin_version["sv"]
    token = jwt.encode(sin_version, configuracion.secret_key, algorithm="HS256")
    assert api.get("/api/reservas/mias", headers=cabecera(token)).status_code == 200
    de_otra_version = jwt.encode(carga_de(cliente.id, sv=99), configuracion.secret_key, algorithm="HS256")
    assert api.get("/api/reservas/mias", headers=cabecera(de_otra_version)).status_code == 401


def test_una_cuenta_desactivada_pierde_el_acceso_al_instante(api, admin, crear_cliente):
    cliente = crear_cliente()
    assert api.get("/api/reservas/mias", headers=cliente.headers).status_code == 200
    api.patch(f"/api/usuarios/{cliente.id}/estado", headers=admin, json={"activo": False})
    assert api.get("/api/reservas/mias", headers=cliente.headers).status_code == 401


# --------------------------------------------------------------------------------------
# Suplantación de IP, cabeceras, tamaño, CORS y filtraciones
# --------------------------------------------------------------------------------------


def test_falsear_x_forwarded_for_no_evita_el_limite_de_intentos(api):
    """Regresión: se tomaba la primera entrada de la cabecera, que escribe el propio cliente."""
    codigos = []
    for n in range(12):
        respuesta = api.post(
            "/api/auth/login",
            json={"correo": f"objetivo{n}@example.com", "contrasena": "mal"},
            headers={"X-Forwarded-For": f"6.6.6.{n}, 10.9.8.7"},  # a la izquierda lo que finge el cliente; a la derecha, el proxy
        )
        codigos.append(respuesta.status_code)
    assert codigos[:10] == [401] * 10 and codigos[10:] == [429, 429]


def test_sin_proxies_de_confianza_la_cabecera_x_forwarded_for_se_ignora(api, monkeypatch):
    """Si la app no está detrás de un proxy, esa cabecera la escribe el cliente: no puede servir para cambiar de identidad."""
    monkeypatch.setattr(configuracion, "proxies_de_confianza", 0)
    codigos = [
        api.post(
            "/api/auth/login",
            json={"correo": f"otro{n}@example.com", "contrasena": "mal"},
            headers={"X-Forwarded-For": f"7.7.7.{n}"},
        ).status_code
        for n in range(12)
    ]
    assert codigos[:10] == [401] * 10 and codigos[10:] == [429, 429]


def test_las_respuestas_llevan_cabeceras_de_seguridad(api):
    respuesta = api.get("/api/health")
    assert respuesta.headers["x-content-type-options"] == "nosniff"
    assert respuesta.headers["x-frame-options"] == "DENY"
    assert respuesta.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in respuesta.headers["content-security-policy"]
    assert "no-store" in respuesta.headers["cache-control"]
    assert "camera=()" in respuesta.headers["permissions-policy"]


def test_un_cuerpo_enorme_se_rechaza_sin_procesarlo(api):
    enorme = b'{"correo": "a@b.com", "contrasena": "' + b"x" * 1_100_000 + b'"}'
    respuesta = api.post("/api/auth/login", content=enorme, headers={"content-type": "application/json"})
    assert respuesta.status_code == 413 and respuesta.json()["codigo"] == "cuerpo_demasiado_grande"
    assert respuesta.headers["x-content-type-options"] == "nosniff"  # también la respuesta de rechazo lleva cabeceras


def test_cors_solo_admite_los_origenes_configurados(api):
    permitido = api.options("/api/auth/login", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert permitido.headers.get("access-control-allow-origin") == "http://localhost:5173"
    ajeno = api.options("/api/auth/login", headers={"Origin": "https://sitio-malicioso.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in ajeno.headers


def test_la_documentacion_de_la_api_no_se_publica_fuera_de_desarrollo(api):
    assert configuracion.depuracion is False
    for ruta in ("/docs", "/redoc", "/openapi.json"):
        assert api.get(ruta).status_code == 404, ruta
    assert "entorno" not in api.get("/").json()


def test_un_error_interno_no_filtra_detalles(api, admin, monkeypatch, catalogo):
    async def explota(*_):
        raise RuntimeError("clave secreta: hunter2 en la ruta C:\\secreto")

    monkeypatch.setattr("app.routers.viajes.generar_numero_vuelo", explota)
    from tests.conftest import cuerpo_de_vuelo
    respuesta = api.post("/api/vuelos", headers=admin, json=cuerpo_de_vuelo(catalogo, catalogo.bogota, catalogo.paris, "2041-01-01T08:00:00"))
    assert respuesta.status_code == 500
    assert "hunter2" not in respuesta.text and "Traceback" not in respuesta.text and "secreto" not in respuesta.text


def test_los_campos_de_mas_no_asignan_privilegios(api):
    """Un cliente no puede fijar su rol, su estado ni banderas internas al registrarse."""
    datos = {
        "nombre": "Camila", "apellido": "Restrepo", "tipoDocumento": "CC", "numeroDocumento": "1150000001", "direccion": "Calle 10 # 5-20",
        "telefono": "3001230000", "correo": "camila.r@example.com", "contrasena": "Amanecer#Andino7", "aceptaTratamientoDatos": True,
        "rol": "administrador", "rol_id": 1, "activo": False, "sesion_version": 50, "debe_cambiar_contrasena": True, "id": 1,
    }
    assert api.post("/api/usuarios/registro", json=datos).status_code == 201
    entrada = api.post("/api/auth/login", json={"correo": "camila.r@example.com", "contrasena": "Amanecer#Andino7"}).json()
    assert entrada["usuario"]["rol"] == "cliente" and entrada["usuario"]["debeCambiarContrasena"] is False
    assert entrada["usuario"]["id"] != 1


def test_un_cliente_no_alcanza_las_rutas_del_personal(api, crear_cliente, viaje):
    cliente = crear_cliente()
    prohibidas = [
        ("get", "/api/reservas"), ("get", "/api/usuarios"), ("get", "/api/clientes"), ("get", "/api/vuelos"), ("get", "/api/hoteles"),
        ("get", "/api/estadisticas"), ("get", "/api/contacto"), ("get", "/api/reportes/ventas"), ("get", "/api/ciudades"),
        ("post", "/api/vuelos"), ("post", "/api/hoteles"), ("post", "/api/paquetes"), ("post", "/api/ventas"), ("post", "/api/ciudades"),
    ]
    for metodo, ruta in prohibidas:
        respuesta = getattr(api, metodo)(ruta, headers=cliente.headers, **({"json": {}} if metodo == "post" else {}))
        assert respuesta.status_code == 403, (metodo, ruta, respuesta.status_code)
    # Y sin sesión, todo lo anterior responde 401.
    for metodo, ruta in prohibidas:
        respuesta = getattr(api, metodo)(ruta, **({"json": {}} if metodo == "post" else {}))
        assert respuesta.status_code == 401, (metodo, ruta, respuesta.status_code)


def test_un_cliente_no_ve_las_ventas_ni_las_pqr_de_otro(api, crear_cliente, viaje, reservar, venta_de):
    dueno, intruso = crear_cliente(), crear_cliente()
    reserva_id, _ = reservar(dueno, viaje)
    venta = venta_de(reserva_id)
    assert api.get(f"/api/ventas/{venta['id']}", headers=intruso.headers).status_code == 403
    assert api.get("/api/ventas", headers=intruso.headers).json() == []
    pqr = api.post("/api/pqr", headers=dueno.headers, json={"tipo": "queja", "asunto": "Demora en el vuelo", "descripcion": "Salió tarde por dos horas."})
    assert pqr.status_code == 201
    assert api.get("/api/pqr", headers=intruso.headers).json() == []
    assert CLAVE_CLIENTE  # la clave de prueba no se reutiliza fuera de los tests
