"""Arranque de la base: crea el esquema, siembra el catálogo y migra bases antiguas."""
import logging
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_datos import Base, FabricaDeSesiones, motor
from app.core.configuracion import configuracion
from app.core.seguridad import hashear_contrasena, verificar_contrasena
from app.models.dominio import (
    Destino, EstadoPago, EstadoReserva, Excursion, Hotel, MetodoPago, Pais, Paquete, Permiso,
    Role, TipoDocumento, User, Vuelo,
)


logger = logging.getLogger("aurora-viajes")

PERMISOS_POR_ROL = {
    "administrador": ["usuarios:gestionar", "productos:gestionar", "servicios:gestionar", "reservas:gestionar", "mensajes:leer"],
    "empleado": ["reservas:gestionar"],
    "cliente": ["reservas:crear"],
}

TIPOS_DOCUMENTO_SEMILLA = [
    ("CC", "Cédula de ciudadanía"),
    ("TI", "Tarjeta de identidad"),
    ("CE", "Cédula de extranjería"),
    ("PA", "Pasaporte"),
]

PAISES_Y_DESTINOS_SEMILLA = [
    ("Francia", "París, Francia", "Recorre el Sena al atardecer y descubre por qué la Ciudad Luz sigue inspirando a viajeros de todo el mundo.", "paris", Decimal("6900000")),
    ("Japón", "Kioto, Japón", "Templos centenarios, jardines de piedra y la calma de los bosques de bambú te esperan en el antiguo Japón.", "kioto", Decimal("8400000")),
    ("Indonesia", "Bali, Indonesia", "Playas volcánicas, arrozales en terraza y una cultura espiritual que transforma cada visita en un ritual.", "bali", Decimal("7600000")),
    ("Colombia", "Cartagena, Colombia", "Murallas coloniales, calles de colores y el Caribe a un paso: la joya histórica de Colombia.", "cartagena", Decimal("1200000")),
    ("Grecia", "Santorini, Grecia", "Casas blancas suspendidas sobre el mar Egeo y atardeceres que se han vuelto leyenda.", "santorini", Decimal("9800000")),
    ("Perú", "Cusco, Perú", "Puerta de entrada a Machu Picchu y corazón del imperio inca, entre montañas y terrazas ancestrales.", "cusco", Decimal("2500000")),
    ("Marruecos", "Marrakech, Marruecos", "Zocos bulliciosos, palacios ocultos y el aroma a especias en cada esquina de la medina.", "marrakech", Decimal("8900000")),
    ("Islandia", "Reikiavik, Islandia", "Auroras boreales, fuentes termales y paisajes volcánicos al borde del Atlántico Norte.", "reikiavik", Decimal("10800000")),
    ("Estados Unidos", "Nueva York, EE. UU.", "Rascacielos icónicos, parques urbanos y una energía que nunca duerme.", "nueva-york", Decimal("7200000")),
    ("Egipto", "El Cairo, Egipto", "Las pirámides de Giza y el Nilo milenario te acercan a una de las civilizaciones más fascinantes de la historia.", "cairo", Decimal("9300000")),
]

VUELOS_SEMILLA = [
    ("AV101", "Aurora Airlines", "Airbus A320", "Bogotá", "París", datetime(2026, 10, 5, 8, 30), datetime(2026, 10, 5, 23, 15), 180, "A12", "1"),
    ("AV202", "Aurora Airlines", "Boeing 787", "Bogotá", "Tokio", datetime(2026, 10, 12, 10, 0), datetime(2026, 10, 13, 8, 30), 260, "B04", "2"),
]

