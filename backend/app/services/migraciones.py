"""Migraciones de esquema para bases MySQL que ya existen (Aiven, XAMPP).

`create_all` solo crea las tablas que faltan: no añade columnas ni cambia las de una tabla
existente. Por eso, al arrancar, este módulo lleva una base antigua al esquema actual.

Reglas que se siguen en todos los pasos:

* **Idempotentes.** Cada paso comprueba primero el estado real (`information_schema`) y no hace
  nada si ya está aplicado. Si el arranque se interrumpe a mitad, el siguiente continúa donde quedó.
* **Expandir, copiar, contraer.** Primero se añaden las columnas nuevas, después se copian los
  datos y solo al final se eliminan las antiguas, y únicamente si la copia quedó completa.
* **Con red de seguridad.** Antes de tocar las tablas que cambian se guarda una copia de sus datos
  en tablas `respaldo_v2_*` dentro de la misma base. Se pueden borrar cuando ya no hagan falta.
* **Sin datos en el SQL.** Los valores van siempre como parámetros y los nombres de tablas y
  columnas salen de constantes de este archivo, validadas por `_q`.
"""

import logging
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.catalogos import normalizar_texto

logger = logging.getLogger("aurora-viajes.migraciones")

_IDENTIFICADOR = re.compile(r"^[a-z][a-z0-9_]*$")
_TIPO_SQL = re.compile(r"^[a-z]+(\(\d+(,\d+)?\))?( unsigned)?$")

# Ciudades de salida que conocen los datos de ejemplo; una ciudad de un vuelo antiguo solo trae el
# nombre, así que el país se deduce de aquí (y si no aparece se agrupa en «Sin especificar»).
PAIS_DE_CIUDADES_CONOCIDAS = {
    "bogota": "Colombia", "medellin": "Colombia", "cali": "Colombia", "cartagena": "Colombia",
    "barranquilla": "Colombia", "lima": "Perú", "madrid": "España", "tokio": "Japón",
    "paris": "Francia", "kioto": "Japón", "nueva york": "Estados Unidos",
}
PAIS_SIN_ESPECIFICAR = "Sin especificar"

TABLAS_A_RESPALDAR = ("destinos", "hoteles", "excursiones", "vuelos", "paquetes", "reservas", "reserva_excursiones")


def _q(nombre: str) -> str:
    """Entrecomilla un identificador tras comprobar que solo lleva letras minúsculas, dígitos y guiones bajos."""
    if not _IDENTIFICADOR.match(nombre):
        raise ValueError(f"Identificador SQL no permitido: {nombre!r}")
    return f"`{nombre}`"


def _es_mysql(sesion: AsyncSession) -> bool:
    return bool(sesion.bind and sesion.bind.dialect.name == "mysql")


# --------------------------------------------------------------------------------------
# Consultas al catálogo del servidor
# --------------------------------------------------------------------------------------


async def _existe_tabla(sesion: AsyncSession, tabla: str) -> bool:
    cantidad = await sesion.scalar(
        text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = :t"),
        {"t": tabla},
    )
    return bool(cantidad)


async def _existe_columna(sesion: AsyncSession, tabla: str, columna: str) -> bool:
    cantidad = await sesion.scalar(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
        ),
        {"t": tabla, "c": columna},
    )
    return bool(cantidad)


async def _tipo_columna(sesion: AsyncSession, tabla: str, columna: str) -> str:
    """Tipo exacto de una columna (`int`, `int(10) unsigned`...). Una clave foránea debe copiarlo."""
    tipo = await sesion.scalar(
        text(
            "SELECT COLUMN_TYPE FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
        ),
        {"t": tabla, "c": columna},
    )
    if not tipo or not _TIPO_SQL.fullmatch(str(tipo).lower()):
        raise RuntimeError(f"Tipo inesperado para {tabla}.{columna}: {tipo!r}")
    return str(tipo).lower()


async def _es_anulable(sesion: AsyncSession, tabla: str, columna: str) -> bool:
    valor = await sesion.scalar(
        text(
            "SELECT IS_NULLABLE FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
        ),
        {"t": tabla, "c": columna},
    )
    return str(valor).upper() == "YES"


async def _existe_restriccion(sesion: AsyncSession, tabla: str, restriccion: str) -> bool:
    cantidad = await sesion.scalar(
        text(
            "SELECT COUNT(*) FROM information_schema.table_constraints "
            "WHERE table_schema = DATABASE() AND table_name = :t AND constraint_name = :r"
        ),
        {"t": tabla, "r": restriccion},
    )
    return bool(cantidad)


