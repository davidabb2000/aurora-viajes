"""Datos de los pasajeros de una reserva y manifiesto de cada vuelo."""
from fastapi import APIRouter

from app.dependencias import EmpleadoOAdmin, ReservaDeRuta, SesionDep, UsuarioActual, es_personal, exigir_acceso_a_reserva
from app.errores import RecursoNoEncontrado
from app.models.dominio import Vuelo
from app.schemas.pasajeros import DatosDePasajeros
from app.services.pasajeros import guardar_datos_de_pasajeros, manifiesto_de_vuelo
from app.services.serializadores import pasajero_a_dict

router = APIRouter(tags=["pasajeros"])


@router.get("/api/reservas/{reserva_id}/pasajeros")
async def datos_de_pasajeros(reserva: ReservaDeRuta, usuario: UsuarioActual):
    exigir_acceso_a_reserva(usuario, reserva)
    return {"plazas": reserva.pasajeros, "pasajeros": [pasajero_a_dict(p) for p in reserva.datos_pasajeros]}


@router.put("/api/reservas/{reserva_id}/pasajeros")
async def registrar_pasajeros(reserva: ReservaDeRuta, datos: DatosDePasajeros, usuario: UsuarioActual, sesion: SesionDep):
    """El cliente (o el personal) deja los datos de quienes viajan. Reemplaza la lista anterior."""
    exigir_acceso_a_reserva(usuario, reserva)
    guardados = await guardar_datos_de_pasajeros(sesion, reserva, datos, es_personal(usuario))
    return {"plazas": reserva.pasajeros, "pasajeros": [pasajero_a_dict(p) for p in guardados]}


@router.get("/api/vuelos/{vuelo_id}/manifiesto")
async def manifiesto(vuelo_id: int, personal: EmpleadoOAdmin, sesion: SesionDep):
    vuelo = await sesion.get(Vuelo, vuelo_id)
    if vuelo is None:
        raise RecursoNoEncontrado("un vuelo", vuelo_id)
    return await manifiesto_de_vuelo(sesion, vuelo)
