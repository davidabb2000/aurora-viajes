from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape as xml_escape

import httpx
import unicodedata
from fastapi import APIRouter, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.configuracion import configuracion
from app.dependencias import EmpleadoOAdmin, SesionDep, UsuarioActual
from app.errores import PermisoDenegado, RecursoNoEncontrado
from app.models.biblioteca import Conversacion, Destino, DetalleFactura, DetalleVenta, Factura, Mensaje, PQR, Producto, Reserva, Servicio, User, Venta
from app.schemas.comercial import ChatEntrada, PQRActualizacion, PQREntrada, VentaEntrada
from app.services.recomendaciones import ProveedorNoDisponible, ServicioDeRecomendaciones

router = APIRouter(prefix="/api", tags=["comercial"])


def _dinero(valor: Decimal | float | None) -> float:
    return round(float(valor or 0), 2)


def _venta_dict(venta: Venta) -> dict:
    return {
        "id": venta.id,
        "cliente": {"id": venta.cliente.id, "nombre": f"{venta.cliente.nombre} {venta.cliente.apellido}"},
        "subtotal": _dinero(venta.subtotal),
        "descuento": _dinero(venta.descuento),
        "impuestos": _dinero(venta.impuestos),
        "total": _dinero(venta.total),
        "estado": venta.estado,
        "fecha": venta.creado_en.isoformat(),
        "factura": {"id": venta.factura.id, "numero": venta.factura.numero, "estado": venta.factura.estado} if venta.factura else None,
        "detalles": [{"id": d.id, "tipo": "producto" if d.producto_id else "servicio", "nombre": d.nombre, "cantidad": d.cantidad, "precioUnitario": _dinero(d.precio_unitario), "subtotal": _dinero(d.subtotal)} for d in venta.detalles],
    }


async def _venta_con_relaciones(sesion: SesionDep, venta_id: int) -> Venta:
    venta = await sesion.scalar(
        select(Venta).options(selectinload(Venta.detalles), selectinload(Venta.factura), selectinload(Venta.cliente)).where(Venta.id == venta_id)
    )
    if not venta:
        raise RecursoNoEncontrado("una venta", venta_id)
    return venta


@router.post("/ventas", status_code=201)
async def crear_venta(payload: VentaEntrada, sesion: SesionDep, usuario: UsuarioActual):
    cliente_id = payload.cliente_id or usuario.id
    cliente = await sesion.get(User, cliente_id)
    if not cliente:
        raise RecursoNoEncontrado("un cliente", cliente_id)
    if payload.cliente_id and usuario.role.nombre == "cliente":
        raise PermisoDenegado("Un cliente solo puede registrar ventas a su nombre.")

    detalles = []
    subtotal = Decimal("0")
    for item in payload.items:
        catalogo = Producto if item.tipo == "producto" else Servicio
        elemento = await sesion.get(catalogo, item.id)
        if not elemento or not elemento.activo:
            raise RecursoNoEncontrado(f"un {item.tipo}", item.id)
        precio = Decimal(str(elemento.precio))
        importe = precio * item.cantidad
        subtotal += importe
        detalles.append(DetalleVenta(producto_id=elemento.id if item.tipo == "producto" else None, servicio_id=elemento.id if item.tipo == "servicio" else None, nombre=elemento.nombre, cantidad=item.cantidad, precio_unitario=precio, subtotal=importe))

    descuento = min(payload.descuento, subtotal)
    base = subtotal - descuento
    impuestos = (base * payload.impuesto_porcentaje / Decimal("100")).quantize(Decimal("0.01"))
    venta = Venta(cliente_id=cliente_id, usuario_id=usuario.id, subtotal=subtotal, descuento=descuento, impuestos=impuestos, total=base + impuestos, estado="completada", detalles=detalles)
    sesion.add(venta)
    await sesion.flush()
    factura = Factura(venta_id=venta.id, numero=f"AUR-{datetime.now(timezone.utc):%Y%m%d}-{venta.id:06d}", estado="emitida")
    factura.detalles = [DetalleFactura(nombre=detalle.nombre, cantidad=detalle.cantidad, precio_unitario=detalle.precio_unitario, subtotal=detalle.subtotal) for detalle in detalles]
    sesion.add(factura)
    await sesion.commit()
    venta = await _venta_con_relaciones(sesion, venta.id)
    return _venta_dict(venta)


@router.get("/ventas")
async def listar_ventas(sesion: SesionDep, usuario: UsuarioActual, desde: date | None = None, hasta: date | None = None, estado: str | None = None, cliente_id: int | None = None, producto_id: int | None = None, servicio_id: int | None = None, valor_minimo: Decimal | None = Query(default=None, ge=0), valor_maximo: Decimal | None = Query(default=None, ge=0)):
    consulta = select(Venta).options(selectinload(Venta.detalles), selectinload(Venta.factura), selectinload(Venta.cliente)).order_by(Venta.creado_en.desc())
    if usuario.role.nombre == "cliente":
        consulta = consulta.where(Venta.cliente_id == usuario.id)
    elif cliente_id:
        consulta = consulta.where(Venta.cliente_id == cliente_id)
    if desde:
        consulta = consulta.where(Venta.creado_en >= datetime.combine(desde, time.min, tzinfo=timezone.utc))
    if hasta:
        consulta = consulta.where(Venta.creado_en < datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=timezone.utc))
    if estado:
        consulta = consulta.where(Venta.estado == estado)
    if producto_id or servicio_id:
        consulta = consulta.join(Venta.detalles)
        if producto_id:
            consulta = consulta.where(DetalleVenta.producto_id == producto_id)
        if servicio_id:
            consulta = consulta.where(DetalleVenta.servicio_id == servicio_id)
    if valor_minimo is not None:
        consulta = consulta.where(Venta.total >= valor_minimo)
    if valor_maximo is not None:
        consulta = consulta.where(Venta.total <= valor_maximo)
    ventas = (await sesion.scalars(consulta)).all()
    return [_venta_dict(venta) for venta in ventas]


