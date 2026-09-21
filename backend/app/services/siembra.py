"""Arranque de la base: crea el esquema, migra bases antiguas y siembra el catálogo de ejemplo.

Todo es idempotente y **no pisa lo que el administrador haya cambiado**: cada dato de ejemplo se
crea solo si falta. Antes cada arranque volvía a poner el precio, la descripción y el estado
«activo» de los destinos, deshaciendo las ediciones.
"""
import logging
from datetime import datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_datos import Base, FabricaDeSesiones, motor
from app.core.configuracion import configuracion
from app.core.politica_contrasena import CONTRASENAS_COMUNES
from app.core.seguridad import hashear_contrasena, verificar_contrasena
from app.models.dominio import (
    Aerolinea, Ciudad, Destino, EstadoPago, EstadoReserva, Excursion, Hotel, MetodoPago, ModeloAvion, Pais, Paquete,
    Permiso, Role, TipoDocumento, User, Vuelo,
)
from app.services.catalogos import ahora, normalizar_texto
from app.services.migraciones import migrar_esquema


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

ESTADOS_RESERVA_SEMILLA = [("pendiente", "Pendiente"), ("confirmada", "Confirmada"), ("cancelada", "Cancelada")]
ESTADOS_PAGO_SEMILLA = [("pendiente", "Pendiente"), ("pagado", "Pagado"), ("fallido", "Fallido")]
METODOS_PAGO_SEMILLA = [
    ("stripe", "Stripe"),
    ("transferencia", "Transferencia"),
    ("efectivo", "Efectivo"),
    ("tarjeta", "Tarjeta (datáfono)"),
]

AEROLINEAS_SEMILLA = [
    ("AUR", "Aurora Airlines"),
    ("AV", "Avianca"),
    ("LA", "LATAM"),
    ("CM", "Copa Airlines"),
    ("IB", "Iberia"),
]

# La capacidad física es de cada modelo; el vuelo vende como máximo esas plazas.
MODELOS_AVION_SEMILLA = [
    ("Airbus A320", 180),
    ("Airbus A330", 300),
    ("Boeing 737", 189),
    ("Boeing 787", 330),
    ("Embraer E195", 132),
]

# Ciudades desde las que se puede salir. Cartagena también es destino: es la misma ciudad.
ORIGENES_SEMILLA = [
    ("Colombia", "Bogotá"), ("Colombia", "Medellín"), ("Colombia", "Cali"), ("Colombia", "Barranquilla"),
    ("Colombia", "Cartagena"), ("Perú", "Lima"), ("España", "Madrid"),
]
ORIGEN_PRINCIPAL = ("Colombia", "Bogotá")

