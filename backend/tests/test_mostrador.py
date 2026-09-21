"""Reservas del personal: reservar a nombre de un cliente, cobrar en el mostrador, cancelar y reactivar."""

from tests.conftest import cuerpo_de_reserva


def test_el_personal_reserva_a_nombre_de_un_cliente_y_cobra_en_el_mostrador(api, crear_empleado, crear_cliente, viaje, venta_de):
    empleado, cliente = crear_empleado(), crear_cliente()
    cuerpo = cuerpo_de_reserva(viaje, "carta", 2, clienteId=cliente.id, pago={"metodo": "efectivo", "referencia": "Recibo 0042"})

    respuesta = api.post("/api/reservas", headers=empleado.headers, json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    creada = respuesta.json()
    assert (creada["estado"], creada["estadoPago"]) == ("confirmada", "pagado")

    # El cliente la ve en su cuenta, con quién la registró y cómo se pagó.
    reserva = api.get(f"/api/reservas/{creada['id']}", headers=cliente.headers).json()
    assert reserva["clienteId"] == cliente.id
    assert reserva["creadaPor"].startswith("Personal Agencia")
    assert (reserva["metodoPago"], reserva["pagoReferencia"]) == ("efectivo", "Recibo 0042")
    assert reserva["pagoRegistradoPor"] == reserva["creadaPor"]
    assert reserva["pagadoEn"] is not None

    venta = venta_de(creada["id"])
    assert (venta["estado"], venta["factura"]["estado"]) == ("completada", "emitida")
    assert venta["cliente"]["id"] == cliente.id


def test_el_personal_puede_dejar_la_reserva_pendiente_para_pagar_despues(api, crear_empleado, crear_cliente, viaje):
    empleado, cliente = crear_empleado(), crear_cliente()
    respuesta = api.post("/api/reservas", headers=empleado.headers, json=cuerpo_de_reserva(viaje, "paquete", 2, clienteId=cliente.id))
    assert respuesta.status_code == 201
    assert (respuesta.json()["estado"], respuesta.json()["estadoPago"]) == ("pendiente", "pendiente")
    # El cliente ya puede pagarla desde su cuenta.
    assert respuesta.json()["id"] in [r["id"] for r in api.get("/api/reservas/mias", headers=cliente.headers).json()]


def test_un_cliente_no_reserva_a_nombre_de_otro_ni_registra_cobros(api, crear_cliente, viaje):
    cliente, otro = crear_cliente(), crear_cliente()
    ajena = api.post("/api/reservas", headers=cliente.headers, json=cuerpo_de_reserva(viaje, "paquete", 1, clienteId=otro.id))
    assert ajena.status_code == 403
    con_cobro = api.post("/api/reservas", headers=cliente.headers, json=cuerpo_de_reserva(viaje, "paquete", 1, pago={"metodo": "efectivo"}))
    assert con_cobro.status_code == 403
    assert api.get("/api/reservas/mias", headers=cliente.headers).json() == []


def test_no_se_reserva_a_nombre_de_alguien_del_personal_ni_de_una_cuenta_inactiva(api, admin, crear_empleado, crear_cliente, viaje):
    empleado, cliente, otro_empleado = crear_empleado(), crear_cliente(), crear_empleado()
    a_personal = api.post("/api/reservas", headers=empleado.headers, json=cuerpo_de_reserva(viaje, "paquete", 1, clienteId=otro_empleado.id))
    assert a_personal.status_code == 400

    api.patch(f"/api/usuarios/{cliente.id}/estado", headers=admin, json={"activo": False})
    a_inactivo = api.post("/api/reservas", headers=empleado.headers, json=cuerpo_de_reserva(viaje, "paquete", 1, clienteId=cliente.id))
    assert a_inactivo.status_code == 400


def test_cobro_de_mostrador_sobre_una_reserva_existente(api, crear_empleado, crear_cliente, viaje, reservar, venta_de):
    empleado, cliente = crear_empleado(), crear_cliente()
    reserva_id, _ = reservar(cliente, viaje)

    # Un cliente no puede cobrarse a sí mismo.
    assert api.post(f"/api/reservas/{reserva_id}/pago/manual", headers=cliente.headers, json={"metodo": "efectivo"}).status_code == 403
    # Un método que no existe se rechaza.
    assert api.post(f"/api/reservas/{reserva_id}/pago/manual", headers=empleado.headers, json={"metodo": "bitcoin"}).status_code == 422

    cobro = api.post(f"/api/reservas/{reserva_id}/pago/manual", headers=empleado.headers, json={"metodo": "transferencia", "referencia": "TRX-778"})
    assert cobro.status_code == 200, cobro.text
    reserva = api.get(f"/api/reservas/{reserva_id}", headers=cliente.headers).json()
    assert (reserva["estado"], reserva["estadoPago"], reserva["metodoPago"]) == ("confirmada", "pagado", "transferencia")
    assert venta_de(reserva_id)["estado"] == "completada"

    # No se cobra dos veces.
    assert api.post(f"/api/reservas/{reserva_id}/pago/manual", headers=empleado.headers, json={"metodo": "efectivo"}).status_code == 409


def test_no_se_cobra_una_reserva_cancelada(api, crear_empleado, crear_cliente, viaje, reservar):
    empleado, cliente = crear_empleado(), crear_cliente()
    reserva_id, _ = reservar(cliente, viaje)
    assert api.post(f"/api/reservas/{reserva_id}/cancelar", headers=cliente.headers).status_code == 200
    assert api.post(f"/api/reservas/{reserva_id}/pago/manual", headers=empleado.headers, json={"metodo": "efectivo"}).status_code == 409


def test_no_se_confirma_a_mano_una_reserva_sin_pago(api, crear_empleado, crear_cliente, viaje, reservar):
    empleado, cliente = crear_empleado(), crear_cliente()
    reserva_id, _ = reservar(cliente, viaje)
    confirmar = api.patch(f"/api/reservas/{reserva_id}/estado", headers=empleado.headers, json={"estado": "confirmada"})
    assert confirmar.status_code == 409
    assert "pago" in confirmar.json()["mensaje"]
    # Un estado inventado ni siquiera llega al servicio.
    assert api.patch(f"/api/reservas/{reserva_id}/estado", headers=empleado.headers, json={"estado": "hackeada"}).status_code == 422


def test_el_cliente_cancela_su_solicitud_pero_no_una_reserva_pagada(api, crear_empleado, crear_cliente, viaje, reservar, venta_de):
    empleado, cliente = crear_empleado(), crear_cliente()
    sin_pagar, _ = reservar(cliente, viaje)
    pagada, _ = reservar(cliente, viaje)
    api.post(f"/api/reservas/{pagada}/pago/manual", headers=empleado.headers, json={"metodo": "tarjeta"})

    cancelada = api.post(f"/api/reservas/{sin_pagar}/cancelar", headers=cliente.headers)
    assert cancelada.status_code == 200
    assert api.get(f"/api/reservas/{sin_pagar}", headers=cliente.headers).json()["estado"] == "cancelada"
    assert venta_de(sin_pagar)["estado"] == "cancelada"
    # Cancelar dos veces no falla ni cambia nada.
    assert api.post(f"/api/reservas/{sin_pagar}/cancelar", headers=cliente.headers).status_code == 200

    rechazada = api.post(f"/api/reservas/{pagada}/cancelar", headers=cliente.headers)
    assert rechazada.status_code == 409
    assert "personal" in rechazada.json()["mensaje"]


def test_cancelar_una_reserva_pagada_avisa_que_hay_que_reembolsar(api, crear_empleado, crear_cliente, viaje, reservar, venta_de):
    empleado, cliente = crear_empleado(), crear_cliente()
    reserva_id, _ = reservar(cliente, viaje)
    api.post(f"/api/reservas/{reserva_id}/pago/manual", headers=empleado.headers, json={"metodo": "efectivo"})

    cancelacion = api.patch(f"/api/reservas/{reserva_id}/estado", headers=empleado.headers, json={"estado": "cancelada"})
    assert cancelacion.status_code == 200
    assert cancelacion.json()["requiereReembolso"] is True
    # Sigue constando como pagada (el dinero entró), pero la venta y la factura quedan anuladas.
    reserva = api.get(f"/api/reservas/{reserva_id}", headers=empleado.headers).json()
    assert (reserva["estado"], reserva["estadoPago"]) == ("cancelada", "pagado")
    venta = venta_de(reserva_id)
    assert (venta["estado"], venta["factura"]["estado"]) == ("cancelada", "anulada")


def test_reactivar_una_reserva_pagada_y_cancelada_la_deja_confirmada(api, crear_empleado, crear_cliente, viaje, reservar):
    empleado, cliente = crear_empleado(), crear_cliente()
    reserva_id, _ = reservar(cliente, viaje)
    api.post(f"/api/reservas/{reserva_id}/pago/manual", headers=empleado.headers, json={"metodo": "efectivo"})
    api.patch(f"/api/reservas/{reserva_id}/estado", headers=empleado.headers, json={"estado": "cancelada"})

    assert api.patch(f"/api/reservas/{reserva_id}/estado", headers=empleado.headers, json={"estado": "pendiente"}).status_code == 409
    assert api.patch(f"/api/reservas/{reserva_id}/estado", headers=empleado.headers, json={"estado": "confirmada"}).status_code == 200
    assert api.get(f"/api/reservas/{reserva_id}", headers=empleado.headers).json()["estado"] == "confirmada"


def test_reactivar_una_cancelada_falla_si_sus_plazas_se_vendieron(api, crear_cliente, crear_empleado, viaje, reservar):
    """Regresión: reactivar una reserva cancelada no volvía a comprobar la capacidad y permitía vender de más."""
    empleado, cliente = crear_empleado(), crear_cliente()
    primera, _ = reservar(cliente, viaje, "carta", 9)
    api.post(f"/api/reservas/{primera}/cancelar", headers=cliente.headers)
    for _ in range(20):  # 20 x 9 = 180 plazas: el vuelo queda lleno
        reservar(cliente, viaje, "carta", 9)

    reactivar = api.patch(f"/api/reservas/{primera}/estado", headers=empleado.headers, json={"estado": "pendiente"})
    assert reactivar.status_code == 400
    assert "plaza" in reactivar.json()["mensaje"]
    assert api.get(f"/api/reservas/{primera}", headers=empleado.headers).json()["estado"] == "cancelada"


def test_el_personal_busca_clientes_sin_que_el_texto_actue_como_patron(api, crear_empleado, crear_cliente):
    empleado, cliente = crear_empleado(), crear_cliente()
    por_correo = api.get("/api/clientes", headers=empleado.headers, params={"q": cliente.correo}).json()
    assert [c["id"] for c in por_correo] == [cliente.id]
    por_documento = api.get("/api/clientes", headers=empleado.headers, params={"q": cliente.documento}).json()
    assert [c["id"] for c in por_documento] == [cliente.id]
    # `%` y `_` son comodines de LIKE: buscados literalmente no deben coincidir con todo.
    assert api.get("/api/clientes", headers=empleado.headers, params={"q": "%"}).json() == []
    assert api.get("/api/clientes", headers=empleado.headers, params={"q": "_"}).json() == []
    # Un cliente no puede listar a los demás.
    assert api.get("/api/clientes", headers=cliente.headers).status_code == 403


def test_alta_rapida_de_un_cliente_en_el_mostrador(api, crear_empleado, crear_cliente):
    empleado, existente = crear_empleado(), crear_cliente()
    nuevo = {
        "nombre": "María José", "apellido": "Del Río", "tipoDocumento": "CC", "numeroDocumento": "1098765432",
        "telefono": "3104445566", "correo": "maria.rio@example.com",
    }
    creado = api.post("/api/clientes", headers=empleado.headers, json=nuevo)
    assert creado.status_code == 201, creado.text
    assert creado.json()["correo"] == "maria.rio@example.com"

    # Ni el correo ni el documento se pueden repetir.
    assert api.post("/api/clientes", headers=empleado.headers, json={**nuevo, "numeroDocumento": "1098765433"}).status_code == 409
    assert api.post("/api/clientes", headers=empleado.headers, json={**nuevo, "correo": "otra@example.com"}).status_code == 409
    assert api.post("/api/clientes", headers=empleado.headers, json={**nuevo, "correo": existente.correo, "numeroDocumento": "1098765400"}).status_code == 409
    # Un cliente no da de alta a nadie.
    assert api.post("/api/clientes", headers=existente.headers, json=nuevo).status_code == 403
    # La clave es aleatoria: nadie puede entrar con una que adivine.
    assert api.post("/api/auth/login", json={"correo": "maria.rio@example.com", "contrasena": "Cliente1!"}).status_code == 401