@router.get("/ventas/{venta_id}")
async def consultar_venta(venta_id: int, sesion: SesionDep, usuario: UsuarioActual):
    venta = await _venta_con_relaciones(sesion, venta_id)
    if usuario.role.nombre == "cliente" and venta.cliente_id != usuario.id:
        raise PermisoDenegado("No tiene permiso para consultar esta venta.")
    return _venta_dict(venta)


@router.get("/facturas")
async def listar_facturas(sesion: SesionDep, usuario: UsuarioActual, numero: str | None = None, cliente_id: int | None = None, desde: date | None = None, hasta: date | None = None):
    consulta = select(Factura).join(Factura.venta).options(selectinload(Factura.venta).selectinload(Venta.cliente), selectinload(Factura.venta).selectinload(Venta.detalles)).order_by(Factura.creado_en.desc())
    if usuario.role.nombre == "cliente":
        consulta = consulta.where(Venta.cliente_id == usuario.id)
    elif cliente_id:
        consulta = consulta.where(Venta.cliente_id == cliente_id)
    if numero:
        consulta = consulta.where(Factura.numero.ilike(f"%{numero}%"))
    if desde:
        consulta = consulta.where(Factura.creado_en >= datetime.combine(desde, time.min, tzinfo=timezone.utc))
    if hasta:
        consulta = consulta.where(Factura.creado_en < datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=timezone.utc))
    facturas = (await sesion.scalars(consulta)).all()
    return [{"id": factura.id, "numero": factura.numero, "fecha": factura.creado_en.isoformat(), "estado": factura.estado, "venta": _venta_dict(factura.venta)} for factura in facturas]


def _filas_reporte(ventas: list[Venta]) -> list[list[object]]:
    filas = [["Venta", "Fecha", "Cliente", "Concepto", "Cantidad", "Valor unitario", "Subtotal", "Total venta", "Estado"]]
    for venta in ventas:
        for detalle in venta.detalles:
            filas.append([
                venta.id,
                venta.creado_en.strftime("%Y-%m-%d %H:%M"),
                f"{venta.cliente.nombre} {venta.cliente.apellido}",
                detalle.nombre,
                detalle.cantidad,
                _dinero(detalle.precio_unitario),
                _dinero(detalle.subtotal),
                _dinero(venta.total),
                venta.estado,
            ])
    return filas


def _concepto_de(nombre: str) -> str:
    """Clasifica una linea de factura en vuelo, hotel o excursion.

    Las lineas las escribe el modulo de reservas con un prefijo fijo, asi que
    basta mirar la primera palabra. Lo que no encaje se agrupa como "otros"
    para que ningun importe se pierda del resumen.
    """
    limpio = unicodedata.normalize("NFKD", nombre or "").encode("ascii", "ignore").decode("ascii").lower()
    if limpio.startswith("vuelo"):
        return "vuelo"
    if limpio.startswith("hotel") or limpio.startswith("alojamiento"):
        return "hotel"
    if limpio.startswith("excursion"):
        return "excursiones"
    return "otros"


def _resumen_de_ventas(ventas: list[Venta]) -> dict:
    """Totales que acompanan al detalle en los reportes y en el panel."""
    lineas = [detalle for venta in ventas for detalle in venta.detalles]
    total = round(sum(_dinero(venta.total) for venta in ventas), 2)
    por_concepto: dict[str, float] = {"vuelo": 0.0, "hotel": 0.0, "excursiones": 0.0, "otros": 0.0}
    for detalle in lineas:
        por_concepto[_concepto_de(detalle.nombre)] += _dinero(detalle.subtotal)
    por_estado: dict[str, dict] = {}
    for venta in ventas:
        registro = por_estado.setdefault(venta.estado, {"cantidad": 0, "total": 0.0})
        registro["cantidad"] += 1
        registro["total"] += _dinero(venta.total)
    pasajeros = sum(detalle.cantidad for detalle in lineas if _concepto_de(detalle.nombre) == "vuelo")
    return {
        "ventas": len(ventas),
        "lineas": len(lineas),
        "total": total,
        "ticketPromedio": round(total / len(ventas), 2) if ventas else 0.0,
        "pasajeros": pasajeros,
        "porConcepto": {clave: round(valor, 2) for clave, valor in por_concepto.items()},
        "porEstado": {clave: {"cantidad": valor["cantidad"], "total": round(valor["total"], 2)} for clave, valor in por_estado.items()},
    }


def _celda_xlsx(valor: object, columna: str, fila: int, estilo: int = 0) -> str:
    referencia = f"{columna}{fila}"
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return f'<c r="{referencia}" s="{estilo}" t="n"><v>{valor}</v></c>'
    texto = xml_escape(str(valor), {"\"": "&quot;"})
    return f'<c r="{referencia}" s="{estilo}" t="inlineStr"><is><t>{texto}</t></is></c>'


# Estilos del libro: 0 normal, 1 titulo, 2 etiqueta, 3 etiqueta sobre lavanda,
# 4 dinero sobre lavanda, 5 encabezado de tabla, 6 celda zebra, 7 dinero zebra,
# 8 dinero normal, 9 fila de totales, 10 dinero en la fila de totales.
_ESTILOS_XLSX = (
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<numFmts count="1"><numFmt numFmtId="164" formatCode="&quot;$&quot;#,##0.00"/></numFmts>'
    '<fonts count="4">'
    '<font><sz val="10"/><name val="Aptos"/></font>'
    '<font><b/><sz val="15"/><color rgb="FFFFFFFF"/><name val="Aptos Display"/></font>'
    '<font><b/><sz val="10"/><name val="Aptos"/></font>'
    '<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Aptos"/></font>'
    '</fonts>'
    '<fills count="5">'
    '<fill><patternFill patternType="none"/></fill>'
    '<fill><patternFill patternType="gray125"/></fill>'
    '<fill><patternFill patternType="solid"><fgColor rgb="FF3F2FA8"/></patternFill></fill>'
    '<fill><patternFill patternType="solid"><fgColor rgb="FFEFEDFC"/></patternFill></fill>'
    '<fill><patternFill patternType="solid"><fgColor rgb="FF0E9E92"/></patternFill></fill>'
    '</fills>'
    '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
    '<cellXfs count="11">'
    '<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'
    '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" applyAlignment="1"><alignment vertical="center"/></xf>'
    '<xf numFmtId="0" fontId="2" fillId="0" borderId="0"/>'
    '<xf numFmtId="0" fontId="2" fillId="3" borderId="0"/>'
    '<xf numFmtId="164" fontId="2" fillId="3" borderId="0"/>'
    '<xf numFmtId="0" fontId="3" fillId="2" borderId="0" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf>'
    '<xf numFmtId="0" fontId="0" fillId="3" borderId="0"/>'
    '<xf numFmtId="164" fontId="0" fillId="3" borderId="0"/>'
    '<xf numFmtId="164" fontId="0" fillId="0" borderId="0"/>'
    '<xf numFmtId="0" fontId="3" fillId="4" borderId="0"/>'
    '<xf numFmtId="164" fontId="3" fillId="4" borderId="0"/>'
    '</cellXfs></styleSheet>'
)


