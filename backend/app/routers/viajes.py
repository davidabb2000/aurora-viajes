"""Vuelos, hoteles, excursiones y paquetes."""
from fastapi import APIRouter, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.dependencias import Administrador, SesionDep, UsuarioActual
from app.errores import ConflictoDeNegocio, ErrorDeDominio, RecursoNoEncontrado
from app.models.dominio import Destino, Excursion, Hotel, Paquete, Reserva, Vuelo
from app.schemas.catalogo import ExcursionCreate, HotelCreate, PaqueteCreate, VueloCreate
from app.services.catalogos import generar_numero_vuelo, normalizar_texto, puerta_terminal_por_ruta, resolver_estado_reserva_id
from app.services.serializadores import excursion_a_dict, hotel_a_dict, paquete_a_dict, vuelo_a_dict

router = APIRouter(tags=["viajes"])


@router.get("/api/vuelos")
async def listar_vuelos(usuario: UsuarioActual, sesion: SesionDep):
    vuelos = await sesion.scalars(select(Vuelo).order_by(Vuelo.fecha_salida.asc()))
    estado_cancelado_id = await resolver_estado_reserva_id(sesion, "cancelada")
    ocupacion = await sesion.execute(
        select(Reserva.vuelo_id, func.coalesce(func.sum(Reserva.pasajeros), 0))
        .where(Reserva.estado_id != estado_cancelado_id, Reserva.vuelo_id.is_not(None))
        .group_by(Reserva.vuelo_id)
    )
    ocupados = {vuelo_id: int(total or 0) for vuelo_id, total in ocupacion.all()}
    resultado = []
    for vuelo in vuelos:
        datos = vuelo_a_dict(vuelo)
        datos["pasajerosDisponibles"] = max(vuelo.capacidad_maxima - ocupados.get(vuelo.id, 0), 0)
        resultado.append(datos)
    return resultado


@router.get("/api/vuelos/{vuelo_id}")
async def obtener_vuelo(vuelo_id: int, usuario: UsuarioActual, sesion: SesionDep):
    vuelo = await sesion.get(Vuelo, vuelo_id)
    if vuelo is None:
        raise RecursoNoEncontrado("un vuelo", vuelo_id)
    return vuelo_a_dict(vuelo)


@router.post("/api/vuelos", status_code=status.HTTP_201_CREATED)
async def crear_vuelo(payload: VueloCreate, admin: Administrador, sesion: SesionDep):
    numero_vuelo = await generar_numero_vuelo(sesion)
    puerta, terminal = payload.puerta, payload.terminal
    if not puerta or not terminal:
        puerta, terminal = puerta_terminal_por_ruta(payload.origen, payload.destino)
    vuelo = Vuelo(
        numero_vuelo=numero_vuelo,
        aerolinea=payload.aerolinea,
        avion=payload.avion,
        origen=payload.origen,
        destino=payload.destino,
        fecha_salida=payload.fechaSalida,
        fecha_llegada=payload.fechaLlegada,
        capacidad_maxima=payload.capacidadMaxima,
        puerta=puerta,
        terminal=terminal,
        estado=payload.estado,
        activo=payload.activo,
    )
    sesion.add(vuelo)
    await sesion.commit()
    await sesion.refresh(vuelo)
    return vuelo_a_dict(vuelo)


@router.put("/api/vuelos/{vuelo_id}")
async def actualizar_vuelo(vuelo_id: int, payload: VueloCreate, admin: Administrador, sesion: SesionDep):
    vuelo = await sesion.get(Vuelo, vuelo_id)
    if vuelo is None:
        raise RecursoNoEncontrado("un vuelo", vuelo_id)
    duplicado = await sesion.scalar(
        select(Vuelo).where(Vuelo.numero_vuelo == payload.numeroVuelo, Vuelo.id != vuelo_id)
    )
    if duplicado is not None:
        raise ConflictoDeNegocio("Ya existe un vuelo con ese número.")
    vuelo.numero_vuelo = payload.numeroVuelo
    vuelo.aerolinea = payload.aerolinea
    vuelo.avion = payload.avion
    vuelo.origen = payload.origen
    vuelo.destino = payload.destino
    vuelo.fecha_salida = payload.fechaSalida
    vuelo.fecha_llegada = payload.fechaLlegada
    vuelo.capacidad_maxima = payload.capacidadMaxima
    vuelo.puerta = payload.puerta
    vuelo.terminal = payload.terminal
    vuelo.estado = payload.estado
    vuelo.activo = payload.activo
    await sesion.commit()
    await sesion.refresh(vuelo)
    return vuelo_a_dict(vuelo)


@router.delete("/api/vuelos/{vuelo_id}")
async def eliminar_vuelo(vuelo_id: int, admin: Administrador, sesion: SesionDep):
    vuelo = await sesion.get(Vuelo, vuelo_id)
    if vuelo is None:
        raise RecursoNoEncontrado("un vuelo", vuelo_id)
    await sesion.delete(vuelo)
    await sesion.commit()
    return {"mensaje": "Vuelo eliminado."}


