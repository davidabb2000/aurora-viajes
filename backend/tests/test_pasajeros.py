"""Datos de los pasajeros de cada reserva y manifiesto por vuelo."""
import pytest

from tests.conftest import cuerpo_de_reserva


def pasajero(n=1, **cambios):
    datos = {"nombre": "Ana", "apellido": "Gomez", "tipoDocumento": "CC", "numeroDocumento": f"1020300{n:02d}"}
    datos.update(cambios)
    return datos


def guardar(api, reserva_id, personas, headers):
    return api.put(f"/api/reservas/{reserva_id}/pasajeros", headers=headers, json={"pasajeros": personas})


def test_el_cliente_registra_corrige_y_quita_los_datos_de_sus_pasajeros(api, crear_cliente, viaje, reservar):
    cliente = crear_cliente()
    reserva_id, _ = reservar(cliente, viaje, "carta", pasajeros=2)

    respuesta = guardar(api, reserva_id, [pasajero(1), pasajero(2, nombre="Luis", tipoDocumento="PA", numeroDocumento="ab123456")], cliente.headers)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["plazas"] == 2
    assert [(p["nombre"], p["tipoDocumento"], p["numeroDocumento"]) for p in respuesta.json()["pasajeros"]] == [
        ("Ana", "CC", "102030001"), ("Luis", "PA", "AB123456"),  # el pasaporte se guarda en mayúsculas
    ]

    reserva = api.get(f"/api/reservas/{reserva_id}", headers=cliente.headers).json()
    assert reserva["pasajerosRegistrados"] == 2 and len(reserva["datosDePasajeros"]) == 2
    assert api.get("/api/reservas/mias", headers=cliente.headers).json()[0]["pasajerosRegistrados"] == 2

    # Guardar de nuevo a la misma persona no choca con su propio registro anterior, y la lista se reemplaza entera.
    assert guardar(api, reserva_id, [pasajero(1, nombre="Ana María")], cliente.headers).status_code == 200
    reserva = api.get(f"/api/reservas/{reserva_id}/pasajeros", headers=cliente.headers).json()
    assert [p["nombre"] for p in reserva["pasajeros"]] == ["Ana María"]
    assert guardar(api, reserva_id, [], cliente.headers).status_code == 200
    assert api.get(f"/api/reservas/{reserva_id}", headers=cliente.headers).json()["pasajerosRegistrados"] == 0


def test_no_se_registran_mas_pasajeros_que_plazas(api, crear_cliente, viaje, reservar):
    cliente = crear_cliente()
    reserva_id, _ = reservar(cliente, viaje, "paquete", pasajeros=1)
    respuesta = guardar(api, reserva_id, [pasajero(1), pasajero(2)], cliente.headers)
    assert respuesta.status_code == 400
    assert "1 pasajero" in respuesta.json()["mensaje"]


@pytest.mark.parametrize(
    ("persona", "campo"),
    [
        (pasajero(tipoDocumento="XX"), "tipoDocumento"),
        (pasajero(numeroDocumento="12"), "numeroDocumento"),
        (pasajero(numeroDocumento="12 345 678"), "numeroDocumento"),
        (pasajero(nombre="Ana123"), "nombre"),
        (pasajero(apellido=""), "apellido"),
    ],
)
def test_los_datos_invalidos_se_rechazan_indicando_el_campo(api, crear_cliente, viaje, reservar, persona, campo):
    cliente = crear_cliente()
    reserva_id, _ = reservar(cliente, viaje, "paquete", pasajeros=2)
    respuesta = guardar(api, reserva_id, [persona], cliente.headers)
    assert respuesta.status_code == 422
    assert any(campo in detalle["campo"] for detalle in respuesta.json()["detalles"]), respuesta.json()


def test_una_persona_repetida_en_la_misma_reserva_se_rechaza(api, crear_cliente, viaje, reservar):
    cliente = crear_cliente()
    reserva_id, _ = reservar(cliente, viaje, "paquete", pasajeros=2)
    respuesta = guardar(api, reserva_id, [pasajero(1), pasajero(1, nombre="Otra")], cliente.headers)
    assert respuesta.status_code == 422
    assert "repetido" in respuesta.text


def test_una_reserva_ajena_no_existe_y_el_personal_si_puede_completarla(api, crear_cliente, crear_empleado, viaje, reservar):
    duena, intrusa, empleado = crear_cliente(), crear_cliente(), crear_empleado()
    reserva_id, _ = reservar(duena, viaje, "paquete", pasajeros=2)
    assert api.get(f"/api/reservas/{reserva_id}/pasajeros", headers=intrusa.headers).status_code == 404
    assert guardar(api, reserva_id, [pasajero(1)], intrusa.headers).status_code == 404
    assert guardar(api, reserva_id, [pasajero(1)], empleado.headers).status_code == 200
    assert api.get(f"/api/reservas/{reserva_id}/pasajeros", headers=duena.headers).json()["pasajeros"][0]["nombre"] == "Ana"


def test_una_reserva_cancelada_no_admite_cambios(api, crear_cliente, viaje, reservar):
    cliente = crear_cliente()
    reserva_id, _ = reservar(cliente, viaje, "paquete", pasajeros=2)
    assert api.post(f"/api/reservas/{reserva_id}/cancelar", headers=cliente.headers).status_code == 200
    respuesta = guardar(api, reserva_id, [pasajero(1)], cliente.headers)
    assert respuesta.status_code == 409 and "cancelada" in respuesta.json()["mensaje"]


