"""Reservas de viaje: cotización, alta, consulta, edición, cancelación y eliminación."""

from fastapi import APIRouter, BackgroundTasks, Query, Request, status
from sqlalchemy import or_, select

from app.core.limitador import limitador, limitar
from app.dependencias import EmpleadoOAdmin, ReservaDeRuta, SesionDep, UsuarioActual, es_personal, exigir_acceso_a_reserva
from app.errores import ConflictoDeNegocio, ErrorDeDominio, PermisoDenegado, RecursoNoEncontrado
from app.models.dominio import EstadoPago, EstadoReserva, Reserva, User
from app.schemas.reservas import EstadoDeReserva, ReservaCreate, ReservaUpdate, SolicitudDeCotizacion
from app.services.catalogos import escapar_like
from app.services.correos import enviar_correo_reserva
from app.services.disponibilidad import plazas_libres
from app.services.pagos import expirar_sesion
from app.services.reservas import (
    actualizar_reserva_existente,
    anular_venta_de_reserva,
    cambiar_estado_reserva,
    preparar_reserva,
    registrar_reserva,
    resumen_para_correo,
)
from app.services.serializadores import cotizacion_a_dict, reserva_a_dict

router = APIRouter(tags=["reservas"])


@router.post("/api/reservas/cotizar")
async def cotizar_reserva(payload: SolicitudDeCotizacion, peticion: Request, usuario: UsuarioActual, sesion: SesionDep):
    """Precio exacto y disponibilidad de un viaje, sin guardar nada.

    Usa el mismo cálculo que la reserva real, de modo que el frontend no repite la
    fórmula de precios (y nunca puede mostrar un total distinto del que se cobra).
    Al editar, `reservaId` hace que se apliquen las reglas de la edición.
    """
    await limitar(peticion, "cotizar", maximo=180, ventana_segundos=600)
    reserva_actual = None
    if payload.reservaId is not None:
        reserva_actual = await sesion.get(Reserva, payload.reservaId)
        if reserva_actual is None:
            raise RecursoNoEncontrado("una reserva", payload.reservaId)
        exigir_acceso_a_reserva(usuario, reserva_actual)
    plan = await preparar_reserva(sesion, payload, reserva_actual=reserva_actual, bloquear=False)
    plazas = await plazas_libres(sesion, [plan.ida] + ([plan.regreso] if plan.regreso else []))
    return cotizacion_a_dict(plan, plazas)


@router.post("/api/reservas", status_code=status.HTTP_201_CREATED)
async def crear_reserva(payload: ReservaCreate, usuario: UsuarioActual, sesion: SesionDep, tareas: BackgroundTasks):
    await limitador.registrar(f"reservas-usuario:{usuario.id}", maximo=30, ventana_segundos=3600)
    personal = usuario if es_personal(usuario) else None
    cliente = usuario
    if payload.clienteId is not None and payload.clienteId != usuario.id:
        if personal is None:
            raise PermisoDenegado("Solo el personal puede reservar a nombre de otro cliente.")
        cliente = await sesion.get(User, payload.clienteId)
        if cliente is None or not cliente.activo or cliente.role.nombre != "cliente":
            raise ErrorDeDominio("El cliente seleccionado no existe o no está activo.")
    if payload.pago is not None and personal is None:
        raise PermisoDenegado("Solo el personal puede registrar un cobro en el mostrador.")

    reserva, plan = await registrar_reserva(sesion, cliente, payload, personal)
    # El correo no debe hacer esperar al cliente ni tumbar la reserva si SMTP falla.
    tareas.add_task(enviar_correo_reserva, cliente.correo, f"{cliente.nombre} {cliente.apellido}", resumen_para_correo(reserva, plan))
    return {
        "id": reserva.id,
        "mensaje": "Reserva registrada." if payload.pago else "Solicitud registrada. Recibirás la confirmación en tu correo.",
        "estado": reserva.estado_rel.codigo,
        "estadoPago": reserva.estado_pago_rel.codigo,
        "montoTotal": float(plan.total),
        "desglose": {
            "vuelo": float(plan.desglose.vuelo),
            "hotel": float(plan.desglose.hotel),
            "excursiones": float(plan.desglose.excursiones),
        },
    }


