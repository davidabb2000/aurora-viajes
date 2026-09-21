"""Destinos, opciones de viaje, lugares, aerolíneas, modelos de avión, productos y servicios."""
from fastapi import APIRouter, status
from sqlalchemy import func, select

from app.dependencias import Administrador, EmpleadoOAdmin, SesionDep
from app.errores import ConflictoDeNegocio, RecursoNoEncontrado
from app.models.dominio import Aerolinea, Ciudad, Destino, Excursion, Hotel, ModeloAvion, Pais, Paquete, Producto, Reserva, Servicio, Vuelo
from app.schemas.catalogo import AerolineaCreate, CiudadCreate, DestinoCreate, ModeloAvionCreate, ProductoCreate, ServicioCreate
from app.services.catalogos import ahora, normalizar_texto
from app.services.disponibilidad import plazas_libres
from app.services.serializadores import (
    ciudad_a_dict,
    destino_a_dict,
    excursion_a_dict,
    hotel_a_dict,
    paquete_a_dict,
    producto_a_dict,
    servicio_a_dict,
    vuelo_a_dict,
)

router = APIRouter(tags=["catalogo"])

MAXIMO_DE_VUELOS_POR_LISTA = 120


@router.get("/api/catalogos/destinos")
async def catalogo_destinos(sesion: SesionDep):
    destinos = await sesion.scalars(select(Destino).where(Destino.activo.is_(True), Destino.precio_base > 0))
    return sorted((destino_a_dict(destino) for destino in destinos.unique()), key=lambda d: normalizar_texto(d["nombre"]))


@router.get("/api/catalogos/destinos/{destino_id}/opciones")
async def opciones_de_destino(destino_id: int, sesion: SesionDep):
    """Todo lo reservable para un destino, en una sola llamada.

    Los vuelos, hoteles y excursiones se relacionan con el destino por su ciudad (una clave
    foránea), no comparando textos, así que lo que aparece aquí es exactamente lo que el servidor
    aceptará al reservar. Incluye las plazas libres de cada vuelo y los paquetes con salida futura.
    """
    destino = await sesion.get(Destino, destino_id)
    if destino is None or not destino.activo:
        raise RecursoNoEncontrado("un destino", destino_id)
    momento = ahora()

    def vendibles(consulta):
        return consulta.where(Vuelo.activo.is_(True), Vuelo.estado == "programado", Vuelo.fecha_salida > momento).order_by(Vuelo.fecha_salida.asc()).limit(MAXIMO_DE_VUELOS_POR_LISTA)

    vuelos_ida = (await sesion.scalars(vendibles(select(Vuelo).where(Vuelo.destino_id == destino.ciudad_id)))).unique().all()
    vuelos_regreso = (await sesion.scalars(vendibles(select(Vuelo).where(Vuelo.origen_id == destino.ciudad_id)))).unique().all()
    hoteles = (await sesion.scalars(
        select(Hotel).where(Hotel.ciudad_id == destino.ciudad_id, Hotel.activo.is_(True)).order_by(Hotel.estrellas.desc(), Hotel.nombre.asc())
    )).unique().all()
    excursiones = (await sesion.scalars(
        select(Excursion).where(Excursion.ciudad_id == destino.ciudad_id, Excursion.activo.is_(True)).order_by(Excursion.nombre.asc())
    )).unique().all()
    paquetes = [
        paquete
        for paquete in (await sesion.scalars(select(Paquete).where(Paquete.destino_id == destino.id, Paquete.activo.is_(True)))).unique().all()
        if paquete.vuelo_rel.activo and paquete.vuelo_rel.estado == "programado" and paquete.vuelo_rel.fecha_salida > momento
    ]
    paquetes.sort(key=lambda p: p.vuelo_rel.fecha_salida)

    vuelos_de_paquetes = [v for p in paquetes for v in (p.vuelo_rel, p.vuelo_regreso_rel) if v is not None]
    plazas = await plazas_libres(sesion, {v.id: v for v in [*vuelos_ida, *vuelos_regreso, *vuelos_de_paquetes]}.values())

    origenes: dict[int, dict] = {}
    for vuelo in vuelos_ida:
        origenes.setdefault(vuelo.origen_id, {"id": vuelo.origen_id, "nombre": vuelo.origen, "pais": vuelo.origen_rel.pais.nombre})

    return {
        "destino": destino_a_dict(destino),
        "origenes": sorted(origenes.values(), key=lambda o: o["nombre"]),
        "vuelosIda": [vuelo_a_dict(v, plazas[v.id]) for v in vuelos_ida],
        "vuelosRegreso": [vuelo_a_dict(v, plazas[v.id]) for v in vuelos_regreso],
        "hoteles": [hotel_a_dict(h) for h in hoteles],
        "excursiones": [excursion_a_dict(e) for e in excursiones],
        "paquetes": [paquete_a_dict(p, plazas) for p in paquetes],
    }


