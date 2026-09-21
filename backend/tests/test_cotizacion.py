"""Cotización y validaciones del viaje: el precio que se muestra es el que se cobra."""
from datetime import timedelta

from tests.conftest import cuerpo_de_reserva


def viaje_sin_contacto(viaje, modo="carta", pasajeros=2, **cambios):
    """El cuerpo de la cotización es el de la reserva sin teléfono ni notas."""
    cuerpo = cuerpo_de_reserva(viaje, modo, pasajeros, **cambios)
    cuerpo.pop("telefonoContacto")
    return cuerpo


def test_la_cotizacion_coincide_exactamente_con_lo_que_se_cobra(api, crear_cliente, viaje):
    cliente = crear_cliente()
    cotizacion = api.post("/api/reservas/cotizar", headers=cliente.headers, json=viaje_sin_contacto(viaje, "carta", 3))
    assert cotizacion.status_code == 200, cotizacion.text
    datos = cotizacion.json()

    reserva = api.post("/api/reservas", headers=cliente.headers, json=cuerpo_de_reserva(viaje, "carta", 3)).json()
    assert datos["total"] == reserva["montoTotal"]
    assert datos["desglose"] == reserva["desglose"]
    assert sum(linea["subtotal"] for linea in datos["lineas"]) == datos["total"]
    assert (datos["noches"], datos["habitaciones"]) == (6, 2)  # 3 pasajeros -> 2 habitaciones
    assert datos["fechaSalida"] == str(viaje.salida) and datos["fechaRegreso"] == str(viaje.regreso)


def test_cotizar_no_guarda_nada_ni_ocupa_plazas(api, crear_cliente, viaje):
    cliente = crear_cliente()
    for _ in range(3):
        assert api.post("/api/reservas/cotizar", headers=cliente.headers, json=viaje_sin_contacto(viaje, "carta", 9)).status_code == 200
    assert api.get("/api/reservas/mias", headers=cliente.headers).json() == []
    opciones = api.get(f"/api/catalogos/destinos/{viaje.destino['id']}/opciones").json()
    ida = next(v for v in opciones["vuelosIda"] if v["id"] == viaje.ida["id"])
    assert ida["plazasLibres"] == ida["capacidadMaxima"]


def test_cotizar_un_paquete_muestra_una_sola_linea_de_cobro(api, crear_cliente, viaje):
    cliente = crear_cliente()
    datos = api.post("/api/reservas/cotizar", headers=cliente.headers, json=viaje_sin_contacto(viaje, "paquete", 2)).json()
    assert datos["total"] == 2_000_000
    cobradas = [linea for linea in datos["lineas"] if linea["subtotal"] > 0]
    assert len(cobradas) == 1 and cobradas[0]["concepto"] == "paquete"
    assert datos["vueloRegreso"]["id"] == viaje.vuelta["id"]  # el paquete trae su regreso


def test_la_cotizacion_avisa_cuando_no_hay_plazas(api, crear_cliente, viaje):
    cliente = crear_cliente()
    for _ in range(20):
        api.post("/api/reservas", headers=cliente.headers, json=cuerpo_de_reserva(viaje, "carta", 9))
    cotizacion = api.post("/api/reservas/cotizar", headers=cliente.headers, json=viaje_sin_contacto(viaje, "carta", 1))
    assert cotizacion.status_code == 400
    assert "plaza" in cotizacion.json()["mensaje"]


def test_la_cotizacion_exige_sesion(api, viaje):
    assert api.post("/api/reservas/cotizar", json=viaje_sin_contacto(viaje)).status_code == 401


def test_excursion_solo_para_parte_de_los_pasajeros(api, crear_cliente, viaje):
    cliente = crear_cliente()
    excursion = viaje.excursiones[0]
    cuerpo = viaje_sin_contacto(viaje, "carta", 4, excursiones=[{"id": excursion["id"], "cantidad": 2}])
    datos = api.post("/api/reservas/cotizar", headers=cliente.headers, json=cuerpo).json()
    linea = next(l for l in datos["lineas"] if l["concepto"] == "excursion")
    assert (linea["cantidad"], linea["subtotal"]) == (2, excursion["precio"] * 2)

    # No puede haber más personas en una excursión que pasajeros en la reserva.
    demasiadas = viaje_sin_contacto(viaje, "carta", 2, excursiones=[{"id": excursion["id"], "cantidad": 3}])
    assert api.post("/api/reservas/cotizar", headers=cliente.headers, json=demasiadas).status_code == 422
    # Ni repetir la misma excursión.
    repetida = viaje_sin_contacto(viaje, "carta", 2, excursiones=[{"id": excursion["id"]}, {"id": excursion["id"]}])
    assert api.post("/api/reservas/cotizar", headers=cliente.headers, json=repetida).status_code == 422


