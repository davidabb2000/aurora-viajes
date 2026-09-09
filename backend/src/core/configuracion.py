from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Configuracion(BaseSettings):
    # Apuntamos correctamente al .env dentro de src/
    model_config = SettingsConfigDict(env_file='src/.env', env_file_encoding='utf-8', extra='ignore')
    
    nombre_app: str
    entorno: str = 'desarrollo'
    depuracion: bool = True
    origenes_permitidos: list[str]
    
    motor_bd: str
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: str
    mysql_charset: str
    mysql_driver: str
    url_base_datos: str = ''
    
    secret_key: str
    algoritmo_jwt: str
    minutos_expiracion_token: int
    
    proveedor_ia_api_key: str | None = None
    proveedor_ia_url: str
    proveedor_ia_modelo: str
    stripe_secret_key: str | None = None

    @model_validator(mode='after')
    def construir_url_base_datos(self):
        credenciales = f'{self.mysql_user}:{self.mysql_password}' if self.mysql_password else self.mysql_user
        self.url_base_datos = f'mysql+{self.mysql_driver}://{credenciales}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset={self.mysql_charset}'
        return self

configuracion = Configuracion()