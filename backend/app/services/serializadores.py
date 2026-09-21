"""Conversión de modelos a los diccionarios JSON que consume el frontend."""
from app.models.dominio import Ciudad, Destino, Excursion, Hotel, Paquete, Producto, Reserva, Servicio, User, Vuelo


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
        "debeCambiarContrasena": usuario.debe_cambiar_contrasena,
        "creadoEn": usuario.creado_en.isoformat() if usuario.creado_en else None,
    }


def usuario_sesion_a_dict(usuario: User) -> dict:
    return {
        "id": usuario.id,
        "nombre": usuario.nombre,
        "apellido": usuario.apellido,
        "correo": usuario.correo,
        "rol": usuario.role.nombre if usuario.role else "cliente",
        "activo": usuario.activo,
        "debeCambiarContrasena": usuario.debe_cambiar_contrasena,
    }


def cliente_resumido_a_dict(usuario: User) -> dict:
    """Lo mínimo para elegir un cliente en el mostrador."""
    return {
        "id": usuario.id,
        "nombre": usuario.nombre,
        "apellido": usuario.apellido,
        "correo": usuario.correo,
        "telefono": usuario.telefono,
        "tipoDocumento": usuario.tipo_documento_catalogo.codigo if usuario.tipo_documento_catalogo else "CC",
        "numeroDocumento": usuario.numero_documento,
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


def ciudad_a_dict(ciudad: Ciudad) -> dict:
    return {"id": ciudad.id, "nombre": ciudad.nombre, "pais": ciudad.pais.nombre, "paisId": ciudad.pais_id}


def destino_a_dict(destino: Destino) -> dict:
    return {
        "id": destino.id,
        "nombre": destino.nombre,
        "ciudadId": destino.ciudad_id,
        "ciudad": destino.ciudad.nombre,
        "pais": destino.pais.nombre,
        "descripcion": destino.descripcion,
        "precioBase": float(destino.precio_base or 0),
        "imagenSlug": destino.imagen_slug,
        "activo": destino.activo,
    }


def vuelo_a_dict(vuelo: Vuelo, plazas_libres: int | None = None) -> dict:
    datos = {
        "id": vuelo.id,
        "numeroVuelo": vuelo.numero_vuelo,
        "aerolineaId": vuelo.aerolinea_id,
        "aerolinea": vuelo.aerolinea,
        "modeloAvionId": vuelo.modelo_avion_id,
        "avion": vuelo.avion,
        "capacidadAvion": vuelo.modelo_avion_rel.capacidad,
        "origenId": vuelo.origen_id,
        "origen": vuelo.origen,
        "origenPais": vuelo.origen_rel.pais.nombre,
        "destinoId": vuelo.destino_id,
        "destino": vuelo.destino,
        "destinoPais": vuelo.destino_rel.pais.nombre,
        "fechaSalida": vuelo.fecha_salida.isoformat(),
        "fechaLlegada": vuelo.fecha_llegada.isoformat(),
        "capacidadMaxima": vuelo.capacidad_maxima,
        "puerta": vuelo.puerta,
        "terminal": vuelo.terminal,
        "estado": vuelo.estado,
        "activo": vuelo.activo,
    }
    if plazas_libres is not None:
        datos["plazasLibres"] = plazas_libres
        datos["plazasOcupadas"] = max(vuelo.capacidad_maxima - plazas_libres, 0)
    return datos


def hotel_a_dict(hotel: Hotel) -> dict:
    return {
        "id": hotel.id,
        "nombre": hotel.nombre,
        "ciudadId": hotel.ciudad_id,
        "ciudad": hotel.ciudad.nombre,
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
        "ciudadId": excursion.ciudad_id,
        "ciudad": excursion.ciudad.nombre,
        "pais": excursion.pais,
        "duracionHoras": excursion.duracion_horas,
        "precio": float(excursion.precio or 0),
        "descripcion": excursion.descripcion,
        "activo": excursion.activo,
    }


def paquete_a_dict(paquete: Paquete, plazas: dict[int, int] | None = None) -> dict:
    """`plazas` es el mapa vuelo_id -> plazas libres, si se quiere mostrar la disponibilidad."""
    ida = vuelo_a_dict(paquete.vuelo_rel, plazas.get(paquete.vuelo_id) if plazas is not None else None)
    regreso = None
    if paquete.vuelo_regreso_rel is not None:
        regreso = vuelo_a_dict(paquete.vuelo_regreso_rel, plazas.get(paquete.vuelo_regreso_id) if plazas is not None else None)
    datos = {
        "id": paquete.id,
        "nombre": paquete.nombre,
        "destinoId": paquete.destino_id,
        "destino": paquete.destino_rel.nombre,
        "vueloId": paquete.vuelo_id,
        "vuelo": ida,
        "vueloRegresoId": paquete.vuelo_regreso_id,
        "vueloRegreso": regreso,
        "hotelId": paquete.hotel_id,
        "hotel": hotel_a_dict(paquete.hotel_rel),
        "excursiones": [excursion_a_dict(excursion) for excursion in sorted(paquete.excursiones, key=lambda e: e.id)],
        "noches": paquete.noches,
        "fechaSalida": paquete.fecha_salida.isoformat(),
        "fechaRegreso": paquete.fecha_regreso.isoformat(),
        "precioBase": float(paquete.precio_base or 0),
        "activo": paquete.activo,
    }
    if plazas is not None:
        libres = [ida["plazasLibres"]] + ([regreso["plazasLibres"]] if regreso else [])
        datos["plazasLibres"] = min(libres)
    return datos


def _nombre(usuario: User | None) -> str | None:
    return f"{usuario.nombre} {usuario.apellido}" if usuario is not None else None


def reserva_a_dict(reserva: Reserva) -> dict:
    ida, regreso = reserva.vuelo_rel, reserva.vuelo_regreso_rel
    return {
        "id": reserva.id,
        "cliente": _nombre(reserva.usuario) or "",
        "clienteId": reserva.usuario_id,
        "clienteCorreo": reserva.usuario.correo if reserva.usuario else None,
        "creadaPor": _nombre(reserva.creada_por),
        "destinoId": reserva.destino_id,
        "destino": reserva.destino_rel.nombre,
        "ciudad": reserva.destino_rel.ciudad.nombre,
        "pais": reserva.destino_rel.pais.nombre,
        "origen": ida.origen if ida else "",
        "vueloId": reserva.vuelo_id,
        "vuelo": vuelo_a_dict(ida) if ida else None,
        "vueloRegresoId": reserva.vuelo_regreso_id,
        "vueloRegreso": vuelo_a_dict(regreso) if regreso else None,
        "paqueteId": reserva.paquete_id,
        "paquete": (
            {"id": reserva.paquete_rel.id, "nombre": reserva.paquete_rel.nombre, "precioBase": float(reserva.paquete_rel.precio_base or 0)}
            if reserva.paquete_rel else None
        ),
        "hotelId": reserva.hotel_id,
        "hotel": {
            "id": reserva.hotel_rel.id,
            "nombre": reserva.hotel_rel.nombre,
            "ciudad": reserva.hotel_rel.ciudad.nombre,
            "pais": reserva.hotel_rel.pais,
            "estrellas": reserva.hotel_rel.estrellas,
            "precioNoche": float(reserva.hotel_rel.precio_noche or 0),
        } if reserva.hotel_rel else None,
        "excursiones": [
            {
                "id": linea.excursion.id,
                "nombre": linea.excursion.nombre,
                "ciudad": linea.excursion.ciudad.nombre,
                "pais": linea.excursion.pais,
                "duracionHoras": linea.excursion.duracion_horas,
                "cantidad": linea.cantidad,
                "precio": float(linea.precio_unitario or 0),
                "subtotal": round(float(linea.precio_unitario or 0) * linea.cantidad, 2),
            }
            for linea in reserva.lineas_excursion
        ],
        "fechaSalida": reserva.fecha_salida.isoformat(),
        "fechaRegreso": reserva.fecha_regreso.isoformat(),
        "noches": reserva.noches,
        "pasajeros": reserva.pasajeros,
        "telefonoContacto": reserva.telefono_contacto,
        "notas": reserva.notas,
        "estado": reserva.estado_rel.codigo,
        "estadoPago": reserva.estado_pago_rel.codigo,
        "metodoPago": reserva.metodo_pago_rel.codigo if reserva.metodo_pago_rel else None,
        "pagoReferencia": reserva.pago_referencia,
        "pagoRegistradoPor": _nombre(reserva.pago_registrado_por),
        "pagadoEn": reserva.pagado_en.isoformat() if reserva.pagado_en else None,
        "montoTotal": float(reserva.monto_total or 0),
        "desglose": {
            "vuelo": float(reserva.monto_vuelo or 0),
            "hotel": float(reserva.monto_hotel or 0),
            "excursiones": float(reserva.monto_excursiones or 0),
        },
        "creadoEn": reserva.creado_en.isoformat() if reserva.creado_en else None,
    }


def cotizacion_a_dict(plan, plazas: dict[int, int] | None = None) -> dict:
    """Respuesta de POST /reservas/cotizar: el desglose exacto que se cobraría."""
    lineas = [
        {
            "concepto": _concepto_de_linea(linea["nombre"]),
            "nombre": linea["nombre"],
            "cantidad": linea["cantidad"],
            "precioUnitario": float(linea["precio_unitario"]),
            "subtotal": float(linea["subtotal"]),
        }
        for linea in plan.lineas
    ]
    return {
        "destino": plan.destino.nombre,
        "paquete": plan.paquete.nombre if plan.paquete else None,
        "vuelo": vuelo_a_dict(plan.ida, plazas.get(plan.ida.id) if plazas else None),
        "vueloRegreso": vuelo_a_dict(plan.regreso, plazas.get(plan.regreso.id) if plazas else None) if plan.regreso else None,
        "hotel": hotel_a_dict(plan.hotel) if plan.hotel else None,
        "fechaSalida": plan.fecha_salida.isoformat(),
        "fechaRegreso": plan.fecha_regreso.isoformat(),
        "noches": plan.noches,
        "pasajeros": plan.pasajeros,
        "habitaciones": (plan.pasajeros + 1) // 2 if plan.hotel else 0,
        "lineas": lineas,
        "desglose": {
            "vuelo": float(plan.desglose.vuelo),
            "hotel": float(plan.desglose.hotel),
            "excursiones": float(plan.desglose.excursiones),
        },
        "total": float(plan.total),
        "moneda": "COP",
    }


def _concepto_de_linea(nombre: str) -> str:
    inicio = nombre.lower()
    if inicio.startswith("paquete"):
        return "paquete"
    if inicio.startswith("vuelo"):
        return "vuelo"
    if inicio.startswith("hotel"):
        return "hotel"
    return "excursion"