async def _claves_foraneas_de(sesion: AsyncSession, tabla: str, columna: str) -> list[str]:
    filas = await sesion.execute(
        text(
            "SELECT DISTINCT constraint_name FROM information_schema.key_column_usage "
            "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c "
            "AND referenced_table_name IS NOT NULL"
        ),
        {"t": tabla, "c": columna},
    )
    return [fila[0] for fila in filas.all()]


async def _indices_de_una_columna(sesion: AsyncSession, tabla: str, columna: str) -> list[tuple[str, bool]]:
    """Índices formados solo por esa columna: (nombre, es_único). La clave primaria no se incluye."""
    filas = await sesion.execute(
        text(
            "SELECT index_name, MIN(non_unique), COUNT(*), MAX(column_name = :c) FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = :t AND index_name <> 'PRIMARY' "
            "GROUP BY index_name"
        ),
        {"t": tabla, "c": columna},
    )
    return [(nombre, int(no_unico) == 0) for nombre, no_unico, cantidad, contiene in filas.all() if int(cantidad) == 1 and int(contiene) == 1]


async def _contar_nulos(sesion: AsyncSession, tabla: str, columna: str) -> int:
    return int(await sesion.scalar(text(f"SELECT COUNT(*) FROM {_q(tabla)} WHERE {_q(columna)} IS NULL")) or 0)


async def _ejecutar(sesion: AsyncSession, sql: str, parametros: dict | None = None) -> None:
    await sesion.execute(text(sql), parametros or {})


async def _intentar(sesion: AsyncSession, descripcion: str, sql: str) -> bool:
    """Ejecuta un cambio no imprescindible; si falla lo anota y sigue.

    No usa SAVEPOINT: en MySQL cada DDL confirma la transacción y el savepoint dejaría de existir
    antes de poder volver a él. Todo lo anterior ya está confirmado cuando se llega aquí.
    """
    try:
        await sesion.execute(text(sql))
        return True
    except Exception:  # noqa: BLE001 - una restricción que no se puede añadir no debe impedir el arranque
        await sesion.rollback()
        logger.warning("No se pudo aplicar «%s»; revisa los datos existentes.", descripcion, exc_info=True)
        return False


# --------------------------------------------------------------------------------------
# Operaciones de esquema reutilizables
# --------------------------------------------------------------------------------------


async def _agregar_columna(sesion: AsyncSession, tabla: str, columna: str, definicion: str) -> bool:
    if await _existe_columna(sesion, tabla, columna):
        return False
    await _ejecutar(sesion, f"ALTER TABLE {_q(tabla)} ADD COLUMN {_q(columna)} {definicion}")
    logger.info("Migración: columna %s.%s añadida.", tabla, columna)
    return True


async def _agregar_columna_fk(sesion: AsyncSession, tabla: str, columna: str, ref_tabla: str, ref_columna: str = "id") -> bool:
    """Añade una columna anulable con el tipo exacto de la clave a la que apuntará."""
    tipo = await _tipo_columna(sesion, ref_tabla, ref_columna)
    return await _agregar_columna(sesion, tabla, columna, f"{tipo} NULL")


async def _agregar_clave_foranea(
    sesion: AsyncSession, tabla: str, columna: str, ref_tabla: str, nombre: str, al_borrar: str = "RESTRICT"
) -> None:
    if await _existe_restriccion(sesion, tabla, nombre) or await _claves_foraneas_de(sesion, tabla, columna):
        return
    if al_borrar not in {"RESTRICT", "SET NULL", "CASCADE"}:
        raise ValueError(al_borrar)
    await _intentar(
        sesion,
        f"clave foránea {nombre}",
        f"ALTER TABLE {_q(tabla)} ADD CONSTRAINT {_q(nombre)} FOREIGN KEY ({_q(columna)}) "
        f"REFERENCES {_q(ref_tabla)}(`id`) ON DELETE {al_borrar}",
    )


async def _exigir_no_nula(sesion: AsyncSession, tabla: str, columna: str) -> bool:
    """Pone NOT NULL si la copia de datos quedó completa. Devuelve False si aún hay filas sin valor."""
    if not await _es_anulable(sesion, tabla, columna):
        return True
    if await _contar_nulos(sesion, tabla, columna):
        logger.error("Migración: %s.%s tiene filas sin valor; se deja anulable.", tabla, columna)
        return False
    tipo = await _tipo_columna(sesion, tabla, columna)
    await _ejecutar(sesion, f"ALTER TABLE {_q(tabla)} MODIFY {_q(columna)} {tipo} NOT NULL")
    return True