def test_una_persona_no_ocupa_dos_plazas_del_mismo_vuelo(api, crear_cliente, viaje, reservar):
    primera, segunda = crear_cliente(), crear_cliente()
    id_1, _ = reservar(primera, viaje, "carta", pasajeros=1)
    id_2, _ = reservar(segunda, viaje, "carta", pasajeros=1)
    assert guardar(api, id_1, [pasajero(1)], primera.headers).status_code == 200

    repetida = guardar(api, id_2, [pasajero(1)], segunda.headers)
    assert repetida.status_code == 409
    assert f"#{id_1}" in repetida.json()["mensaje"] and "mismo vuelo" in repetida.json()["mensaje"]
    # Otra persona sí puede; y si la primera reserva se cancela, la plaza de esa persona queda libre.
    assert guardar(api, id_2, [pasajero(2)], segunda.headers).status_code == 200
    api.post(f"/api/reservas/{id_1}/cancelar", headers=primera.headers)
    assert guardar(api, id_2, [pasajero(1)], segunda.headers).status_code == 200


def test_no_se_puede_reducir_una_reserva_por_debajo_de_los_pasajeros_registrados(api, admin, crear_cliente, viaje, reservar):
    cliente = crear_cliente()
    reserva_id, _ = reservar(cliente, viaje, "carta", pasajeros=3)
    guardar(api, reserva_id, [pasajero(1), pasajero(2), pasajero(3)], cliente.headers)

    reducida = api.put(f"/api/reservas/{reserva_id}", headers=admin, json=cuerpo_de_reserva(viaje, "carta", pasajeros=2))
    assert reducida.status_code == 409 and "3 pasajeros" in reducida.json()["mensaje"]
    guardar(api, reserva_id, [pasajero(1), pasajero(2)], cliente.headers)
    assert api.put(f"/api/reservas/{reserva_id}", headers=admin, json=cuerpo_de_reserva(viaje, "carta", pasajeros=2)).status_code == 200


def test_el_manifiesto_lista_quien_viaja_en_cada_tramo_sin_las_canceladas(api, admin, crear_cliente, crear_empleado, viaje, reservar):
    uno, dos, tres, empleado = crear_cliente(), crear_cliente(), crear_cliente(), crear_empleado()
    id_1, _ = reservar(uno, viaje, "carta", pasajeros=3)
    id_2, _ = reservar(dos, viaje, "carta", pasajeros=1)
    id_3, _ = reservar(tres, viaje, "carta", pasajeros=2)
    guardar(api, id_1, [pasajero(1), pasajero(2)], uno.headers)
    guardar(api, id_2, [pasajero(3)], dos.headers)
    api.post(f"/api/reservas/{id_3}/cancelar", headers=tres.headers)

    ida = api.get(f"/api/vuelos/{viaje.ida['id']}/manifiesto", headers=empleado.headers)
    assert ida.status_code == 200, ida.text
    datos = ida.json()
    assert datos["vuelo"]["id"] == viaje.ida["id"]
    assert datos["resumen"] == {"reservas": 2, "plazas": 4, "conDatos": 3, "faltanDatos": 1}
    assert [f["reservaId"] for f in datos["reservas"]] == [id_1, id_2]
    assert datos["reservas"][0]["faltan"] == 1 and datos["reservas"][0]["cliente"].strip() and datos["reservas"][0]["telefono"] == "3001112233"
    assert {f["tramo"] for f in datos["reservas"]} == {"ida"}
    assert datos["vuelo"]["plazasOcupadas"] == 4

    regreso = api.get(f"/api/vuelos/{viaje.vuelta['id']}/manifiesto", headers=admin).json()
    assert {f["tramo"] for f in regreso["reservas"]} == {"regreso"} and regreso["resumen"]["plazas"] == 4


def test_el_manifiesto_es_solo_para_el_personal(api, crear_cliente, viaje):
    cliente = crear_cliente()
    assert api.get(f"/api/vuelos/{viaje.ida['id']}/manifiesto", headers=cliente.headers).status_code == 403
    assert api.get(f"/api/vuelos/{viaje.ida['id']}/manifiesto").status_code == 401


def test_el_manifiesto_de_un_vuelo_inexistente_da_404(api, admin):
    assert api.get("/api/vuelos/99999999/manifiesto", headers=admin).status_code == 404


def test_borrar_una_reserva_borra_los_datos_de_sus_pasajeros(api, admin, crear_cliente, viaje, reservar):
    cliente = crear_cliente()
    reserva_id, _ = reservar(cliente, viaje, "carta", pasajeros=2)
    guardar(api, reserva_id, [pasajero(1), pasajero(2)], cliente.headers)
    assert api.get(f"/api/vuelos/{viaje.ida['id']}/manifiesto", headers=admin).json()["resumen"]["conDatos"] == 2

    assert api.delete(f"/api/reservas/{reserva_id}", headers=admin).status_code == 200
    manifiesto = api.get(f"/api/vuelos/{viaje.ida['id']}/manifiesto", headers=admin).json()
    assert manifiesto["resumen"] == {"reservas": 0, "plazas": 0, "conDatos": 0, "faltanDatos": 0}
