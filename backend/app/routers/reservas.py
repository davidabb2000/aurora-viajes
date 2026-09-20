"""Reservas de viaje: alta, consulta, edición, cambio de estado y eliminación."""

from fastapi import APIRouter, BackgroundTasks, status
from sqlalchemy import select

from app.dependencias import EmpleadoOAdmin, ReservaDeRuta, SesionDep, UsuarioActual, exigir_acceso_a_reserva
from app.errores import ConflictoDeNegocio
from app.models.dominio import Reserva
from app.schemas.reservas import EstadoDeReserva, ReservaCreate, ReservaUpdate
from app.services.correos import enviar_correo_reserva
from app.services.pagos import expirar_sesion
from app.services.reservas import (
    actualizar_reserva_existente,
    anular_venta_de_reserva,
    cambiar_estado_reserva,
    opciones_carga_reserva,
    registrar_reserva,
)
from app.services.serializadores import reserva_a_dict

router = APIRouter(tags=["reservas"])


@router.post("/api/reservas", status_code=status.HTTP_201_CREATED)
async def crear_reserva(payload: ReservaCreate, usuario: UsuarioActual, sesion: SesionDep, tareas: BackgroundTasks):
    reserva, plan = await registrar_reserva(sesion, usuario, payload)
    reserva_dict = {
        "destino": plan.destino.nombre,
        "fechaSalida": payload.fechaSalida.isoformat(),
        "fechaRegreso": payload.fechaRegreso.isoformat(),
        "pasajeros": payload.pasajeros,
        "montoTotal": float(reserva.monto_total or 0),
        "estado": "pendiente",
        "hotel": plan.hotel.nombre if plan.hotel else None,
        "excursiones": [excursion.nombre for excursion in plan.excursiones],
    }
    # El correo no debe hacer esperar al cliente ni tumbar la reserva si SMTP falla.
    tareas.add_task(enviar_correo_reserva, usuario.correo, f"{usuario.nombre} {usuario.apellido}", reserva_dict)
    return {
        "id": reserva.id,
        "mensaje": "Solicitud registrada. Recibirás la confirmación en tu correo.",
        "montoTotal": float(plan.desglose.total),
        "desglose": {
            "vuelo": float(plan.desglose.vuelo),
            "hotel": float(plan.desglose.hotel),
            "excursiones": float(plan.desglose.excursiones),
        },
    }


@router.get("/api/reservas")
async def listar_reservas(personal: EmpleadoOAdmin, sesion: SesionDep):
    reservas = await sesion.scalars(select(Reserva).options(*opciones_carga_reserva()).order_by(Reserva.id.desc()))
    return [reserva_a_dict(reserva) for reserva in reservas]


@router.get("/api/reservas/mias")
async def mis_reservas(usuario: UsuarioActual, sesion: SesionDep):
    reservas = await sesion.scalars(
        select(Reserva).where(Reserva.usuario_id == usuario.id).options(*opciones_carga_reserva()).order_by(Reserva.id.desc())
    )
    return [reserva_a_dict(reserva) for reserva in reservas]


@router.get("/api/reservas/{reserva_id}")
async def obtener_reserva(reserva: ReservaDeRuta, usuario: UsuarioActual):
    exigir_acceso_a_reserva(usuario, reserva)
    return reserva_a_dict(reserva)


@router.put("/api/reservas/{reserva_id}")
async def actualizar_reserva(reserva: ReservaDeRuta, payload: ReservaUpdate, personal: EmpleadoOAdmin, sesion: SesionDep):
    _, sesion_obsoleta = await actualizar_reserva_existente(sesion, reserva, payload)
    await expirar_sesion(sesion_obsoleta)
    return {"mensaje": "Solicitud actualizada correctamente."}


@router.patch("/api/reservas/{reserva_id}/estado")
async def actualizar_estado_reserva(reserva: ReservaDeRuta, payload: EstadoDeReserva, personal: EmpleadoOAdmin, sesion: SesionDep):
    codigo = payload.estado.strip()
    await cambiar_estado_reserva(sesion, reserva, codigo)
    await sesion.commit()
    if codigo == "cancelada" and reserva.estado_pago_rel.codigo != "pagado":
        await expirar_sesion(reserva.stripe_session_id)
    return {"mensaje": "Estado actualizado."}


@router.delete("/api/reservas/{reserva_id}")
async def eliminar_reserva(reserva: ReservaDeRuta, usuario: UsuarioActual, sesion: SesionDep):
    exigir_acceso_a_reserva(usuario, reserva)
    if reserva.estado_pago_rel.codigo == "pagado":
        # Borrarla haría desaparecer un cobro real sin dejar rastro ni reembolso.
        raise ConflictoDeNegocio("Una reserva pagada no se puede eliminar. Cancélala cambiando su estado.")
    sesion_de_pago = reserva.stripe_session_id
    await anular_venta_de_reserva(sesion, reserva)
    await sesion.delete(reserva)
    await sesion.commit()
    await expirar_sesion(sesion_de_pago)
    return {"mensaje": "Reserva eliminada."}