# --------------------------------------------------------------------------------------
# Lugares, aerolíneas y modelos de avión: los usa el formulario de vuelos del personal
# --------------------------------------------------------------------------------------


@router.get("/api/ciudades")
async def listar_ciudades(personal: EmpleadoOAdmin, sesion: SesionDep):
    ciudades = (await sesion.scalars(select(Ciudad))).unique().all()
    return sorted((ciudad_a_dict(c) for c in ciudades), key=lambda c: (normalizar_texto(c["pais"]), normalizar_texto(c["nombre"])))


@router.post("/api/ciudades", status_code=status.HTTP_201_CREATED)
async def crear_ciudad(payload: CiudadCreate, admin: Administrador, sesion: SesionDep):
    pais = next((p for p in (await sesion.scalars(select(Pais))).all() if normalizar_texto(p.nombre) == normalizar_texto(payload.pais)), None)
    if pais is None:
        pais = Pais(nombre=payload.pais)
        sesion.add(pais)
        await sesion.flush()
    existentes = (await sesion.scalars(select(Ciudad).where(Ciudad.pais_id == pais.id))).unique().all()
    if any(normalizar_texto(c.nombre) == normalizar_texto(payload.nombre) for c in existentes):
        raise ConflictoDeNegocio(f"{payload.nombre} ya existe en {pais.nombre}.")
    ciudad = Ciudad(pais_id=pais.id, nombre=payload.nombre)
    sesion.add(ciudad)
    await sesion.commit()
    await sesion.refresh(ciudad)
    return ciudad_a_dict(ciudad)


# --------------------------------------------------------------------------------------
# Destinos: las ciudades que la agencia vende
# --------------------------------------------------------------------------------------


@router.get("/api/destinos")
async def listar_destinos(personal: EmpleadoOAdmin, sesion: SesionDep):
    """Todos los destinos, también los inactivos (el catálogo público solo muestra los activos con tarifa)."""
    destinos = (await sesion.scalars(select(Destino))).unique().all()
    return sorted((destino_a_dict(d) for d in destinos), key=lambda d: normalizar_texto(d["nombre"]))


async def _exigir_ciudad_libre(sesion, ciudad_id: int, propio: int | None) -> Ciudad:
    ciudad = await sesion.get(Ciudad, ciudad_id)
    if ciudad is None:
        raise RecursoNoEncontrado("una ciudad", ciudad_id)
    otro = await sesion.scalar(select(Destino.id).where(Destino.ciudad_id == ciudad_id))
    if otro is not None and otro != propio:
        raise ConflictoDeNegocio(f"{ciudad.nombre_completo} ya es un destino: modifica el que existe.")
    return ciudad


@router.post("/api/destinos", status_code=status.HTTP_201_CREATED)
async def crear_destino(payload: DestinoCreate, admin: Administrador, sesion: SesionDep):
    await _exigir_ciudad_libre(sesion, payload.ciudadId, None)
    destino = Destino(
        ciudad_id=payload.ciudadId, descripcion=payload.descripcion, precio_base=payload.precioBase,
        imagen_slug=payload.imagenSlug, activo=payload.activo,
    )
    sesion.add(destino)
    await sesion.commit()
    await sesion.refresh(destino)
    return destino_a_dict(destino)


