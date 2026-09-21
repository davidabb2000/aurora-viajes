"""Vuelos, hoteles, excursiones y paquetes: el catálogo de viaje que administra el personal."""
from datetime import timedelta

from fastapi import APIRouter, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencias import Administrador, EmpleadoOAdmin, SesionDep, UsuarioActual, es_personal
from app.errores import ConflictoDeNegocio, ErrorDeDominio, RecursoNoEncontrado
from app.models.dominio import Aerolinea, Ciudad, Destino, Excursion, Hotel, ModeloAvion, Paquete, Reserva, ReservaExcursion, Vuelo
from app.schemas.catalogo import ExcursionCreate, HotelCreate, PaqueteCreate, VueloCreate
from app.services.catalogos import ahora, generar_numero_vuelo, normalizar_texto, puerta_terminal_por_ruta
from app.services.disponibilidad import plazas_libres, plazas_ocupadas
from app.services.serializadores import excursion_a_dict, hotel_a_dict, paquete_a_dict, vuelo_a_dict

router = APIRouter(tags=["viajes"])


# --------------------------------------------------------------------------------------
# Vuelos
# --------------------------------------------------------------------------------------


async def _exigir(sesion: AsyncSession, modelo, identificador: int, mensaje: str):
    fila = await sesion.get(modelo, identificador)
    if fila is None:
        raise ErrorDeDominio(mensaje)
    return fila


async def _reservas_y_paquetes_de_vuelo(sesion: AsyncSession, vuelo_id: int) -> tuple[int, int]:
    """Cuántas reservas (de cualquier estado) y paquetes activos usan el vuelo."""
    reservas = await sesion.scalar(
        select(func.count(Reserva.id)).where(or_(Reserva.vuelo_id == vuelo_id, Reserva.vuelo_regreso_id == vuelo_id))
    )
    paquetes = await sesion.scalar(
        select(func.count(Paquete.id)).where(Paquete.activo.is_(True), or_(Paquete.vuelo_id == vuelo_id, Paquete.vuelo_regreso_id == vuelo_id))
    )
    return int(reservas or 0), int(paquetes or 0)


async def _validar_vuelo(sesion: AsyncSession, payload: VueloCreate, vuelo: Vuelo | None) -> tuple[str, int]:
    """Comprueba las referencias y devuelve el número de vuelo y la capacidad a la venta."""
    await _exigir(sesion, Aerolinea, payload.aerolineaId, "La aerolínea seleccionada no existe.")
    modelo = await _exigir(sesion, ModeloAvion, payload.modeloAvionId, "El modelo de avión seleccionado no existe.")
    await _exigir(sesion, Ciudad, payload.origenId, "La ciudad de origen no existe.")
    await _exigir(sesion, Ciudad, payload.destinoId, "La ciudad de destino no existe.")

    capacidad = payload.capacidadMaxima or modelo.capacidad
    if capacidad > modelo.capacidad:
        raise ErrorDeDominio(f"El {modelo.nombre} tiene {modelo.capacidad} plazas: no se pueden vender {capacidad}.")

    numero = payload.numeroVuelo or (vuelo.numero_vuelo if vuelo else await generar_numero_vuelo(sesion))
    duplicado = await sesion.scalar(
        select(Vuelo.id).where(Vuelo.numero_vuelo == numero, Vuelo.fecha_salida == payload.fechaSalida, *([Vuelo.id != vuelo.id] if vuelo else []))
    )
    if duplicado is not None:
        raise ConflictoDeNegocio(f"Ya existe el vuelo {numero} en esa fecha y hora.")

    if vuelo is None and payload.fechaSalida <= ahora():
        raise ErrorDeDominio("La salida de un vuelo nuevo debe ser en el futuro.")
    return numero, capacidad


@router.get("/api/vuelos")
async def listar_vuelos(
    personal: EmpleadoOAdmin,
    sesion: SesionDep,
    pasados: bool = Query(default=False, description="Incluir vuelos que ya salieron"),
    limite: int = Query(default=500, ge=1, le=1000),
):
    consulta = select(Vuelo).order_by(Vuelo.fecha_salida.asc()).limit(limite)
    if not pasados:
        consulta = consulta.where(Vuelo.fecha_salida >= ahora() - timedelta(days=1))
    vuelos = (await sesion.scalars(consulta)).unique().all()
    plazas = await plazas_libres(sesion, vuelos)
    return [vuelo_a_dict(vuelo, plazas[vuelo.id]) for vuelo in vuelos]