def _hoja_resumen_xlsx(periodo: str, resumen: dict, por_dia: list[tuple[str, int, float]]) -> str:
    """Primera hoja del libro: indicadores y ventas por fecha.

    Antes el Excel era una sola tabla de detalle; quien lo abria tenia que
    sumar a mano para saber cuanto se facturo.
    """
    filas = [
        '<row r="1" ht="28" customHeight="1"><c r="A1" s="1" t="inlineStr"><is><t>Aurora Viajes | Resumen comercial</t></is></c></row>',
        f'<row r="2"><c r="A2" s="2" t="inlineStr"><is><t>Periodo</t></is></c>{_celda_xlsx(periodo, "B", 2, 3)}</row>',
        '<row r="3"/>',
        f'<row r="4">{_celda_xlsx("Indicador", "A", 4, 5)}{_celda_xlsx("Valor", "B", 4, 5)}</row>',
    ]
    indicadores = [
        ("Ventas registradas", resumen["ventas"], 6),
        ("Lineas facturadas", resumen["lineas"], 6),
        ("Pasajeros", resumen["pasajeros"], 6),
        ("Total facturado", resumen["total"], 7),
        ("Ticket promedio", resumen["ticketPromedio"], 7),
        ("Ingresos por vuelos", resumen["porConcepto"]["vuelo"], 7),
        ("Ingresos por hoteles", resumen["porConcepto"]["hotel"], 7),
        ("Ingresos por excursiones", resumen["porConcepto"]["excursiones"], 7),
        ("Otros ingresos", resumen["porConcepto"]["otros"], 7),
    ]
    numero = 5
    for etiqueta, valor, estilo in indicadores:
        filas.append(f'<row r="{numero}">{_celda_xlsx(etiqueta, "A", numero, 2)}{_celda_xlsx(valor, "B", numero, estilo)}</row>')
        numero += 1

    numero += 1
    filas.append(f'<row r="{numero}">{_celda_xlsx("Fecha", "A", numero, 5)}{_celda_xlsx("Ventas", "B", numero, 5)}{_celda_xlsx("Total", "C", numero, 5)}</row>')
    numero += 1
    for fecha, cantidad, importe in por_dia:
        filas.append(f'<row r="{numero}">{_celda_xlsx(fecha, "A", numero, 0)}{_celda_xlsx(cantidad, "B", numero, 0)}{_celda_xlsx(importe, "C", numero, 8)}</row>')
        numero += 1
    if por_dia:
        total_dias = round(sum(importe for _, _, importe in por_dia), 2)
        cantidad_total = sum(cantidad for _, cantidad, _ in por_dia)
        filas.append(f'<row r="{numero}">{_celda_xlsx("TOTAL", "A", numero, 9)}{_celda_xlsx(cantidad_total, "B", numero, 9)}{_celda_xlsx(total_dias, "C", numero, 10)}</row>')

    return (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<cols><col min="1" max="1" width="28" customWidth="1"/><col min="2" max="3" width="18" customWidth="1"/></cols>'
        f'<sheetData>{"".join(filas)}</sheetData><mergeCells count="1"><mergeCell ref="A1:C1"/></mergeCells></worksheet>'
    )


def _xlsx(filas: list[list[object]], periodo: str, resumen: dict, por_dia: list[tuple[str, int, float]]) -> bytes:
    columnas = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]
    encabezado = filas[0]
    datos = filas[1:]
    total = resumen["total"]

    filas_xml = [
        '<row r="1" ht="28" customHeight="1"><c r="A1" s="1" t="inlineStr"><is><t>Aurora Viajes | Reporte de ventas</t></is></c></row>',
        f'<row r="2"><c r="A2" s="2" t="inlineStr"><is><t>Periodo</t></is></c>{_celda_xlsx(periodo, "B", 2, 3)}<c r="D2" s="2" t="inlineStr"><is><t>Registros</t></is></c>{_celda_xlsx(len(datos), "E", 2, 3)}<c r="G2" s="2" t="inlineStr"><is><t>Total facturado</t></is></c>{_celda_xlsx(total, "H", 2, 4)}</row>',
        '<row r="3"/>',
        f'<row r="4">{"".join(_celda_xlsx(valor, columna, 4, 5) for columna, valor in zip(columnas, encabezado))}</row>',
    ]
    for numero, fila in enumerate(datos, 5):
        celdas = []
        for indice, (valor, columna) in enumerate(zip(fila, columnas)):
            zebra = numero % 2 == 1
            dinero = indice in (5, 6, 7)
            estilo = (7 if zebra else 8) if dinero else (6 if zebra else 0)
            celdas.append(_celda_xlsx(valor, columna, numero, estilo))
        filas_xml.append(f'<row r="{numero}">{"".join(celdas)}</row>')

    ultima_fila = max(4, len(datos) + 4)
    if datos:
        # Fila de totales: el detalle ya no obliga a sumar a mano.
        fila_total = ultima_fila + 1
        celdas_total = [
            _celda_xlsx("TOTAL", "A", fila_total, 9),
            _celda_xlsx("", "B", fila_total, 9),
            _celda_xlsx(f"{resumen['ventas']} venta(s)", "C", fila_total, 9),
            _celda_xlsx(f"{resumen['lineas']} linea(s)", "D", fila_total, 9),
            _celda_xlsx(sum(int(fila[4] or 0) for fila in datos), "E", fila_total, 9),
            _celda_xlsx("", "F", fila_total, 9),
            _celda_xlsx(round(sum(float(fila[6] or 0) for fila in datos), 2), "G", fila_total, 10),
            _celda_xlsx(total, "H", fila_total, 10),
            _celda_xlsx("", "I", fila_total, 9),
        ]
        filas_xml.append(f'<row r="{fila_total}">{"".join(celdas_total)}</row>')

    contenido = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        '<cols><col min="1" max="1" width="10" customWidth="1"/><col min="2" max="2" width="19" customWidth="1"/><col min="3" max="3" width="25" customWidth="1"/><col min="4" max="4" width="32" customWidth="1"/><col min="5" max="5" width="11" customWidth="1"/><col min="6" max="8" width="16" customWidth="1"/><col min="9" max="9" width="15" customWidth="1"/></cols>'
        f'<sheetData>{"".join(filas_xml)}</sheetData><mergeCells count="1"><mergeCell ref="A1:I1"/></mergeCells><autoFilter ref="A4:I{ultima_fila}"/></worksheet>'
    )
    libro = '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Resumen" sheetId="1" r:id="rId1"/><sheet name="Ventas" sheetId="2" r:id="rId2"/></sheets></workbook>'
    relaciones = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '</Relationships>'
    )
    tipos = (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '</Types>'
    )
    salida = BytesIO()
    with ZipFile(salida, "w", ZIP_DEFLATED) as archivo:
        archivo.writestr("[Content_Types].xml", tipos)
        archivo.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archivo.writestr("xl/workbook.xml", libro)
        archivo.writestr("xl/_rels/workbook.xml.rels", relaciones)
        archivo.writestr("xl/worksheets/sheet1.xml", _hoja_resumen_xlsx(periodo, resumen, por_dia))
        archivo.writestr("xl/worksheets/sheet2.xml", contenido)
        archivo.writestr("xl/styles.xml", _ESTILOS_XLSX)
    return salida.getvalue()


