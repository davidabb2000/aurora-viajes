"""Avisos por correo que salen después de responder, cuando el cambio ya quedó guardado."""

import logging

from app.core.base_datos import FabricaDeSesiones
from app.models.dominio import Reserva
from app.services.correos import Adjunto, enviar_correo_pago_confirmado
from app.services.facturas import cargar_factura, pdf_de_factura
from app.services.reservas import venta_de_reserva
from app.services.serializadores import reserva_a_dict

logger = logging.getLogger("aurora-viajes.correos")


async def notificar_pago_confirmado(reserva_id: int) -> None:
    """Envía al cliente la confirmación del pago con todo el detalle de la reserva y la factura en PDF.

    Corre como tarea en segundo plano: abre su propia sesión (la de la petición ya se cerró) y lee lo que quedó
    guardado. Nunca lanza: el pago ya está registrado y un correo que no sale no debe romper nada.
    """
    try:
        async with FabricaDeSesiones() as sesion:
            reserva = await sesion.get(Reserva, reserva_id)
            if reserva is None or reserva.usuario is None or reserva.estado_pago_rel.codigo != "pagado":
                return
            if reserva.estado_rel.codigo == "cancelada":
                # «Reserva confirmada» sería falso: ese pago se resuelve con un reembolso manual.
                logger.warning("No se envía confirmación del pago de la reserva cancelada %s.", reserva_id)
                return
            detalle = reserva_a_dict(reserva)
            venta = await venta_de_reserva(sesion, reserva_id)
            cobro = {
                "lineas": [
                    {"nombre": linea.nombre, "cantidad": linea.cantidad, "precioUnitario": float(linea.precio_unitario or 0), "subtotal": float(linea.subtotal or 0)}
                    for linea in (venta.detalles if venta else [])
                ],
                "subtotal": float(venta.subtotal if venta else reserva.monto_total or 0),
                "descuento": float(venta.descuento if venta else 0),
                "impuestos": float(venta.impuestos if venta else 0),
                "total": float(venta.total if venta else reserva.monto_total or 0),
                "factura": venta.factura.numero if venta and venta.factura else None,
            }
            if not cobro["lineas"]:
                cobro["lineas"] = [{"nombre": f"Reserva #{reserva.id}", "cantidad": 1, "precioUnitario": cobro["total"], "subtotal": cobro["total"]}]
            adjuntos = []
            if venta is not None and venta.factura is not None:
                try:
                    factura = await cargar_factura(sesion, venta.factura.id)
                    adjuntos.append(Adjunto(f"{factura.numero}.pdf", pdf_de_factura(factura)))
                except Exception:  # noqa: BLE001 - sin PDF el correo sale igual, con todo el detalle en el cuerpo
                    logger.exception("No se pudo generar el PDF de la factura de la reserva %s para el correo.", reserva_id)
            destinatario = reserva.usuario.correo
            nombre = f"{reserva.usuario.nombre} {reserva.usuario.apellido}"
        await enviar_correo_pago_confirmado(destinatario, nombre, detalle, cobro, adjuntos)
    except Exception:  # noqa: BLE001 - ver la docstring
        logger.exception("No se pudo preparar el correo de confirmación del pago de la reserva %s.", reserva_id)