@router.get("/api/vuelos/{vuelo_id}")
async def obtener_vuelo(vuelo_id: int, personal: EmpleadoOAdmin, sesion: SesionDep):
    vuelo = await sesion.get(Vuelo, vuelo_id)
    if vuelo is None:
        raise RecursoNoEncontrado("un vuelo", vuelo_id)
    return vuelo_a_dict(vuelo, (await plazas_libres(sesion, [vuelo]))[vuelo.id])


@router.post("/api/vuelos", status_code=status.HTTP_201_CREATED)
async def crear_vuelo(payload: VueloCreate, admin: Administrador, sesion: SesionDep):
    numero, capacidad = await _validar_vuelo(sesion, payload, None)
    origen = await sesion.get(Ciudad, payload.origenId)
    destino = await sesion.get(Ciudad, payload.destinoId)
    puerta, terminal = payload.puerta, payload.terminal
    if not puerta or not terminal:
        auto_puerta, auto_terminal = puerta_terminal_por_ruta(origen.nombre, destino.nombre)
        puerta, terminal = puerta or auto_puerta, terminal or auto_terminal
    vuelo = Vuelo(
        numero_vuelo=numero, aerolinea_id=payload.aerolineaId, modelo_avion_id=payload.modeloAvionId,
        origen_id=payload.origenId, destino_id=payload.destinoId, fecha_salida=payload.fechaSalida,
        fecha_llegada=payload.fechaLlegada, capacidad_maxima=capacidad, puerta=puerta, terminal=terminal,
        estado=payload.estado, activo=payload.activo,
    )
    sesion.add(vuelo)
    await sesion.commit()
    await sesion.refresh(vuelo)  # recarga también las relaciones (aerolínea, modelo, ciudades)
    return vuelo_a_dict(vuelo, capacidad)


@router.put("/api/vuelos/{vuelo_id}")
async def actualizar_vuelo(vuelo_id: int, payload: VueloCreate, admin: Administrador, sesion: SesionDep):
    vuelo = await sesion.get(Vuelo, vuelo_id)
    if vuelo is None:
        raise RecursoNoEncontrado("un vuelo", vuelo_id)
    numero, capacidad = await _validar_vuelo(sesion, payload, vuelo)

    ocupadas = (await plazas_ocupadas(sesion, [vuelo.id]))[vuelo.id]
    reservas, paquetes = await _reservas_y_paquetes_de_vuelo(sesion, vuelo.id)
    ruta_o_fecha_cambian = (
        vuelo.origen_id != payload.origenId
        or vuelo.destino_id != payload.destinoId
        or vuelo.fecha_salida.date() != payload.fechaSalida.date()
    )
    if ruta_o_fecha_cambian and (reservas or paquetes):
        raise ConflictoDeNegocio(
            "Este vuelo ya lo usan reservas o paquetes: no se puede cambiar su ruta ni su día. Cancélalo y crea otro."
        )
    if capacidad < ocupadas:
        raise ConflictoDeNegocio(f"La capacidad no puede ser menor que las plazas ya vendidas ({ocupadas}).")

    afectadas = ocupadas if (payload.estado == "cancelado" or not payload.activo) and (vuelo.estado != "cancelado" and vuelo.activo) else 0
    vuelo.numero_vuelo = numero
    vuelo.aerolinea_id, vuelo.modelo_avion_id = payload.aerolineaId, payload.modeloAvionId
    vuelo.origen_id, vuelo.destino_id = payload.origenId, payload.destinoId
    vuelo.fecha_salida, vuelo.fecha_llegada = payload.fechaSalida, payload.fechaLlegada
    vuelo.capacidad_maxima = capacidad
    vuelo.puerta, vuelo.terminal = payload.puerta, payload.terminal
    vuelo.estado, vuelo.activo = payload.estado, payload.activo
    await sesion.commit()
    await sesion.refresh(vuelo)
    datos = vuelo_a_dict(vuelo, max(capacidad - ocupadas, 0))
    if afectadas:
        datos["advertencia"] = f"Hay {afectadas} pasajero(s) con reserva en este vuelo: avísales o cámbialos de vuelo."
    return datos