async def _validar_paquete(sesion: SesionDep, payload: PaqueteCreate):
    destino = await sesion.get(Destino, payload.destinoId)
    vuelo = await sesion.get(Vuelo, payload.vueloId)
    hotel = await sesion.get(Hotel, payload.hotelId)
    if destino is None:
        raise RecursoNoEncontrado("un destino", payload.destinoId)
    if vuelo is None:
        raise RecursoNoEncontrado("un vuelo", payload.vueloId)
    if hotel is None or not hotel.activo:
        raise ErrorDeDominio("El hotel seleccionado no existe o está inactivo.")
    ubicacion_destino = [normalizar_texto(parte) for parte in destino.nombre.split(",")]
    if normalizar_texto(hotel.ciudad) not in ubicacion_destino or normalizar_texto(hotel.pais) not in ubicacion_destino:
        raise ErrorDeDominio("El hotel debe pertenecer a la ciudad y país del destino seleccionado.")
    if not vuelo.activo or vuelo.estado in {"cancelado", "aterrizado"}:
        raise ErrorDeDominio("El vuelo seleccionado no está disponible.")
    if vuelo.fecha_salida.date() != payload.fechaSalida:
        raise ErrorDeDominio("La fecha del paquete debe coincidir con la salida del vuelo.")
    if normalizar_texto(vuelo.destino) not in normalizar_texto(destino.nombre) and normalizar_texto(destino.nombre) not in normalizar_texto(vuelo.destino):
        raise ErrorDeDominio("El destino del paquete no coincide con el destino del vuelo.")
    excursiones = list(await sesion.scalars(select(Excursion).where(Excursion.id.in_(set(payload.excursionIds))))) if payload.excursionIds else []
    if len(excursiones) != len(set(payload.excursionIds)) or any(not excursion.activo for excursion in excursiones):
        raise ErrorDeDominio("Una o más excursiones no existen o están inactivas.")
    if any(normalizar_texto(excursion.ciudad) not in ubicacion_destino or normalizar_texto(excursion.pais) not in ubicacion_destino for excursion in excursiones):
        raise ErrorDeDominio("Las excursiones deben pertenecer a la ciudad y país del destino seleccionado.")
    return destino, vuelo, hotel, excursiones


@router.get("/api/hoteles")
async def listar_hoteles(usuario: UsuarioActual, sesion: SesionDep):
    hoteles = await sesion.scalars(select(Hotel).order_by(Hotel.nombre.asc()))
    return [hotel_a_dict(hotel) for hotel in hoteles]


@router.post("/api/hoteles", status_code=status.HTTP_201_CREATED)
async def crear_hotel(payload: HotelCreate, admin: Administrador, sesion: SesionDep):
    hotel = Hotel(nombre=payload.nombre.strip(), ciudad=payload.ciudad.strip(), pais=payload.pais.strip(), estrellas=payload.estrellas, precio_noche=payload.precioNoche, descripcion=payload.descripcion, activo=payload.activo)
    sesion.add(hotel)
    await sesion.commit()
    await sesion.refresh(hotel)
    return hotel_a_dict(hotel)


@router.put("/api/hoteles/{hotel_id}")
async def actualizar_hotel(hotel_id: int, payload: HotelCreate, admin: Administrador, sesion: SesionDep):
    hotel = await sesion.get(Hotel, hotel_id)
    if hotel is None:
        raise RecursoNoEncontrado("un hotel", hotel_id)
    hotel.nombre, hotel.ciudad, hotel.pais, hotel.estrellas = payload.nombre.strip(), payload.ciudad.strip(), payload.pais.strip(), payload.estrellas
    hotel.precio_noche, hotel.descripcion, hotel.activo = payload.precioNoche, payload.descripcion, payload.activo
    await sesion.commit()
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
async def listar_excursiones(usuario: UsuarioActual, sesion: SesionDep):
    excursiones = await sesion.scalars(select(Excursion).order_by(Excursion.nombre.asc()))
    return [excursion_a_dict(excursion) for excursion in excursiones]


@router.post("/api/excursiones", status_code=status.HTTP_201_CREATED)
async def crear_excursion(payload: ExcursionCreate, admin: Administrador, sesion: SesionDep):
    excursion = Excursion(nombre=payload.nombre.strip(), ciudad=payload.ciudad.strip(), pais=payload.pais.strip(), duracion_horas=payload.duracionHoras, precio=payload.precio, descripcion=payload.descripcion, activo=payload.activo)
    sesion.add(excursion)
    await sesion.commit()
    await sesion.refresh(excursion)
    return excursion_a_dict(excursion)


@router.put("/api/excursiones/{excursion_id}")
async def actualizar_excursion(excursion_id: int, payload: ExcursionCreate, admin: Administrador, sesion: SesionDep):
    excursion = await sesion.get(Excursion, excursion_id)
    if excursion is None:
        raise RecursoNoEncontrado("una excursión", excursion_id)
    excursion.nombre, excursion.ciudad, excursion.pais, excursion.duracion_horas = payload.nombre.strip(), payload.ciudad.strip(), payload.pais.strip(), payload.duracionHoras
    excursion.precio, excursion.descripcion, excursion.activo = payload.precio, payload.descripcion, payload.activo
    await sesion.commit()
    return excursion_a_dict(excursion)


