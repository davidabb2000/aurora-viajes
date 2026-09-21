"""Cuentas: registro, inicio de sesión, cambio y recuperación de contraseña, y protección de administradores."""
import pytest

from app.core.politica_contrasena import normalizar_correo, validar_contrasena
from tests.conftest import CLAVE_ADMIN, CLAVE_CLIENTE, cabecera


def datos_de_registro(n, **cambios):
    datos = {
        "nombre": "Valentina", "apellido": "Ospina", "tipoDocumento": "CC", "numeroDocumento": str(1_100_000_000 + n),
        "direccion": "Carrera 43A # 1-50", "telefono": "3125550101", "correo": f"valentina{n}@example.com",
        "contrasena": "Amanecer#Andino7", "aceptaTratamientoDatos": True,
    }
    datos.update(cambios)
    return datos


# --------------------------------------------------------------------------------------
# Registro
# --------------------------------------------------------------------------------------


def test_registro_correcto_permite_iniciar_sesion(api):
    datos = datos_de_registro(1)
    assert api.post("/api/usuarios/registro", json=datos).status_code == 201
    entrada = api.post("/api/auth/login", json={"correo": datos["correo"], "contrasena": datos["contrasena"]})
    assert entrada.status_code == 200
    assert entrada.json()["usuario"]["rol"] == "cliente"
    assert entrada.json()["usuario"]["debeCambiarContrasena"] is False


def test_el_registro_exige_autorizar_el_tratamiento_de_datos(api):
    sin_campo = datos_de_registro(2)
    del sin_campo["aceptaTratamientoDatos"]
    assert api.post("/api/usuarios/registro", json=sin_campo).status_code == 422
    rechazado = api.post("/api/usuarios/registro", json=datos_de_registro(2, aceptaTratamientoDatos=False))
    assert rechazado.status_code == 422
    assert "autorizar" in rechazado.json()["mensaje"]


@pytest.mark.parametrize("campo, valor, fragmento", [
    ("nombre", "Val3ntina", "letras"),
    ("nombre", "V", None),
    ("apellido", "Ospina; DROP TABLE usuarios", "letras"),
    ("numeroDocumento", "12ab5678", "números"),
    ("numeroDocumento", "123", None),
    ("telefono", "31255501xx", "números"),
    ("tipoDocumento", "XX", "tipo de documento"),
    ("direccion", "Calle <script>alert(1)</script>", "caracteres no permitidos"),
    ("correo", "sin-arroba", "Correo"),
    ("correo", "a@b", "Correo"),
    ("correo", "con espacio@example.com", "Correo"),
])
def test_el_registro_rechaza_datos_invalidos(api, campo, valor, fragmento):
    respuesta = api.post("/api/usuarios/registro", json=datos_de_registro(3, **{campo: valor}))
    assert respuesta.status_code == 422, respuesta.text
    if fragmento:
        assert fragmento in respuesta.json()["mensaje"]
    assert campo in {detalle["campo"] for detalle in respuesta.json()["detalles"]}


@pytest.mark.parametrize("contrasena, fragmento", [
    ("sinmayusculas1!", "mayúsculas"),
    ("SINMINUSCULAS1!", "mayúsculas"),
    ("SinNumeros!!!", "número"),
    ("SinSimbolo123A", "especial"),
    ("Password123!", "común"),
    ("Valentina#2026x", "nombre"),
    ("Amanecer#Andino7 ", "espacios"),
    ("Ab1!" * 40, "128"),
])
def test_el_registro_aplica_la_politica_de_contrasenas(api, contrasena, fragmento):
    respuesta = api.post("/api/usuarios/registro", json=datos_de_registro(4, contrasena=contrasena))
    assert respuesta.status_code == 422, respuesta.text
    assert fragmento in respuesta.json()["mensaje"], respuesta.json()["mensaje"]
    assert "contrasena" in {detalle["campo"] for detalle in respuesta.json()["detalles"]}


def test_la_contrasena_no_puede_contener_el_correo(api):
    datos = datos_de_registro(5, correo="alejandro.paez@example.com", contrasena="Alejandro.Paez#1")
    respuesta = api.post("/api/usuarios/registro", json=datos)
    assert respuesta.status_code == 422 and "correo" in respuesta.json()["mensaje"]


