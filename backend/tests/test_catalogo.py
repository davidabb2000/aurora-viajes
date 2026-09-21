"""Catálogo normalizado: lugares únicos, vuelos, hoteles, excursiones y paquetes con reglas de integridad."""
from datetime import date, timedelta

from tests.conftest import cuerpo_de_reserva, cuerpo_de_vuelo


def cuerpo_de_hotel(ciudad, nombre="Hotel de Prueba", **cambios):
    cuerpo = {"nombre": nombre, "ciudadId": ciudad["id"], "estrellas": 4, "precioNoche": 250000, "descripcion": "Prueba", "activo": True}
    cuerpo.update(cambios)
    return cuerpo


# --------------------------------------------------------------------------------------
# Lugares
# --------------------------------------------------------------------------------------


def test_las_ciudades_se_escriben_una_sola_vez(api, admin, catalogo):
    duplicada = api.post("/api/ciudades", headers=admin, json={"nombre": "PARÍS", "pais": "francia"})
    assert duplicada.status_code == 409  # sin distinguir mayúsculas ni tildes

    nueva = api.post("/api/ciudades", headers=admin, json={"nombre": "Lyon", "pais": "Francia"})
    assert nueva.status_code == 201
    assert nueva.json()["pais"] == "Francia"  # reutiliza el país existente en lugar de crear otro
    paises = {c["pais"] for c in api.get("/api/ciudades", headers=admin).json()}
    assert "francia" not in paises


def test_solo_el_administrador_crea_lugares_aerolineas_y_modelos(api, crear_empleado):
    empleado = crear_empleado()
    assert api.get("/api/ciudades", headers=empleado.headers).status_code == 200
    assert api.post("/api/ciudades", headers=empleado.headers, json={"nombre": "Niza", "pais": "Francia"}).status_code == 403
    assert api.post("/api/aerolineas", headers=empleado.headers, json={"codigo": "XX", "nombre": "Aerolínea X"}).status_code == 403
    assert api.post("/api/modelos-avion", headers=empleado.headers, json={"nombre": "Modelo X", "capacidad": 100}).status_code == 403


def test_aerolineas_y_modelos_no_se_duplican(api, admin):
    nueva = api.post("/api/aerolineas", headers=admin, json={"codigo": "tx1", "nombre": "Transporte Uno"})
    assert nueva.status_code == 201 and nueva.json()["codigo"] == "TX1"
    assert api.post("/api/aerolineas", headers=admin, json={"codigo": "TX1", "nombre": "Otra"}).status_code == 409
    assert api.post("/api/aerolineas", headers=admin, json={"codigo": "TX2", "nombre": "Transporte Uno"}).status_code == 409
    assert api.post("/api/modelos-avion", headers=admin, json={"nombre": "Airbus A320", "capacidad": 180}).status_code == 409


# --------------------------------------------------------------------------------------
# Vuelos
# --------------------------------------------------------------------------------------


def test_un_vuelo_no_puede_salir_y_llegar_a_la_misma_ciudad(api, admin, catalogo):
    cuerpo = cuerpo_de_vuelo(catalogo, catalogo.bogota, catalogo.bogota, "2040-03-01T08:00:00")
    assert api.post("/api/vuelos", headers=admin, json=cuerpo).status_code == 422


def test_la_llegada_debe_ser_posterior_a_la_salida(api, admin, catalogo):
    cuerpo = cuerpo_de_vuelo(catalogo, catalogo.bogota, catalogo.paris, "2040-03-01T08:00:00", llegada="2040-03-01T07:00:00")
    assert api.post("/api/vuelos", headers=admin, json=cuerpo).status_code == 422


def test_las_plazas_a_la_venta_no_superan_las_del_avion(api, admin, catalogo):
    cuerpo = cuerpo_de_vuelo(catalogo, catalogo.bogota, catalogo.paris, "2040-03-02T08:00:00", capacidadMaxima=181)
    rechazado = api.post("/api/vuelos", headers=admin, json=cuerpo)
    assert rechazado.status_code == 400 and "180" in rechazado.json()["mensaje"]

    # Sin indicarlas se venden todas; con un número menor, solo esas (cupo de la agencia).
    completo = api.post("/api/vuelos", headers=admin, json=cuerpo_de_vuelo(catalogo, catalogo.bogota, catalogo.paris, "2040-03-03T08:00:00")).json()
    parcial = api.post("/api/vuelos", headers=admin, json=cuerpo_de_vuelo(catalogo, catalogo.bogota, catalogo.paris, "2040-03-04T08:00:00", capacidadMaxima=40)).json()
    assert (completo["capacidadMaxima"], completo["plazasLibres"]) == (180, 180)
    assert (parcial["capacidadMaxima"], parcial["plazasLibres"]) == (40, 40)