DESTINOS_SEMILLA = [
    {
        "pais": "Francia", "ciudad": "París", "slug": "paris", "precio": Decimal("6900000"), "vuelo": "AUR301",
        "descripcion": "Recorre el Sena al atardecer y descubre por qué la Ciudad Luz sigue inspirando a viajeros de todo el mundo.",
        "hoteles": [("Hotel Lumière Aurora", 5, 480000), ("Hôtel Petit Rivoli", 3, 220000)],
        "excursiones": [("Crucero nocturno por el Sena", 3, 180000), ("Ruta de arte en Montmartre", 4, 145000), ("Versalles y sus jardines", 6, 220000)],
    },
    {
        "pais": "Japón", "ciudad": "Kioto", "slug": "kioto", "precio": Decimal("8400000"), "vuelo": "AUR302",
        "descripcion": "Templos centenarios, jardines de piedra y la calma de los bosques de bambú te esperan en el antiguo Japón.",
        "hoteles": [("Ryokan Sakura Aurora", 4, 390000), ("Kyoto Garden Inn", 3, 210000)],
        "excursiones": [("Ceremonia del té tradicional", 3, 165000), ("Bosque de bambú de Arashiyama", 5, 210000), ("Nara y sus templos", 8, 260000)],
    },
    {
        "pais": "Indonesia", "ciudad": "Bali", "slug": "bali", "precio": Decimal("7600000"), "vuelo": "AUR303",
        "descripcion": "Playas volcánicas, arrozales en terraza y una cultura espiritual que transforma cada visita en un ritual.",
        "hoteles": [("Ubud Rice Terrace Resort", 5, 310000), ("Seminyak Beach Bungalows", 3, 160000)],
        "excursiones": [("Amanecer en el monte Batur", 7, 240000), ("Templos y arrozales de Ubud", 6, 190000), ("Snorkel en Nusa Penida", 8, 280000)],
    },
    {
        "pais": "Colombia", "ciudad": "Cartagena", "slug": "cartagena", "precio": Decimal("1200000"), "vuelo": "AUR304",
        "descripcion": "Murallas coloniales, calles de colores y el Caribe a un paso: la joya histórica de Colombia.",
        "hoteles": [("Casa del Mar Boutique", 4, 280000), ("Hostal Getsemaní Colonial", 3, 150000)],
        "excursiones": [("Recorrido por la ciudad amurallada", 3, 85000), ("Atardecer en la bahía", 2, 110000), ("Islas del Rosario", 8, 230000)],
    },
    {
        "pais": "Grecia", "ciudad": "Santorini", "slug": "santorini", "precio": Decimal("9800000"), "vuelo": "AUR305",
        "descripcion": "Casas blancas suspendidas sobre el mar Egeo y atardeceres que se han vuelto leyenda.",
        "hoteles": [("Aegean White Suites", 5, 520000), ("Oia Cave Rooms", 3, 260000)],
        "excursiones": [("Caldera y pueblos blancos", 5, 220000), ("Cata de vinos volcánicos", 4, 195000), ("Paseo en catamarán", 7, 290000)],
    },
    {
        "pais": "Perú", "ciudad": "Cusco", "slug": "cusco", "precio": Decimal("2500000"), "vuelo": "AUR306",
        "descripcion": "Puerta de entrada a Machu Picchu y corazón del imperio inca, entre montañas y terrazas ancestrales.",
        "hoteles": [("Andenes del Sol Hotel", 4, 250000), ("Plaza de Armas Hostal", 3, 120000)],
        "excursiones": [("Machu Picchu en tren", 10, 420000), ("Valle Sagrado de los Incas", 8, 260000), ("Montaña de siete colores", 12, 230000)],
    },
    {
        "pais": "Marruecos", "ciudad": "Marrakech", "slug": "marrakech", "precio": Decimal("8900000"), "vuelo": "AUR307",
        "descripcion": "Zocos bulliciosos, palacios ocultos y el aroma a especias en cada esquina de la medina.",
        "hoteles": [("Riad Medina Aurora", 4, 300000), ("Riad Jardin Secret", 3, 140000)],
        "excursiones": [("Sabores de la medina", 4, 150000), ("Palacio de la Bahía y zocos", 5, 130000), ("Desierto de Agafay", 8, 250000)],
    },
    {
        "pais": "Islandia", "ciudad": "Reikiavik", "slug": "reikiavik", "precio": Decimal("10800000"), "vuelo": "AUR308",
        "descripcion": "Auroras boreales, fuentes termales y paisajes volcánicos al borde del Atlántico Norte.",
        "hoteles": [("Northern Lights Lodge", 4, 430000), ("Reykjavik Harbor Guesthouse", 3, 230000)],
        "excursiones": [("Cacería de auroras boreales", 5, 260000), ("Círculo dorado", 8, 290000), ("Laguna Azul y costa volcánica", 7, 310000)],
    },
    {
        "pais": "Estados Unidos", "ciudad": "Nueva York", "slug": "nueva-york", "precio": Decimal("7200000"), "vuelo": "AUR309",
        "descripcion": "Rascacielos icónicos, parques urbanos y una energía que nunca duerme.",
        "hoteles": [("Manhattan Skyline Hotel", 4, 560000), ("Brooklyn Bridge Inn", 3, 300000)],
        "excursiones": [("Manhattan y Central Park", 6, 210000), ("Luces de Broadway", 4, 280000), ("Estatua de la Libertad", 5, 190000)],
    },
    {
        "pais": "Egipto", "ciudad": "El Cairo", "slug": "cairo", "precio": Decimal("9300000"), "vuelo": "AUR310",
        "descripcion": "Las pirámides de Giza y el Nilo milenario te acercan a una de las civilizaciones más fascinantes de la historia.",
        "hoteles": [("Nile View Palace", 5, 270000), ("Giza Pyramids View Inn", 3, 130000)],
        "excursiones": [("Pirámides de Giza y esfinge", 6, 230000), ("Museo Egipcio y bazar Khan el Khalili", 5, 170000), ("Crucero al atardecer por el Nilo", 3, 155000)],
    },
]

