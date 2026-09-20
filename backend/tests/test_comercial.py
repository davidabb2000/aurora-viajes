"""Ventas, reportes y estadísticas."""


def test_un_cliente_no_puede_registrar_ventas(api, admin, crear_cliente):
    """Regresión: cualquier cliente podía crear una venta «completada» con el descuento que quisiera."""
    producto = api.post("/api/productos", headers=admin, json={"nombre": "Seguro de viaje", "precio": 500000}).json()
    cliente = crear_cliente()
    cuerpo = {"descuento": 99_999_999, "items": [{"tipo": "producto", "id": producto["id"], "cantidad": 2}]}

    assert api.post("/api/ventas", headers=cliente.headers, json=cuerpo).status_code == 403
    assert api.post("/api/ventas", json=cuerpo).status_code == 401

    venta = api.post("/api/ventas", headers=admin, json={"items": cuerpo["items"]})
    assert venta.status_code == 201
    assert venta.json()["total"] == 1_000_000
    assert venta.json()["estado"] == "completada"


def test_las_estadisticas_no_cuentan_las_ventas_canceladas(api, admin, crear_cliente, viaje, reservar):
    def facturacion():
        return api.get("/api/estadisticas", headers=admin).json()["indicadores"]["facturacion"]

    cliente = crear_cliente()
    base = facturacion()
    reserva_id, respuesta = reservar(cliente, viaje)
    assert facturacion() == base + respuesta["montoTotal"]

    api.patch(f"/api/reservas/{reserva_id}/estado", headers=admin, json={"estado": "cancelada"})
    estadisticas = api.get("/api/estadisticas", headers=admin).json()
    assert estadisticas["indicadores"]["facturacion"] == base
    estados = {fila["estado"] for fila in estadisticas["porEstado"]}
    assert "cancelada" in estados  # la venta perdida sigue visible en el desglose por estado


def test_el_reporte_separa_paquetes_y_excluye_canceladas(api, admin, crear_cliente, viaje, reservar):
    cliente = crear_cliente()
    reserva_id, respuesta = reservar(cliente, viaje, "paquete")
    reporte = api.get("/api/reportes/ventas", headers=admin).json()
    assert reporte["resumen"]["porConcepto"]["paquete"] >= respuesta["montoTotal"]

    api.patch(f"/api/reservas/{reserva_id}/estado", headers=admin, json={"estado": "cancelada"})
    despues = api.get("/api/reportes/ventas", headers=admin).json()
    assert despues["total"] == reporte["total"] - respuesta["montoTotal"]


def test_los_reportes_en_archivo_se_generan(api, admin, crear_cliente, viaje, reservar):
    reservar(crear_cliente(), viaje)
    pdf = api.get("/api/reportes/ventas", headers=admin, params={"formato": "pdf"})
    xlsx = api.get("/api/reportes/ventas", headers=admin, params={"formato": "xlsx"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert xlsx.status_code == 200 and xlsx.content.startswith(b"PK")  # un .xlsx es un zip


def test_un_cliente_solo_descarga_sus_facturas(api, crear_cliente, viaje, reservar):
    dueno, intruso = crear_cliente(), crear_cliente()
    reservar(dueno, viaje)
    factura = api.get("/api/facturas", headers=dueno.headers).json()[0]

    assert api.get(f"/api/facturas/{factura['id']}/pdf", headers=dueno.headers).status_code == 200
    assert api.get(f"/api/facturas/{factura['id']}/pdf", headers=intruso.headers).status_code == 403
    assert api.get("/api/facturas", headers=intruso.headers).json() == []


def test_los_clientes_no_ven_estadisticas(api, crear_cliente):
    assert api.get("/api/estadisticas", headers=crear_cliente().headers).status_code == 403