def test_un_vuelo_nuevo_debe_salir_en_el_futuro(api, admin, catalogo):
    ayer = (date.today() - timedelta(days=2)).isoformat()
    cuerpo = cuerpo_de_vuelo(catalogo, catalogo.bogota, catalogo.paris, f"{ayer}T08:00:00")
    assert api.post("/api/vuelos", headers=admin, json=cuerpo).status_code == 400


def test_no_se_repite_el_mismo_numero_de_vuelo_en_el_mismo_horario(api, admin, catalogo):
    cuerpo = cuerpo_de_vuelo(catalogo, catalogo.bogota, catalogo.paris, "2040-04-01T08:00:00", numeroVuelo="zz900")
    primero = api.post("/api/vuelos", headers=admin, json=cuerpo)
    assert primero.status_code == 201 and primero.json()["numeroVuelo"] == "ZZ900"
    assert api.post("/api/vuelos", headers=admin, json=cuerpo).status_code == 409
    # El mismo número otro día es lo normal: un vuelo se repite cada semana.
    otro_dia = {**cuerpo, "fechaSalida": "2040-04-08T08:00:00", "fechaLlegada": "2040-04-08T23:30:00"}
    assert api.post("/api/vuelos", headers=admin, json=otro_dia).status_code == 201


def test_un_vuelo_con_reservas_no_cambia_de_ruta_ni_de_dia(api, admin, crear_cliente, catalogo, viaje, reservar):
    reservar(crear_cliente(), viaje, "carta", 2)
    base = {
        "aerolineaId": catalogo.aerolinea["id"], "modeloAvionId": catalogo.avion["id"], "origenId": catalogo.bogota["id"],
        "destinoId": catalogo.paris["id"], "fechaSalida": f"{viaje.salida}T08:00:00", "fechaLlegada": f"{viaje.salida}T23:30:00",
        "numeroVuelo": viaje.ida["numeroVuelo"],
    }
    otro_dia = {**base, "fechaSalida": f"{viaje.salida + timedelta(days=1)}T08:00:00", "fechaLlegada": f"{viaje.salida + timedelta(days=1)}T23:30:00"}
    assert api.put(f"/api/vuelos/{viaje.ida['id']}", headers=admin, json=otro_dia).status_code == 409
    otra_ruta = {**base, "destinoId": catalogo.kioto["id"]}
    assert api.put(f"/api/vuelos/{viaje.ida['id']}", headers=admin, json=otra_ruta).status_code == 409
    # Cambiar la hora el mismo día sí se puede.
    otra_hora = {**base, "fechaSalida": f"{viaje.salida}T09:15:00"}
    assert api.put(f"/api/vuelos/{viaje.ida['id']}", headers=admin, json=otra_hora).status_code == 200
    # Y no se pueden dejar menos plazas de las ya vendidas.
    assert api.put(f"/api/vuelos/{viaje.ida['id']}", headers=admin, json={**base, "capacidadMaxima": 1}).status_code == 409


def test_cancelar_un_vuelo_con_reservas_avisa_cuantos_pasajeros_afecta(api, admin, crear_cliente, catalogo, viaje, reservar):
    reservar(crear_cliente(), viaje, "carta", 3)
    cuerpo = {
        "aerolineaId": catalogo.aerolinea["id"], "modeloAvionId": catalogo.avion["id"], "origenId": catalogo.bogota["id"],
        "destinoId": catalogo.paris["id"], "fechaSalida": f"{viaje.salida}T08:00:00", "fechaLlegada": f"{viaje.salida}T23:30:00",
        "numeroVuelo": viaje.ida["numeroVuelo"], "estado": "cancelado",
    }
    respuesta = api.put(f"/api/vuelos/{viaje.ida['id']}", headers=admin, json=cuerpo)
    assert respuesta.status_code == 200
    assert "3 pasajero" in respuesta.json()["advertencia"]