@router.delete("/api/vuelos/{vuelo_id}")
async def eliminar_vuelo(vuelo_id: int, admin: Administrador, sesion: SesionDep):
    vuelo = await sesion.get(Vuelo, vuelo_id)
    if vuelo is None:
        raise RecursoNoEncontrado("un vuelo", vuelo_id)
    usado_por_paquetes = await sesion.scalar(
        select(func.count(Paquete.id)).where(or_(Paquete.vuelo_id == vuelo_id, Paquete.vuelo_regreso_id == vuelo_id))
    )
    reservas, _ = await _reservas_y_paquetes_de_vuelo(sesion, vuelo_id)
    if reservas or usado_por_paquetes:
        raise ConflictoDeNegocio(
            "El vuelo tiene reservas o paquetes asociados y no se puede eliminar. Cámbialo a «cancelado» o desactívalo."
        )
    await sesion.delete(vuelo)
    await sesion.commit()
    return {"mensaje": "Vuelo eliminado."}


# --------------------------------------------------------------------------------------
# Hoteles y excursiones
# --------------------------------------------------------------------------------------


async def _exigir_ciudad(sesion: AsyncSession, ciudad_id: int) -> Ciudad:
    return await _exigir(sesion, Ciudad, ciudad_id, "La ciudad seleccionada no existe.")


async def _exigir_nombre_libre(sesion: AsyncSession, modelo, ciudad_id: int, nombre: str, propio: int | None) -> None:
    """Un hotel o una excursión no se repite en la misma ciudad (sin distinguir mayúsculas ni tildes)."""
    existentes = (await sesion.scalars(select(modelo).where(modelo.ciudad_id == ciudad_id))).unique().all()
    if any(fila.id != propio and normalizar_texto(fila.nombre) == normalizar_texto(nombre) for fila in existentes):
        raise ConflictoDeNegocio(f"Ya existe «{nombre}» en esa ciudad.")


@router.get("/api/hoteles")
async def listar_hoteles(personal: EmpleadoOAdmin, sesion: SesionDep):
    hoteles = (await sesion.scalars(select(Hotel).order_by(Hotel.nombre.asc()))).unique().all()
    return [hotel_a_dict(hotel) for hotel in hoteles]


@router.post("/api/hoteles", status_code=status.HTTP_201_CREATED)
async def crear_hotel(payload: HotelCreate, admin: Administrador, sesion: SesionDep):
    await _exigir_ciudad(sesion, payload.ciudadId)
    await _exigir_nombre_libre(sesion, Hotel, payload.ciudadId, payload.nombre, None)
    hotel = Hotel(
        nombre=payload.nombre, ciudad_id=payload.ciudadId, estrellas=payload.estrellas,
        precio_noche=payload.precioNoche, descripcion=payload.descripcion, activo=payload.activo,
    )
    sesion.add(hotel)
    await sesion.commit()
    await sesion.refresh(hotel)
    return hotel_a_dict(hotel)


@router.put("/api/hoteles/{hotel_id}")
async def actualizar_hotel(hotel_id: int, payload: HotelCreate, admin: Administrador, sesion: SesionDep):
    hotel = await sesion.get(Hotel, hotel_id)
    if hotel is None:
        raise RecursoNoEncontrado("un hotel", hotel_id)
    await _exigir_ciudad(sesion, payload.ciudadId)
    await _exigir_nombre_libre(sesion, Hotel, payload.ciudadId, payload.nombre, hotel.id)
    if hotel.ciudad_id != payload.ciudadId:
        en_uso = await sesion.scalar(select(func.count(Paquete.id)).where(Paquete.hotel_id == hotel.id)) or await sesion.scalar(
            select(func.count(Reserva.id)).where(Reserva.hotel_id == hotel.id)
        )
        if en_uso:
            raise ConflictoDeNegocio("El hotel ya está en paquetes o reservas: no se puede cambiar de ciudad.")
    hotel.nombre, hotel.ciudad_id, hotel.estrellas = payload.nombre, payload.ciudadId, payload.estrellas
    hotel.precio_noche, hotel.descripcion, hotel.activo = payload.precioNoche, payload.descripcion, payload.activo
    await sesion.commit()
    await sesion.refresh(hotel)
    return hotel_a_dict(hotel)


@router.delete("/api/hoteles/{hotel_id}")
async def eliminar_hotel(hotel_id: int, admin: Administrador, sesion: SesionDep):
    hotel = await sesion.get(Hotel, hotel_id)
    if hotel is None:
        raise RecursoNoEncontrado("un hotel", hotel_id)
    hotel.activo = False
    await sesion.commit()
    return {"mensaje": "Hotel desactivado."}


@router.get("/api/excursiones")
async def listar_excursiones(personal: EmpleadoOAdmin, sesion: SesionDep):
    excursiones = (await sesion.scalars(select(Excursion).order_by(Excursion.nombre.asc()))).unique().all()
    return [excursion_a_dict(excursion) for excursion in excursiones]