@router.put("/api/destinos/{destino_id}")
async def actualizar_destino(destino_id: int, payload: DestinoCreate, admin: Administrador, sesion: SesionDep):
    destino = await sesion.get(Destino, destino_id)
    if destino is None:
        raise RecursoNoEncontrado("un destino", destino_id)
    await _exigir_ciudad_libre(sesion, payload.ciudadId, destino.id)
    if destino.ciudad_id != payload.ciudadId:
        en_uso = await sesion.scalar(select(func.count(Paquete.id)).where(Paquete.destino_id == destino.id)) or await sesion.scalar(
            select(func.count(Reserva.id)).where(Reserva.destino_id == destino.id)
        )
        if en_uso:
            raise ConflictoDeNegocio("El destino ya tiene paquetes o reservas: no se puede cambiar de ciudad.")
    destino.ciudad_id, destino.descripcion, destino.precio_base = payload.ciudadId, payload.descripcion, payload.precioBase
    destino.imagen_slug, destino.activo = payload.imagenSlug, payload.activo
    await sesion.commit()
    await sesion.refresh(destino)
    return destino_a_dict(destino)


@router.delete("/api/destinos/{destino_id}")
async def desactivar_destino(destino_id: int, admin: Administrador, sesion: SesionDep):
    """Deja de ofrecerse a los clientes. Sus reservas y paquetes existentes no se tocan."""
    destino = await sesion.get(Destino, destino_id)
    if destino is None:
        raise RecursoNoEncontrado("un destino", destino_id)
    destino.activo = False
    await sesion.commit()
    return {"mensaje": "Destino desactivado."}


@router.get("/api/aerolineas")
async def listar_aerolineas(personal: EmpleadoOAdmin, sesion: SesionDep):
    aerolineas = await sesion.scalars(select(Aerolinea).order_by(Aerolinea.nombre))
    return [{"id": a.id, "codigo": a.codigo, "nombre": a.nombre} for a in aerolineas]


@router.post("/api/aerolineas", status_code=status.HTTP_201_CREATED)
async def crear_aerolinea(payload: AerolineaCreate, admin: Administrador, sesion: SesionDep):
    duplicada = await sesion.scalar(select(Aerolinea.id).where((Aerolinea.codigo == payload.codigo) | (Aerolinea.nombre == payload.nombre)))
    if duplicada is not None:
        raise ConflictoDeNegocio("Ya existe una aerolínea con ese código o nombre.")
    aerolinea = Aerolinea(codigo=payload.codigo, nombre=payload.nombre)
    sesion.add(aerolinea)
    await sesion.commit()
    return {"id": aerolinea.id, "codigo": aerolinea.codigo, "nombre": aerolinea.nombre}


@router.get("/api/modelos-avion")
async def listar_modelos_avion(personal: EmpleadoOAdmin, sesion: SesionDep):
    modelos = await sesion.scalars(select(ModeloAvion).order_by(ModeloAvion.nombre))
    return [{"id": m.id, "nombre": m.nombre, "capacidad": m.capacidad} for m in modelos]


@router.post("/api/modelos-avion", status_code=status.HTTP_201_CREATED)
async def crear_modelo_avion(payload: ModeloAvionCreate, admin: Administrador, sesion: SesionDep):
    if await sesion.scalar(select(ModeloAvion.id).where(ModeloAvion.nombre == payload.nombre)) is not None:
        raise ConflictoDeNegocio("Ya existe un modelo de avión con ese nombre.")
    modelo = ModeloAvion(nombre=payload.nombre, capacidad=payload.capacidad)
    sesion.add(modelo)
    await sesion.commit()
    return {"id": modelo.id, "nombre": modelo.nombre, "capacidad": modelo.capacidad}