# La programación se renueva sola: el catálogo de ejemplo llevaba fechas fijas que acababan en el pasado
# y, pasadas esas fechas, no quedaba ningún vuelo que reservar.
DIAS_ENTRE_SALIDAS = 7
DIAS_DE_ANTELACION = 10
HORIZONTE_DE_VENTA_DIAS = 70

CLAVE_DE_EJEMPLO = "Admin123!"


def _es_clave_conocida(clave: str) -> bool:
    return clave == CLAVE_DE_EJEMPLO or clave.lower() in CONTRASENAS_COMUNES


def _clausula_no_duplicados(sesion: AsyncSession) -> str:
    return "INSERT IGNORE" if sesion.bind and sesion.bind.dialect.name == "mysql" else "INSERT OR IGNORE"


async def _rechazar_sqlite_antigua(conexion) -> None:
    """Una SQLite de desarrollo creada con una versión anterior no se migra: se avisa cómo recrearla."""
    columnas = await conexion.execute(text("PRAGMA table_info(hoteles)"))
    nombres = {fila[1] for fila in columnas.fetchall()}
    if "ciudad" in nombres and "ciudad_id" not in nombres:
        raise RuntimeError(
            "La base SQLite local es de una versión anterior. Bórrala (por defecto ./aurora_viajes.db) "
            "y arranca de nuevo: se creará con el esquema actual y sus datos de ejemplo."
        )


async def asegurar_base_inicial() -> None:
    async with motor.begin() as conexion:
        if conexion.dialect.name == "sqlite":
            await _rechazar_sqlite_antigua(conexion)
        await conexion.run_sync(Base.metadata.create_all)
    async with FabricaDeSesiones() as sesion:
        await _sembrar_catalogos_base(sesion)
        await migrar_esquema(sesion)  # solo MySQL; necesita que los catálogos anteriores ya existan
        await _sembrar_destinos_y_alojamientos(sesion)
        await _asegurar_programacion_de_vuelos(sesion)
        await _asegurar_paquetes(sesion)
        await _asegurar_roles_y_permisos(sesion)
        await _asegurar_administrador(sesion)
        await sesion.commit()


# --------------------------------------------------------------------------------------
# Catálogos pequeños
# --------------------------------------------------------------------------------------


async def _sembrar_catalogos_base(sesion: AsyncSession) -> None:
    """Tablas de referencia que la migración y el resto del arranque necesitan."""
    for modelo, filas in ((TipoDocumento, TIPOS_DOCUMENTO_SEMILLA), (EstadoReserva, ESTADOS_RESERVA_SEMILLA),
                          (EstadoPago, ESTADOS_PAGO_SEMILLA), (MetodoPago, METODOS_PAGO_SEMILLA)):
        for codigo, nombre in filas:
            if await sesion.scalar(select(modelo.id).where(modelo.codigo == codigo)) is None:
                sesion.add(modelo(codigo=codigo, nombre=nombre))
    for codigo, nombre in AEROLINEAS_SEMILLA:
        if await sesion.scalar(select(Aerolinea.id).where(Aerolinea.nombre == nombre)) is None:
            sesion.add(Aerolinea(codigo=codigo, nombre=nombre))
    for nombre, capacidad in MODELOS_AVION_SEMILLA:
        if await sesion.scalar(select(ModeloAvion.id).where(ModeloAvion.nombre == nombre)) is None:
            sesion.add(ModeloAvion(nombre=nombre, capacidad=capacidad))
    await sesion.commit()


async def _pais(sesion: AsyncSession, nombre: str) -> Pais:
    pais = await sesion.scalar(select(Pais).where(Pais.nombre == nombre))
    if pais is None:
        pais = Pais(nombre=nombre)
        sesion.add(pais)
        await sesion.flush()
    return pais


