"""Arranque de la base: crea el esquema, migra bases antiguas y siembra el catálogo de ejemplo.

Todo es idempotente y **no pisa lo que el administrador haya cambiado**: cada dato de ejemplo se
crea solo si falta. Antes cada arranque volvía a poner el precio, la descripción y el estado
«activo» de los destinos, deshaciendo las ediciones.
"""
import logging
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_datos import Base, FabricaDeSesiones, motor
from app.core.configuracion import configuracion
from app.core.politica_contrasena import CONTRASENAS_COMUNES
from app.core.seguridad import hashear_contrasena, verificar_contrasena
from app.models.dominio import (
    Aerolinea, Ciudad, Destino, EstadoPago, EstadoReserva, Excursion, Hotel, MetodoPago, ModeloAvion, Pais, Paquete,
    Permiso, Role, TipoDocumento, User, Vuelo, rol_permisos,
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


async def _crear_tablas_si_faltan() -> None:
    """`create_all` pregunta por cada tabla si existe (decenas de consultas); con una sola se ve si falta alguna."""
    async with motor.begin() as conexion:
        if conexion.dialect.name == "sqlite":
            await _rechazar_sqlite_antigua(conexion)
        existentes = await conexion.run_sync(lambda c: set(inspect(c).get_table_names()))
        if not set(Base.metadata.tables) <= existentes:
            await conexion.run_sync(Base.metadata.create_all)


async def asegurar_base_inicial() -> None:
    """Deja la base lista: esquema, migración de bases antiguas y datos de ejemplo.

    Cada reinicio repite esto, y con una base remota cada consulta cuesta una ida y vuelta por la red (decenas de
    milisegundos): por eso los catálogos se leen enteros de una vez y se comparan en memoria, en lugar de preguntar
    por cada hotel, vuelo o permiso. Un arranque sin cambios hace una treintena de consultas.
    """
    await _crear_tablas_si_faltan()
    async with FabricaDeSesiones() as sesion:
        await _sembrar_catalogos_base(sesion)
        await migrar_esquema(sesion)  # solo MySQL; necesita que los catálogos anteriores ya existan
        lugares = await _Lugares.cargar(sesion)
        catalogo = await _sembrar_destinos_y_alojamientos(sesion, lugares)
        vuelos = await _asegurar_programacion_de_vuelos(sesion, lugares)
        await _asegurar_paquetes(sesion, lugares, catalogo, vuelos)
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
        existentes = set((await sesion.scalars(select(modelo.codigo))).all())
        for codigo, nombre in filas:
            if codigo not in existentes:
                sesion.add(modelo(codigo=codigo, nombre=nombre))
    aerolineas = set((await sesion.scalars(select(Aerolinea.nombre))).all())
    for codigo, nombre in AEROLINEAS_SEMILLA:
        if nombre not in aerolineas:
            sesion.add(Aerolinea(codigo=codigo, nombre=nombre))
    modelos = set((await sesion.scalars(select(ModeloAvion.nombre))).all())
    for nombre, capacidad in MODELOS_AVION_SEMILLA:
        if nombre not in modelos:
            sesion.add(ModeloAvion(nombre=nombre, capacidad=capacidad))
    await sesion.commit()


class _Lugares:
    """Países y ciudades en memoria: se leen una vez y se crean los que falten."""

    def __init__(self, paises: dict[str, Pais], ciudades: dict[int, list[Ciudad]]):
        self.paises = paises
        self.ciudades = ciudades

    @classmethod
    async def cargar(cls, sesion: AsyncSession) -> "_Lugares":
        paises = {pais.nombre: pais for pais in (await sesion.scalars(select(Pais))).unique().all()}
        ciudades: dict[int, list[Ciudad]] = defaultdict(list)
        for ciudad in (await sesion.scalars(select(Ciudad))).unique().all():
            ciudades[ciudad.pais_id].append(ciudad)
        return cls(paises, ciudades)

    async def ciudad(self, sesion: AsyncSession, pais: str, nombre: str) -> Ciudad:
        """La ciudad de ese país; se busca sin distinguir tildes por si una migración la creó con otra grafía."""
        fila_pais = self.paises.get(pais)
        if fila_pais is None:
            fila_pais = Pais(nombre=pais)
            sesion.add(fila_pais)
            await sesion.flush()
            self.paises[pais] = fila_pais
        buscada = normalizar_texto(nombre)
        for ciudad in self.ciudades[fila_pais.id]:
            if normalizar_texto(ciudad.nombre) == buscada:
                return ciudad
        ciudad = Ciudad(pais_id=fila_pais.id, nombre=nombre)
        sesion.add(ciudad)
        await sesion.flush()
        self.ciudades[fila_pais.id].append(ciudad)
        return ciudad


# --------------------------------------------------------------------------------------
# Destinos, hoteles y excursiones de ejemplo
# --------------------------------------------------------------------------------------


class _Catalogo:
    """Destinos, hoteles y excursiones ya guardados, para comprobar en memoria lo que falta."""

    def __init__(self, destinos: dict[int, Destino], hoteles: dict[tuple[int, str], Hotel], excursiones: dict[tuple[int, str], Excursion]):
        self.destinos = destinos
        self.hoteles = hoteles
        self.excursiones = excursiones


async def _sembrar_destinos_y_alojamientos(sesion: AsyncSession, lugares: _Lugares) -> _Catalogo:
    for pais, ciudad in ORIGENES_SEMILLA:
        await lugares.ciudad(sesion, pais, ciudad)

    catalogo = _Catalogo(
        destinos={d.ciudad_id: d for d in (await sesion.scalars(select(Destino))).unique().all()},
        hoteles={(h.ciudad_id, h.nombre): h for h in (await sesion.scalars(select(Hotel))).unique().all()},
        excursiones={(e.ciudad_id, e.nombre): e for e in (await sesion.scalars(select(Excursion))).unique().all()},
    )
    for datos in DESTINOS_SEMILLA:
        ciudad = await lugares.ciudad(sesion, datos["pais"], datos["ciudad"])
        if ciudad.id not in catalogo.destinos:
            catalogo.destinos[ciudad.id] = Destino(
                ciudad_id=ciudad.id, descripcion=datos["descripcion"], precio_base=datos["precio"],
                imagen_slug=datos["slug"], activo=True,
            )
            sesion.add(catalogo.destinos[ciudad.id])
        for nombre, estrellas, precio_noche in datos["hoteles"]:
            if (ciudad.id, nombre) not in catalogo.hoteles:
                catalogo.hoteles[(ciudad.id, nombre)] = Hotel(
                    nombre=nombre, ciudad_id=ciudad.id, estrellas=estrellas, precio_noche=precio_noche, activo=True,
                    descripcion=f"Alojamiento seleccionado en {datos['ciudad']}, con desayuno, recepción 24 horas y ubicación estratégica para recorrer el destino.",
                )
                sesion.add(catalogo.hoteles[(ciudad.id, nombre)])
        for nombre, duracion, precio in datos["excursiones"]:
            if (ciudad.id, nombre) not in catalogo.excursiones:
                catalogo.excursiones[(ciudad.id, nombre)] = Excursion(
                    nombre=nombre, ciudad_id=ciudad.id, duracion_horas=duracion, precio=precio, activo=True,
                    descripcion=f"Experiencia guiada para conocer {datos['ciudad']} con acompañamiento local y tiempo para fotografías.",
                )
                sesion.add(catalogo.excursiones[(ciudad.id, nombre)])
    await sesion.flush()
    return catalogo


# --------------------------------------------------------------------------------------
# Programación de vuelos
# --------------------------------------------------------------------------------------


def _numero_de_regreso(numero_ida: str) -> str:
    return numero_ida.replace("AUR3", "AUR4", 1)


async def _asegurar_programacion_de_vuelos(sesion: AsyncSession, lugares: _Lugares) -> list[Vuelo]:
    """Mantiene, para cada destino de ejemplo, salidas semanales de ida y su vuelo de regreso.

    Solo añade fechas a continuación de la última que ya exista para esa ruta, así que no
    resucita vuelos que un administrador haya borrado o desactivado. Devuelve todos los vuelos de ejemplo
    (los que ya estaban y los nuevos) para que los paquetes no tengan que volver a consultarlos.
    """
    hoy = ahora().date()
    aerolinea = await sesion.scalar(select(Aerolinea).where(Aerolinea.nombre == "Aurora Airlines"))
    modelos = {m.nombre: m for m in (await sesion.scalars(select(ModeloAvion))).all()}
    origen = await lugares.ciudad(sesion, *ORIGEN_PRINCIPAL)

    numeros = [d["vuelo"] for d in DESTINOS_SEMILLA] + [_numero_de_regreso(d["vuelo"]) for d in DESTINOS_SEMILLA]
    vuelos: list[Vuelo] = list((await sesion.scalars(select(Vuelo).where(Vuelo.numero_vuelo.in_(numeros)))).unique().all())
    # Salidas ya programadas por ruta de ida, y salidas de regreso por número de vuelo.
    salidas_de_ida: dict[tuple[str, int, int], list[date]] = defaultdict(list)
    salidas_de_regreso: set[tuple[str, datetime]] = set()
    for vuelo in vuelos:
        salidas_de_ida[(vuelo.numero_vuelo, vuelo.origen_id, vuelo.destino_id)].append(vuelo.fecha_salida.date())
        salidas_de_regreso.add((vuelo.numero_vuelo, vuelo.fecha_salida))

    for indice, datos in enumerate(DESTINOS_SEMILLA):
        ciudad = await lugares.ciudad(sesion, datos["pais"], datos["ciudad"])
        numero_ida, numero_regreso = datos["vuelo"], _numero_de_regreso(datos["vuelo"])
        noches = 6 + indice % 3
        modelo = modelos["Airbus A320" if indice % 2 == 0 else "Boeing 787"]
        capacidad = 180 if indice % 2 == 0 else 260
        duracion = timedelta(hours=9 + indice % 4, minutes=45)
        puerta, terminal = f"{chr(65 + indice % 4)}{10 + indice:02d}", str(1 + indice % 3)

        salidas = salidas_de_ida[(numero_ida, origen.id, ciudad.id)]
        fechas = set(salidas)
        siguiente = max(max(salidas) + timedelta(days=DIAS_ENTRE_SALIDAS) if salidas else hoy, hoy + timedelta(days=DIAS_DE_ANTELACION))
        while siguiente <= hoy + timedelta(days=HORIZONTE_DE_VENTA_DIAS):
            salida = datetime.combine(siguiente, time(7 + indice % 5, 30))
            nuevo = Vuelo(
                numero_vuelo=numero_ida, aerolinea_id=aerolinea.id, modelo_avion_id=modelo.id, origen_id=origen.id,
                destino_id=ciudad.id, fecha_salida=salida, fecha_llegada=salida + duracion, capacidad_maxima=capacidad,
                puerta=puerta, terminal=terminal, estado="programado", activo=True,
            )
            sesion.add(nuevo)
            vuelos.append(nuevo)
            salidas_de_regreso.add((numero_ida, salida))
            fechas.add(siguiente)
            siguiente += timedelta(days=DIAS_ENTRE_SALIDAS)

        # Cada salida futura tiene su vuelo de regreso `noches` días después.
        for fecha in sorted(f for f in fechas if f > hoy):
            regreso = datetime.combine(fecha + timedelta(days=noches), time(11 + indice % 4, 0))
            if (numero_regreso, regreso) not in salidas_de_regreso:
                nuevo = Vuelo(
                    numero_vuelo=numero_regreso, aerolinea_id=aerolinea.id, modelo_avion_id=modelo.id, origen_id=ciudad.id,
                    destino_id=origen.id, fecha_salida=regreso, fecha_llegada=regreso + duracion, capacidad_maxima=capacidad,
                    puerta=puerta, terminal=terminal, estado="programado", activo=True,
                )
                sesion.add(nuevo)
                vuelos.append(nuevo)
                salidas_de_regreso.add((numero_regreso, regreso))
    await sesion.flush()
    return vuelos


async def _asegurar_paquetes(sesion: AsyncSession, lugares: _Lugares, catalogo: _Catalogo, vuelos: list[Vuelo]) -> None:
    """Un paquete de ejemplo por destino, siempre apuntando a la próxima salida disponible."""
    momento = ahora()
    origen = await lugares.ciudad(sesion, *ORIGEN_PRINCIPAL)
    nombres = [f"Aurora {d['ciudad']}: experiencia completa" for d in DESTINOS_SEMILLA]
    paquetes = {p.nombre: p for p in (await sesion.scalars(select(Paquete).where(Paquete.nombre.in_(nombres)))).unique().all()}

    for indice, datos in enumerate(DESTINOS_SEMILLA):
        ciudad = await lugares.ciudad(sesion, datos["pais"], datos["ciudad"])
        destino = catalogo.destinos[ciudad.id]
        nombre = nombres[indice]
        noches = 6 + indice % 3
        paquete = paquetes.get(nombre)

        # Próxima salida futura de esta ruta con su vuelo de regreso.
        ida = min(
            (v for v in vuelos if v.numero_vuelo == datos["vuelo"] and v.origen_id == origen.id and v.destino_id == ciudad.id
             and v.activo and v.estado == "programado" and v.fecha_salida > momento + timedelta(days=3)),
            key=lambda v: v.fecha_salida, default=None,
        )
        if ida is None:
            continue
        desde = datetime.combine(ida.fecha_salida.date() + timedelta(days=noches), time.min)
        hasta = datetime.combine(ida.fecha_salida.date() + timedelta(days=noches + 1), time.min)
        regreso = next((v for v in vuelos if v.numero_vuelo == _numero_de_regreso(datos["vuelo"]) and desde <= v.fecha_salida < hasta), None)

        if paquete is None:
            hotel = catalogo.hoteles.get((ciudad.id, datos["hoteles"][0][0]))
            excursiones = [catalogo.excursiones.get((ciudad.id, excursion[0])) for excursion in datos["excursiones"]]
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
    roles = {rol.nombre: rol for rol in (await sesion.scalars(select(Role))).unique().all()}
    for nombre in PERMISOS_POR_ROL:
        if nombre not in roles:
            roles[nombre] = Role(nombre=nombre)
            sesion.add(roles[nombre])
    permisos = {permiso.nombre: permiso for permiso in (await sesion.scalars(select(Permiso))).unique().all()}
    for lista in PERMISOS_POR_ROL.values():
        for nombre in lista:
            if nombre not in permisos:
                permisos[nombre] = Permiso(nombre=nombre)
                sesion.add(permisos[nombre])
    await sesion.flush()
    asignados = {(rol_id, permiso_id) for rol_id, permiso_id in (await sesion.execute(select(rol_permisos.c.rol_id, rol_permisos.c.permiso_id))).all()}
    for rol_nombre, lista in PERMISOS_POR_ROL.items():
        for permiso_nombre in lista:
            par = (roles[rol_nombre].id, permisos[permiso_nombre].id)
            if par not in asignados:
                await sesion.execute(
                    text(f"{clausula} INTO rol_permisos (rol_id, permiso_id) VALUES (:rol_id, :permiso_id)"),
                    {"rol_id": par[0], "permiso_id": par[1]},
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