async def _eliminar_columna(sesion: AsyncSession, tabla: str, columna: str) -> None:
    """Elimina una columna antigua junto con las claves foráneas e índices que solo dependían de ella."""
    if not await _existe_columna(sesion, tabla, columna):
        return
    for clave in await _claves_foraneas_de(sesion, tabla, columna):
        await _ejecutar(sesion, f"ALTER TABLE {_q(tabla)} DROP FOREIGN KEY {_q(clave)}")
    for indice, _unico in await _indices_de_una_columna(sesion, tabla, columna):
        await _ejecutar(sesion, f"ALTER TABLE {_q(tabla)} DROP INDEX {_q(indice)}")
    await _ejecutar(sesion, f"ALTER TABLE {_q(tabla)} DROP COLUMN {_q(columna)}")
    logger.info("Migración: columna %s.%s eliminada.", tabla, columna)


async def _relajar_columna(sesion: AsyncSession, tabla: str, columna: str) -> None:
    """Deja anulable una columna antigua que no se pudo borrar, para que las altas nuevas no fallen."""
    if await _existe_columna(sesion, tabla, columna) and not await _es_anulable(sesion, tabla, columna):
        tipo = await _tipo_columna(sesion, tabla, columna)
        await _ejecutar(sesion, f"ALTER TABLE {_q(tabla)} MODIFY {_q(columna)} {tipo} NULL")


# --------------------------------------------------------------------------------------
# Versión 0 -> 1: columnas que se fueron añadiendo a lo largo del proyecto
# --------------------------------------------------------------------------------------


async def _migrar_a_v1(sesion: AsyncSession) -> None:
    # Reserva con hotel y desglose por concepto.
    if await _agregar_columna_fk(sesion, "reservas", "hotel_id", "hoteles"):
        await _agregar_clave_foranea(sesion, "reservas", "hotel_id", "hoteles", "fk_reserva_hotel")
    for columna in ("monto_vuelo", "monto_hotel", "monto_excursiones"):
        await _agregar_columna(sesion, "reservas", columna, "DECIMAL(12,2) NOT NULL DEFAULT 0")

    # Las reservas a la carta no tienen paquete.
    creada = await _agregar_columna_fk(sesion, "reservas", "paquete_id", "paquetes")
    if not creada and not await _es_anulable(sesion, "reservas", "paquete_id"):
        tipo = await _tipo_columna(sesion, "reservas", "paquete_id")
        await _ejecutar(sesion, f"ALTER TABLE reservas MODIFY COLUMN paquete_id {tipo} NULL")
    await _agregar_clave_foranea(sesion, "reservas", "paquete_id", "paquetes", "fk_reserva_paquete")

    # El tipo de documento pasó de texto a catálogo.
    if await _existe_columna(sesion, "usuarios", "tipo_documento") and not await _existe_columna(sesion, "usuarios", "tipo_documento_id"):
        tipo_id = await _tipo_columna(sesion, "tipos_documento", "id")
        await _ejecutar(sesion, f"ALTER TABLE usuarios ADD COLUMN tipo_documento_id {tipo_id} NULL AFTER apellido")
        await _ejecutar(
            sesion,
            "INSERT IGNORE INTO tipos_documento (codigo, nombre) "
            "SELECT DISTINCT UPPER(TRIM(tipo_documento)), UPPER(TRIM(tipo_documento)) FROM usuarios "
            "WHERE tipo_documento IS NOT NULL AND TRIM(tipo_documento) <> ''",
        )
        await _ejecutar(
            sesion,
            "UPDATE usuarios u JOIN tipos_documento td ON td.codigo = UPPER(TRIM(u.tipo_documento)) SET u.tipo_documento_id = td.id",
        )
        await _ejecutar(
            sesion,
            "UPDATE usuarios u JOIN tipos_documento td ON td.codigo = 'CC' SET u.tipo_documento_id = td.id WHERE u.tipo_documento_id IS NULL",
        )
        await _ejecutar(sesion, f"ALTER TABLE usuarios MODIFY tipo_documento_id {tipo_id} NOT NULL")
        await _ejecutar(sesion, "ALTER TABLE usuarios DROP COLUMN tipo_documento")

    if await _existe_columna(sesion, "reservas", "destino") and not await _existe_columna(sesion, "reservas", "destino_id"):
        raise RuntimeError(
            "La base de datos es de una versión muy antigua (reservas.destino es texto). "
            "Restaura un respaldo o vuelve a crear la base: el arranque la poblará de nuevo."
        )

    if await _agregar_columna_fk(sesion, "reservas", "vuelo_id", "vuelos"):
        await _agregar_clave_foranea(sesion, "reservas", "vuelo_id", "vuelos", "fk_reserva_vuelo")

    # Enlace venta -> reserva: permite que pagar o cancelar una reserva actualice su venta y su factura.
    if not await _existe_columna(sesion, "ventas", "reserva_id"):
        tipo_id = await _tipo_columna(sesion, "reservas", "id")
        await _ejecutar(sesion, f"ALTER TABLE ventas ADD COLUMN reserva_id {tipo_id} NULL")
        await _ejecutar(sesion, "ALTER TABLE ventas ADD CONSTRAINT uq_venta_reserva UNIQUE (reserva_id)")
        await _ejecutar(
            sesion,
            "ALTER TABLE ventas ADD CONSTRAINT fk_venta_reserva FOREIGN KEY (reserva_id) REFERENCES reservas(id) ON DELETE SET NULL",
        )
        await _enlazar_ventas_antiguas(sesion)


