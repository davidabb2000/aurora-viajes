"""Conexión TLS a la base (verificación con la CA del proveedor) y envío de correo por la API de SendGrid."""
import asyncio
import datetime
import logging
import ssl

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app.core.configuracion import Configuracion, configuracion
from app.services import correos

URL_GESTIONADA = "mysql://usuario:clave@base.ejemplo.com:3306/aurora?ssl-mode=REQUIRED"


def certificado_de_prueba() -> str:
    """Una CA autofirmada en formato PEM, generada al vuelo."""
    clave = ec.generate_private_key(ec.SECP256R1())
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "CA de prueba")])
    ahora = datetime.datetime.now(datetime.timezone.utc)
    certificado = (
        x509.CertificateBuilder().subject_name(nombre).issuer_name(nombre).public_key(clave.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(ahora).not_valid_after(ahora + datetime.timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True).sign(clave, hashes.SHA256())
    )
    return certificado.public_bytes(serialization.Encoding.PEM).decode()


def configurar(**cambios) -> Configuracion:
    return Configuracion(secret_key="x" * 40, database_url=URL_GESTIONADA, **cambios)


def test_sin_ca_la_conexion_se_cifra_pero_no_se_verifica():
    contexto = configurar().argumentos_conexion["ssl"]
    assert contexto.verify_mode == ssl.CERT_NONE and contexto.check_hostname is False


def test_con_la_ca_en_una_variable_se_verifica_el_certificado():
    contexto = configurar(mysql_ssl_ca_pem=certificado_de_prueba()).argumentos_conexion["ssl"]
    assert contexto.verify_mode == ssl.CERT_REQUIRED
    assert contexto.check_hostname is False  # VERIFY_CA: lo que recomiendan los servicios gestionados


def test_se_puede_exigir_tambien_que_coincida_el_nombre_del_servidor():
    contexto = configurar(mysql_ssl_ca_pem=certificado_de_prueba(), mysql_ssl_verificar_host=True).argumentos_conexion["ssl"]
    assert contexto.verify_mode == ssl.CERT_REQUIRED and contexto.check_hostname is True


@pytest.mark.parametrize("envolver", [lambda pem: pem, lambda pem: pem.replace("\n", "\\n"), lambda pem: f'"{pem.replace(chr(10), chr(92) + "n")}"'])
def test_el_pem_llega_bien_venga_como_venga_en_la_variable(envolver):
    """Con saltos de línea reales, con «\\n» escritos a mano, o entrecomillado (como lo dejan los paneles de las plataformas)."""
    contexto = configurar(mysql_ssl_ca_pem=envolver(certificado_de_prueba())).argumentos_conexion["ssl"]
    assert contexto.verify_mode == ssl.CERT_REQUIRED


def test_un_pem_invalido_impide_arrancar_con_un_mensaje_claro():
    with pytest.raises(ValueError, match="MYSQL_SSL_CA_PEM"):
        configurar(mysql_ssl_ca_pem="esto no es un certificado")


def test_la_ca_tambien_puede_ser_un_archivo(tmp_path):
    ruta = tmp_path / "ca.pem"
    ruta.write_text(certificado_de_prueba(), encoding="utf-8")
    contexto = configurar(mysql_ssl_ca=str(ruta)).argumentos_conexion["ssl"]
    assert contexto.verify_mode == ssl.CERT_REQUIRED


def test_sqlite_no_lleva_argumentos_de_conexion():
    assert Configuracion(secret_key="x" * 40, motor_bd="sqlite", database_url=None, mysql_ssl_ca_pem=certificado_de_prueba()).argumentos_conexion == {}


# --------------------------------------------------------------------------------------
# Correo por la API HTTPS de SendGrid
# --------------------------------------------------------------------------------------


@pytest.fixture
def sendgrid(monkeypatch):
    monkeypatch.setattr(configuracion, "sendgrid_api_key", "SG.clave-secreta-de-prueba")
    monkeypatch.setattr(configuracion, "smtp_from", "noreply@auroraviajes.com")
    capturado = {"peticiones": [], "respuesta": httpx.Response(202)}

    async def falsa(self, url, **kwargs):
        capturado["peticiones"].append((url, kwargs))
        if isinstance(capturado["respuesta"], Exception):
            raise capturado["respuesta"]
        return capturado["respuesta"]

    monkeypatch.setattr(httpx.AsyncClient, "post", falsa)
    return capturado


def enviar() -> bool:
    return asyncio.run(correos._enviar("Asunto de prueba", "cliente@example.com", "Hola", "<p>Hola</p>"))


def test_con_clave_de_sendgrid_el_correo_sale_por_https(sendgrid):
    assert enviar() is True
    (url, datos), = sendgrid["peticiones"]
    assert url == "https://api.sendgrid.com/v3/mail/send"
    assert datos["headers"] == {"Authorization": "Bearer SG.clave-secreta-de-prueba"}
    assert datos["json"]["personalizations"] == [{"to": [{"email": "cliente@example.com"}]}]
    assert datos["json"]["from"]["email"] == "noreply@auroraviajes.com"
    assert datos["json"]["subject"] == "Asunto de prueba"
    assert [c["type"] for c in datos["json"]["content"]] == ["text/plain", "text/html"]


def test_si_sendgrid_rechaza_el_correo_se_anota_sin_revelar_la_clave(sendgrid, caplog):
    sendgrid["respuesta"] = httpx.Response(401, text='{"errors":[{"message":"The provided authorization grant is invalid"}]}')
    with caplog.at_level(logging.INFO, logger="aurora-viajes.correos"):
        assert enviar() is False
    assert "HTTP 401" in caplog.text and "SG.clave-secreta-de-prueba" not in caplog.text


def test_si_no_se_llega_a_sendgrid_el_envio_falla_sin_romper_nada(sendgrid, caplog):
    sendgrid["respuesta"] = httpx.ConnectError("sin red")
    with caplog.at_level(logging.INFO, logger="aurora-viajes.correos"):
        assert enviar() is False
    assert "SG.clave-secreta-de-prueba" not in caplog.text


def test_sin_sendgrid_ni_smtp_no_se_envia_nada(monkeypatch):
    monkeypatch.setattr(configuracion, "sendgrid_api_key", None)
    monkeypatch.setattr(configuracion, "smtp_host", None)
    assert enviar() is False
