"""Conversión de modelos a los diccionarios JSON que consume el frontend."""
from app.models.dominio import Excursion, Hotel, Paquete, Producto, Reserva, Servicio, User, Vuelo


def usuario_a_dict(usuario: User) -> dict:
    return {
        "id": usuario.id,
        "nombre": usuario.nombre,
        "apellido": usuario.apellido,
        "tipoDocumento": usuario.tipo_documento_catalogo.codigo if usuario.tipo_documento_catalogo else "CC",
        "numeroDocumento": usuario.numero_documento,
        "direccion": usuario.direccion,
        "telefono": usuario.telefono,
        "correo": usuario.correo,
        "rol": usuario.role.nombre if usuario.role else "cliente",
        "activo": usuario.activo,
    }


def usuario_sesion_a_dict(usuario: User) -> dict:
    return {
        "id": usuario.id,
        "nombre": usuario.nombre,
        "apellido": usuario.apellido,
        "correo": usuario.correo,
        "rol": usuario.role.nombre if usuario.role else "cliente",
        "activo": usuario.activo,
    }


def producto_a_dict(producto: Producto) -> dict:
    return {
        "id": producto.id,
        "nombre": producto.nombre,
        "descripcion": producto.descripcion,
        "precio": float(producto.precio or 0),
        "activo": producto.activo,
    }


def servicio_a_dict(servicio: Servicio) -> dict:
    return {
        "id": servicio.id,
        "nombre": servicio.nombre,
        "descripcion": servicio.descripcion,
        "precio": float(servicio.precio or 0),
        "activo": servicio.activo,
    }


def vuelo_a_dict(vuelo: Vuelo) -> dict:
    return {
        "id": vuelo.id,
        "numeroVuelo": vuelo.numero_vuelo,
        "aerolinea": vuelo.aerolinea,
        "avion": vuelo.avion,
        "origen": vuelo.origen,
        "destino": vuelo.destino,
        "fechaSalida": vuelo.fecha_salida.isoformat(),
        "fechaLlegada": vuelo.fecha_llegada.isoformat(),
        "capacidadMaxima": vuelo.capacidad_maxima,
        "puerta": vuelo.puerta,
        "terminal": vuelo.terminal,
        "estado": vuelo.estado,
        "activo": vuelo.activo,
    }


def hotel_a_dict(hotel: Hotel) -> dict:
    return {
        "id": hotel.id,
        "nombre": hotel.nombre,
        "ciudad": hotel.ciudad,
        "pais": hotel.pais,
        "estrellas": hotel.estrellas,
        "precioNoche": float(hotel.precio_noche or 0),
        "descripcion": hotel.descripcion,
        "activo": hotel.activo,
    }


def excursion_a_dict(excursion: Excursion) -> dict:
    return {
        "id": excursion.id,
        "nombre": excursion.nombre,
        "ciudad": excursion.ciudad,
        "pais": excursion.pais,
        "duracionHoras": excursion.duracion_horas,
        "precio": float(excursion.precio or 0),
        "descripcion": excursion.descripcion,
        "activo": excursion.activo,
    }


def paquete_a_dict(paquete: Paquete) -> dict:
    return {
        "id": paquete.id,
        "nombre": paquete.nombre,
        "destinoId": paquete.destino_id,
        "destino": paquete.destino_rel.nombre if paquete.destino_rel else "",
        "vueloId": paquete.vuelo_id,
        "vuelo": vuelo_a_dict(paquete.vuelo_rel),
        "hotelId": paquete.hotel_id,
        "hotel": hotel_a_dict(paquete.hotel_rel),
        "excursiones": [excursion_a_dict(excursion) for excursion in paquete.excursiones],
        "fechaSalida": paquete.fecha_salida.isoformat(),
        "fechaRegreso": paquete.fecha_regreso.isoformat(),
        "precioBase": float(paquete.precio_base or 0),
        "activo": paquete.activo,
    }


def reserva_a_dict(reserva: Reserva) -> dict:
    return {
        "id": reserva.id,
        "cliente": f"{reserva.usuario.nombre} {reserva.usuario.apellido}" if reserva.usuario else "",
        "destinoId": reserva.destino_id,
        "destino": reserva.destino_rel.nombre if reserva.destino_rel else "",
        "pais": reserva.destino_rel.pais.nombre if reserva.destino_rel and reserva.destino_rel.pais else "",
        "origen": reserva.vuelo_rel.origen if reserva.vuelo_rel else "",
        "vueloId": reserva.vuelo_id,
        "vuelo": vuelo_a_dict(reserva.vuelo_rel) if reserva.vuelo_rel else None,
        "paqueteId": reserva.paquete_id,
        "paquete": paquete_a_dict(reserva.paquete_rel) if reserva.paquete_rel else None,
        "hotelId": reserva.hotel_id,
        "hotel": {
            "id": reserva.hotel_rel.id,
            "nombre": reserva.hotel_rel.nombre,
            "ciudad": reserva.hotel_rel.ciudad,
            "estrellas": reserva.hotel_rel.estrellas,
            "precioNoche": float(reserva.hotel_rel.precio_noche or 0),
        } if reserva.hotel_rel else None,
        "excursiones": [
            {
                "id": excursion.id,
                "nombre": excursion.nombre,
                "duracionHoras": excursion.duracion_horas,
                "precio": float(excursion.precio or 0),
            }
            for excursion in (reserva.excursiones or [])
        ],
        "fechaSalida": reserva.fecha_salida.isoformat(),
        "fechaRegreso": reserva.fecha_regreso.isoformat(),
        "pasajeros": reserva.pasajeros,
        "telefonoContacto": reserva.telefono_contacto,
        "notas": reserva.notas,
        "estado": reserva.estado_rel.codigo if reserva.estado_rel else "pendiente",
        "estadoPago": reserva.estado_pago_rel.codigo if reserva.estado_pago_rel else "pendiente",
        "metodoPago": reserva.metodo_pago_rel.codigo if reserva.metodo_pago_rel else None,
        "montoTotal": float(reserva.monto_total or 0),
        "desglose": {
            "vuelo": float(reserva.monto_vuelo or 0),
            "hotel": float(reserva.monto_hotel or 0),
            "excursiones": float(reserva.monto_excursiones or 0),
        },
        "stripeSessionId": reserva.stripe_session_id,
    }