PAQUETES_PUBLICADOS_SEMILLA = [
    ("París, Francia", "AUR301", "Bogotá", "París", "Hotel Lumière Aurora", "París", "Francia", 5, 480000, ("Crucero nocturno por el Sena", 3, 180000), ("Ruta de arte en Montmartre", 4, 145000), ("Versalles y sus jardines", 6, 220000)),
    ("Kioto, Japón", "AUR302", "Bogotá", "Kioto", "Ryokan Sakura Aurora", "Kioto", "Japón", 4, 390000, ("Ceremonia del té tradicional", 3, 165000), ("Bosque de bambú de Arashiyama", 5, 210000), ("Nara y sus templos", 8, 260000)),
    ("Bali, Indonesia", "AUR303", "Bogotá", "Bali", "Ubud Rice Terrace Resort", "Bali", "Indonesia", 5, 310000, ("Amanecer en el monte Batur", 7, 240000), ("Templos y arrozales de Ubud", 6, 190000), ("Snorkel en Nusa Penida", 8, 280000)),
    ("Cartagena, Colombia", "AUR304", "Bogotá", "Cartagena", "Casa del Mar Boutique", "Cartagena", "Colombia", 4, 280000, ("Recorrido por la ciudad amurallada", 3, 85000), ("Atardecer en la bahía", 2, 110000), ("Islas del Rosario", 8, 230000)),
    ("Santorini, Grecia", "AUR305", "Bogotá", "Santorini", "Aegean White Suites", "Santorini", "Grecia", 5, 520000, ("Caldera y pueblos blancos", 5, 220000), ("Cata de vinos volcánicos", 4, 195000), ("Paseo en catamarán", 7, 290000)),
    ("Cusco, Perú", "AUR306", "Bogotá", "Cusco", "Andenes del Sol Hotel", "Cusco", "Perú", 4, 250000, ("Machu Picchu en tren", 10, 420000), ("Valle Sagrado de los Incas", 8, 260000), ("Montaña de siete colores", 12, 230000)),
    ("Marrakech, Marruecos", "AUR307", "Bogotá", "Marrakech", "Riad Medina Aurora", "Marrakech", "Marruecos", 4, 300000, ("Sabores de la medina", 4, 150000), ("Palacio de la Bahía y zocos", 5, 130000), ("Desierto de Agafay", 8, 250000)),
    ("Reikiavik, Islandia", "AUR308", "Bogotá", "Reikiavik", "Northern Lights Lodge", "Reikiavik", "Islandia", 4, 430000, ("Cacería de auroras boreales", 5, 260000), ("Círculo dorado", 8, 290000), ("Laguna Azul y costa volcánica", 7, 310000)),
    ("Nueva York, EE. UU.", "AUR309", "Bogotá", "Nueva York", "Manhattan Skyline Hotel", "Nueva York", "EE. UU.", 4, 560000, ("Manhattan y Central Park", 6, 210000), ("Luces de Broadway", 4, 280000), ("Estatua de la Libertad", 5, 190000)),
    ("El Cairo, Egipto", "AUR310", "Bogotá", "El Cairo", "Nile View Palace", "El Cairo", "Egipto", 5, 270000, ("Pirámides de Giza y esfinge", 6, 230000), ("Museo Egipcio y bazar Khan el Khalili", 5, 170000), ("Crucero al atardecer por el Nilo", 3, 155000)),
]

ESTADOS_RESERVA_SEMILLA = [
    ("pendiente", "Pendiente"),
    ("confirmada", "Confirmada"),
    ("cancelada", "Cancelada"),
]

ESTADOS_PAGO_SEMILLA = [
    ("pendiente", "Pendiente"),
    ("pagado", "Pagado"),
    ("fallido", "Fallido"),
]

METODOS_PAGO_SEMILLA = [
    ("stripe", "Stripe"),
    ("transferencia", "Transferencia"),
]


def _clausula_no_duplicados(sesion: AsyncSession) -> str:
    return "INSERT IGNORE" if sesion.bind and sesion.bind.dialect.name == "mysql" else "INSERT OR IGNORE"


