"""Plazas de los vuelos: se cuentan en la ida y en el regreso, y se liberan al cancelar."""
from datetime import timedelta

from tests.conftest import cuerpo_de_reserva, cuerpo_de_vuelo


def plazas_libres(api, viaje, vuelo):
    opciones = api.get(f"/api/catalogos/destinos/{viaje.destino['id']}/opciones").json()
    return next(v for v in opciones["vuelosIda"] + opciones["vuelosRegreso"] if v["id"] == vuelo["id"])["plazasLibres"]


def test_una_reserva_ocupa_plazas_en_la_ida_y_en_el_regreso(api, crear_cliente, viaje, reservar):
    reservar(crear_cliente(), viaje, "carta", 4)
    assert plazas_libres(api, viaje, viaje.ida) == 176
    assert plazas_libres(api, viaje, viaje.vuelta) == 176


def test_un_paquete_ocupa_las_plazas_de_sus_dos_vuelos(api, crear_cliente, viaje, reservar):
    reservar(crear_cliente(), viaje, "paquete", 3)
    assert plazas_libres(api, viaje, viaje.ida) == 177
    assert plazas_libres(api, viaje, viaje.vuelta) == 177


def test_cancelar_libera_las_plazas_y_reactivar_las_toma_de_nuevo(api, crear_cliente, crear_empleado, viaje, reservar):
    empleado, cliente = crear_empleado(), crear_cliente()
    reserva_id, _ = reservar(cliente, viaje, "carta", 5)
    assert plazas_libres(api, viaje, viaje.ida) == 175

    api.post(f"/api/reservas/{reserva_id}/cancelar", headers=cliente.headers)
    assert plazas_libres(api, viaje, viaje.ida) == 180
    assert plazas_libres(api, viaje, viaje.vuelta) == 180

    api.patch(f"/api/reservas/{reserva_id}/estado", headers=empleado.headers, json={"estado": "pendiente"})
    assert plazas_libres(api, viaje, viaje.ida) == 175


def test_eliminar_una_reserva_sin_pagar_libera_las_plazas(api, crear_cliente, viaje, reservar):
    cliente = crear_cliente()
    reserva_id, _ = reservar(cliente, viaje, "carta", 5)
    assert api.delete(f"/api/reservas/{reserva_id}", headers=cliente.headers).status_code == 200
    assert plazas_libres(api, viaje, viaje.ida) == 180


def test_el_regreso_tambien_puede_llenarse(api, admin, crear_cliente, catalogo, viaje, reservar):
    """El vuelo de regreso es un vuelo más: si se llena, no se vende más aunque la ida tenga sitio."""
    cliente = crear_cliente()
    # Se reduce el cupo del regreso a 3 plazas.
    cuerpo = cuerpo_de_vuelo(
        catalogo, catalogo.paris, catalogo.bogota, f"{viaje.regreso}T11:00:00", numeroVuelo=viaje.vuelta["numeroVuelo"], capacidadMaxima=3
    )
    assert api.put(f"/api/vuelos/{viaje.vuelta['id']}", headers=admin, json=cuerpo).status_code == 200

    reservar(cliente, viaje, "carta", 2)
    lleno = api.post("/api/reservas", headers=cliente.headers, json=cuerpo_de_reserva(viaje, "carta", 2))
    assert lleno.status_code == 400
    assert viaje.vuelta["numeroVuelo"] in lleno.json()["mensaje"] and "regreso" in lleno.json()["mensaje"]
    # Con una sola plaza sí cabe.
    assert api.post("/api/reservas", headers=cliente.headers, json=cuerpo_de_reserva(viaje, "carta", 1)).status_code == 201


def test_editar_una_reserva_no_cuenta_dos_veces_sus_propias_plazas(api, crear_empleado, crear_cliente, viaje, reservar):
    empleado, cliente = crear_empleado(), crear_cliente()
    reserva_id, _ = reservar(cliente, viaje, "carta", 9)
    for _ in range(19):  # 19 x 9 + 9 = 180: el vuelo está lleno
        reservar(cliente, viaje, "carta", 9)
    assert plazas_libres(api, viaje, viaje.ida) == 0

    # Guardar la misma reserva con otras notas no debe fallar por «falta de plazas».
    sin_cambios = cuerpo_de_reserva(viaje, "carta", 9, notas="Cambio de nota")
    assert api.put(f"/api/reservas/{reserva_id}", headers=empleado.headers, json=sin_cambios).status_code == 200
    # Pero pasar de 9 a un pasajero más ya no cabe... y de 9 a 8 sí.
    assert api.put(f"/api/reservas/{reserva_id}", headers=empleado.headers, json=cuerpo_de_reserva(viaje, "carta", 8)).status_code == 200
    assert plazas_libres(api, viaje, viaje.ida) == 1


def test_no_se_deja_una_reserva_sin_vuelo_valido_al_editarla(api, crear_empleado, crear_cliente, catalogo, viaje, reservar):
    empleado, cliente = crear_empleado(), crear_cliente()
    reserva_id, _ = reservar(cliente, viaje, "carta", 2)
    otro_destino = cuerpo_de_reserva(viaje, "carta", 2, destinoId=catalogo.destino_kioto["id"])
    rechazado = api.put(f"/api/reservas/{reserva_id}", headers=empleado.headers, json=otro_destino)
    assert rechazado.status_code == 400
    # La reserva original sigue intacta.
    reserva = api.get(f"/api/reservas/{reserva_id}", headers=empleado.headers).json()
    assert reserva["destinoId"] == viaje.destino["id"] and reserva["pasajeros"] == 2


def test_mover_una_reserva_a_otro_vuelo_traslada_las_plazas(api, admin, crear_empleado, crear_cliente, catalogo, viaje, reservar):
    empleado, cliente = crear_empleado(), crear_cliente()
    reserva_id, _ = reservar(cliente, viaje, "carta", 3)
    # Otro vuelo de ida a París, un día después, con su propio regreso.
    nueva_ida = api.post("/api/vuelos", headers=admin, json=cuerpo_de_vuelo(catalogo, catalogo.bogota, catalogo.paris, f"{viaje.salida + timedelta(days=1)}T08:00:00")).json()
    nueva_vuelta = api.post("/api/vuelos", headers=admin, json=cuerpo_de_vuelo(catalogo, catalogo.paris, catalogo.bogota, f"{viaje.regreso + timedelta(days=1)}T11:00:00")).json()

    cambio = cuerpo_de_reserva(viaje, "carta", 3, vueloId=nueva_ida["id"], vueloRegresoId=nueva_vuelta["id"])
    assert api.put(f"/api/reservas/{reserva_id}", headers=empleado.headers, json=cambio).status_code == 200
    assert plazas_libres(api, viaje, viaje.ida) == 180
    assert plazas_libres(api, viaje, nueva_ida) == 177
    reserva = api.get(f"/api/reservas/{reserva_id}", headers=empleado.headers).json()
    assert reserva["fechaSalida"] == str(viaje.salida + timedelta(days=1))