async def _enlazar_ventas_antiguas(sesion: AsyncSession) -> None:
    """Empareja las ventas anteriores a la columna con su reserva y pone al día sus estados.

    Una venta y su reserva se crean en la misma petición, así que coinciden en
    cliente, total y hora (con unos segundos de margen). Si el emparejamiento es
    ambiguo se omite: es preferible una venta sin enlace a una enlazada mal.
    """
    try:
        async with sesion.begin_nested():
            await _ejecutar(
                sesion,
                "UPDATE ventas v JOIN reservas r ON r.usuario_id = v.cliente_id AND r.monto_total = v.total "
                "AND ABS(TIMESTAMPDIFF(SECOND, r.creado_en, v.creado_en)) <= 5 "
                "SET v.reserva_id = r.id WHERE v.reserva_id IS NULL",
            )
    except Exception:  # noqa: BLE001 - el enlace de ventas antiguas es un extra, no debe impedir el arranque
        logger.warning("No se pudieron enlazar las ventas antiguas con sus reservas.", exc_info=True)
        return
    await _ejecutar(
        sesion,
        "UPDATE ventas v JOIN reservas r ON r.id = v.reserva_id "
        "JOIN estados_reserva er ON er.id = r.estado_id JOIN estados_pago ep ON ep.id = r.estado_pago_id "
        "SET v.estado = CASE WHEN er.codigo = 'cancelada' THEN 'cancelada' "
        "WHEN ep.codigo = 'pagado' THEN 'completada' ELSE 'pendiente' END",
    )
    await _ejecutar(
        sesion,
        "UPDATE facturas f JOIN ventas v ON v.id = f.venta_id "
        "SET f.estado = CASE WHEN v.estado = 'cancelada' THEN 'anulada' ELSE 'emitida' END "
        "WHERE v.reserva_id IS NOT NULL",
    )


# --------------------------------------------------------------------------------------
# Versión 1 -> 2: tercera forma normal
# --------------------------------------------------------------------------------------