async def asegurar_base_inicial() -> None:
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
        for tabla in ("hoteles", "excursiones"):
            if conexion.dialect.name == "mysql":
                columnas = await conexion.execute(text(f"SHOW COLUMNS FROM {tabla} LIKE 'pais'"))
                existe_pais = columnas.first() is not None
            else:
                columnas = await conexion.execute(text(f"PRAGMA table_info({tabla})"))
                existe_pais = any(columna[1] == "pais" for columna in columnas.fetchall())
            if not existe_pais:
                posicion = " AFTER ciudad" if conexion.dialect.name == "mysql" else ""
                await conexion.execute(text(f"ALTER TABLE {tabla} ADD COLUMN pais VARCHAR(120) NOT NULL DEFAULT ''{posicion}"))
    async with FabricaDeSesiones() as sesion:
        clausula = _clausula_no_duplicados(sesion)

        tipos_documento_cache: dict[str, TipoDocumento] = {}
        for codigo, nombre in TIPOS_DOCUMENTO_SEMILLA:
            tipo_documento = await sesion.scalar(select(TipoDocumento).where(TipoDocumento.codigo == codigo))
            if tipo_documento is None:
                tipo_documento = TipoDocumento(codigo=codigo, nombre=nombre)
                sesion.add(tipo_documento)
                await sesion.flush()
            tipos_documento_cache[codigo] = tipo_documento

        paises_cache: dict[str, Pais] = {}
        for pais_nombre, *_resto in PAISES_Y_DESTINOS_SEMILLA:
            pais = await sesion.scalar(select(Pais).where(Pais.nombre == pais_nombre))
            if pais is None:
                pais = Pais(nombre=pais_nombre)
                sesion.add(pais)
                await sesion.flush()
            paises_cache[pais_nombre] = pais

        destinos_cache: dict[str, Destino] = {}
        for pais_nombre, nombre, descripcion, slug, precio_base in PAISES_Y_DESTINOS_SEMILLA:
            destino = await sesion.scalar(select(Destino).where(Destino.nombre == nombre))
            if destino is None:
                destino = Destino(
                    pais_id=paises_cache[pais_nombre].id,
                    nombre=nombre,
                    descripcion=descripcion,
                    precio_base=precio_base,
                    imagen_slug=slug,
                    activo=True,
                )
                sesion.add(destino)
                await sesion.flush()
            else:
                destino.pais_id = paises_cache[pais_nombre].id
                destino.descripcion = descripcion
                destino.precio_base = precio_base
                destino.imagen_slug = slug
                destino.activo = True
            destinos_cache[nombre] = destino

        for numero, aerolinea, avion, origen, destino, salida, llegada, capacidad, puerta, terminal in VUELOS_SEMILLA:
            vuelo = await sesion.scalar(select(Vuelo).where(Vuelo.numero_vuelo == numero))
            if vuelo is None:
                sesion.add(
                    Vuelo(
                        numero_vuelo=numero,
                        aerolinea=aerolinea,
                        avion=avion,
                        origen=origen,
                        destino=destino,
                        fecha_salida=salida,
                        fecha_llegada=llegada,
                        capacidad_maxima=capacidad,
                        puerta=puerta,
                        terminal=terminal,
                        estado="programado",
                        activo=True,
                    )
                )

        for indice, datos in enumerate(PAQUETES_PUBLICADOS_SEMILLA):
            (
                destino_nombre, numero_vuelo, origen, ciudad, hotel_nombre, hotel_ciudad, hotel_pais,
                estrellas, precio_noche, *datos_excursiones,
            ) = datos
            nombre_paquete = f"Aurora {destino_nombre.split(',')[0]}: experiencia completa"
            paquete_existente = await sesion.scalar(select(Paquete).where(Paquete.nombre == nombre_paquete))
            if paquete_existente is not None:
                continue

            destino = destinos_cache[destino_nombre]
            fecha_salida = date(2026, 10, 5) + timedelta(days=4 * indice)
            fecha_regreso = fecha_salida + timedelta(days=6 + indice % 3)
            vuelo = await sesion.scalar(select(Vuelo).where(Vuelo.numero_vuelo == numero_vuelo))
            if vuelo is None:
                vuelo = Vuelo(
                    numero_vuelo=numero_vuelo,
                    aerolinea="Aurora Airlines",
                    avion="Airbus A320" if indice % 2 == 0 else "Boeing 787",
                    origen=origen,
                    destino=ciudad,
                    fecha_salida=datetime.combine(fecha_salida, time(7 + indice % 5, 30), tzinfo=timezone.utc),
                    fecha_llegada=datetime.combine(fecha_salida, time(19 + indice % 3, 15), tzinfo=timezone.utc) + timedelta(days=1 if indice in (1, 5, 7) else 0),
                    capacidad_maxima=180 if indice % 2 == 0 else 260,
                    puerta=f"{chr(65 + indice % 4)}{10 + indice:02d}",
                    terminal=str(1 + indice % 3),
                    estado="programado",
                    activo=True,
                )
                sesion.add(vuelo)
                await sesion.flush()

            hotel = await sesion.scalar(select(Hotel).where(Hotel.nombre == hotel_nombre))
            if hotel is None:
                hotel = Hotel(
                    nombre=hotel_nombre,
                    ciudad=hotel_ciudad,
                    pais=hotel_pais,
                    estrellas=estrellas,
                    precio_noche=precio_noche,
                    descripcion=f"Alojamiento seleccionado en {hotel_ciudad}, con desayuno, recepción 24 horas y ubicación estratégica para recorrer el destino.",
                    activo=True,
                )
                sesion.add(hotel)
                await sesion.flush()

            excursiones = []
            for numero_excursion, (nombre, duracion, precio) in enumerate(datos_excursiones, 1):
                excursion = await sesion.scalar(select(Excursion).where(Excursion.nombre == nombre))
                if excursion is None:
                    excursion = Excursion(
                        nombre=nombre,
                        ciudad=hotel_ciudad,
                        pais=hotel_pais,
                        duracion_horas=duracion,
                        precio=precio,
                        descripcion=f"Experiencia guiada para conocer {hotel_ciudad} con acompañamiento local y tiempo para fotografías.",
                        activo=True,
                    )
                    sesion.add(excursion)
                    await sesion.flush()
                excursiones.append(excursion)

            precio_base = (Decimal(str(destino.precio_base)) * Decimal("1.12")).quantize(Decimal("0.01"))
            sesion.add(
                Paquete(
                    nombre=nombre_paquete,
                    destino_id=destino.id,
                    vuelo_id=vuelo.id,
                    hotel_id=hotel.id,
                    fecha_salida=fecha_salida,
                    fecha_regreso=fecha_regreso,
                    precio_base=precio_base,
                    activo=True,
                    excursiones=excursiones,
                )
            )

        estados_reserva_cache: dict[str, EstadoReserva] = {}
        for codigo, nombre in ESTADOS_RESERVA_SEMILLA:
            estado = await sesion.scalar(select(EstadoReserva).where(EstadoReserva.codigo == codigo))
            if estado is None:
                estado = EstadoReserva(codigo=codigo, nombre=nombre)
                sesion.add(estado)
                await sesion.flush()
            estados_reserva_cache[codigo] = estado

        estados_pago_cache: dict[str, EstadoPago] = {}
        for codigo, nombre in ESTADOS_PAGO_SEMILLA:
            estado = await sesion.scalar(select(EstadoPago).where(EstadoPago.codigo == codigo))
            if estado is None:
                estado = EstadoPago(codigo=codigo, nombre=nombre)
                sesion.add(estado)
                await sesion.flush()
            estados_pago_cache[codigo] = estado

        metodos_pago_cache: dict[str, MetodoPago] = {}
        for codigo, nombre in METODOS_PAGO_SEMILLA:
            metodo = await sesion.scalar(select(MetodoPago).where(MetodoPago.codigo == codigo))
            if metodo is None:
                metodo = MetodoPago(codigo=codigo, nombre=nombre)
                sesion.add(metodo)
                await sesion.flush()
            metodos_pago_cache[codigo] = metodo

        await _migrar_esquema_legacy(sesion)

        roles_cache: dict[str, Role] = {}
        for rol_nombre in PERMISOS_POR_ROL:
            rol = await sesion.scalar(select(Role).where(Role.nombre == rol_nombre))
            if rol is None:
                rol = Role(nombre=rol_nombre)
                sesion.add(rol)
                await sesion.flush()
            roles_cache[rol_nombre] = rol

        permisos_cache: dict[str, Permiso] = {}
        for permisos in PERMISOS_POR_ROL.values():
            for permiso_nombre in permisos:
                permiso = await sesion.scalar(select(Permiso).where(Permiso.nombre == permiso_nombre))
                if permiso is None:
                    permiso = Permiso(nombre=permiso_nombre)
                    sesion.add(permiso)
                    await sesion.flush()
                permisos_cache[permiso_nombre] = permiso

        for rol_nombre, permisos in PERMISOS_POR_ROL.items():
            rol = roles_cache[rol_nombre]
            for permiso_nombre in permisos:
                permiso = permisos_cache[permiso_nombre]
                await sesion.execute(
                    text(
                        f"{clausula} INTO rol_permisos (rol_id, permiso_id) VALUES (:rol_id, :permiso_id)"
                    ),
                    {"rol_id": rol.id, "permiso_id": permiso.id},
                )

        admin_role = roles_cache.get("administrador")
        if admin_role is not None:
            admin_email = configuracion.admin_email.lower()
            admin_user = await sesion.scalar(select(User).where(User.correo == admin_email))
            if admin_user is None:
                sesion.add(
                    User(
                        nombre="Administrador",
                        apellido="Aurora",
                        tipo_documento_id=tipos_documento_cache["CC"].id,
                        numero_documento="1000000000",
                        direccion="Oficina principal Aurora Viajes",
                        telefono="3000000000",
                        correo=configuracion.admin_email.lower(),
                        contrasena_hash=hashear_contrasena(configuracion.admin_password),
                        rol_id=admin_role.id,
                        activo=True,
                    )
                )
            else:
                admin_user.nombre = admin_user.nombre or "Administrador"
                admin_user.apellido = admin_user.apellido or "Aurora"
                admin_user.tipo_documento_id = tipos_documento_cache["CC"].id
                admin_user.rol_id = admin_role.id
                admin_user.activo = True
                try:
                    if not verificar_contrasena(configuracion.admin_password, admin_user.contrasena_hash):
                        admin_user.contrasena_hash = hashear_contrasena(configuracion.admin_password)
                except Exception:
                    admin_user.contrasena_hash = hashear_contrasena(configuracion.admin_password)

        await sesion.commit()