async def _ciudad(sesion: AsyncSession, pais: str, nombre: str) -> Ciudad:
    """La ciudad de ese país; se busca sin distinguir tildes por si una migración la creó con otra grafía."""
    pais_fila = await _pais(sesion, pais)
    ciudades = (await sesion.scalars(select(Ciudad).where(Ciudad.pais_id == pais_fila.id))).unique().all()
    for ciudad in ciudades:
        if normalizar_texto(ciudad.nombre) == normalizar_texto(nombre):
            return ciudad
    ciudad = Ciudad(pais_id=pais_fila.id, nombre=nombre)
    sesion.add(ciudad)
    await sesion.flush()
    return ciudad


# --------------------------------------------------------------------------------------
# Destinos, hoteles y excursiones de ejemplo
# --------------------------------------------------------------------------------------


async def _sembrar_destinos_y_alojamientos(sesion: AsyncSession) -> None:
    for pais, ciudad in ORIGENES_SEMILLA:
        await _ciudad(sesion, pais, ciudad)

    for datos in DESTINOS_SEMILLA:
        ciudad = await _ciudad(sesion, datos["pais"], datos["ciudad"])
        if await sesion.scalar(select(Destino.id).where(Destino.ciudad_id == ciudad.id)) is None:
            sesion.add(Destino(
                ciudad_id=ciudad.id, descripcion=datos["descripcion"], precio_base=datos["precio"],
                imagen_slug=datos["slug"], activo=True,
            ))
        for nombre, estrellas, precio_noche in datos["hoteles"]:
            if await sesion.scalar(select(Hotel.id).where(Hotel.ciudad_id == ciudad.id, Hotel.nombre == nombre)) is None:
                sesion.add(Hotel(
                    nombre=nombre, ciudad_id=ciudad.id, estrellas=estrellas, precio_noche=precio_noche, activo=True,
                    descripcion=f"Alojamiento seleccionado en {datos['ciudad']}, con desayuno, recepción 24 horas y ubicación estratégica para recorrer el destino.",
                ))
        for nombre, duracion, precio in datos["excursiones"]:
            if await sesion.scalar(select(Excursion.id).where(Excursion.ciudad_id == ciudad.id, Excursion.nombre == nombre)) is None:
                sesion.add(Excursion(
                    nombre=nombre, ciudad_id=ciudad.id, duracion_horas=duracion, precio=precio, activo=True,
                    descripcion=f"Experiencia guiada para conocer {datos['ciudad']} con acompañamiento local y tiempo para fotografías.",
                ))
        await sesion.flush()


# --------------------------------------------------------------------------------------
# Programación de vuelos
# --------------------------------------------------------------------------------------


def _numero_de_regreso(numero_ida: str) -> str:
    return numero_ida.replace("AUR3", "AUR4", 1)


async def _asegurar_programacion_de_vuelos(sesion: AsyncSession) -> None:
    """Mantiene, para cada destino de ejemplo, salidas semanales de ida y su vuelo de regreso.

    Solo añade fechas a continuación de la última que ya exista para esa ruta, así que no
    resucita vuelos que un administrador haya borrado o desactivado.
    """
    hoy = ahora().date()
    aerolinea = await sesion.scalar(select(Aerolinea).where(Aerolinea.nombre == "Aurora Airlines"))
    modelos = {m.nombre: m for m in (await sesion.scalars(select(ModeloAvion))).all()}
    origen = await _ciudad(sesion, *ORIGEN_PRINCIPAL)

    for indice, datos in enumerate(DESTINOS_SEMILLA):
        ciudad = await _ciudad(sesion, datos["pais"], datos["ciudad"])
        numero_ida, numero_regreso = datos["vuelo"], _numero_de_regreso(datos["vuelo"])
        noches = 6 + indice % 3
        modelo = modelos["Airbus A320" if indice % 2 == 0 else "Boeing 787"]
        capacidad = 180 if indice % 2 == 0 else 260
        duracion = timedelta(hours=9 + indice % 4, minutes=45)
        puerta, terminal = f"{chr(65 + indice % 4)}{10 + indice:02d}", str(1 + indice % 3)

        salidas = [
            momento.date() for momento in (await sesion.scalars(
                select(Vuelo.fecha_salida).where(Vuelo.numero_vuelo == numero_ida, Vuelo.origen_id == origen.id, Vuelo.destino_id == ciudad.id)
            )).all()
        ]
        fechas = set(salidas)
        siguiente = max(max(salidas) + timedelta(days=DIAS_ENTRE_SALIDAS) if salidas else hoy, hoy + timedelta(days=DIAS_DE_ANTELACION))
        while siguiente <= hoy + timedelta(days=HORIZONTE_DE_VENTA_DIAS):
            salida = datetime.combine(siguiente, time(7 + indice % 5, 30))
            sesion.add(Vuelo(
                numero_vuelo=numero_ida, aerolinea_id=aerolinea.id, modelo_avion_id=modelo.id, origen_id=origen.id,
                destino_id=ciudad.id, fecha_salida=salida, fecha_llegada=salida + duracion, capacidad_maxima=capacidad,
                puerta=puerta, terminal=terminal, estado="programado", activo=True,
            ))
            fechas.add(siguiente)
            siguiente += timedelta(days=DIAS_ENTRE_SALIDAS)

        # Cada salida futura tiene su vuelo de regreso `noches` días después.
        for fecha in sorted(f for f in fechas if f > hoy):
            regreso = datetime.combine(fecha + timedelta(days=noches), time(11 + indice % 4, 0))
            existe = await sesion.scalar(select(Vuelo.id).where(Vuelo.numero_vuelo == numero_regreso, Vuelo.fecha_salida == regreso))
            if existe is None:
                sesion.add(Vuelo(
                    numero_vuelo=numero_regreso, aerolinea_id=aerolinea.id, modelo_avion_id=modelo.id, origen_id=ciudad.id,
                    destino_id=origen.id, fecha_salida=regreso, fecha_llegada=regreso + duracion, capacidad_maxima=capacidad,
                    puerta=puerta, terminal=terminal, estado="programado", activo=True,
                ))
        await sesion.flush()