class _Lugares:
    """Busca o crea países y ciudades a partir de los textos de las tablas antiguas."""

    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion
        self.paises: dict[str, int] = {}
        self.ciudades: list[tuple[int, int, str]] = []  # (id, pais_id, nombre normalizado)

    async def cargar(self) -> None:
        self.paises = {normalizar_texto(n): i for i, n in (await self.sesion.execute(text("SELECT id, nombre FROM paises"))).all()}
        self.ciudades = [
            (i, p, normalizar_texto(n)) for i, p, n in (await self.sesion.execute(text("SELECT id, pais_id, nombre FROM ciudades"))).all()
        ]

    async def pais(self, nombre: str) -> int:
        clave = normalizar_texto(nombre)
        if clave not in self.paises:
            resultado = await self.sesion.execute(text("INSERT INTO paises (nombre) VALUES (:n)"), {"n": nombre.strip()[:80]})
            self.paises[clave] = int(resultado.lastrowid)
        return self.paises[clave]

    async def _crear(self, nombre: str, pais_id: int) -> int:
        resultado = await self.sesion.execute(
            text("INSERT INTO ciudades (pais_id, nombre) VALUES (:p, :n)"), {"p": pais_id, "n": nombre.strip()[:80]}
        )
        ciudad_id = int(resultado.lastrowid)
        self.ciudades.append((ciudad_id, pais_id, normalizar_texto(nombre)))
        return ciudad_id

    async def de_pais(self, nombre: str, pais_id: int) -> int:
        """La ciudad con ese nombre dentro de ese país (se crea si no existe)."""
        clave = normalizar_texto(nombre)
        for ciudad_id, pais, normal in self.ciudades:
            if pais == pais_id and normal == clave:
                return ciudad_id
        return await self._crear(nombre, pais_id)

    async def resolver(self, nombre: str, pais: str | None = None) -> int:
        """La ciudad que corresponde a un texto suelto. Un país escrito distinto («EE. UU.») no la duplica."""
        clave = normalizar_texto(nombre)
        candidatas = [c for c in self.ciudades if c[2] == clave]
        if candidatas:
            if len(candidatas) > 1 and pais:
                pais_id = self.paises.get(normalizar_texto(pais))
                for ciudad_id, pais_ciudad, _ in candidatas:
                    if pais_ciudad == pais_id:
                        return ciudad_id
            return candidatas[0][0]
        nombre_pais = pais or PAIS_DE_CIUDADES_CONOCIDAS.get(clave) or PAIS_SIN_ESPECIFICAR
        return await self._crear(nombre, await self.pais(nombre_pais))


async def _respaldar(sesion: AsyncSession) -> None:
    """Copia de seguridad, dentro de la misma base, de las tablas que la migración modifica.

    Se hace con `CREATE TABLE ... LIKE` más `INSERT ... SELECT`, y no con `CREATE TABLE ... AS SELECT`, que
    MySQL rechaza cuando el servidor exige consistencia de GTID (como en varios servicios gestionados). La
    copia se escribe primero en una tabla temporal que solo se renombra al terminar: si el arranque se
    interrumpe a mitad, nunca queda una copia incompleta que parezca válida.
    """
    for tabla in TABLAS_A_RESPALDAR:
        final, temporal = f"respaldo_v2_{tabla}", f"respaldo_v2_{tabla}_tmp"
        if not await _existe_tabla(sesion, tabla) or await _existe_tabla(sesion, final):
            continue
        if await _existe_tabla(sesion, temporal):
            await _ejecutar(sesion, f"DROP TABLE {_q(temporal)}")
        await _ejecutar(sesion, f"CREATE TABLE {_q(temporal)} LIKE {_q(tabla)}")
        await _ejecutar(sesion, f"INSERT INTO {_q(temporal)} SELECT * FROM {_q(tabla)}")
        await _ejecutar(sesion, f"RENAME TABLE {_q(temporal)} TO {_q(final)}")
        logger.info("Migración: respaldo de %s guardado en %s.", tabla, final)


async def _agregar_columnas_v2(sesion: AsyncSession) -> None:
    for tabla in ("destinos", "hoteles", "excursiones"):
        await _agregar_columna_fk(sesion, tabla, "ciudad_id", "ciudades")
    for columna, ref in (("aerolinea_id", "aerolineas"), ("modelo_avion_id", "modelos_avion"), ("origen_id", "ciudades"), ("destino_id", "ciudades")):
        await _agregar_columna_fk(sesion, "vuelos", columna, ref)
    await _agregar_columna_fk(sesion, "paquetes", "vuelo_regreso_id", "vuelos")
    await _agregar_columna(sesion, "paquetes", "noches", "INT NULL")
    await _agregar_columna_fk(sesion, "reservas", "vuelo_regreso_id", "vuelos")
    await _agregar_columna_fk(sesion, "reservas", "creada_por_id", "usuarios")
    await _agregar_columna_fk(sesion, "reservas", "pago_registrado_por_id", "usuarios")
    await _agregar_columna(sesion, "reservas", "pago_referencia", "VARCHAR(80) NULL")
    await _agregar_columna(sesion, "reservas", "pagado_en", "DATETIME NULL")
    await _agregar_columna(sesion, "reserva_excursiones", "cantidad", "INT NULL")
    await _agregar_columna(sesion, "reserva_excursiones", "precio_unitario", "DECIMAL(12,2) NULL")
    await _agregar_columna(sesion, "usuarios", "sesion_version", "INT NOT NULL DEFAULT 0")
    await _agregar_columna(sesion, "usuarios", "debe_cambiar_contrasena", "TINYINT(1) NOT NULL DEFAULT 0")
    await _agregar_columna(sesion, "usuarios", "acepto_datos_en", "DATETIME NULL")