async def _columna_existe(sesion: AsyncSession, tabla: str, columna: str) -> bool:
    if sesion.bind and sesion.bind.dialect.name == "mysql":
        consulta = text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :tabla AND column_name = :columna"
        )
        cantidad = await sesion.scalar(consulta, {"tabla": tabla, "columna": columna})
        return bool(cantidad)
    return False


async def _restriccion_existe(sesion: AsyncSession, tabla: str, restriccion: str) -> bool:
    if sesion.bind and sesion.bind.dialect.name == "mysql":
        cantidad = await sesion.scalar(
            text(
                "SELECT COUNT(*) FROM information_schema.table_constraints "
                "WHERE table_schema = DATABASE() AND table_name = :tabla "
                "AND constraint_name = :restriccion"
            ),
            {"tabla": tabla, "restriccion": restriccion},
        )
        return bool(cantidad)
    return False


async def _migrar_esquema_legacy(sesion: AsyncSession) -> None:
    if not sesion.bind or sesion.bind.dialect.name != "mysql":
        return

    # Columnas de hotel y desglose: create_all no altera tablas existentes.
    if not await _columna_existe(sesion, "reservas", "hotel_id"):
        await sesion.execute(text("ALTER TABLE reservas ADD COLUMN hotel_id INT NULL AFTER paquete_id"))
        await sesion.execute(
            text(
                "ALTER TABLE reservas ADD CONSTRAINT fk_reserva_hotel "
                "FOREIGN KEY (hotel_id) REFERENCES hoteles(id) ON DELETE RESTRICT"
            )
        )
    for columna in ("monto_vuelo", "monto_hotel", "monto_excursiones"):
        if not await _columna_existe(sesion, "reservas", columna):
            await sesion.execute(
                text(f"ALTER TABLE reservas ADD COLUMN {columna} DECIMAL(12,2) NOT NULL DEFAULT 0 AFTER monto_total")
            )

    if not await _columna_existe(sesion, "reservas", "paquete_id"):
        await sesion.execute(text("ALTER TABLE reservas ADD COLUMN paquete_id INT NULL AFTER vuelo_id"))
        await sesion.execute(
            text(
                "ALTER TABLE reservas ADD CONSTRAINT fk_reserva_paquete "
                "FOREIGN KEY (paquete_id) REFERENCES paquetes(id) ON DELETE RESTRICT"
            )
        )
    else:
        await sesion.execute(text("ALTER TABLE reservas MODIFY COLUMN paquete_id INT NULL"))
        if not await _restriccion_existe(sesion, "reservas", "fk_reserva_paquete"):
            await sesion.execute(
                text(
                    "ALTER TABLE reservas ADD CONSTRAINT fk_reserva_paquete "
                    "FOREIGN KEY (paquete_id) REFERENCES paquetes(id) ON DELETE RESTRICT"
                )
            )

    if await _columna_existe(sesion, "usuarios", "tipo_documento") and not await _columna_existe(sesion, "usuarios", "tipo_documento_id"):
        await sesion.execute(text("ALTER TABLE usuarios ADD COLUMN tipo_documento_id INT UNSIGNED NULL AFTER apellido"))
        tipos_legacy = await sesion.execute(
            text("SELECT DISTINCT tipo_documento FROM usuarios WHERE tipo_documento IS NOT NULL AND tipo_documento <> ''")
        )
        for fila in tipos_legacy:
            codigo = str(fila[0]).strip().upper()
            if codigo:
                await sesion.execute(
                    text("INSERT IGNORE INTO tipos_documento (codigo, nombre) VALUES (:codigo, :nombre)"),
                    {"codigo": codigo, "nombre": codigo},
                )
        await sesion.execute(
            text(
                "UPDATE usuarios u "
                "JOIN tipos_documento td ON td.codigo = u.tipo_documento "
                "SET u.tipo_documento_id = td.id"
            )
        )
        await sesion.execute(
            text(
                "UPDATE usuarios u "
                "JOIN tipos_documento td ON td.codigo = 'CC' "
                "SET u.tipo_documento_id = td.id "
                "WHERE u.tipo_documento_id IS NULL"
            )
        )
        await sesion.execute(text("ALTER TABLE usuarios MODIFY tipo_documento_id INT UNSIGNED NOT NULL"))
        await sesion.execute(text("ALTER TABLE usuarios DROP COLUMN tipo_documento"))

    if await _columna_existe(sesion, "reservas", "destino") and not await _columna_existe(sesion, "reservas", "destino_id"):
        await sesion.execute(text("ALTER TABLE reservas ADD COLUMN destino_id INT UNSIGNED NULL AFTER usuario_id"))
        await sesion.execute(text("ALTER TABLE reservas ADD COLUMN estado_id INT UNSIGNED NULL AFTER notas"))
        await sesion.execute(text("ALTER TABLE reservas ADD COLUMN estado_pago_id INT UNSIGNED NULL AFTER estado_id"))
        await sesion.execute(text("ALTER TABLE reservas ADD COLUMN metodo_pago_id INT UNSIGNED NULL AFTER estado_pago_id"))

        destinos_legacy = await sesion.execute(
            text("SELECT DISTINCT destino FROM reservas WHERE destino IS NOT NULL AND destino <> ''")
        )
        for fila in destinos_legacy:
            destino_nombre = str(fila[0]).strip()
            if not destino_nombre:
                continue
            destino = await sesion.scalar(select(Destino).where(Destino.nombre == destino_nombre))
            if destino is None:
                pais_nombre = destino_nombre.split(",")[-1].strip() if "," in destino_nombre else "Colombia"
                pais = await sesion.scalar(select(Pais).where(Pais.nombre == pais_nombre))
                if pais is None:
                    pais = Pais(nombre=pais_nombre)
                    sesion.add(pais)
                    await sesion.flush()
                destino = Destino(
                    pais_id=pais.id,
                    nombre=destino_nombre,
                    descripcion=destino_nombre,
                    precio_base=Decimal("0"),
                    imagen_slug=None,
                    activo=True,
                )
                sesion.add(destino)
                await sesion.flush()

        for codigo, nombre in ESTADOS_RESERVA_SEMILLA:
            estado = await sesion.scalar(select(EstadoReserva).where(EstadoReserva.codigo == codigo))
            if estado is None:
                estado = EstadoReserva(codigo=codigo, nombre=nombre)
                sesion.add(estado)
                await sesion.flush()
        for codigo, nombre in ESTADOS_PAGO_SEMILLA:
            estado = await sesion.scalar(select(EstadoPago).where(EstadoPago.codigo == codigo))
            if estado is None:
                estado = EstadoPago(codigo=codigo, nombre=nombre)
                sesion.add(estado)
                await sesion.flush()
        for codigo, nombre in METODOS_PAGO_SEMILLA:
            metodo = await sesion.scalar(select(MetodoPago).where(MetodoPago.codigo == codigo))
            if metodo is None:
                metodo = MetodoPago(codigo=codigo, nombre=nombre)
                sesion.add(metodo)
                await sesion.flush()

        await sesion.execute(
            text(
                "UPDATE reservas r "
                "JOIN destinos d ON d.nombre = r.destino "
                "SET r.destino_id = d.id"
            )
        )
        await sesion.execute(
            text(
                "UPDATE reservas r "
                "JOIN estados_reserva er ON er.codigo = r.estado "
                "SET r.estado_id = er.id"
            )
        )
        await sesion.execute(
            text(
                "UPDATE reservas r "
                "JOIN estados_pago ep ON ep.codigo = r.estado_pago "
                "SET r.estado_pago_id = ep.id"
            )
        )
        await sesion.execute(
            text(
                "UPDATE reservas r "
                "LEFT JOIN metodos_pago mp ON mp.codigo = r.metodo_pago "
                "SET r.metodo_pago_id = mp.id"
            )
        )
        await sesion.execute(
            text(
                "UPDATE reservas r "
                "JOIN destinos d ON d.id = r.destino_id "
                "JOIN estados_reserva er ON er.codigo = 'pendiente' "
                "JOIN estados_pago ep ON ep.codigo = 'pendiente' "
                "SET r.destino_id = d.id, r.estado_id = COALESCE(r.estado_id, er.id), r.estado_pago_id = COALESCE(r.estado_pago_id, ep.id) "
                "WHERE r.destino_id IS NULL OR r.estado_id IS NULL OR r.estado_pago_id IS NULL"
            )
        )
        await sesion.execute(text("ALTER TABLE reservas MODIFY destino_id INT UNSIGNED NOT NULL"))
        await sesion.execute(text("ALTER TABLE reservas MODIFY estado_id INT UNSIGNED NOT NULL"))
        await sesion.execute(text("ALTER TABLE reservas MODIFY estado_pago_id INT UNSIGNED NOT NULL"))
        await sesion.execute(text("ALTER TABLE reservas DROP COLUMN destino"))
        await sesion.execute(text("ALTER TABLE reservas DROP COLUMN estado"))
        await sesion.execute(text("ALTER TABLE reservas DROP COLUMN estado_pago"))
        await sesion.execute(text("ALTER TABLE reservas DROP COLUMN metodo_pago"))

    if not await _columna_existe(sesion, "reservas", "vuelo_id"):
        await sesion.execute(text("ALTER TABLE reservas ADD COLUMN vuelo_id INT UNSIGNED NULL AFTER destino_id"))
        await sesion.execute(
            text(
                "ALTER TABLE reservas ADD CONSTRAINT fk_reserva_vuelo "
                "FOREIGN KEY (vuelo_id) REFERENCES vuelos(id) ON DELETE RESTRICT"
            )
        )

    # Enlace venta -> reserva: permite que pagar o cancelar una reserva actualice su venta y su factura.
    if not await _columna_existe(sesion, "ventas", "reserva_id"):
        tipo_id = await sesion.scalar(
            text(
                "SELECT COLUMN_TYPE FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'reservas' AND column_name = 'id'"
            )
        )
        # La columna debe tener exactamente el tipo del id al que apunta (con o sin signo).
        if not tipo_id or not re.fullmatch(r"[a-z]+(\(\d+\))?( unsigned)?", str(tipo_id).lower()):
            raise RuntimeError(f"Tipo inesperado para reservas.id: {tipo_id!r}")
        await sesion.execute(text(f"ALTER TABLE ventas ADD COLUMN reserva_id {tipo_id} NULL"))
        await sesion.execute(text("ALTER TABLE ventas ADD CONSTRAINT uq_venta_reserva UNIQUE (reserva_id)"))
        await sesion.execute(
            text(
                "ALTER TABLE ventas ADD CONSTRAINT fk_venta_reserva "
                "FOREIGN KEY (reserva_id) REFERENCES reservas(id) ON DELETE SET NULL"
            )
        )
        await _enlazar_ventas_antiguas(sesion)

    await sesion.commit()