def test_regreso_abierto_sin_vuelo_de_vuelta(api, crear_cliente, viaje):
    cliente = crear_cliente()
    regreso = viaje.salida + timedelta(days=10)
    cuerpo = viaje_sin_contacto(viaje, "carta", 2, fechaRegreso=str(regreso))
    cuerpo.pop("vueloRegresoId")
    datos = api.post("/api/reservas/cotizar", headers=cliente.headers, json=cuerpo).json()
    assert datos["vueloRegreso"] is None and datos["noches"] == 10 and datos["fechaRegreso"] == str(regreso)

    # El regreso no puede ser anterior a la salida.
    antes = {**cuerpo, "fechaRegreso": str(viaje.salida - timedelta(days=1))}
    assert api.post("/api/reservas/cotizar", headers=cliente.headers, json=antes).status_code == 400
    # Con hotel, el regreso debe ser al menos un día después de la salida.
    mismo_dia = {**cuerpo, "fechaRegreso": str(viaje.salida)}
    rechazado = api.post("/api/reservas/cotizar", headers=cliente.headers, json=mismo_dia)
    assert rechazado.status_code == 400 and "hotel" in rechazado.json()["mensaje"]
    # Una fecha y un vuelo de regreso a la vez es ambiguo; ninguno de los dos, incompleto.
    ambiguo = {**cuerpo, "vueloRegresoId": viaje.vuelta["id"]}
    assert api.post("/api/reservas/cotizar", headers=cliente.headers, json=ambiguo).status_code == 422
    incompleto = {k: v for k, v in cuerpo.items() if k != "fechaRegreso"}
    assert api.post("/api/reservas/cotizar", headers=cliente.headers, json=incompleto).status_code == 422


def test_un_paquete_no_admite_piezas_sueltas(api, crear_cliente, viaje):
    cliente = crear_cliente()
    mezcla = viaje_sin_contacto(viaje, "paquete", 2, hotelId=viaje.hotel["id"])
    assert api.post("/api/reservas/cotizar", headers=cliente.headers, json=mezcla).status_code == 422
    otro_destino = viaje_sin_contacto(viaje, "paquete", 2, destinoId=viaje.destino["id"] + 1)
    rechazado = api.post("/api/reservas/cotizar", headers=cliente.headers, json=otro_destino)
    assert rechazado.status_code == 400


def test_los_vuelos_deben_llevar_al_destino_y_volver_al_origen(api, crear_cliente, viaje, catalogo):
    cliente = crear_cliente()
    # Un vuelo de París elegido para viajar a Kioto.
    a_otro_destino = viaje_sin_contacto(viaje, "carta", 2, destinoId=catalogo.destino_kioto["id"], hotelId=None, excursiones=[])
    rechazado = api.post("/api/reservas/cotizar", headers=cliente.headers, json=a_otro_destino)
    assert rechazado.status_code == 400 and "no llega" in rechazado.json()["mensaje"]
    # El vuelo de ida usado como regreso: sale del sitio equivocado.
    cruzado = viaje_sin_contacto(viaje, "carta", 2, vueloRegresoId=viaje.ida["id"])
    assert api.post("/api/reservas/cotizar", headers=cliente.headers, json=cruzado).status_code == 400
    # Un vuelo que no existe.
    inexistente = viaje_sin_contacto(viaje, "carta", 2, vueloId=99_999_999)
    assert api.post("/api/reservas/cotizar", headers=cliente.headers, json=inexistente).status_code == 400


def test_los_hoteles_y_excursiones_deben_ser_de_la_ciudad_del_destino(api, crear_cliente, viaje, catalogo):
    cliente = crear_cliente()
    kioto = api.get(f"/api/catalogos/destinos/{catalogo.destino_kioto['id']}/opciones").json()
    hotel_ajeno = viaje_sin_contacto(viaje, "carta", 2, hotelId=kioto["hoteles"][0]["id"])
    rechazado = api.post("/api/reservas/cotizar", headers=cliente.headers, json=hotel_ajeno)
    assert rechazado.status_code == 400 and "no está en" in rechazado.json()["mensaje"]

    excursion_ajena = viaje_sin_contacto(viaje, "carta", 2, excursiones=[{"id": kioto["excursiones"][0]["id"]}])
    assert api.post("/api/reservas/cotizar", headers=cliente.headers, json=excursion_ajena).status_code == 400


def test_no_se_cotiza_un_vuelo_que_ya_salio_o_esta_cancelado(api, admin, crear_cliente, viaje, catalogo):
    cliente = crear_cliente()
    cancelado = {
        "aerolineaId": catalogo.aerolinea["id"], "modeloAvionId": catalogo.avion["id"], "origenId": catalogo.bogota["id"],
        "destinoId": catalogo.paris["id"], "fechaSalida": f"{viaje.salida}T08:00:00", "fechaLlegada": f"{viaje.salida}T23:30:00",
        "estado": "cancelado", "numeroVuelo": viaje.ida["numeroVuelo"],
    }
    assert api.put(f"/api/vuelos/{viaje.ida['id']}", headers=admin, json=cancelado).status_code == 200
    rechazado = api.post("/api/reservas/cotizar", headers=cliente.headers, json=viaje_sin_contacto(viaje, "carta", 1))
    assert rechazado.status_code == 400 and "no está disponible" in rechazado.json()["mensaje"]
    # Tampoco aparece en las opciones que ve un cliente.
    opciones = api.get(f"/api/catalogos/destinos/{viaje.destino['id']}/opciones").json()
    assert viaje.ida["id"] not in [v["id"] for v in opciones["vuelosIda"]]
    assert viaje.paquete["id"] not in [p["id"] for p in opciones["paquetes"]]


