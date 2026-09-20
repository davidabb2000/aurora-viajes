"""Destinos, productos y servicios."""
from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencias import Administrador, SesionDep
from app.errores import RecursoNoEncontrado
from app.models.dominio import Destino, Excursion, Hotel, Producto, Servicio, Vuelo
from app.schemas.catalogo import ProductoCreate, ServicioCreate
from app.services.catalogos import ciudad_del_destino, normalizar_texto
from app.services.serializadores import excursion_a_dict, hotel_a_dict, producto_a_dict, servicio_a_dict, vuelo_a_dict

router = APIRouter(tags=["catalogo"])


@router.get("/api/catalogos/destinos")
async def catalogo_destinos(sesion: SesionDep):
    destinos = await sesion.scalars(
        select(Destino)
        .options(selectinload(Destino.pais))
        .where(Destino.activo.is_(True))
        .where(Destino.precio_base > 0)
        .order_by(Destino.nombre.asc())
    )
    return [
        {
            "id": destino.id,
            "nombre": destino.nombre,
            "pais": destino.pais.nombre if destino.pais else "",
            "descripcion": destino.descripcion,
            "precioBase": float(destino.precio_base or 0),
            "imagenSlug": destino.imagen_slug,
        }
        for destino in destinos
    ]


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


@router.get("/api/catalogos/destinos/{destino_id}/opciones")
async def opciones_de_destino(destino_id: int, sesion: SesionDep):
    """Todo lo reservable para un destino, en una sola llamada.

    El asistente de reserva necesita vuelos, hoteles y excursiones del destino
    elegido. Antes el cliente tenia que pedir los tres catalogos completos y
    filtrarlos a mano, sin forma fiable de saber cuales correspondian al viaje.
    """
    destino = await sesion.get(Destino, destino_id, options=[selectinload(Destino.pais)])
    if destino is None or not destino.activo:
        raise RecursoNoEncontrado("un destino", destino_id)

    ciudad = ciudad_del_destino(destino)
    pais = normalizar_texto(destino.pais.nombre) if destino.pais else ""

    vuelos = (await sesion.scalars(
        select(Vuelo).where(Vuelo.activo.is_(True)).order_by(Vuelo.fecha_salida.asc())
    )).all()
    vuelos_destino = [v for v in vuelos if normalizar_texto(v.destino) == ciudad]

    hoteles = (await sesion.scalars(
        select(Hotel).where(Hotel.activo.is_(True)).order_by(Hotel.estrellas.desc(), Hotel.nombre.asc())
    )).all()
    excursiones = (await sesion.scalars(
        select(Excursion).where(Excursion.activo.is_(True)).order_by(Excursion.nombre.asc())
    )).all()

    return {
        "destino": {
            "id": destino.id,
            "nombre": destino.nombre,
            "pais": destino.pais.nombre if destino.pais else "",
            "precioBase": float(destino.precio_base or 0),
            "imagenSlug": destino.imagen_slug,
            "descripcion": destino.descripcion,
        },
        "vuelos": [vuelo_a_dict(v) for v in vuelos_destino],
        "hoteles": [hotel_a_dict(h) for h in hoteles if normalizar_texto(h.ciudad) == ciudad and (not pais or normalizar_texto(h.pais) == pais)],
        "excursiones": [excursion_a_dict(e) for e in excursiones if normalizar_texto(e.ciudad) == ciudad and (not pais or normalizar_texto(e.pais) == pais)],
    }