async def _asegurar_paquetes(sesion: AsyncSession) -> None:
    """Un paquete de ejemplo por destino, siempre apuntando a la próxima salida disponible."""
    momento = ahora()
    origen = await _ciudad(sesion, *ORIGEN_PRINCIPAL)
    for indice, datos in enumerate(DESTINOS_SEMILLA):
        ciudad = await _ciudad(sesion, datos["pais"], datos["ciudad"])
        destino = await sesion.scalar(select(Destino).where(Destino.ciudad_id == ciudad.id))
        nombre = f"Aurora {datos['ciudad']}: experiencia completa"
        noches = 6 + indice % 3
        paquete = await sesion.scalar(select(Paquete).where(Paquete.nombre == nombre))

        # Próxima salida futura de esta ruta con su vuelo de regreso.
        ida = await sesion.scalar(
            select(Vuelo)
            .where(Vuelo.numero_vuelo == datos["vuelo"], Vuelo.origen_id == origen.id, Vuelo.destino_id == ciudad.id,
                   Vuelo.activo.is_(True), Vuelo.estado == "programado", Vuelo.fecha_salida > momento + timedelta(days=3))
            .order_by(Vuelo.fecha_salida.asc())
            .limit(1)
        )
        if ida is None:
            continue
        regreso = await sesion.scalar(
            select(Vuelo).where(
                Vuelo.numero_vuelo == _numero_de_regreso(datos["vuelo"]),
                Vuelo.fecha_salida >= datetime.combine(ida.fecha_salida.date() + timedelta(days=noches), time.min),
                Vuelo.fecha_salida < datetime.combine(ida.fecha_salida.date() + timedelta(days=noches + 1), time.min),
            )
        )

        if paquete is None:
            hotel = await sesion.scalar(select(Hotel).where(Hotel.ciudad_id == ciudad.id, Hotel.nombre == datos["hoteles"][0][0]))
            excursiones = [
                await sesion.scalar(select(Excursion).where(Excursion.ciudad_id == ciudad.id, Excursion.nombre == excursion[0]))
                for excursion in datos["excursiones"]
            ]
            sesion.add(Paquete(
                nombre=nombre, destino_id=destino.id, vuelo_id=ida.id, vuelo_regreso_id=regreso.id if regreso else None,
                hotel_id=hotel.id, noches=noches,
                precio_base=(Decimal(str(destino.precio_base)) * Decimal("1.12")).quantize(Decimal("0.01")),
                activo=True, excursiones=[e for e in excursiones if e is not None],
            ))
        elif paquete.activo and (paquete.vuelo_rel.fecha_salida <= momento or paquete.vuelo_rel.estado != "programado"):
            # Su salida ya pasó: el paquete pasa a la siguiente. Las reservas ya hechas guardan sus propios vuelos.
            paquete.vuelo_id = ida.id
            paquete.vuelo_regreso_id = regreso.id if regreso else None
        elif paquete.activo and paquete.vuelo_regreso_id is None and regreso is not None and paquete.vuelo_id == ida.id:
            paquete.vuelo_regreso_id = regreso.id  # completa los paquetes anteriores al vuelo de regreso
        await sesion.flush()


