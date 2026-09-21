"""Reservas: precio, factura, edición, cancelación y borrado."""

from decimal import Decimal

from tests.conftest import cuerpo_de_reserva
from tests.utiles import pagar_por_webhook


def suma_de_lineas(venta):
    return sum(Decimal(str(d["subtotal"])) for d in venta["detalles"])


def test_paquete_factura_las_lineas_suman_el_total(crear_cliente, viaje, reservar, venta_de):
    cliente = crear_cliente()
    reserva_id, respuesta = reservar(cliente, viaje, "paquete", pasajeros=2)

    assert respuesta["montoTotal"] == 2_000_000  # precio del paquete x 2 pasajeros
    venta = venta_de(reserva_id)
    assert venta["estado"] == "pendiente"
    assert venta["total"] == 2_000_000
    # Regresión: las excursiones se sumaban además del precio cerrado del paquete.
    assert suma_de_lineas(venta) == Decimal(str(venta["total"]))
    assert venta["factura"]["estado"] == "emitida"


def test_a_la_carta_suma_vuelo_hotel_y_excursiones(api, crear_cliente, viaje, reservar, venta_de):
    cliente = crear_cliente()
    reserva_id, respuesta = reservar(cliente, viaje, "carta", pasajeros=3)

    noches, habitaciones = 6, 2  # 3 pasajeros -> 2 habitaciones
    esperado = (
        viaje.destino["precioBase"] * 3
        + viaje.hotel["precioNoche"] * noches * habitaciones
        + sum(e["precio"] for e in viaje.excursiones) * 3
    )
    assert respuesta["montoTotal"] == esperado
    assert respuesta["desglose"]["hotel"] == viaje.hotel["precioNoche"] * noches * habitaciones
    assert suma_de_lineas(venta_de(reserva_id)) == Decimal(str(esperado))


def test_editar_una_reserva_recalcula_precio_venta_y_factura(api, admin, crear_cliente, viaje, reservar, venta_de):
    """Regresión: PUT /api/reservas llamaba a una función que no existía y devolvía 500."""
    cliente = crear_cliente()
    reserva_id, antes = reservar(cliente, viaje, "carta", pasajeros=2)

    cuerpo = cuerpo_de_reserva(viaje, "carta", pasajeros=4)
    cuerpo["excursiones"] = []  # se quita una compra: el total debe bajar por ese concepto
    respuesta = api.put(f"/api/reservas/{reserva_id}", headers=admin, json=cuerpo)
    assert respuesta.status_code == 200, respuesta.text

    reserva = api.get(f"/api/reservas/{reserva_id}", headers=admin).json()
    assert reserva["pasajeros"] == 4
    assert reserva["excursiones"] == []
    assert reserva["desglose"]["excursiones"] == 0
    assert reserva["desglose"]["vuelo"] == viaje.destino["precioBase"] * 4
    assert reserva["montoTotal"] == sum(reserva["desglose"].values())
    venta = venta_de(reserva_id)
    assert venta["total"] == reserva["montoTotal"]
    assert suma_de_lineas(venta) == Decimal(str(reserva["montoTotal"]))
    assert reserva["montoTotal"] != antes["montoTotal"]


def test_una_reserva_pagada_no_puede_cambiar_de_precio(api, admin, crear_cliente, viaje, reservar):
    cliente = crear_cliente()
    reserva_id, respuesta = reservar(cliente, viaje, "paquete", pasajeros=2)
    pagar_por_webhook(api, reserva_id, respuesta["montoTotal"])

    cambio_de_precio = api.put(f"/api/reservas/{reserva_id}", headers=admin, json=cuerpo_de_reserva(viaje, "paquete", pasajeros=3))
    assert cambio_de_precio.status_code == 409
    sin_cambio_de_precio = api.put(f"/api/reservas/{reserva_id}", headers=admin, json=cuerpo_de_reserva(viaje, "paquete", pasajeros=2))
    assert sin_cambio_de_precio.status_code == 200


def test_cancelar_anula_la_venta_y_reactivar_la_restaura(api, admin, crear_cliente, viaje, reservar, venta_de):
    cliente = crear_cliente()
    reserva_id, _ = reservar(cliente, viaje)

    assert api.patch(f"/api/reservas/{reserva_id}/estado", headers=admin, json={"estado": "cancelada"}).status_code == 200
    venta = venta_de(reserva_id)
    assert (venta["estado"], venta["factura"]["estado"]) == ("cancelada", "anulada")

    assert api.patch(f"/api/reservas/{reserva_id}/estado", headers=admin, json={"estado": "pendiente"}).status_code == 200
    venta = venta_de(reserva_id)
    assert (venta["estado"], venta["factura"]["estado"]) == ("pendiente", "emitida")


def test_pagar_completa_la_venta(api, crear_cliente, viaje, reservar, venta_de):
    cliente = crear_cliente()
    reserva_id, respuesta = reservar(cliente, viaje)
    pagar_por_webhook(api, reserva_id, respuesta["montoTotal"])

    reserva = api.get(f"/api/reservas/{reserva_id}", headers=cliente.headers).json()
    assert (reserva["estado"], reserva["estadoPago"], reserva["metodoPago"]) == ("confirmada", "pagado", "stripe")
    assert venta_de(reserva_id)["estado"] == "completada"