# Anchos de Helvetica y Helvetica-Bold en milesimas de punto para ASCII 32..126.
# Permiten medir el texto de verdad: sin esto no se puede alinear a la derecha
# ni partir una linea por el ancho real de la columna.
_ANCHOS_HELVETICA = (
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
)
_ANCHOS_HELVETICA_NEGRITA = (
    278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611,
    975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556,
    333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611,
    611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584,
)


def _ancho_caracter(caracter: str, negrita: bool) -> int:
    tabla = _ANCHOS_HELVETICA_NEGRITA if negrita else _ANCHOS_HELVETICA
    codigo = ord(caracter)
    if 32 <= codigo <= 126:
        return tabla[codigo - 32]
    # Las vocales acentuadas miden como su letra base en las fuentes Helvetica.
    base = unicodedata.normalize("NFKD", caracter)[:1]
    codigo_base = ord(base) if base else 0
    if 32 <= codigo_base <= 126:
        return tabla[codigo_base - 32]
    return 556


def _ancho_texto(texto: str, tamano: float, negrita: bool = False) -> float:
    return sum(_ancho_caracter(caracter, negrita) for caracter in texto) * tamano / 1000


def _pdf_normalizar(texto: object) -> str:
    """Deja el texto en el juego WinAnsi, que es el que declara la fuente.

    Antes se pasaba todo por ASCII y cada tilde se convertia en un '?': un
    cliente llamado "Martin Nunez" salia en la factura como "Marti?n Nu?n?ez".
    """
    cadena = str(texto)
    try:
        cadena.encode("cp1252")
        return cadena
    except UnicodeEncodeError:
        pass
    salida = []
    for caracter in cadena:
        try:
            caracter.encode("cp1252")
            salida.append(caracter)
        except UnicodeEncodeError:
            # Se conserva la letra base y se descarta lo que la fuente no tiene.
            reemplazo = unicodedata.normalize("NFKD", caracter).encode("cp1252", "ignore").decode("cp1252")
            salida.append(reemplazo or "?")
    return "".join(salida)


def _pdf_text(texto: object, ancho_disponible: float, tamano: float = 7.5, negrita: bool = False) -> list[str]:
    """Parte el texto en lineas que caben en el ancho dado."""
    limpio = _pdf_normalizar(texto)
    palabras = limpio.split()
    lineas: list[str] = []
    actual = ""
    for palabra in palabras or [""]:
        tentativa = f"{actual} {palabra}".strip()
        if actual and _ancho_texto(tentativa, tamano, negrita) > ancho_disponible:
            lineas.append(actual)
            actual = palabra
        else:
            actual = tentativa
    if actual or not lineas:
        lineas.append(actual)
    return lineas


def _pdf_escapar(texto: object) -> str:
    limpio = _pdf_normalizar(texto)
    return limpio.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


_TINTA = (0.10, 0.09, 0.20)
_INDIGO = (0.247, 0.184, 0.659)
_INDIGO_OSCURO = (0.141, 0.102, 0.388)
_LAVANDA = (0.937, 0.929, 0.988)
_LAVANDA_SUAVE = (0.969, 0.965, 0.996)
_AQUA = (0.055, 0.620, 0.573)
_GRIS = (0.42, 0.40, 0.54)