# --------------------------------------------------------------------------------------
# Roles y administrador
# --------------------------------------------------------------------------------------


async def _asegurar_roles_y_permisos(sesion: AsyncSession) -> None:
    clausula = _clausula_no_duplicados(sesion)
    roles: dict[str, Role] = {}
    for nombre in PERMISOS_POR_ROL:
        rol = await sesion.scalar(select(Role).where(Role.nombre == nombre))
        if rol is None:
            rol = Role(nombre=nombre)
            sesion.add(rol)
            await sesion.flush()
        roles[nombre] = rol
    permisos: dict[str, Permiso] = {}
    for lista in PERMISOS_POR_ROL.values():
        for nombre in lista:
            permiso = await sesion.scalar(select(Permiso).where(Permiso.nombre == nombre))
            if permiso is None:
                permiso = Permiso(nombre=nombre)
                sesion.add(permiso)
                await sesion.flush()
            permisos[nombre] = permiso
    for rol_nombre, lista in PERMISOS_POR_ROL.items():
        for permiso_nombre in lista:
            await sesion.execute(
                text(f"{clausula} INTO rol_permisos (rol_id, permiso_id) VALUES (:rol_id, :permiso_id)"),
                {"rol_id": roles[rol_nombre].id, "permiso_id": permisos[permiso_nombre].id},
            )


async def _asegurar_administrador(sesion: AsyncSession) -> None:
    """Crea el administrador inicial y vigila que no siga con una clave conocida.

    La clave de `ADMIN_PASSWORD` solo se aplica al crear la cuenta (o si se pide restablecerla con
    `ADMIN_RESTABLECER_CONTRASENA=true`). Antes se reaplicaba en cada arranque: cambiar la contraseña
    desde la app no servía de nada tras el siguiente despliegue. Y si la clave es la de ejemplo, la
    cuenta queda obligada a cambiarla en su primer acceso.
    """
    rol = await sesion.scalar(select(Role).where(Role.nombre == "administrador"))
    tipo = await sesion.scalar(select(TipoDocumento).where(TipoDocumento.codigo == "CC"))
    correo = configuracion.admin_email.lower()
    admin = await sesion.scalar(select(User).where(User.correo == correo))
    clave_conocida = _es_clave_conocida(configuracion.admin_password)

    if admin is None:
        sesion.add(User(
            nombre="Administrador", apellido="Aurora", tipo_documento_id=tipo.id, numero_documento="1000000000",
            direccion="Oficina principal Aurora Viajes", telefono="3000000000", correo=correo,
            contrasena_hash=hashear_contrasena(configuracion.admin_password), rol_id=rol.id, activo=True,
            debe_cambiar_contrasena=clave_conocida,
        ))
        if clave_conocida:
            logger.warning("El administrador se creó con una clave de ejemplo: deberá cambiarla al entrar. Define ADMIN_PASSWORD.")
        return

    admin.rol_id = rol.id
    admin.activo = True
    if configuracion.admin_restablecer_contrasena:
        admin.contrasena_hash = hashear_contrasena(configuracion.admin_password)
        admin.sesion_version += 1
        admin.debe_cambiar_contrasena = clave_conocida
        logger.warning("La contraseña del administrador se restableció desde ADMIN_PASSWORD.")
    elif not admin.debe_cambiar_contrasena:
        try:
            es_conocida = verificar_contrasena(CLAVE_DE_EJEMPLO, admin.contrasena_hash)
        except Exception:  # noqa: BLE001 - un hash ilegible no debe impedir el arranque
            es_conocida = False
        if es_conocida:
            admin.debe_cambiar_contrasena = True
            logger.warning("El administrador sigue con la clave de ejemplo: se le obligará a cambiarla en su próximo acceso.")

