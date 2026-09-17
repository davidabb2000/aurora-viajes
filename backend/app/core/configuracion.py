from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    nombre_app: str = "Aurora Viajes API"
    entorno: str = "desarrollo"
    depuracion: bool = True
    origenes_permitidos: list[str] = [
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

    secret_key: str
    algoritmo_jwt: str = "HS256"
    minutos_expiracion_token: int = 60

    proveedor_ia_api_key: str | None = None
    proveedor_ia_url: str = "https://api.groq.com/openai/v1/chat/completions"
    proveedor_ia_modelo: str = "llama-3.1-8b-instant"
    proveedor_ia_timeout: float = 20.0
    proveedor_ia_reintentos: int = 2
    stripe_secret_key: str | None = None
    frontend_url: str = "http://localhost:5173"

    admin_email: str = "admin@auroraviajes.com"
    admin_password: str = "Admin123!"
    
    # Configuración de correos
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "noreply@auroraviajes.com"
    smtp_use_tls: bool = True

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

    @model_validator(mode="after")
    def construir_url_base_datos(self):
        if self.database_url:
            url = self.database_url.strip()
            if url.startswith("mysql://"):
                url = f"mysql+{self.mysql_driver}://{url[len('mysql://'):]}"
            elif url.startswith("mysql+pymysql://"):
                url = f"mysql+{self.mysql_driver}://{url[len('mysql+pymysql://'):]}"
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
        return self


configuracion = Configuracion()