@router.delete("/api/excursiones/{excursion_id}")
async def eliminar_excursion(excursion_id: int, admin: Administrador, sesion: SesionDep):
    excursion = await sesion.get(Excursion, excursion_id)
    if excursion is None:
        raise RecursoNoEncontrado("una excursión", excursion_id)
    excursion.activo = False
    await sesion.commit()
    return {"mensaje": "Excursión desactivada."}


@router.get("/api/paquetes")
async def listar_paquetes(usuario: UsuarioActual, sesion: SesionDep):
    paquetes = await sesion.scalars(select(Paquete).where(Paquete.activo.is_(True)).order_by(Paquete.fecha_salida.asc()))
    estado_cancelado_id = await resolver_estado_reserva_id(sesion, "cancelada")
    ocupacion = await sesion.execute(
        select(Reserva.vuelo_id, func.coalesce(func.sum(Reserva.pasajeros), 0))
        .where(Reserva.estado_id != estado_cancelado_id, Reserva.vuelo_id.is_not(None))
        .group_by(Reserva.vuelo_id)
    )
    ocupados = {vuelo_id: int(total or 0) for vuelo_id, total in ocupacion.all()}
    resultado = []
    for paquete in paquetes:
        datos = paquete_a_dict(paquete)
        datos["vuelo"]["pasajerosDisponibles"] = max(paquete.vuelo_rel.capacidad_maxima - ocupados.get(paquete.vuelo_id, 0), 0)
        resultado.append(datos)
    return resultado


@router.post("/api/paquetes", status_code=status.HTTP_201_CREATED)
async def crear_paquete(payload: PaqueteCreate, admin: Administrador, sesion: SesionDep):
    if payload.vuelo is not None:
        numero_vuelo = await generar_numero_vuelo(sesion)
        puerta, terminal = payload.vuelo.puerta, payload.vuelo.terminal
        if not puerta or not terminal:
            puerta, terminal = puerta_terminal_por_ruta(payload.vuelo.origen, payload.vuelo.destino)
        vuelo_nuevo = Vuelo(
            numero_vuelo=numero_vuelo,
            aerolinea=payload.vuelo.aerolinea,
            avion=payload.vuelo.avion,
            origen=payload.vuelo.origen,
            destino=payload.vuelo.destino,
            fecha_salida=payload.vuelo.fechaSalida,
            fecha_llegada=payload.vuelo.fechaLlegada,
            capacidad_maxima=payload.vuelo.capacidadMaxima,
            puerta=puerta,
            terminal=terminal,
            estado=payload.vuelo.estado,
            activo=payload.vuelo.activo,
        )
        sesion.add(vuelo_nuevo)
        await sesion.flush()
        payload.vueloId = vuelo_nuevo.id
    destino, vuelo, hotel, excursiones = await _validar_paquete(sesion, payload)
    paquete = Paquete(nombre=payload.nombre.strip(), destino_id=destino.id, vuelo_id=vuelo.id, hotel_id=hotel.id, fecha_salida=payload.fechaSalida, fecha_regreso=payload.fechaRegreso, precio_base=payload.precioBase, activo=payload.activo, excursiones=excursiones)
    sesion.add(paquete)
    await sesion.commit()
    await sesion.refresh(paquete)
    return paquete_a_dict(paquete)


@router.put("/api/paquetes/{paquete_id}")
async def actualizar_paquete(paquete_id: int, payload: PaqueteCreate, admin: Administrador, sesion: SesionDep):
    paquete = await sesion.get(Paquete, paquete_id, options=[selectinload(Paquete.excursiones)])
    if paquete is None:
        raise RecursoNoEncontrado("un paquete", paquete_id)
    destino, vuelo, hotel, excursiones = await _validar_paquete(sesion, payload)
    paquete.nombre, paquete.destino_id, paquete.vuelo_id, paquete.hotel_id = payload.nombre.strip(), destino.id, vuelo.id, hotel.id
    paquete.fecha_salida, paquete.fecha_regreso, paquete.precio_base, paquete.activo = payload.fechaSalida, payload.fechaRegreso, payload.precioBase, payload.activo
    paquete.excursiones = excursiones
    await sesion.commit()
    await sesion.refresh(paquete)
    return paquete_a_dict(paquete)


@router.delete("/api/paquetes/{paquete_id}")
async def eliminar_paquete(paquete_id: int, admin: Administrador, sesion: SesionDep):
    paquete = await sesion.get(Paquete, paquete_id)
    if paquete is None:
        raise RecursoNoEncontrado("un paquete", paquete_id)
    paquete.activo = False
    await sesion.commit()
    return {"mensaje": "Paquete desactivado."}