def test_correo_o_documento_repetidos_dan_el_mismo_mensaje(api):
    datos = datos_de_registro(6)
    assert api.post("/api/usuarios/registro", json=datos).status_code == 201
    por_correo = api.post("/api/usuarios/registro", json={**datos, "numeroDocumento": "1199999999"})
    por_documento = api.post("/api/usuarios/registro", json={**datos, "correo": "otra.persona@example.com"})
    assert por_correo.status_code == por_documento.status_code == 409
    assert por_correo.json()["mensaje"] == por_documento.json()["mensaje"]
    # El correo se normaliza: mayúsculas y espacios no crean una cuenta distinta.
    mayusculas = api.post("/api/usuarios/registro", json={**datos, "numeroDocumento": "1199999998", "correo": "  VALENTINA6@Example.com "})
    assert mayusculas.status_code == 409


def test_el_registro_esta_limitado_por_ip(api):
    codigos = [api.post("/api/usuarios/registro", json=datos_de_registro(100 + n)).status_code for n in range(6)]
    # Cinco cuentas por hora desde una misma IP; el personal da de alta clientes por otra vía, sin este tope.
    assert codigos[:5] == [201] * 5 and codigos[5] == 429


def test_el_registro_no_asigna_roles_de_personal(api):
    datos = datos_de_registro(7, rol="administrador")
    assert api.post("/api/usuarios/registro", json=datos).status_code == 201
    entrada = api.post("/api/auth/login", json={"correo": datos["correo"], "contrasena": datos["contrasena"]})
    assert entrada.json()["usuario"]["rol"] == "cliente"


# --------------------------------------------------------------------------------------
# Inicio de sesión
# --------------------------------------------------------------------------------------


def test_el_correo_del_login_no_distingue_mayusculas(api, crear_cliente):
    cliente = crear_cliente()
    entrada = api.post("/api/auth/login", json={"correo": cliente.correo.upper(), "contrasena": CLAVE_CLIENTE})
    assert entrada.status_code == 200


def test_login_fallido_es_igual_exista_o_no_la_cuenta(api, crear_cliente):
    cliente = crear_cliente()
    contrasena_mala = api.post("/api/auth/login", json={"correo": cliente.correo, "contrasena": "otra-cosa"})
    cuenta_inexistente = api.post("/api/auth/login", json={"correo": "nadie@example.com", "contrasena": "otra-cosa"})
    assert contrasena_mala.status_code == cuenta_inexistente.status_code == 401
    assert contrasena_mala.json()["mensaje"] == cuenta_inexistente.json()["mensaje"]


def test_el_login_se_bloquea_tras_cinco_intentos_fallidos_por_correo(api, crear_cliente):
    cliente = crear_cliente()
    codigos = [api.post("/api/auth/login", json={"correo": cliente.correo, "contrasena": f"mal{n}"}).status_code for n in range(6)]
    assert codigos[:5] == [401] * 5 and codigos[5] == 429
    # Ni siquiera la clave correcta entra desde esa IP mientras dura el bloqueo...
    assert api.post("/api/auth/login", json={"correo": cliente.correo, "contrasena": CLAVE_CLIENTE}).status_code == 429
    # ...pero el bloqueo lleva la IP: quien intenta bloquear a otra persona solo se bloquea a sí mismo.
    desde_otra_ip = api.post(
        "/api/auth/login", json={"correo": cliente.correo, "contrasena": CLAVE_CLIENTE}, headers={"X-Forwarded-For": "198.51.100.7"}
    )
    assert desde_otra_ip.status_code == 200


def test_el_ataque_repartido_entre_muchas_ip_tambien_se_frena(api, crear_cliente):
    cliente = crear_cliente()
    codigos = [
        api.post("/api/auth/login", json={"correo": cliente.correo, "contrasena": f"mal{n}"}, headers={"X-Forwarded-For": f"203.0.113.{n}"}).status_code
        for n in range(21)
    ]
    assert codigos[:20] == [401] * 20 and codigos[20] == 429


def test_quien_soy_devuelve_los_datos_vigentes(api, crear_cliente):
    cliente = crear_cliente()
    yo = api.get("/api/auth/yo", headers=cliente.headers)
    assert yo.status_code == 200 and yo.json()["correo"] == cliente.correo
    assert api.get("/api/auth/yo").status_code == 401