@router.post("/api/excursiones", status_code=status.HTTP_201_CREATED)
async def crear_excursion(payload: ExcursionCreate, admin: Administrador, sesion: SesionDep):
    await _exigir_ciudad(sesion, payload.ciudadId)
    await _exigir_nombre_libre(sesion, Excursion, payload.ciudadId, payload.nombre, None)
    excursion = Excursion(
        nombre=payload.nombre, ciudad_id=payload.ciudadId, duracion_horas=payload.duracionHoras,
        precio=payload.precio, descripcion=payload.descripcion, activo=payload.activo,
    )
    sesion.add(excursion)
    await sesion.commit()
    await sesion.refresh(excursion)
    return excursion_a_dict(excursion)


@router.put("/api/excursiones/{excursion_id}")
async def actualizar_excursion(excursion_id: int, payload: ExcursionCreate, admin: Administrador, sesion: SesionDep):
    excursion = await sesion.get(Excursion, excursion_id)
    if excursion is None:
        raise RecursoNoEncontrado("una excursión", excursion_id)
    await _exigir_ciudad(sesion, payload.ciudadId)
    await _exigir_nombre_libre(sesion, Excursion, payload.ciudadId, payload.nombre, excursion.id)
    if excursion.ciudad_id != payload.ciudadId:
        en_uso = await sesion.scalar(select(func.count(ReservaExcursion.reserva_id)).where(ReservaExcursion.excursion_id == excursion.id))
        en_paquetes = (await sesion.scalars(select(Paquete.id).where(Paquete.excursiones.any(Excursion.id == excursion.id)))).first()
        if en_uso or en_paquetes:
            raise ConflictoDeNegocio("La excursión ya está en paquetes o reservas: no se puede cambiar de ciudad.")
    excursion.nombre, excursion.ciudad_id, excursion.duracion_horas = payload.nombre, payload.ciudadId, payload.duracionHoras
    excursion.precio, excursion.descripcion, excursion.activo = payload.precio, payload.descripcion, payload.activo
    await sesion.commit()
    await sesion.refresh(excursion)
    return excursion_a_dict(excursion)


@router.delete("/api/excursiones/{excursion_id}")
async def eliminar_excursion(excursion_id: int, admin: Administrador, sesion: SesionDep):
    excursion = await sesion.get(Excursion, excursion_id)
    if excursion is None:
        raise RecursoNoEncontrado("una excursión", excursion_id)
    excursion.activo = False
    await sesion.commit()
    return {"mensaje": "Excursión desactivada."}


# --------------------------------------------------------------------------------------
# Paquetes
# --------------------------------------------------------------------------------------


async def _validar_paquete(sesion: AsyncSession, payload: PaqueteCreate, paquete: Paquete | None) -> tuple[Destino, Vuelo, Vuelo | None, Hotel, list[Excursion], int]:
    destino = await sesion.get(Destino, payload.destinoId)
    if destino is None:
        raise RecursoNoEncontrado("un destino", payload.destinoId)
    ida = await _exigir(sesion, Vuelo, payload.vueloId, "El vuelo de ida no existe.")
    hotel = await sesion.get(Hotel, payload.hotelId)
    if hotel is None or not hotel.activo:
        raise ErrorDeDominio("El hotel seleccionado no existe o está inactivo.")
    if hotel.ciudad_id != destino.ciudad_id:
        raise ErrorDeDominio("El hotel debe estar en la ciudad del destino seleccionado.")

    if ida.destino_id != destino.ciudad_id:
        raise ErrorDeDominio(f"El vuelo {ida.numero_vuelo} no llega a {destino.nombre}.")
    cambia_de_vuelo = paquete is None or paquete.vuelo_id != ida.id
    if cambia_de_vuelo and (not ida.activo or ida.estado != "programado" or ida.fecha_salida <= ahora()):
        raise ErrorDeDominio("El vuelo de ida no está disponible (cancelado, inactivo o ya salió).")

    regreso: Vuelo | None = None
    noches = payload.noches
    if payload.vueloRegresoId is not None:
        regreso = await _exigir(sesion, Vuelo, payload.vueloRegresoId, "El vuelo de regreso no existe.")
        if regreso.origen_id != destino.ciudad_id or regreso.destino_id != ida.origen_id:
            raise ErrorDeDominio("El vuelo de regreso debe salir del destino y volver al origen del vuelo de ida.")
        dias = (regreso.fecha_salida.date() - ida.fecha_salida.date()).days
        if dias < 1:
            raise ErrorDeDominio("El vuelo de regreso debe salir al menos un día después del de ida.")
        if noches is not None and noches != dias:
            raise ErrorDeDominio(f"Las noches ({noches}) no coinciden con las fechas de los vuelos ({dias}).")
        noches = dias
        if paquete is None or paquete.vuelo_regreso_id != regreso.id:
            if not regreso.activo or regreso.estado != "programado" or regreso.fecha_salida <= ahora():
                raise ErrorDeDominio("El vuelo de regreso no está disponible (cancelado, inactivo o ya salió).")

    ids = set(payload.excursionIds)
    excursiones: list[Excursion] = []
    if ids:
        excursiones = list((await sesion.scalars(select(Excursion).where(Excursion.id.in_(ids)))).unique().all())
        if len(excursiones) != len(ids) or any(not e.activo for e in excursiones):
            raise ErrorDeDominio("Una o más excursiones no existen o están inactivas.")
        if any(e.ciudad_id != destino.ciudad_id for e in excursiones):
            raise ErrorDeDominio("Las excursiones deben estar en la ciudad del destino seleccionado.")

    repetido = (await sesion.scalars(select(Paquete).where(func.lower(Paquete.nombre) == payload.nombre.lower()))).unique().all()
    if any(p.id != (paquete.id if paquete else None) for p in repetido):
        raise ConflictoDeNegocio("Ya existe un paquete con ese nombre.")
    return destino, ida, regreso, hotel, excursiones, noches


