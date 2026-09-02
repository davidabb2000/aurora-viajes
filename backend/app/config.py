import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:@localhost:3306/aurora_viajes?charset=utf8mb4",
    )
    JWT_SECRET: str = os.getenv("JWT_SECRET", "aurora_viajes_secret")
    JWT_EXPIRES_IN: str = os.getenv("JWT_EXPIRES_IN", "8h")
    ALGORITHM: str = "HS256"
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@auroraviajes.com")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "Admin123!")


settings = Settings()