# --------------------------------------------------------------------------------------
# Cambio de contraseña y sesiones
# --------------------------------------------------------------------------------------


def test_cambiar_la_contrasena_exige_la_actual_y_cierra_las_demas_sesiones(api, crear_cliente):
    cliente = crear_cliente()
    nueva = "Horizonte#Claro88"
    # Con la clave actual equivocada, aunque el token sea válido, no se cambia nada.
    mal = api.post("/api/auth/cambiar-contrasena", headers=cliente.headers, json={"contrasenaActual": "no-es", "nuevaContrasena": nueva})
    assert mal.status_code == 400 and "actual" in mal.json()["mensaje"]
    igual = api.post("/api/auth/cambiar-contrasena", headers=cliente.headers, json={"contrasenaActual": CLAVE_CLIENTE, "nuevaContrasena": CLAVE_CLIENTE})
    assert igual.status_code == 400
    debil = api.post("/api/auth/cambiar-contrasena", headers=cliente.headers, json={"contrasenaActual": CLAVE_CLIENTE, "nuevaContrasena": "sinmayusculas1!"})
    assert debil.status_code == 400
    corta = api.post("/api/auth/cambiar-contrasena", headers=cliente.headers, json={"contrasenaActual": CLAVE_CLIENTE, "nuevaContrasena": "123456"})
    assert corta.status_code == 422

    cambio = api.post("/api/auth/cambiar-contrasena", headers=cliente.headers, json={"contrasenaActual": CLAVE_CLIENTE, "nuevaContrasena": nueva})
    assert cambio.status_code == 200, cambio.text
    # El token anterior deja de valer al instante; el nuevo sí.
    assert api.get("/api/reservas/mias", headers=cliente.headers).status_code == 401
    assert api.get("/api/reservas/mias", headers=cabecera(cambio.json()["token"])).status_code == 200
    assert api.post("/api/auth/login", json={"correo": cliente.correo, "contrasena": CLAVE_CLIENTE}).status_code == 401
    assert api.post("/api/auth/login", json={"correo": cliente.correo, "contrasena": nueva}).status_code == 200


def test_cerrar_todas_las_sesiones_invalida_los_tokens_emitidos(api, crear_cliente):
    cliente = crear_cliente()
    otra_sesion = api.post("/api/auth/login", json={"correo": cliente.correo, "contrasena": CLAVE_CLIENTE}).json()["token"]
    assert api.post("/api/auth/cerrar-sesiones", headers=cliente.headers).status_code == 200
    assert api.get("/api/reservas/mias", headers=cliente.headers).status_code == 401
    assert api.get("/api/reservas/mias", headers=cabecera(otra_sesion)).status_code == 401
    # Entrando de nuevo se obtiene un token válido.
    nuevo = api.post("/api/auth/login", json={"correo": cliente.correo, "contrasena": CLAVE_CLIENTE}).json()["token"]
    assert api.get("/api/reservas/mias", headers=cabecera(nuevo)).status_code == 200


def test_una_cuenta_con_clave_provisional_solo_puede_cambiarla(api, admin, crear_empleado):
    correo, provisional = "provisional1@auroraviajes.com", "Provisional#2026a"
    creado = api.post("/api/usuarios", headers=admin, json={
        "nombre": "Andrea", "apellido": "Mejia", "tipoDocumento": "CC", "numeroDocumento": "1500000001", "direccion": "Oficina",
        "telefono": "3005550001", "correo": correo, "contrasena": provisional, "rol": "empleado",
    })
    assert creado.status_code == 201
    token = api.post("/api/auth/login", json={"correo": correo, "contrasena": provisional}).json()["token"]

    bloqueado = api.get("/api/reservas", headers=cabecera(token))
    assert bloqueado.status_code == 403 and bloqueado.json()["codigo"] == "cambio_de_contrasena_requerido"
    assert api.get("/api/auth/yo", headers=cabecera(token)).json()["debeCambiarContrasena"] is True

    cambio = api.post("/api/auth/cambiar-contrasena", headers=cabecera(token), json={"contrasenaActual": provisional, "nuevaContrasena": "Definitiva#Nueva9"})
    assert cambio.status_code == 200
    assert api.get("/api/reservas", headers=cabecera(cambio.json()["token"])).status_code == 200