async def _copiar_datos_v2(sesion: AsyncSession) -> None:
    """Rellena las columnas nuevas a partir de los textos antiguos."""
    lugares = _Lugares(sesion)
    await lugares.cargar()

    if await _existe_columna(sesion, "destinos", "nombre"):
        filas = (await sesion.execute(text("SELECT id, nombre, pais_id FROM destinos WHERE ciudad_id IS NULL"))).all()
        for destino_id, nombre, pais_id in filas:
            ciudad = str(nombre).split(",")[0].strip() or str(nombre).strip()
            ciudad_id = await lugares.de_pais(ciudad, pais_id)
            await _ejecutar(sesion, "UPDATE destinos SET ciudad_id = :c WHERE id = :i", {"c": ciudad_id, "i": destino_id})

    for tabla in ("hoteles", "excursiones"):
        if await _existe_columna(sesion, tabla, "ciudad"):
            filas = (await sesion.execute(text(f"SELECT id, ciudad, pais FROM {_q(tabla)} WHERE ciudad_id IS NULL"))).all()
            for fila_id, ciudad, pais in filas:
                ciudad_id = await lugares.resolver(str(ciudad), str(pais) if pais else None)
                await _ejecutar(sesion, f"UPDATE {_q(tabla)} SET ciudad_id = :c WHERE id = :i", {"c": ciudad_id, "i": fila_id})

    if await _existe_columna(sesion, "vuelos", "aerolinea"):
        aerolineas = {normalizar_texto(n): i for i, n in (await sesion.execute(text("SELECT id, nombre FROM aerolineas"))).all()}
        codigos = {c for (c,) in (await sesion.execute(text("SELECT codigo FROM aerolineas"))).all()}
        modelos = {normalizar_texto(n): i for i, n in (await sesion.execute(text("SELECT id, nombre FROM modelos_avion"))).all()}
        filas = (await sesion.execute(text(
            "SELECT id, aerolinea, avion, origen, destino, capacidad_maxima FROM vuelos "
            "WHERE aerolinea_id IS NULL OR modelo_avion_id IS NULL OR origen_id IS NULL OR destino_id IS NULL"
        ))).all()
        for vuelo_id, aerolinea, avion, origen, destino, capacidad in filas:
            clave = normalizar_texto(str(aerolinea))
            if clave not in aerolineas:
                codigo = "".join(c for c in str(aerolinea).upper() if c.isalpha())[:3] or "XX"
                while codigo in codigos:
                    codigo = (codigo[:2] + str(len(codigos) % 10))[:4]
                codigos.add(codigo)
                resultado = await sesion.execute(text("INSERT INTO aerolineas (codigo, nombre) VALUES (:c, :n)"), {"c": codigo, "n": str(aerolinea).strip()[:80]})
                aerolineas[clave] = int(resultado.lastrowid)
            clave_modelo = normalizar_texto(str(avion))
            if clave_modelo not in modelos:
                resultado = await sesion.execute(
                    text("INSERT INTO modelos_avion (nombre, capacidad) VALUES (:n, :c)"), {"n": str(avion).strip()[:80], "c": max(int(capacidad or 1), 1)}
                )
                modelos[clave_modelo] = int(resultado.lastrowid)
            await _ejecutar(
                sesion,
                "UPDATE vuelos SET aerolinea_id = :a, modelo_avion_id = :m, origen_id = :o, destino_id = :d WHERE id = :i",
                {
                    "a": aerolineas[clave], "m": modelos[clave_modelo],
                    "o": await lugares.resolver(str(origen)), "d": await lugares.resolver(str(destino)), "i": vuelo_id,
                },
            )

    if await _existe_columna(sesion, "paquetes", "fecha_salida"):
        await _ejecutar(sesion, "UPDATE paquetes SET noches = GREATEST(1, DATEDIFF(fecha_regreso, fecha_salida)) WHERE noches IS NULL")

    # Las reservas anteriores al desglose tienen el total pero ningún componente: todo era «vuelo».
    await _ejecutar(
        sesion,
        "UPDATE reservas SET monto_vuelo = monto_total "
        "WHERE monto_vuelo = 0 AND monto_hotel = 0 AND monto_excursiones = 0 AND monto_total > 0",
    )
    # Antes, una reserva de paquete no guardaba el hotel ni las excursiones que el paquete incluía: se completan con
    # las del paquete (sin cobro aparte), para que se vean igual que las reservas nuevas. Es repetible sin duplicar.
    await _ejecutar(sesion, "UPDATE reservas r JOIN paquetes p ON p.id = r.paquete_id SET r.hotel_id = p.hotel_id WHERE r.hotel_id IS NULL")
    await _ejecutar(
        sesion,
        "INSERT INTO reserva_excursiones (reserva_id, excursion_id, cantidad, precio_unitario) "
        "SELECT r.id, pe.excursion_id, r.pasajeros, 0 FROM reservas r JOIN paquete_excursiones pe ON pe.paquete_id = r.paquete_id "
        "WHERE NOT EXISTS (SELECT 1 FROM reserva_excursiones re WHERE re.reserva_id = r.id AND re.excursion_id = pe.excursion_id)",
    )
    # Las excursiones que ya tenía cada reserva conservan el precio de hoy como precio de venta;
    # en un paquete van incluidas, sin cobro aparte.
    await _ejecutar(
        sesion,
        "UPDATE reserva_excursiones re JOIN reservas r ON r.id = re.reserva_id JOIN excursiones e ON e.id = re.excursion_id "
        "SET re.cantidad = r.pasajeros, re.precio_unitario = CASE WHEN r.paquete_id IS NULL THEN e.precio ELSE 0 END "
        "WHERE re.cantidad IS NULL OR re.precio_unitario IS NULL",
    )