def test_borrar_una_reserva_sin_pagar_conserva_la_venta_anulada(api, crear_cliente, viaje, reservar, venta_de, admin):
    cliente = crear_cliente()
    reserva_id, _ = reservar(cliente, viaje)
    venta_id = venta_de(reserva_id)["id"]

    assert api.delete(f"/api/reservas/{reserva_id}", headers=cliente.headers).status_code == 200
    assert api.get(f"/api/reservas/{reserva_id}", headers=admin).status_code == 404
    venta = api.get(f"/api/ventas/{venta_id}", headers=admin).json()
    assert (venta["estado"], venta["reservaId"], venta["factura"]["estado"]) == ("cancelada", None, "anulada")


def test_no_se_puede_borrar_una_reserva_pagada(api, crear_cliente, viaje, reservar):
    cliente = crear_cliente()
    reserva_id, respuesta = reservar(cliente, viaje)
    pagar_por_webhook(api, reserva_id, respuesta["montoTotal"])

    borrada = api.delete(f"/api/reservas/{reserva_id}", headers=cliente.headers)
    assert borrada.status_code == 409
    assert api.get(f"/api/reservas/{reserva_id}", headers=cliente.headers).status_code == 200


def test_un_cliente_no_ve_las_reservas_de_otro(api, crear_cliente, viaje, reservar):
    dueno, intruso = crear_cliente(), crear_cliente()
    reserva_id, _ = reservar(dueno, viaje)

    # Se responde «no existe», no «prohibido»: así no se puede recorrer la numeración para ver cuáles hay.
    assert api.get(f"/api/reservas/{reserva_id}", headers=intruso.headers).status_code == 404
    assert api.delete(f"/api/reservas/{reserva_id}", headers=intruso.headers).status_code == 404
    assert api.post(f"/api/reservas/{reserva_id}/cancelar", headers=intruso.headers).status_code == 404
    assert reserva_id not in [r["id"] for r in api.get("/api/reservas/mias", headers=intruso.headers).json()]


def test_no_se_vende_mas_de_la_capacidad_del_vuelo(api, crear_cliente, viaje):
    cliente = crear_cliente()
    # Un Airbus A320 tiene 180 plazas y cada reserva admite hasta 9 pasajeros.
    for _ in range(20):
        assert api.post("/api/reservas", headers=cliente.headers, json=cuerpo_de_reserva(viaje, "carta", 9)).status_code == 201
    lleno = api.post("/api/reservas", headers=cliente.headers, json=cuerpo_de_reserva(viaje, "carta", 1))
    assert lleno.status_code == 400
    assert "plaza" in lleno.json()["mensaje"]


def test_editar_conserva_el_hotel_y_las_excursiones_que_el_catalogo_retiro_despues(api, admin, catalogo, crear_cliente, viaje, reservar):
    """Un hotel o una excursión desactivados dejan de ofrecerse, pero no se le quitan a quien ya los compró."""
    hotel = api.post("/api/hoteles", headers=admin, json={"nombre": "Hotel que cerrará", "ciudadId": catalogo.paris["id"], "estrellas": 3, "precioNoche": 200_000})
    excursion = api.post("/api/excursiones", headers=admin, json={"nombre": "Tour que se retira", "ciudadId": catalogo.paris["id"], "duracionHoras": 2, "precio": 50_000})
    assert hotel.status_code == 201 and excursion.status_code == 201
    propios = {"hotelId": hotel.json()["id"], "excursiones": [{"id": excursion.json()["id"]}]}
    cliente = crear_cliente()
    reserva_id, antes = reservar(cliente, viaje, "carta", pasajeros=2, **propios)

    assert api.delete(f"/api/hoteles/{hotel.json()['id']}", headers=admin).status_code < 300
    assert api.delete(f"/api/excursiones/{excursion.json()['id']}", headers=admin).status_code < 300

    edicion = api.put(f"/api/reservas/{reserva_id}", headers=admin, json=cuerpo_de_reserva(viaje, "carta", pasajeros=2, notas="Solo cambian las notas", **propios))
    assert edicion.status_code == 200, edicion.text
    despues = api.get(f"/api/reservas/{reserva_id}", headers=admin).json()
    assert despues["notas"] == "Solo cambian las notas"
    assert despues["montoTotal"] == antes["montoTotal"]
    assert [e["id"] for e in despues["excursiones"]] == [excursion.json()["id"]]

    # Para una reserva nueva, en cambio, ya no están en el catálogo.
    nueva = api.post("/api/reservas", headers=cliente.headers, json=cuerpo_de_reserva(viaje, "carta", pasajeros=2, **propios))
    assert nueva.status_code == 400
    # Y tampoco se pueden agregar a otra reserva que no los tenía.
    otra_id, _ = reservar(cliente, viaje, "carta", pasajeros=1)
    agregar = api.put(f"/api/reservas/{otra_id}", headers=admin, json=cuerpo_de_reserva(viaje, "carta", pasajeros=1, **propios))
    assert agregar.status_code == 400


def test_editar_conserva_el_paquete_que_se_desactivo_despues_de_la_venta(api, admin, crear_cliente, viaje, reservar):
    cliente = crear_cliente()
    reserva_id, antes = reservar(cliente, viaje, "paquete", pasajeros=2)
    assert api.delete(f"/api/paquetes/{viaje.paquete['id']}", headers=admin).status_code < 300

    edicion = api.put(f"/api/reservas/{reserva_id}", headers=admin, json=cuerpo_de_reserva(viaje, "paquete", pasajeros=2, notas="Ventana, por favor"))
    assert edicion.status_code == 200, edicion.text
    assert api.get(f"/api/reservas/{reserva_id}", headers=admin).json()["montoTotal"] == antes["montoTotal"]

    nueva = api.post("/api/reservas", headers=cliente.headers, json=cuerpo_de_reserva(viaje, "paquete", pasajeros=2))
    assert nueva.status_code == 400