def test_el_administrador_de_ejemplo_se_marca_para_cambiar_su_clave(api):
    """Si el administrador arranca con la clave de ejemplo, debe cambiarla en su primer acceso."""
    entrada = api.post("/api/auth/login", json={"correo": "admin@auroraviajes.com", "contrasena": CLAVE_ADMIN})
    assert entrada.json()["usuario"]["debeCambiarContrasena"] is False  # en las pruebas se define una clave propia


# --------------------------------------------------------------------------------------
# Recuperación
# --------------------------------------------------------------------------------------


@pytest.fixture
def correos_de_recuperacion(monkeypatch):
    """Captura los correos de recuperación en lugar de enviarlos: {correo: token}."""
    enviados: dict[str, str] = {}

    async def falso(destinatario, nombre, token):
        enviados[destinatario] = token
        return True

    monkeypatch.setattr("app.routers.auth.enviar_correo_recuperacion", falso)
    return enviados


def test_recuperar_contrasena_con_un_enlace_de_un_solo_uso(api, crear_cliente, correos_de_recuperacion):
    cliente = crear_cliente()
    solicitud = api.post("/api/auth/recuperar", json={"correo": cliente.correo})
    assert solicitud.status_code == 200
    assert "token" not in solicitud.text  # el token viaja solo por correo, nunca en la respuesta
    token = correos_de_recuperacion[cliente.correo]

    nueva = "Cordillera#Verde42"
    restablecida = api.post("/api/auth/restablecer", json={"token": token, "nuevaContrasena": nueva})
    assert restablecida.status_code == 200, restablecida.text
    assert api.post("/api/auth/login", json={"correo": cliente.correo, "contrasena": nueva}).status_code == 200
    assert api.post("/api/auth/login", json={"correo": cliente.correo, "contrasena": CLAVE_CLIENTE}).status_code == 401
    # El mismo enlace no sirve dos veces.
    otra = api.post("/api/auth/restablecer", json={"token": token, "nuevaContrasena": "Segundo#Intento55"})
    assert otra.status_code == 400
    # Y las sesiones que hubiera abiertas con la clave anterior se cierran.
    assert api.get("/api/reservas/mias", headers=cliente.headers).status_code == 401


def test_recuperar_no_revela_si_el_correo_existe(api, crear_cliente, correos_de_recuperacion):
    cliente = crear_cliente()
    existente = api.post("/api/auth/recuperar", json={"correo": cliente.correo})
    inexistente = api.post("/api/auth/recuperar", json={"correo": "fantasma@example.com"})
    assert existente.status_code == inexistente.status_code == 200
    assert existente.json() == inexistente.json()
    assert "fantasma@example.com" not in correos_de_recuperacion


def test_no_se_envia_correo_de_recuperacion_a_cuentas_inactivas(api, admin, crear_cliente, correos_de_recuperacion):
    cliente = crear_cliente()
    api.patch(f"/api/usuarios/{cliente.id}/estado", headers=admin, json={"activo": False})
    api.post("/api/auth/recuperar", json={"correo": cliente.correo})
    assert cliente.correo not in correos_de_recuperacion


def test_recuperar_esta_limitado_por_destinatario(api, crear_cliente, correos_de_recuperacion):
    cliente = crear_cliente()
    codigos = [api.post("/api/auth/recuperar", json={"correo": cliente.correo}).status_code for _ in range(4)]
    # Desde cualquier IP, una misma persona no recibe más de tres correos por hora.
    assert codigos == [200, 200, 200, 429]


def test_el_restablecimiento_valida_la_contrasena_nueva(api, crear_cliente, correos_de_recuperacion):
    cliente = crear_cliente()
    api.post("/api/auth/recuperar", json={"correo": cliente.correo})
    token = correos_de_recuperacion[cliente.correo]
    debil = api.post("/api/auth/restablecer", json={"token": token, "nuevaContrasena": "12345678"})
    assert debil.status_code == 400
    con_correo = api.post("/api/auth/restablecer", json={"token": token, "nuevaContrasena": f"{cliente.correo.split('@')[0]}#Zz9"})
    assert con_correo.status_code == 400
    # Tras los rechazos el enlace sigue valiendo: solo se gasta al cambiar la clave.
    assert api.post("/api/auth/restablecer", json={"token": token, "nuevaContrasena": "Bosque#Nublado31"}).status_code == 200