def _pdf_documento(
    titulo: str,
    subtitulo: str,
    columnas: list[tuple],
    filas: list[list[object]],
    resumen: list[tuple[str, object]],
    bloques: list[tuple[str, list[tuple[str, object]]]] | None = None,
    totales: list[object] | None = None,
    notas: str | None = None,
) -> bytes:
    """Arma el PDF de un reporte o una factura.

    columnas admite (nombre, ancho) o (nombre, ancho, alineacion), donde la
    alineacion es "izq" o "der". bloques dibuja fichas de datos (emisor,
    cliente) sobre la tabla y totales cierra el detalle con una fila destacada.
    """
    ancho_pagina, alto_pagina, margen = 612, 792, 40
    ancho_util = ancho_pagina - margen * 2
    paginas: list[list[str]] = []
    comandos: list[str] = []
    y = 0.0
    columnas = [(nombre, ancho, alineacion[0] if alineacion else "izq") for nombre, ancho, *alineacion in columnas]
    ancho_tabla = sum(ancho for _, ancho, _ in columnas)
    generado = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def texto(valor: object, x: float, posicion_y: float, tamano: float = 9, negrita: bool = False, color: tuple[float, float, float] = _TINTA) -> None:
        fuente = "/F2" if negrita else "/F1"
        comandos.append(f"{color[0]} {color[1]} {color[2]} rg BT {fuente} {tamano} Tf {x:.1f} {posicion_y:.1f} Td ({_pdf_escapar(valor)}) Tj ET")

    def texto_derecha(valor: object, x_derecha: float, posicion_y: float, tamano: float = 9, negrita: bool = False, color: tuple[float, float, float] = _TINTA) -> None:
        ancho = _ancho_texto(_pdf_normalizar(valor), tamano, negrita)
        texto(valor, x_derecha - ancho, posicion_y, tamano, negrita, color)

    def rectangulo(x: float, posicion_y: float, ancho: float, alto: float, color: tuple[float, float, float]) -> None:
        comandos.append(f"{color[0]} {color[1]} {color[2]} rg {x:.1f} {posicion_y:.1f} {ancho:.1f} {alto:.1f} re f")

    def nueva_pagina() -> None:
        nonlocal comandos, y
        if comandos:
            paginas.append(comandos)
        comandos = []
        rectangulo(0, 0, ancho_pagina, alto_pagina, (0.995, 0.995, 1))
        # Cabecera en dos tonos, con un filo aqua que remata la banda.
        rectangulo(0, 700, ancho_pagina, 92, _INDIGO_OSCURO)
        rectangulo(0, 700, ancho_pagina * 0.62, 92, _INDIGO)
        rectangulo(0, 697, ancho_pagina, 3, _AQUA)
        texto("AURORA VIAJES", margen, 762, 10, True, (0.70, 0.94, 0.92))
        texto(titulo, margen, 734, 20, True, (1, 1, 1))
        texto(subtitulo, margen, 714, 9, False, (0.85, 0.86, 0.97))
        texto_derecha(f"Generado: {generado}", ancho_pagina - margen, 762, 8, False, (0.80, 0.82, 0.96))
        y = 672

    def dibujar_encabezados() -> None:
        nonlocal y
        x = margen
        rectangulo(margen, y - 5, ancho_tabla, 22, _INDIGO)
        for nombre, ancho, alineacion in columnas:
            if alineacion == "der":
                texto_derecha(nombre, x + ancho - 5, y + 3, 8, True, (1, 1, 1))
            else:
                texto(nombre, x + 5, y + 3, 8, True, (1, 1, 1))
            x += ancho
        y -= 22

    nueva_pagina()

    # Fichas de datos (emisor, cliente...) antes del resumen.
    for etiqueta_bloque, campos in bloques or []:
        alto_bloque = 26 + len(campos) * 12
        if y - alto_bloque < 90:
            nueva_pagina()
        rectangulo(margen, y - alto_bloque + 8, ancho_util, alto_bloque, _LAVANDA)
        texto(etiqueta_bloque.upper(), margen + 10, y - 8, 7.5, True, _INDIGO)
        linea_y = y - 22
        for etiqueta, valor in campos:
            texto(f"{etiqueta}:", margen + 10, linea_y, 8, True, _GRIS)
            texto(valor, margen + 110, linea_y, 8, False, _TINTA)
            linea_y -= 12
        y -= alto_bloque + 8

    if resumen:
        tarjeta_ancho = (ancho_tabla - 6 * max(len(resumen) - 1, 0)) / max(len(resumen), 1)
        for indice, (etiqueta, valor) in enumerate(resumen):
            x = margen + indice * (tarjeta_ancho + 6)
            rectangulo(x, y - 42, tarjeta_ancho, 38, _LAVANDA)
            rectangulo(x, y - 42, 2.5, 38, _AQUA)
            texto(etiqueta.upper(), x + 8, y - 18, 7, True, _GRIS)
            texto(valor, x + 8, y - 35, 12, True, _INDIGO)
        y -= 62

    dibujar_encabezados()
    for indice_fila, fila in enumerate(filas):
        envueltas = [_pdf_text(valor, ancho - 10) for (_, ancho, _), valor in zip(columnas, fila)]
        alto_fila = max(20, max((len(lineas) for lineas in envueltas), default=1) * 10 + 9)
        if y - alto_fila < 60:
            nueva_pagina()
            dibujar_encabezados()
            envueltas = [_pdf_text(valor, ancho - 10) for (_, ancho, _), valor in zip(columnas, fila)]
        if indice_fila % 2 == 0:
            rectangulo(margen, y - alto_fila + 5, ancho_tabla, alto_fila, _LAVANDA_SUAVE)
        x = margen
        for (_, ancho, alineacion), lineas in zip(columnas, envueltas):
            for indice_linea, linea in enumerate(lineas):
                if alineacion == "der":
                    texto_derecha(linea, x + ancho - 5, y - 9 - indice_linea * 10, 7.5)
                else:
                    texto(linea, x + 5, y - 9 - indice_linea * 10, 7.5)
            x += ancho
        y -= alto_fila

    if totales:
        if y - 24 < 60:
            nueva_pagina()
            dibujar_encabezados()
        rectangulo(margen, y - 19, ancho_tabla, 24, _INDIGO)
        x = margen
        for (_, ancho, alineacion), valor in zip(columnas, totales):
            if valor not in (None, ""):
                if alineacion == "der":
                    texto_derecha(valor, x + ancho - 5, y - 11, 8.5, True, (1, 1, 1))
                else:
                    texto(valor, x + 5, y - 11, 8.5, True, (1, 1, 1))
            x += ancho
        y -= 30

    if notas:
        for linea in _pdf_text(notas, ancho_util - 20, 8):
            if y - 14 < 60:
                nueva_pagina()
            texto(linea, margen, y - 6, 8, False, _GRIS)
            y -= 11

    paginas.append(comandos)

    # El pie se escribe al final porque solo aqui se sabe cuantas paginas hay.
    for numero, comandos_pagina in enumerate(paginas, 1):
        comandos = comandos_pagina
        rectangulo(margen, 44, ancho_tabla if ancho_tabla else ancho_util, 0.7, (0.85, 0.84, 0.93))
        texto("Aurora Viajes S.A.S. | contacto@auroraviajes.com | +57 350 357 6793", margen, 32, 7.5, False, _GRIS)
        texto_derecha(f"Pagina {numero} de {len(paginas)}", ancho_pagina - margen, 32, 7.5, True, _INDIGO)

    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    referencias_paginas = []
    for comandos_pagina in paginas:
        contenido = "BT /F1 9 Tf ET\n" + "\n".join(comandos_pagina)
        datos_contenido = contenido.encode("cp1252", "replace")
        objeto_contenido = b"<< /Length " + str(len(datos_contenido)).encode("ascii") + b" >>\nstream\n" + datos_contenido + b"\nendstream"
        indice_contenido = len(objetos) + 1
        objetos.append(objeto_contenido)
        indice_pagina = len(objetos) + 1
        objetos.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {ancho_pagina} {alto_pagina}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {indice_contenido} 0 R >>".encode("ascii"))
        referencias_paginas.append(f"{indice_pagina} 0 R")
    objetos[1] = f"<< /Type /Pages /Kids [{ ' '.join(referencias_paginas) }] /Count {len(referencias_paginas)} >>".encode("ascii")
    salida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for indice, objeto in enumerate(objetos, 1):
        offsets.append(len(salida))
        salida.extend(f"{indice} 0 obj\n".encode("ascii"))
        salida.extend(objeto)
        salida.extend(b"\nendobj\n")
    xref = len(salida)
    salida.extend(f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode("ascii"))
    salida.extend("".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode("ascii"))
    salida.extend(f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return bytes(salida)


@router.get("/reportes/ventas")
async def reporte_ventas(
    sesion: SesionDep,
    usuario: EmpleadoOAdmin,
    fecha: date | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    formato: str = Query(default="json", pattern="^(json|xlsx|pdf)$"),
):
    """Reporte de ventas de un dia o de un rango.

    Antes solo aceptaba un dia suelto, de modo que un cierre de mes obligaba a
    descargar treinta archivos. `fecha` se mantiene por compatibilidad.
    """
    if fecha is not None:
        inicio_dia, fin_dia = fecha, fecha
    else:
        fin_dia = hasta or datetime.now(timezone.utc).date()
        inicio_dia = desde or fin_dia
    if inicio_dia > fin_dia:
        inicio_dia, fin_dia = fin_dia, inicio_dia
    inicio = datetime.combine(inicio_dia, time.min, tzinfo=timezone.utc)
    fin = datetime.combine(fin_dia + timedelta(days=1), time.min, tzinfo=timezone.utc)

    ventas = (await sesion.scalars(
        select(Venta)
        .options(selectinload(Venta.detalles), selectinload(Venta.cliente))
        .where(Venta.creado_en >= inicio, Venta.creado_en < fin)
        .order_by(Venta.creado_en.asc())
    )).all()
    filas = _filas_reporte(ventas)
    resumen = _resumen_de_ventas(ventas)
    total = resumen["total"]
    periodo = inicio_dia.isoformat() if inicio_dia == fin_dia else f"{inicio_dia.isoformat()} a {fin_dia.isoformat()}"
    nombre_archivo = f"ventas-{inicio_dia}" if inicio_dia == fin_dia else f"ventas-{inicio_dia}_{fin_dia}"

    agrupado: dict[str, list] = {}
    for venta in ventas:
        clave = venta.creado_en.date().isoformat()
        registro = agrupado.setdefault(clave, [0, 0.0])
        registro[0] += 1
        registro[1] += _dinero(venta.total)
    por_dia = [(clave, valor[0], round(valor[1], 2)) for clave, valor in sorted(agrupado.items())]

    if formato == "xlsx":
        return StreamingResponse(
            BytesIO(_xlsx(filas, periodo, resumen, por_dia)),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={nombre_archivo}.xlsx"},
        )
    if formato == "pdf":
        columnas = [
            ("Venta", 34), ("Fecha", 62), ("Cliente", 92), ("Concepto", 106), ("Cant.", 32, "der"),
            ("Unitario", 52, "der"), ("Subtotal", 52, "der"), ("Total", 56, "der"), ("Estado", 46),
        ]
        filas_pdf = [
            [fila[0], fila[1], fila[2], fila[3], fila[4], f"${fila[5]:,.2f}", f"${fila[6]:,.2f}", f"${fila[7]:,.2f}", fila[8]]
            for fila in filas[1:]
        ]
        totales = [
            "TOTAL", "", f"{resumen['ventas']} venta(s)", f"{resumen['lineas']} linea(s)",
            str(sum(int(fila[4] or 0) for fila in filas[1:])), "",
            f"${sum(float(fila[6] or 0) for fila in filas[1:]):,.2f}", f"${total:,.2f}", "",
        ]
        conceptos = resumen["porConcepto"]
        notas = (
            f"Composicion de los ingresos: vuelos ${conceptos['vuelo']:,.2f} | hoteles ${conceptos['hotel']:,.2f} | "
            f"excursiones ${conceptos['excursiones']:,.2f} | otros ${conceptos['otros']:,.2f}. "
            f"Ticket promedio ${resumen['ticketPromedio']:,.2f} sobre {resumen['ventas']} venta(s)."
        )
        documento = _pdf_documento(
            "Reporte de ventas",
            f"Periodo: {periodo} | Aurora Viajes",
            columnas,
            filas_pdf,
            [("Ventas", resumen["ventas"]), ("Lineas", resumen["lineas"]), ("Pasajeros", resumen["pasajeros"]), ("Ticket medio", f"${resumen['ticketPromedio']:,.2f}"), ("Total", f"${total:,.2f}")],
            totales=totales,
            notas=notas,
        )
        return Response(documento, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={nombre_archivo}.pdf"})
    return {
        "fecha": str(inicio_dia),
        "desde": str(inicio_dia),
        "hasta": str(fin_dia),
        "ventas": [_venta_dict(venta) for venta in ventas],
        "total": total,
        "cantidad": len(ventas),
        "resumen": resumen,
        "porDia": [{"fecha": clave, "ventas": cantidad, "total": importe} for clave, cantidad, importe in por_dia],
    }


@router.get("/facturas/{factura_id}/pdf")
async def descargar_factura(factura_id: int, sesion: SesionDep, usuario: UsuarioActual):
    factura = await sesion.scalar(select(Factura).options(selectinload(Factura.detalles), selectinload(Factura.venta).selectinload(Venta.cliente)).where(Factura.id == factura_id))
    if not factura:
        raise RecursoNoEncontrado("una factura", factura_id)
    if usuario.role.nombre == "cliente" and factura.venta.cliente_id != usuario.id:
        raise PermisoDenegado("No tiene permiso para descargar esta factura.")
    venta = factura.venta
    cliente = venta.cliente
    filas_pdf = [
        [detalle.nombre, detalle.cantidad, f"${_dinero(detalle.precio_unitario):,.2f}", f"${_dinero(detalle.subtotal):,.2f}"]
        for detalle in factura.detalles
    ]
    columnas = [("Concepto", 247), ("Cant.", 55, "der"), ("Precio unitario", 110, "der"), ("Subtotal", 120, "der")]
    totales = ["TOTAL A PAGAR", str(sum(detalle.cantidad for detalle in factura.detalles)), "", f"${_dinero(venta.total):,.2f}"]
    # La factura ahora identifica a quien emite y a quien se le cobra: antes
    # solo llevaba el nombre del cliente metido en el subtitulo.
    bloques = [
        ("Emisor", [
            ("Razon social", "Aurora Viajes S.A.S."),
            ("NIT", "901.455.783-1"),
            ("Direccion", "Medellin, Colombia"),
            ("Contacto", "contacto@auroraviajes.com | +57 350 357 6793"),
        ]),
        ("Cliente", [
            ("Nombre", f"{cliente.nombre} {cliente.apellido}"),
            ("Documento", getattr(cliente, "numero_documento", None) or "No registrado"),
            ("Correo", cliente.correo),
            ("Telefono", getattr(cliente, "telefono", None) or "No registrado"),
        ]),
        ("Factura", [
            ("Numero", factura.numero),
            ("Fecha de emision", factura.creado_en.strftime("%Y-%m-%d %H:%M")),
            ("Estado", factura.estado),
            ("Venta asociada", f"#{venta.id} ({venta.estado})"),
        ]),
    ]
    documento = _pdf_documento(
        "Factura de venta",
        f"{factura.numero} | Cliente: {cliente.nombre} {cliente.apellido}",
        columnas,
        filas_pdf,
        [
            ("Subtotal", f"${_dinero(venta.subtotal):,.2f}"),
            ("Descuento", f"${_dinero(venta.descuento):,.2f}"),
            ("Impuestos", f"${_dinero(venta.impuestos):,.2f}"),
            ("Total", f"${_dinero(venta.total):,.2f}"),
        ],
        bloques=bloques,
        totales=totales,
        notas="Documento generado electronicamente por Aurora Viajes. Conservelo como soporte de su reserva; cualquier aclaracion puede solicitarla respondiendo al correo de confirmacion.",
    )
    return Response(documento, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={factura.numero}.pdf"})


@router.get("/estadisticas")
async def estadisticas(sesion: SesionDep, usuario: EmpleadoOAdmin, desde: date | None = None, hasta: date | None = None, periodo: str = Query(default="dia", pattern="^(dia|semana|mes)$"), estado: str | None = None, cliente_id: int | None = None, producto_id: int | None = None, servicio_id: int | None = None):
    """Resumen del panel: indicadores, evolucion y composicion del negocio.

    Antes solo devolvia cuatro contadores y una serie de totales por dia, con
    lo que el panel no podia decir de donde sale el dinero, que destinos tiran
    del negocio ni si el periodo va mejor o peor que el anterior.
    """
    dia_inicial = desde or date.today() - timedelta(days=29)
    dia_final = hasta or date.today()
    inicio = datetime.combine(dia_inicial, time.min, tzinfo=timezone.utc)
    fin = datetime.combine(dia_final + timedelta(days=1), time.min, tzinfo=timezone.utc)

    def filtrar(consulta, desde_dt: datetime, hasta_dt: datetime):
        consulta = consulta.where(Venta.creado_en >= desde_dt, Venta.creado_en < hasta_dt)
        if estado:
            consulta = consulta.where(Venta.estado == estado)
        if cliente_id:
            consulta = consulta.where(Venta.cliente_id == cliente_id)
        if producto_id or servicio_id:
            consulta = consulta.join(Venta.detalles)
            if producto_id:
                consulta = consulta.where(DetalleVenta.producto_id == producto_id)
            if servicio_id:
                consulta = consulta.where(DetalleVenta.servicio_id == servicio_id)
        return consulta

    base = select(Venta).options(selectinload(Venta.detalles), selectinload(Venta.cliente))
    ventas = (await sesion.scalars(filtrar(base, inicio, fin))).unique().all()

    por_dia: dict[str, dict] = {}
    for venta in ventas:
        fecha = venta.creado_en.date()
        if periodo == "semana":
            fecha = fecha - timedelta(days=fecha.weekday())
        elif periodo == "mes":
            fecha = fecha.replace(day=1)
        registro = por_dia.setdefault(fecha.isoformat(), {"total": 0.0, "ventas": 0})
        registro["total"] += _dinero(venta.total)
        registro["ventas"] += 1

    resumen = _resumen_de_ventas(list(ventas))

    # Mismo numero de dias justo antes del periodo, para poder comparar.
    dias = (dia_final - dia_inicial).days + 1
    inicio_previo = inicio - timedelta(days=dias)
    ventas_previas = (await sesion.scalars(filtrar(select(Venta), inicio_previo, inicio))).unique().all()
    total_previo = round(sum(_dinero(venta.total) for venta in ventas_previas), 2)
    variacion = round((resumen["total"] - total_previo) / total_previo * 100, 1) if total_previo else None

    por_cliente: dict[str, dict] = {}
    for venta in ventas:
        nombre = f"{venta.cliente.nombre} {venta.cliente.apellido}" if venta.cliente else "Sin cliente"
        registro = por_cliente.setdefault(nombre, {"ventas": 0, "total": 0.0})
        registro["ventas"] += 1
        registro["total"] += _dinero(venta.total)
    top_clientes = sorted(
        ({"cliente": nombre, "ventas": datos["ventas"], "total": round(datos["total"], 2)} for nombre, datos in por_cliente.items()),
        key=lambda item: item["total"],
        reverse=True,
    )[:5]

    # Los destinos salen de las reservas, que son las que conocen el viaje.
    reservas = (await sesion.scalars(
        select(Reserva)
        .options(selectinload(Reserva.destino_rel).selectinload(Destino.pais))
        .where(Reserva.creado_en >= inicio, Reserva.creado_en < fin)
    )).unique().all()
    por_destino: dict[str, dict] = {}
    for reserva in reservas:
        destino = reserva.destino_rel
        nombre = destino.nombre if destino else "Sin destino"
        registro = por_destino.setdefault(nombre, {"reservas": 0, "pasajeros": 0, "total": 0.0})
        registro["reservas"] += 1
        registro["pasajeros"] += reserva.pasajeros or 0
        registro["total"] += _dinero(reserva.monto_total)
    top_destinos = sorted(
        ({"destino": nombre, **datos, "total": round(datos["total"], 2)} for nombre, datos in por_destino.items()),
        key=lambda item: item["total"],
        reverse=True,
    )[:5]

    usuarios = await sesion.scalar(select(func.count(User.id)))
    productos = await sesion.scalar(select(func.count(Producto.id)).where(Producto.activo.is_(True)))
    servicios = await sesion.scalar(select(func.count(Servicio.id)).where(Servicio.activo.is_(True)))
    pendientes = await sesion.scalar(select(func.count(PQR.id)).where(PQR.estado.in_(["pendiente", "en_proceso"])))
    facturas = await sesion.scalar(
        select(func.count(Factura.id)).where(Factura.creado_en >= inicio, Factura.creado_en < fin)
    )

    return {
        "periodo": {"desde": dia_inicial.isoformat(), "hasta": dia_final.isoformat(), "dias": dias, "agrupacion": periodo},
        "indicadores": {
            "usuarios": usuarios or 0,
            "productos": productos or 0,
            "servicios": servicios or 0,
            "ventas": len(ventas),
            "facturacion": round(sum(registro["total"] for registro in por_dia.values()), 2),
            "pqrPendientes": pendientes or 0,
            "ticketPromedio": resumen["ticketPromedio"],
            "pasajeros": resumen["pasajeros"],
            "lineas": resumen["lineas"],
            "reservas": len(reservas),
            "facturas": facturas or 0,
        },
        "ventasPorDia": [{"fecha": clave, "total": round(datos["total"], 2), "ventas": datos["ventas"]} for clave, datos in sorted(por_dia.items())],
        "porConcepto": resumen["porConcepto"],
        "porEstado": [{"estado": clave, **datos} for clave, datos in sorted(resumen["porEstado"].items())],
        "topDestinos": top_destinos,
        "topClientes": top_clientes,
        "comparativa": {"totalAnterior": total_previo, "variacion": variacion},
    }


@router.post("/pqr", status_code=201)
async def crear_pqr(payload: PQREntrada, sesion: SesionDep, usuario: UsuarioActual):
    pqr = PQR(cliente_id=usuario.id, tipo=payload.tipo, asunto=payload.asunto, descripcion=payload.descripcion)
    sesion.add(pqr)
    await sesion.commit()
    await sesion.refresh(pqr)
    return {"id": pqr.id, "tipo": pqr.tipo, "asunto": pqr.asunto, "descripcion": pqr.descripcion, "estado": pqr.estado, "fecha": pqr.creado_en.isoformat()}


@router.get("/pqr")
async def listar_pqr(sesion: SesionDep, usuario: UsuarioActual, estado: str | None = None):
    consulta = select(PQR).options(selectinload(PQR.cliente)).order_by(PQR.creado_en.desc())
    if usuario.role.nombre == "cliente":
        consulta = consulta.where(PQR.cliente_id == usuario.id)
    if estado:
        consulta = consulta.where(PQR.estado == estado)
    solicitudes = (await sesion.scalars(consulta)).all()
    return [{"id": item.id, "tipo": item.tipo, "asunto": item.asunto, "descripcion": item.descripcion, "respuesta": item.respuesta, "estado": item.estado, "cliente": f"{item.cliente.nombre} {item.cliente.apellido}", "fecha": item.creado_en.isoformat()} for item in solicitudes]


@router.patch("/pqr/{pqr_id}")
async def actualizar_pqr(pqr_id: int, payload: PQRActualizacion, sesion: SesionDep, usuario: EmpleadoOAdmin):
    pqr = await sesion.get(PQR, pqr_id)
    if not pqr:
        raise RecursoNoEncontrado("una PQR", pqr_id)
    pqr.estado = payload.estado
    pqr.respuesta = payload.respuesta
    await sesion.commit()
    return {"mensaje": "PQR actualizada.", "estado": pqr.estado}


@router.post("/chatbot")
async def chatbot(payload: ChatEntrada, sesion: SesionDep):
    respuesta_local = "Puedo orientarte sobre destinos, reservas, productos, servicios y PQR. Para crear una PQR, escribe el asunto y la descripción desde el módulo de atención."
    conversacion = await sesion.get(Conversacion, payload.conversacion_id) if payload.conversacion_id else None
    if conversacion is None:
        conversacion = Conversacion()
        sesion.add(conversacion)
        await sesion.flush()
    try:
        async with httpx.AsyncClient(timeout=configuracion.proveedor_ia_timeout) as cliente:
            servicio = ServicioDeRecomendaciones(cliente)
            respuesta = await servicio.conversar(payload.mensaje, payload.historial)
            fuente = "groq"
    except ProveedorNoDisponible:
        respuesta = respuesta_local
        fuente = "faq"
    sesion.add_all([Mensaje(conversacion_id=conversacion.id, rol="usuario", contenido=payload.mensaje), Mensaje(conversacion_id=conversacion.id, rol="asistente", contenido=respuesta)])
    await sesion.commit()
    return {"respuesta": respuesta, "fuente": fuente, "conversacion_id": conversacion.id}