@router.get("/api/reservas")
async def listar_reservas(
    personal: EmpleadoOAdmin,
    sesion: SesionDep,
    q: str | None = Query(default=None, max_length=80, description="Cliente (nombre, correo, documento) o número de reserva"),
    estado: str | None = Query(default=None, pattern="^(pendiente|confirmada|cancelada)$"),
    pago: str | None = Query(default=None, pattern="^(pendiente|pagado|fallido)$"),
    limite: int = Query(default=300, ge=1, le=500),
    desplazamiento: int = Query(default=0, ge=0),
):
    consulta = select(Reserva)
    if estado:
        consulta = consulta.where(Reserva.estado_id == select(EstadoReserva.id).where(EstadoReserva.codigo == estado).scalar_subquery())
    if pago:
        consulta = consulta.where(Reserva.estado_pago_id == select(EstadoPago.id).where(EstadoPago.codigo == pago).scalar_subquery())
    if q and q.strip():
        patron = f"%{escapar_like(q.strip().lower())}%"
        condiciones = [
            User.nombre.ilike(patron, escape="\\"),
            User.apellido.ilike(patron, escape="\\"),
            User.correo.ilike(patron, escape="\\"),
            User.numero_documento.like(patron, escape="\\"),
            (User.nombre + " " + User.apellido).ilike(patron, escape="\\"),
        ]
        if q.strip().lstrip("#").isdigit():
            condiciones.append(Reserva.id == int(q.strip().lstrip("#")))
        consulta = consulta.join(User, User.id == Reserva.usuario_id).where(or_(*condiciones))
    reservas = await sesion.scalars(consulta.order_by(Reserva.id.desc()).limit(limite).offset(desplazamiento))
    return [reserva_a_dict(reserva) for reserva in reservas.unique()]


@router.get("/api/reservas/mias")
async def mis_reservas(usuario: UsuarioActual, sesion: SesionDep):
    reservas = await sesion.scalars(select(Reserva).where(Reserva.usuario_id == usuario.id).order_by(Reserva.id.desc()))
    return [reserva_a_dict(reserva) for reserva in reservas.unique()]


@router.get("/api/reservas/{reserva_id}")
async def obtener_reserva(reserva: ReservaDeRuta, usuario: UsuarioActual):
    exigir_acceso_a_reserva(usuario, reserva)
    return reserva_a_dict(reserva)


@router.put("/api/reservas/{reserva_id}")
async def actualizar_reserva(reserva: ReservaDeRuta, payload: ReservaUpdate, personal: EmpleadoOAdmin, sesion: SesionDep):
    _, sesion_obsoleta = await actualizar_reserva_existente(sesion, reserva, payload)
    await expirar_sesion(sesion_obsoleta)
    return {"mensaje": "Reserva actualizada correctamente."}


@router.patch("/api/reservas/{reserva_id}/estado")
async def actualizar_estado_reserva(reserva: ReservaDeRuta, payload: EstadoDeReserva, personal: EmpleadoOAdmin, sesion: SesionDep):
    await cambiar_estado_reserva(sesion, reserva, payload.estado)
    await sesion.commit()
    return await _respuesta_de_cancelacion(reserva, payload.estado)


@router.post("/api/reservas/{reserva_id}/cancelar")
async def cancelar_reserva(reserva: ReservaDeRuta, usuario: UsuarioActual, sesion: SesionDep):
    """El cliente cancela su solicitud sin pagar; el personal puede cancelar también las pagadas."""
    exigir_acceso_a_reserva(usuario, reserva)
    if reserva.estado_rel.codigo == "cancelada":
        return {"mensaje": "La reserva ya estaba cancelada."}
    if reserva.estado_pago_rel.codigo == "pagado" and not es_personal(usuario):
        raise ConflictoDeNegocio(
            "Una reserva pagada solo la puede cancelar el personal de Aurora. Escríbenos desde la página de contacto."
        )
    await cambiar_estado_reserva(sesion, reserva, "cancelada")
    await sesion.commit()
    return await _respuesta_de_cancelacion(reserva, "cancelada")


async def _respuesta_de_cancelacion(reserva: Reserva, estado: str) -> dict:
    respuesta = {"mensaje": "Estado actualizado."}
    if estado == "cancelada":
        if reserva.estado_pago_rel.codigo == "pagado":
            # El dinero ya entró: cancelar no lo devuelve, eso se hace en el panel de Stripe o en caja.
            respuesta.update(mensaje="Reserva cancelada. Estaba pagada: el reembolso hay que hacerlo aparte.", requiereReembolso=True)
        else:
            await expirar_sesion(reserva.stripe_session_id)
            respuesta["mensaje"] = "Reserva cancelada."
    return respuesta


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
