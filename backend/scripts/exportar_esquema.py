"""Genera sql/schema.sql a partir de los modelos, para que el script SQL nunca se desfase del código.

    python -m scripts.exportar_esquema

Solo contiene la estructura. El catálogo (destinos, vuelos, hoteles, roles, permisos) y el
administrador los crea la propia aplicación la primera vez que arranca.
"""

import os
from pathlib import Path

# No hace falta configuración real para compilar el DDL: se evita leer backend/.env.
os.environ.setdefault("AURORA_ENV_FILE", "")
os.environ.setdefault("SECRET_KEY", "solo-para-exportar-el-esquema-" + "x" * 16)
os.environ.setdefault("MOTOR_BD", "sqlite")

from sqlalchemy.dialects import mysql  # noqa: E402
from sqlalchemy.schema import CreateIndex, CreateTable  # noqa: E402

from app.core.base_datos import Base  # noqa: E402
import app.models.dominio  # noqa: E402,F401  (registra las tablas en Base.metadata)

DESTINO = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"


def generar() -> str:
    dialecto = mysql.dialect()
    tablas = list(Base.metadata.sorted_tables)  # ordenadas para que cada clave foránea encuentre su tabla
    lineas = [
        "-- Generado por scripts/exportar_esquema.py a partir de app/models/dominio.py. No editar a mano.",
        "-- Solo estructura: el catálogo, los roles y el administrador los siembra la aplicación al arrancar.",
        "CREATE DATABASE IF NOT EXISTS aurora_viajes CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
        "USE aurora_viajes;",
        "",
        "SET FOREIGN_KEY_CHECKS = 0;",
        *[f"DROP TABLE IF EXISTS {tabla.name};" for tabla in reversed(tablas)],
        "SET FOREIGN_KEY_CHECKS = 1;",
        "",
    ]
    for tabla in tablas:
        lineas.append(str(CreateTable(tabla).compile(dialect=dialecto)).strip() + ";")
        for indice in sorted(tabla.indexes, key=lambda i: i.name or ""):
            lineas.append(str(CreateIndex(indice).compile(dialect=dialecto)).strip() + ";")
        lineas.append("")
    return "\n".join(lineas)


if __name__ == "__main__":
    DESTINO.write_text(generar(), encoding="utf-8")
    print(f"Esquema escrito en {DESTINO}")