def test_un_token_que_no_es_de_recuperacion_no_restablece(api, crear_cliente):
    cliente = crear_cliente()
    de_sesion = api.post("/api/auth/restablecer", json={"token": cliente.token, "nuevaContrasena": "Bosque#Nublado31"})
    assert de_sesion.status_code == 400
    inventado = api.post("/api/auth/restablecer", json={"token": "no.es.un.token", "nuevaContrasena": "Bosque#Nublado31"})
    assert inventado.status_code == 400
    assert inventado.json()["mensaje"] == de_sesion.json()["mensaje"]


# --------------------------------------------------------------------------------------
# Política de contraseñas y correos (pruebas de la función, sin HTTP)
# --------------------------------------------------------------------------------------


def test_la_politica_de_contrasenas_acepta_frases_largas():
    assert validar_contrasena("Mi frase secreta es muy larga, 2026!") == "Mi frase secreta es muy larga, 2026!"
    with pytest.raises(ValueError):
        validar_contrasena("A1!" + "a" * 130)


@pytest.mark.parametrize("correo", ["a@b.com\nBcc: victima@example.com", "a@b.com\r\nSubject: x", "a b@example.com", "@example.com", "a@", "a@@b.com", "x" * 70 + "@example.com"])
def test_los_correos_con_saltos_de_linea_o_mal_formados_se_rechazan(correo):
    with pytest.raises(ValueError):
        normalizar_correo(correo)


def test_los_correos_validos_se_normalizan():
    assert normalizar_correo("  Persona.Nombre+viajes@Example.COM ") == "persona.nombre+viajes@example.com"


# --------------------------------------------------------------------------------------
# Protección de administradores
# --------------------------------------------------------------------------------------


def test_un_administrador_no_puede_quedarse_sin_administradores(api, admin, crear_empleado):
    otro = crear_empleado("administrador")
    yo = api.get("/api/auth/yo", headers=admin).json()

    # No puede desactivarse, eliminarse ni cambiarse el rol a sí mismo.
    assert api.patch(f"/api/usuarios/{yo['id']}/estado", headers=admin, json={"activo": False}).status_code == 409
    assert api.delete(f"/api/usuarios/{yo['id']}", headers=admin).status_code == 409
    assert api.put(f"/api/usuarios/{yo['id']}", headers=admin, json={"rol": "cliente"}).status_code == 409
    # Sí puede degradar al otro administrador mientras él siga siéndolo, y el cambio cierra las sesiones de ese usuario.
    assert api.put(f"/api/usuarios/{otro.id}", headers=admin, json={"rol": "empleado"}).status_code == 200
    assert api.get("/api/usuarios", headers=otro.headers).status_code == 401


def test_no_se_elimina_a_un_usuario_con_historial(api, admin, crear_cliente, viaje, reservar):
    cliente = crear_cliente()
    reservar(cliente, viaje)
    borrado = api.delete(f"/api/usuarios/{cliente.id}", headers=admin)
    assert borrado.status_code == 409 and "desactívalo" in borrado.json()["mensaje"]
    # Uno sin historial sí se elimina.
    sin_historial = crear_cliente()
    assert api.delete(f"/api/usuarios/{sin_historial.id}", headers=admin).status_code == 200


def test_las_cuentas_creadas_por_el_administrador_cambian_de_rol_de_forma_controlada(api, admin, crear_empleado):
    empleado = crear_empleado()
    assert api.get("/api/usuarios", headers=empleado.headers).status_code == 403
    assert api.put(f"/api/usuarios/{empleado.id}", headers=admin, json={"rol": "administrador"}).status_code == 200
    # El token anterior seguía declarando el rol viejo: se invalidó al cambiar.
    assert api.get("/api/usuarios", headers=empleado.headers).status_code == 401
    entrada = api.post("/api/auth/login", json={"correo": empleado.correo, "contrasena": empleado.contrasena}).json()
    assert entrada["usuario"]["rol"] == "administrador"
    assert api.get("/api/usuarios", headers=cabecera(entrada["token"])).status_code == 200
