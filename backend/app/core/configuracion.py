import json
import os
import ssl
from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Configuracion(BaseSettings):
    # AURORA_ENV_FILE="" desactiva la lectura del .env; los tests la usan para no tocar servicios reales.
    model_config = SettingsConfigDict(env_file=os.getenv("AURORA_ENV_FILE", ".env") or None, env_file_encoding="utf-8", extra="ignore")

    nombre_app: str = "Aurora Viajes API"
    entorno: str = "desarrollo"
    # Apagado por defecto: encendido publica /docs y vuelca cada consulta SQL (con sus datos) en el log.
    depuracion: bool = False
    origenes_permitidos: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    motor_bd: str = "mysql"
    sqlite_path: str = "./aurora_viajes.db"
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "aurora_viajes"
    mysql_charset: str = "utf8mb4"
    mysql_driver: str = "aiomysql"
    database_url: str | None = None
    url_base_datos: str = ""
    # Proveedores como Aiven o Clever Cloud exigen TLS. Puede forzarse con
    # MYSQL_SSL=true o deducirse del ssl-mode que traiga la propia URL.
    # Con true no se mantienen conexiones abiertas entre peticiones. Cuesta unos
    # milisegundos por peticion, pero permite que el modo serverless de Railway
    # llegue a dormir el servicio: un pool ocioso lo mantiene despierto.
    bd_sin_pool: bool = False
    mysql_ssl: bool = False
    mysql_ssl_ca: str | None = None
    argumentos_conexion: dict = {}

    secret_key: str
    algoritmo_jwt: str = "HS256"
    minutos_expiracion_token: int = 60

    proveedor_ia_api_key: str | None = None
    proveedor_ia_url: str = "https://api.groq.com/openai/v1/chat/completions"
    proveedor_ia_modelo: str = "llama-3.1-8b-instant"
    proveedor_ia_timeout: float = 20.0
    proveedor_ia_reintentos: int = 2
    stripe_secret_key: str | None = None
    # Secreto de firma del webhook (Stripe -> Developers -> Webhooks). Sin él, el endpoint se niega a operar.
    stripe_webhook_secret: str | None = None
    frontend_url: str = "http://localhost:5173"

    admin_email: str = "admin@auroraviajes.com"
    admin_password: str = "Admin123!"
    # El administrador se crea una sola vez. Con ADMIN_RESTABLECER_CONTRASENA=true el
    # siguiente arranque vuelve a fijar su clave a ADMIN_PASSWORD (para recuperar el acceso).
    admin_restablecer_contrasena: bool = False

    # Cuántos proxies de confianza hay delante de la app (Railway = 1). La IP del cliente es la
    # de la derecha de X-Forwarded-For: lo que el cliente escriba a la izquierda no cuenta.
    proxies_de_confianza: int = 1
    # Tope del cuerpo de una petición. La API solo recibe JSON pequeño.
    tamano_maximo_cuerpo: int = 1_000_000
    
    # Configuración de correos
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "noreply@auroraviajes.com"
    smtp_use_tls: bool = True

    @field_validator("origenes_permitidos", mode="before")
    @classmethod
    def normalizar_origenes(cls, value):
        """Acepta JSON (["https://a","https://b"]) o una lista separada por comas.

        En los paneles de Render o Cloudflare es facil escribir el valor sin
        comillas; sin esto la aplicacion no arranca por un error de parseo JSON.
        """
        if value is None or isinstance(value, list):
            return value
        texto = str(value).strip()
        if not texto:
            return []
        if texto.startswith("["):
            try:
                return json.loads(texto)
            except json.JSONDecodeError:
                texto = texto.strip("[]")
        limpios = []
        for parte in texto.split(","):
            origen = parte.strip().strip('"').strip("'").rstrip("/")
            if origen:
                limpios.append(origen)
        return limpios

    @field_validator("proveedor_ia_api_key", mode="before")
    @classmethod
    def normalizar_clave_ia(cls, value):
        if value is None:
            return None
        texto = str(value).strip()
        return texto or None

    @field_validator("proveedor_ia_url", "proveedor_ia_modelo", mode="before")
    @classmethod
    def normalizar_cadenas_ia(cls, value, info):
        texto = str(value).strip() if value is not None else ""
        if texto:
            return texto
        if info.field_name == "proveedor_ia_url":
            return "https://api.groq.com/openai/v1/chat/completions"
        return "llama-3.1-8b-instant"

    # Parametros que los proveedores ponen en la URL y que aiomysql no acepta:
    # se interpretan aqui y se quitan antes de entregarsela a SQLAlchemy.
    _PARAMETROS_SSL = ("ssl-mode", "sslmode", "ssl_mode", "ssl-ca", "sslca", "ssl_ca")

    def _depurar_url_mysql(self, url: str) -> tuple[str, bool]:
        """Devuelve la URL sin parametros de SSL y si el proveedor pidio TLS."""
        partes = urlsplit(url)
        consulta = parse_qsl(partes.query, keep_blank_values=True)
        exige_tls = False
        limpia = []
        for clave, valor in consulta:
            if clave.lower() not in self._PARAMETROS_SSL:
                limpia.append((clave, valor))
                continue
            if clave.lower() in ("ssl-ca", "sslca", "ssl_ca"):
                self.mysql_ssl_ca = valor or self.mysql_ssl_ca
                exige_tls = True
            elif valor.upper() not in ("DISABLED", "FALSE", "0", ""):
                exige_tls = True
        return urlunsplit(partes._replace(query=urlencode(limpia))), exige_tls

    @model_validator(mode="after")
    def endurecer_produccion(self):
        if self.entorno.lower() in {"produccion", "producción", "production", "prod"}:
            self.depuracion = False
        return self

    @model_validator(mode="after")
    def construir_url_base_datos(self):
        if self.database_url:
            url = self.database_url.strip()
            if url.startswith("mysql://"):
                url = f"mysql+{self.mysql_driver}://{url[len('mysql://'):]}"
            elif url.startswith("mysql+pymysql://"):
                url = f"mysql+{self.mysql_driver}://{url[len('mysql+pymysql://'):]}"
            if url.startswith("mysql+"):
                url, exige_tls = self._depurar_url_mysql(url)
                if exige_tls:
                    self.mysql_ssl = True
            if url.startswith("mysql+") and "charset=" not in url:
                # Sin charset explicito MySQL puede caer en latin1 y romper tildes/enies.
                url = f"{url}{'&' if '?' in url else '?'}charset={self.mysql_charset}"
            self.url_base_datos = url
        elif self.motor_bd.lower() == "mysql":
            credenciales = self.mysql_user
            if self.mysql_password:
                credenciales = f"{self.mysql_user}:{self.mysql_password}"
            self.url_base_datos = (
                f"mysql+{self.mysql_driver}://{credenciales}"
                f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
                f"?charset={self.mysql_charset}"
            )
        else:
            self.url_base_datos = f"sqlite+aiosqlite:///{self.sqlite_path}"

        if self.url_base_datos.startswith("mysql+") and self.mysql_ssl:
            contexto = ssl.create_default_context(cafile=self.mysql_ssl_ca or None)
            if self.mysql_ssl_ca is None:
                # Sin CA propia se cifra igual, pero no se verifica el certificado:
                # los hosts gestionados suelen usar una CA privada.
                contexto.check_hostname = False
                contexto.verify_mode = ssl.CERT_NONE
            self.argumentos_conexion = {"ssl": contexto}
        return self


configuracion = Configuracion()