async def _enlazar_ventas_antiguas(sesion: AsyncSession) -> None:
    """Empareja las ventas anteriores a la columna con su reserva y pone al día sus estados.

    Una venta y su reserva se crean en la misma petición, así que coinciden en
    cliente, total y hora (con unos segundos de margen). Si el emparejamiento es
    ambiguo se omite: es preferible una venta sin enlace a una enlazada mal.
    """
    try:
        async with sesion.begin_nested():
            await sesion.execute(
                text(
                    "UPDATE ventas v JOIN reservas r ON r.usuario_id = v.cliente_id AND r.monto_total = v.total "
                    "AND ABS(TIMESTAMPDIFF(SECOND, r.creado_en, v.creado_en)) <= 5 "
                    "SET v.reserva_id = r.id WHERE v.reserva_id IS NULL"
                )
            )
    except Exception:  # noqa: BLE001 - el enlace de ventas antiguas es un extra, no debe impedir el arranque
        logger.warning("No se pudieron enlazar las ventas antiguas con sus reservas.", exc_info=True)
        return
    await sesion.execute(
        text(
            "UPDATE ventas v JOIN reservas r ON r.id = v.reserva_id "
            "JOIN estados_reserva er ON er.id = r.estado_id JOIN estados_pago ep ON ep.id = r.estado_pago_id "
            "SET v.estado = CASE WHEN er.codigo = 'cancelada' THEN 'cancelada' "
            "WHEN ep.codigo = 'pagado' THEN 'completada' ELSE 'pendiente' END"
        )
    )
    await sesion.execute(
        text(
            "UPDATE facturas f JOIN ventas v ON v.id = f.venta_id "
            "SET f.estado = CASE WHEN v.estado = 'cancelada' THEN 'anulada' ELSE 'emitida' END "
            "WHERE v.reserva_id IS NOT NULL"
        )
    )