async def _cerrar_v2(sesion: AsyncSession) -> None:
    """Exige las columnas nuevas, crea sus claves y restricciones y elimina las antiguas ya copiadas."""
    # (tabla, columna, tabla referenciada, columnas antiguas que sustituye)
    reemplazos = [
        ("destinos", "ciudad_id", "ciudades", ["nombre", "pais_id"]),
        ("hoteles", "ciudad_id", "ciudades", ["ciudad", "pais"]),
        ("excursiones", "ciudad_id", "ciudades", ["ciudad", "pais"]),
    ]
    for tabla, columna, ref, antiguas in reemplazos:
        completa = await _exigir_no_nula(sesion, tabla, columna)
        await _agregar_clave_foranea(sesion, tabla, columna, ref, f"fk_{tabla}_{columna}")
        for antigua in antiguas:
            await (_eliminar_columna(sesion, tabla, antigua) if completa else _relajar_columna(sesion, tabla, antigua))

    vuelos_completo = True
    for columna, ref in (("aerolinea_id", "aerolineas"), ("modelo_avion_id", "modelos_avion"), ("origen_id", "ciudades"), ("destino_id", "ciudades")):
        vuelos_completo = await _exigir_no_nula(sesion, "vuelos", columna) and vuelos_completo
        await _agregar_clave_foranea(sesion, "vuelos", columna, ref, f"fk_vuelos_{columna}")
    for antigua in ("aerolinea", "avion", "origen", "destino"):
        await (_eliminar_columna(sesion, "vuelos", antigua) if vuelos_completo else _relajar_columna(sesion, "vuelos", antigua))

    paquetes_completo = await _exigir_no_nula(sesion, "paquetes", "noches")
    await _agregar_clave_foranea(sesion, "paquetes", "vuelo_regreso_id", "vuelos", "fk_paquetes_vuelo_regreso")
    for antigua in ("fecha_salida", "fecha_regreso"):
        await (_eliminar_columna(sesion, "paquetes", antigua) if paquetes_completo else _relajar_columna(sesion, "paquetes", antigua))

    await _agregar_clave_foranea(sesion, "reservas", "vuelo_regreso_id", "vuelos", "fk_reservas_vuelo_regreso")
    await _agregar_clave_foranea(sesion, "reservas", "creada_por_id", "usuarios", "fk_reservas_creada_por", "SET NULL")
    await _agregar_clave_foranea(sesion, "reservas", "pago_registrado_por_id", "usuarios", "fk_reservas_pago_por", "SET NULL")

    await _exigir_no_nula(sesion, "reserva_excursiones", "cantidad")
    await _exigir_no_nula(sesion, "reserva_excursiones", "precio_unitario")

    # El mismo número de vuelo se repite cada semana: lo único es «número + salida».
    for indice, unico in await _indices_de_una_columna(sesion, "vuelos", "numero_vuelo"):
        if unico:
            await _ejecutar(sesion, f"ALTER TABLE vuelos DROP INDEX {_q(indice)}")
            await _ejecutar(sesion, "CREATE INDEX ix_vuelos_numero_vuelo ON vuelos (numero_vuelo)")

    restricciones_unicas = [
        ("destinos", "uq_destinos_ciudad", "UNIQUE (ciudad_id)"),
        ("hoteles", "uq_hotel_ciudad_nombre", "UNIQUE (ciudad_id, nombre)"),
        ("excursiones", "uq_excursion_ciudad_nombre", "UNIQUE (ciudad_id, nombre)"),
        ("vuelos", "uq_vuelo_numero_fecha", "UNIQUE (numero_vuelo, fecha_salida)"),
    ]
    for tabla, nombre, definicion in restricciones_unicas:
        if not await _existe_restriccion(sesion, tabla, nombre) and not (nombre == "uq_destinos_ciudad" and await _tiene_indice_unico(sesion, "destinos", "ciudad_id")):
            await _intentar(sesion, nombre, f"ALTER TABLE {_q(tabla)} ADD CONSTRAINT {_q(nombre)} {definicion}")

    validaciones = [
        ("reservas", "ck_reserva_pasajeros", "pasajeros >= 1 AND pasajeros <= 9"),
        ("reservas", "ck_reserva_fechas", "fecha_regreso >= fecha_salida"),
        (
            "reservas", "ck_reserva_monto",
            "monto_vuelo >= 0 AND monto_hotel >= 0 AND monto_excursiones >= 0 "
            "AND ABS(monto_total - (monto_vuelo + monto_hotel + monto_excursiones)) < 0.005",
        ),
        ("vuelos", "ck_vuelo_ruta", "origen_id <> destino_id"),
        ("vuelos", "ck_vuelo_horario", "fecha_llegada > fecha_salida"),
        ("vuelos", "ck_vuelo_capacidad", "capacidad_maxima >= 1"),
        ("hoteles", "ck_hotel_estrellas", "estrellas >= 1 AND estrellas <= 5"),
        ("hoteles", "ck_hotel_precio", "precio_noche >= 0"),
        ("excursiones", "ck_excursion_duracion", "duracion_horas >= 1 AND duracion_horas <= 48"),
        ("excursiones", "ck_excursion_precio", "precio >= 0"),
        ("paquetes", "ck_paquete_noches", "noches >= 1"),
        ("paquetes", "ck_paquete_precio", "precio_base >= 0"),
        ("destinos", "ck_destino_precio", "precio_base >= 0"),
        ("reserva_excursiones", "ck_reserva_excursion_cantidad", "cantidad >= 1"),
        ("reserva_excursiones", "ck_reserva_excursion_precio", "precio_unitario >= 0"),
    ]
    for tabla, nombre, condicion in validaciones:
        if not await _existe_restriccion(sesion, tabla, nombre):
            await _intentar(sesion, nombre, f"ALTER TABLE {_q(tabla)} ADD CONSTRAINT {_q(nombre)} CHECK ({condicion})")


async def _tiene_indice_unico(sesion: AsyncSession, tabla: str, columna: str) -> bool:
    return any(unico for _, unico in await _indices_de_una_columna(sesion, tabla, columna))


async def _migrar_a_v2(sesion: AsyncSession) -> None:
    hay_legado = False
    for tabla, columna in (("destinos", "nombre"), ("hoteles", "ciudad"), ("excursiones", "ciudad"), ("vuelos", "aerolinea"), ("paquetes", "fecha_salida")):
        hay_legado = hay_legado or await _existe_columna(sesion, tabla, columna)
    if hay_legado:
        await _respaldar(sesion)
    await _agregar_columnas_v2(sesion)
    if hay_legado:
        await _copiar_datos_v2(sesion)
    await _cerrar_v2(sesion)


async def migrar_esquema(sesion: AsyncSession) -> None:
    """Lleva una base MySQL antigua al esquema actual. En SQLite no hace nada: allí la base se crea de cero."""
    if not _es_mysql(sesion):
        return
    await _migrar_a_v1(sesion)
    await _migrar_a_v2(sesion)
    await sesion.commit()