def test_un_vuelo_con_reservas_o_paquetes_no_se_elimina(api, admin, crear_cliente, catalogo, viaje, reservar):
    reservar(crear_cliente(), viaje, "carta", 1)
    assert api.delete(f"/api/vuelos/{viaje.ida['id']}", headers=admin).status_code == 409
    assert api.delete(f"/api/vuelos/{viaje.vuelta['id']}", headers=admin).status_code == 409  # lo usa el paquete

    libre = api.post("/api/vuelos", headers=admin, json=cuerpo_de_vuelo(catalogo, catalogo.bogota, catalogo.paris, "2040-05-01T08:00:00")).json()
    assert api.delete(f"/api/vuelos/{libre['id']}", headers=admin).status_code == 200
    assert api.get(f"/api/vuelos/{libre['id']}", headers=admin).status_code == 404


def test_los_clientes_no_listan_los_vuelos_internos(api, crear_cliente, crear_empleado):
    assert api.get("/api/vuelos", headers=crear_cliente().headers).status_code == 403
    assert api.get("/api/vuelos", headers=crear_empleado().headers).status_code == 200
    assert api.get("/api/hoteles", headers=crear_cliente().headers).status_code == 403
    assert api.get("/api/excursiones", headers=crear_cliente().headers).status_code == 403


# --------------------------------------------------------------------------------------
# Hoteles y excursiones
# --------------------------------------------------------------------------------------


def test_un_hotel_no_se_repite_en_la_misma_ciudad(api, admin, catalogo):
    creado = api.post("/api/hoteles", headers=admin, json=cuerpo_de_hotel(catalogo.paris, "Hôtel Único"))
    assert creado.status_code == 201
    assert creado.json()["pais"] == "Francia"  # el país se deriva de la ciudad, no se escribe
    assert api.post("/api/hoteles", headers=admin, json=cuerpo_de_hotel(catalogo.paris, "hotel unico")).status_code == 409
    # El mismo nombre en otra ciudad sí es otro hotel.
    assert api.post("/api/hoteles", headers=admin, json=cuerpo_de_hotel(catalogo.kioto, "Hôtel Único")).status_code == 201


def test_hoteles_con_datos_invalidos(api, admin, catalogo):
    assert api.post("/api/hoteles", headers=admin, json=cuerpo_de_hotel(catalogo.paris, "Cero", estrellas=0)).status_code == 422
    assert api.post("/api/hoteles", headers=admin, json=cuerpo_de_hotel(catalogo.paris, "Seis", estrellas=6)).status_code == 422
    assert api.post("/api/hoteles", headers=admin, json=cuerpo_de_hotel(catalogo.paris, "Barato", precioNoche=-1)).status_code == 422
    assert api.post("/api/hoteles", headers=admin, json=cuerpo_de_hotel({"id": 9_999_999}, "Sin ciudad")).status_code == 400
    assert api.post("/api/hoteles", headers=admin, json=cuerpo_de_hotel(catalogo.paris, "   ")).status_code == 422


def test_un_hotel_en_uso_no_cambia_de_ciudad(api, admin, catalogo, viaje):
    hotel = viaje.hotel
    cambio = api.put(f"/api/hoteles/{hotel['id']}", headers=admin, json=cuerpo_de_hotel(catalogo.kioto, hotel["nombre"]))
    assert cambio.status_code == 409  # está en un paquete de París


def test_desactivar_un_hotel_lo_saca_de_las_opciones_pero_no_de_las_reservas(api, admin, crear_cliente, viaje, reservar):
    cliente = crear_cliente()
    reserva_id, _ = reservar(cliente, viaje, "carta", 2)
    assert api.delete(f"/api/hoteles/{viaje.hotel['id']}", headers=admin).status_code == 200
    opciones = api.get(f"/api/catalogos/destinos/{viaje.destino['id']}/opciones").json()
    assert viaje.hotel["id"] not in [h["id"] for h in opciones["hoteles"]]
    # La reserva ya hecha conserva su hotel.
    assert api.get(f"/api/reservas/{reserva_id}", headers=cliente.headers).json()["hotel"]["id"] == viaje.hotel["id"]


def test_una_excursion_no_se_repite_ni_cambia_de_ciudad_si_esta_en_uso(api, admin, catalogo, viaje):
    excursion = viaje.excursiones[0]
    cuerpo = {
        "nombre": excursion["nombre"], "ciudadId": catalogo.paris["id"], "duracionHoras": 3, "precio": 100000, "descripcion": None, "activo": True,
    }
    assert api.post("/api/excursiones", headers=admin, json=cuerpo).status_code == 409
    a_kioto = {**cuerpo, "ciudadId": catalogo.kioto["id"]}
    assert api.put(f"/api/excursiones/{excursion['id']}", headers=admin, json=a_kioto).status_code == 409
    assert api.post("/api/excursiones", headers=admin, json={**cuerpo, "nombre": "Excursión nueva", "duracionHoras": 49}).status_code == 422