@router.get("/api/paquetes")
async def listar_paquetes(usuario: UsuarioActual, sesion: SesionDep):
    """Los clientes ven los paquetes con salida futura; el personal, todos los activos."""
    paquetes = (await sesion.scalars(select(Paquete).where(Paquete.activo.is_(True)))).unique().all()
    if not es_personal(usuario):
        momento = ahora()
        paquetes = [p for p in paquetes if p.vuelo_rel.activo and p.vuelo_rel.estado == "programado" and p.vuelo_rel.fecha_salida > momento]
    paquetes = sorted(paquetes, key=lambda p: p.vuelo_rel.fecha_salida)
    vuelos = {v.id: v for p in paquetes for v in (p.vuelo_rel, p.vuelo_regreso_rel) if v is not None}
    plazas = await plazas_libres(sesion, vuelos.values())
    return [paquete_a_dict(paquete, plazas) for paquete in paquetes]


@router.post("/api/paquetes", status_code=status.HTTP_201_CREATED)
async def crear_paquete(payload: PaqueteCreate, admin: Administrador, sesion: SesionDep):
    destino, ida, regreso, hotel, excursiones, noches = await _validar_paquete(sesion, payload, None)
    paquete = Paquete(
        nombre=payload.nombre, destino_id=destino.id, vuelo_id=ida.id, vuelo_regreso_id=regreso.id if regreso else None,
        hotel_id=hotel.id, noches=noches, precio_base=payload.precioBase, activo=payload.activo, excursiones=excursiones,
    )
    sesion.add(paquete)
    await sesion.commit()
    await sesion.refresh(paquete)
    return paquete_a_dict(paquete, await plazas_libres(sesion, [v for v in (paquete.vuelo_rel, paquete.vuelo_regreso_rel) if v]))


@router.put("/api/paquetes/{paquete_id}")
async def actualizar_paquete(paquete_id: int, payload: PaqueteCreate, admin: Administrador, sesion: SesionDep):
    paquete = await sesion.get(Paquete, paquete_id)
    if paquete is None:
        raise RecursoNoEncontrado("un paquete", paquete_id)
    destino, ida, regreso, hotel, excursiones, noches = await _validar_paquete(sesion, payload, paquete)
    paquete.nombre, paquete.destino_id, paquete.vuelo_id = payload.nombre, destino.id, ida.id
    paquete.vuelo_regreso_id = regreso.id if regreso else None
    paquete.hotel_id, paquete.noches, paquete.precio_base, paquete.activo = hotel.id, noches, payload.precioBase, payload.activo
    paquete.excursiones = excursiones
    await sesion.commit()
    await sesion.refresh(paquete)
    return paquete_a_dict(paquete, await plazas_libres(sesion, [v for v in (paquete.vuelo_rel, paquete.vuelo_regreso_rel) if v]))


@router.delete("/api/paquetes/{paquete_id}")
async def eliminar_paquete(paquete_id: int, admin: Administrador, sesion: SesionDep):
    paquete = await sesion.get(Paquete, paquete_id)
    if paquete is None:
        raise RecursoNoEncontrado("un paquete", paquete_id)
    paquete.activo = False
    await sesion.commit()
    return {"mensaje": "Paquete desactivado."}