def test_editar_una_reserva_pagada_no_la_reprecifica_con_las_tarifas_de_hoy(api, admin, crear_cliente, crear_empleado, viaje, reservar):
    """Cambiar el teléfono de una reserva pagada fallaba si desde entonces había cambiado el precio de un hotel."""
    empleado, cliente = crear_empleado(), crear_cliente()
    reserva_id, creada = reservar(cliente, viaje, "carta", 2)
    api.post(f"/api/reservas/{reserva_id}/pago/manual", headers=empleado.headers, json={"metodo": "efectivo"})

    hotel = viaje.hotel
    subida = api.put(f"/api/hoteles/{hotel['id']}", headers=admin, json={
        "nombre": hotel["nombre"], "ciudadId": hotel["ciudadId"], "estrellas": hotel["estrellas"],
        "precioNoche": hotel["precioNoche"] * 2, "descripcion": hotel["descripcion"], "activo": True,
    })
    assert subida.status_code == 200, subida.text

    cambio = cuerpo_de_reserva(viaje, "carta", 2, telefonoContacto="3159990000")
    assert api.put(f"/api/reservas/{reserva_id}", headers=empleado.headers, json=cambio).status_code == 200
    reserva = api.get(f"/api/reservas/{reserva_id}", headers=empleado.headers).json()
    assert reserva["telefonoContacto"] == "3159990000"
    assert reserva["montoTotal"] == creada["montoTotal"]  # conserva la tarifa con la que se vendió

    # Una reserva nueva sí usa la tarifa actual.
    nueva = api.post("/api/reservas/cotizar", headers=cliente.headers, json=viaje_sin_contacto(viaje, "carta", 2)).json()
    assert nueva["desglose"]["hotel"] == creada["desglose"]["hotel"] * 2


def test_cotizar_al_editar_aplica_las_reglas_de_la_edicion(api, admin, catalogo, crear_cliente, crear_empleado, viaje, reservar):
    """Con `reservaId` la cotización es la de la edición: lo ya vendido conserva su precio y no se rechaza porque el catálogo cambió."""
    hotel = api.post("/api/hoteles", headers=admin, json={"nombre": "Hotel de cotización", "ciudadId": catalogo.paris["id"], "estrellas": 4, "precioNoche": 300_000}).json()
    empleado, cliente = crear_empleado(), crear_cliente()
    reserva_id, creada = reservar(cliente, viaje, "carta", 2, hotelId=hotel["id"])
    retirado = api.put(f"/api/hoteles/{hotel['id']}", headers=admin, json={
        "nombre": hotel["nombre"], "ciudadId": hotel["ciudadId"], "estrellas": hotel["estrellas"], "precioNoche": 600_000, "descripcion": None, "activo": False,
    })
    assert retirado.status_code == 200, retirado.text

    cuerpo = viaje_sin_contacto(viaje, "carta", 2, hotelId=hotel["id"])
    # Para una reserva nueva, el hotel retirado ya no se puede cotizar...
    assert api.post("/api/reservas/cotizar", headers=empleado.headers, json=cuerpo).status_code == 400
    # ...pero al editar la reserva que ya lo tenía, sí, y con la tarifa con la que se vendió.
    al_editar = api.post("/api/reservas/cotizar", headers=empleado.headers, json={**cuerpo, "reservaId": reserva_id})
    assert al_editar.status_code == 200, al_editar.text
    assert al_editar.json()["total"] == creada["montoTotal"]


def test_cotizar_con_reserva_respeta_de_quien_es_la_reserva(api, crear_cliente, viaje, reservar):
    duena, otra = crear_cliente(), crear_cliente()
    reserva_id, _ = reservar(duena, viaje, "carta", 2)
    cuerpo = viaje_sin_contacto(viaje, "carta", 2)

    assert api.post("/api/reservas/cotizar", headers=duena.headers, json={**cuerpo, "reservaId": reserva_id}).status_code == 200
    # Para quien no es dueño la reserva «no existe», igual que en el resto de la API.
    assert api.post("/api/reservas/cotizar", headers=otra.headers, json={**cuerpo, "reservaId": reserva_id}).status_code == 404
    assert api.post("/api/reservas/cotizar", headers=duena.headers, json={**cuerpo, "reservaId": 99_999_999}).status_code == 404