# --------------------------------------------------------------------------------------
# Paquetes
# --------------------------------------------------------------------------------------


def paquete_base(viaje, **cambios):
    cuerpo = {
        "nombre": f"Paquete alterno {viaje.salida}", "destinoId": viaje.destino["id"], "vueloId": viaje.ida["id"],
        "vueloRegresoId": viaje.vuelta["id"], "hotelId": viaje.hotel["id"], "excursionIds": [e["id"] for e in viaje.excursiones],
        "precioBase": 900000,
    }
    cuerpo.update(cambios)
    return cuerpo


def test_las_noches_del_paquete_salen_de_los_vuelos(api, viaje):
    assert viaje.paquete["noches"] == 6
    assert (viaje.paquete["fechaSalida"], viaje.paquete["fechaRegreso"]) == (str(viaje.salida), str(viaje.regreso))


def test_paquete_con_vuelos_hotel_o_excursiones_incoherentes(api, admin, catalogo, viaje):
    # Nombre repetido.
    assert api.post("/api/paquetes", headers=admin, json=paquete_base(viaje, nombre=viaje.paquete["nombre"].upper())).status_code == 409
    # Noches que no cuadran con las fechas de los vuelos.
    assert api.post("/api/paquetes", headers=admin, json=paquete_base(viaje, noches=4)).status_code == 400
    # El regreso no puede ser el mismo vuelo de ida ni salir antes.
    assert api.post("/api/paquetes", headers=admin, json=paquete_base(viaje, vueloRegresoId=viaje.ida["id"])).status_code == 400
    # Hotel o excursiones de otra ciudad.
    kioto = api.get(f"/api/catalogos/destinos/{catalogo.destino_kioto['id']}/opciones").json()
    assert api.post("/api/paquetes", headers=admin, json=paquete_base(viaje, hotelId=kioto["hoteles"][0]["id"])).status_code == 400
    assert api.post("/api/paquetes", headers=admin, json=paquete_base(viaje, excursionIds=[kioto["excursiones"][0]["id"]])).status_code == 400
    # Un vuelo de ida que no llega al destino.
    otro = api.post("/api/vuelos", headers=admin, json=cuerpo_de_vuelo(catalogo, catalogo.bogota, catalogo.kioto, f"{viaje.salida}T10:00:00")).json()
    assert api.post("/api/paquetes", headers=admin, json=paquete_base(viaje, vueloId=otro["id"])).status_code == 400


def test_paquete_sin_vuelo_de_regreso_pide_las_noches(api, admin, viaje):
    sin_regreso = paquete_base(viaje, nombre="Paquete abierto")
    sin_regreso.pop("vueloRegresoId")
    assert api.post("/api/paquetes", headers=admin, json=sin_regreso).status_code == 422
    creado = api.post("/api/paquetes", headers=admin, json={**sin_regreso, "noches": 5})
    assert creado.status_code == 201
    assert creado.json()["vueloRegreso"] is None
    assert creado.json()["fechaRegreso"] == str(viaje.salida + timedelta(days=5))


def test_los_clientes_solo_ven_paquetes_con_salida_futura_y_el_personal_todos(api, admin, crear_cliente, viaje):
    listado = api.get("/api/paquetes", headers=crear_cliente().headers).json()
    assert viaje.paquete["id"] in [p["id"] for p in listado]
    propio = next(p for p in listado if p["id"] == viaje.paquete["id"])
    assert propio["plazasLibres"] == 180


def test_desactivar_un_paquete_no_afecta_a_las_reservas_hechas(api, admin, crear_cliente, viaje, reservar):
    cliente = crear_cliente()
    reserva_id, _ = reservar(cliente, viaje, "paquete", 2)
    assert api.delete(f"/api/paquetes/{viaje.paquete['id']}", headers=admin).status_code == 200
    opciones = api.get(f"/api/catalogos/destinos/{viaje.destino['id']}/opciones").json()
    assert viaje.paquete["id"] not in [p["id"] for p in opciones["paquetes"]]
    assert api.post("/api/reservas", headers=cliente.headers, json=cuerpo_de_reserva(viaje, "paquete", 1)).status_code == 400
    reserva = api.get(f"/api/reservas/{reserva_id}", headers=cliente.headers).json()
    assert reserva["paquete"]["nombre"] == viaje.paquete["nombre"]