# --------------------------------------------------------------------------------------
# Productos y servicios de mostrador
# --------------------------------------------------------------------------------------


@router.get("/api/productos")
async def listar_productos(sesion: SesionDep):
    productos = await sesion.scalars(select(Producto).order_by(Producto.id.desc()))
    return [producto_a_dict(producto) for producto in productos]


@router.get("/api/productos/{producto_id}")
async def obtener_producto(producto_id: int, sesion: SesionDep):
    producto = await sesion.get(Producto, producto_id)
    if producto is None:
        raise RecursoNoEncontrado("un producto", producto_id)
    return producto_a_dict(producto)


@router.post("/api/productos", status_code=status.HTTP_201_CREATED)
async def crear_producto(payload: ProductoCreate, admin: Administrador, sesion: SesionDep):
    producto = Producto(nombre=payload.nombre, descripcion=payload.descripcion, precio=payload.precio, activo=payload.activo)
    sesion.add(producto)
    await sesion.commit()
    await sesion.refresh(producto)
    return {"id": producto.id, "mensaje": "Producto creado."}


@router.put("/api/productos/{producto_id}")
async def actualizar_producto(producto_id: int, payload: ProductoCreate, admin: Administrador, sesion: SesionDep):
    producto = await sesion.get(Producto, producto_id)
    if producto is None:
        raise RecursoNoEncontrado("un producto", producto_id)
    producto.nombre = payload.nombre
    producto.descripcion = payload.descripcion
    producto.precio = payload.precio
    producto.activo = payload.activo
    await sesion.commit()
    return {"mensaje": "Producto actualizado."}


@router.delete("/api/productos/{producto_id}")
async def eliminar_producto(producto_id: int, admin: Administrador, sesion: SesionDep):
    producto = await sesion.get(Producto, producto_id)
    if producto is None:
        raise RecursoNoEncontrado("un producto", producto_id)
    await sesion.delete(producto)
    await sesion.commit()
    return {"mensaje": "Producto eliminado."}


@router.get("/api/servicios")
async def listar_servicios(sesion: SesionDep):
    servicios = await sesion.scalars(select(Servicio).order_by(Servicio.id.desc()))
    return [servicio_a_dict(servicio) for servicio in servicios]


@router.get("/api/servicios/{servicio_id}")
async def obtener_servicio(servicio_id: int, sesion: SesionDep):
    servicio = await sesion.get(Servicio, servicio_id)
    if servicio is None:
        raise RecursoNoEncontrado("un servicio", servicio_id)
    return servicio_a_dict(servicio)


@router.post("/api/servicios", status_code=status.HTTP_201_CREATED)
async def crear_servicio(payload: ServicioCreate, admin: Administrador, sesion: SesionDep):
    servicio = Servicio(nombre=payload.nombre, descripcion=payload.descripcion, precio=payload.precio, activo=payload.activo)
    sesion.add(servicio)
    await sesion.commit()
    await sesion.refresh(servicio)
    return {"id": servicio.id, "mensaje": "Servicio creado."}


@router.put("/api/servicios/{servicio_id}")
async def actualizar_servicio(servicio_id: int, payload: ServicioCreate, admin: Administrador, sesion: SesionDep):
    servicio = await sesion.get(Servicio, servicio_id)
    if servicio is None:
        raise RecursoNoEncontrado("un servicio", servicio_id)
    servicio.nombre = payload.nombre
    servicio.descripcion = payload.descripcion
    servicio.precio = payload.precio
    servicio.activo = payload.activo
    await sesion.commit()
    return {"mensaje": "Servicio actualizado."}


@router.delete("/api/servicios/{servicio_id}")
async def eliminar_servicio(servicio_id: int, admin: Administrador, sesion: SesionDep):
    servicio = await sesion.get(Servicio, servicio_id)
    if servicio is None:
        raise RecursoNoEncontrado("un servicio", servicio_id)
    await sesion.delete(servicio)
    await sesion.commit()
    return {"mensaje": "Servicio eliminado."}
