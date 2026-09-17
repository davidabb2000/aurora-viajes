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
from app.models.biblioteca import Conversacion, DetalleFactura, DetalleVenta, Factura, Mensaje, PQR, Producto, Servicio, User, Venta
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


def _xlsx(filas: list[list[object]], fecha: date, total: float) -> bytes:
    columnas = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]
    encabezado = filas[0]
    datos = filas[1:]
    def celda(valor: object, columna: str, fila: int, estilo: int = 0) -> str:
        referencia = f"{columna}{fila}"
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            return f'<c r="{referencia}" s="{estilo}" t="n"><v>{valor}</v></c>'
        texto = xml_escape(str(valor), {"\"": "&quot;"})
        return f'<c r="{referencia}" s="{estilo}" t="inlineStr"><is><t>{texto}</t></is></c>'

    filas_xml = [
        '<row r="1" ht="28" customHeight="1"><c r="A1" s="1" t="inlineStr"><is><t>Aurora Viajes | Reporte de ventas</t></is></c></row>',
        f'<row r="2"><c r="A2" s="2" t="inlineStr"><is><t>Periodo</t></is></c>{celda(fecha.isoformat(), "B", 2, 2)}<c r="D2" s="2" t="inlineStr"><is><t>Registros</t></is></c>{celda(len(datos), "E", 2, 3)}<c r="G2" s="2" t="inlineStr"><is><t>Total facturado</t></is></c>{celda(total, "H", 2, 4)}</row>',
        '<row r="3"/>',
        f'<row r="4">{"".join(celda(valor, columna, 4, 5) for columna, valor in zip(columnas, encabezado))}</row>',
    ]
    for numero, fila in enumerate(datos, 5):
        celdas = []
        for indice, (valor, columna) in enumerate(zip(fila, columnas)):
            estilo = 7 if numero % 2 and indice in (5, 6, 7) else 6 if numero % 2 else 4 if indice in (5, 6, 7) else 0
            celdas.append(celda(valor, columna, numero, estilo))
        filas_xml.append(f'<row r="{numero}">{"".join(celdas)}</row>')
    ultima_fila = max(4, len(datos) + 4)
    contenido = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        '<cols><col min="1" max="1" width="10" customWidth="1"/><col min="2" max="2" width="19" customWidth="1"/><col min="3" max="3" width="25" customWidth="1"/><col min="4" max="4" width="32" customWidth="1"/><col min="5" max="5" width="11" customWidth="1"/><col min="6" max="8" width="16" customWidth="1"/><col min="9" max="9" width="15" customWidth="1"/></cols>'
        f'<sheetData>{"".join(filas_xml)}</sheetData><mergeCells count="1"><mergeCell ref="A1:I1"/></mergeCells><autoFilter ref="A4:I{ultima_fila}"/></worksheet>'
    )
    libro = '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Ventas" sheetId="1" r:id="rId1"/></sheets></workbook>'
    relaciones = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'
    tipos = '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>'
    estilos = '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="1"><numFmt numFmtId="164" formatCode="&quot;$&quot;#,##0.00"/></numFmts><fonts count="3"><font><sz val="10"/><name val="Aptos"/></font><font><b/><sz val="15"/><color rgb="FFFFFFFF"/><name val="Aptos Display"/></font><font><b/><sz val="10"/><name val="Aptos"/></font></fonts><fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF17483F"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFEAF2ED"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="8"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" applyAlignment="1"><alignment vertical="center"/></xf><xf numFmtId="0" fontId="2" fillId="0" borderId="0"/><xf numFmtId="0" fontId="2" fillId="3" borderId="0"/><xf numFmtId="164" fontId="2" fillId="3" borderId="0"/><xf numFmtId="0" fontId="2" fillId="2" borderId="0" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf><xf numFmtId="0" fontId="0" fillId="3" borderId="0"/><xf numFmtId="164" fontId="0" fillId="3" borderId="0"/></cellXfs></styleSheet>'
    salida = BytesIO()
    with ZipFile(salida, "w", ZIP_DEFLATED) as archivo:
        archivo.writestr("[Content_Types].xml", tipos)
        archivo.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archivo.writestr("xl/workbook.xml", libro)
        archivo.writestr("xl/_rels/workbook.xml.rels", relaciones)
        archivo.writestr("xl/worksheets/sheet1.xml", contenido)
        archivo.writestr("xl/styles.xml", estilos)
    return salida.getvalue()


def _pdf_text(texto: object, max_chars: int) -> list[str]:
    limpio = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "replace").decode("ascii")
    palabras = limpio.split()
    lineas: list[str] = []
    actual = ""
    for palabra in palabras or [""]:
        if actual and len(actual) + len(palabra) + 1 > max_chars:
            lineas.append(actual)
            actual = palabra
        else:
            actual = f"{actual} {palabra}".strip()
    if actual or not lineas:
        lineas.append(actual)
    return lineas


def _pdf_escapar(texto: object) -> str:
    limpio = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "replace").decode("ascii")
    return limpio.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_documento(titulo: str, subtitulo: str, columnas: list[tuple[str, float]], filas: list[list[object]], resumen: list[tuple[str, object]]) -> bytes:
    ancho_pagina, alto_pagina, margen = 612, 792, 40
    paginas: list[list[str]] = []
    comandos: list[str] = []
    y = 0.0

    def texto(valor: object, x: float, posicion_y: float, tamano: float = 9, negrita: bool = False, color: tuple[float, float, float] = (0.12, 0.17, 0.16)) -> None:
        fuente = "/F2" if negrita else "/F1"
        comandos.append(f"{color[0]} {color[1]} {color[2]} rg BT {fuente} {tamano} Tf {x:.1f} {posicion_y:.1f} Td ({_pdf_escapar(valor)}) Tj ET")

    def rectangulo(x: float, posicion_y: float, ancho: float, alto: float, color: tuple[float, float, float]) -> None:
        comandos.append(f"{color[0]} {color[1]} {color[2]} rg {x:.1f} {posicion_y:.1f} {ancho:.1f} {alto:.1f} re f")

    def nueva_pagina() -> None:
        nonlocal comandos, y
        if comandos:
            paginas.append(comandos)
        comandos = []
        rectangulo(0, 0, ancho_pagina, alto_pagina, (0.98, 0.99, 0.98))
        rectangulo(0, 708, ancho_pagina, 84, (0.09, 0.28, 0.25))
        texto("AURORA VIAJES", margen, 758, 10, True, (0.76, 0.90, 0.79))
        texto(titulo, margen, 733, 20, True, (1, 1, 1))
        texto(subtitulo, margen, 716, 9, False, (0.86, 0.94, 0.88))
        y = 680

    def dibujar_tabla(encabezados: bool = False) -> None:
        nonlocal y
        x = margen
        alto_fila = 22
        if encabezados:
            rectangulo(margen, y - 5, sum(ancho for _, ancho in columnas), alto_fila, (0.76, 0.90, 0.79))
            for nombre, ancho in columnas:
                texto(nombre, x + 5, y + 3, 8, True, (0.09, 0.28, 0.25))
                x += ancho
            y -= alto_fila

    nueva_pagina()
    total_resumen = sum(ancho for _, ancho in columnas)
    tarjeta_ancho = (total_resumen - 12) / max(len(resumen), 1)
    for indice, (etiqueta, valor) in enumerate(resumen):
        x = margen + indice * (tarjeta_ancho + 6)
        rectangulo(x, y - 42, tarjeta_ancho, 38, (0.91, 0.95, 0.91))
        texto(etiqueta.upper(), x + 8, y - 18, 7, True, (0.28, 0.40, 0.36))
        texto(valor, x + 8, y - 35, 13, True, (0.09, 0.28, 0.25))
    y -= 66
    dibujar_tabla(True)
    for indice_fila, fila in enumerate(filas):
        alturas = []
        for (nombre, ancho), valor in zip(columnas, fila):
            alturas.append(len(_pdf_text(valor, max(8, int((ancho - 10) / 4.7)))))
        alto_fila = max(22, max(alturas) * 11 + 9)
        if y - alto_fila < 55:
            nueva_pagina()
            dibujar_tabla(True)
        if indice_fila % 2 == 0:
            rectangulo(margen, y - alto_fila + 5, total_resumen, alto_fila, (0.95, 0.97, 0.95))
        x = margen
        for (nombre, ancho), valor in zip(columnas, fila):
            for indice_linea, linea in enumerate(_pdf_text(valor, max(8, int((ancho - 10) / 4.7)))):
                texto(linea, x + 5, y - 10 - indice_linea * 11, 7.5, False)
            x += ancho
        y -= alto_fila
    paginas.append(comandos)

    objetos = [b"<< /Type /Catalog /Pages 2 0 R >>", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"]
    referencias_paginas = []
    for comandos_pagina in paginas:
        contenido = "BT /F1 9 Tf ET\n" + "\n".join(comandos_pagina)
        objeto_contenido = f"<< /Length {len(contenido.encode('ascii'))} >>\nstream\n{contenido}\nendstream".encode("ascii")
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
async def reporte_ventas(sesion: SesionDep, usuario: EmpleadoOAdmin, fecha: date | None = None, formato: str = Query(default="json", pattern="^(json|xlsx|pdf)$")):
    dia = fecha or datetime.now(timezone.utc).date()
    inicio = datetime.combine(dia, time.min, tzinfo=timezone.utc)
    ventas = (await sesion.scalars(select(Venta).options(selectinload(Venta.detalles), selectinload(Venta.cliente)).where(Venta.creado_en >= inicio, Venta.creado_en < inicio + timedelta(days=1)))).all()
    filas = _filas_reporte(ventas)
    total = round(sum(_dinero(venta.total) for venta in ventas), 2)
    if formato == "xlsx":
        return StreamingResponse(BytesIO(_xlsx(filas, dia, total)), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename=ventas-{dia}.xlsx"})
    if formato == "pdf":
        columnas = [("Venta", 35), ("Fecha", 60), ("Cliente", 95), ("Concepto", 100), ("Cant.", 35), ("Unitario", 50), ("Subtotal", 50), ("Total", 57), ("Estado", 50)]
        filas_pdf = [[fila[0], fila[1], fila[2], fila[3], fila[4], f"${fila[5]:,.2f}", f"${fila[6]:,.2f}", f"${fila[7]:,.2f}", fila[8]] for fila in filas[1:]]
        documento = _pdf_documento("Reporte de ventas", f"Periodo: {dia.isoformat()} | Aurora Viajes", columnas, filas_pdf, [("Ventas", len(ventas)), ("Lineas", len(filas_pdf)), ("Total", f"${total:,.2f}")])
        return Response(documento, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=ventas-{dia}.pdf"})
    return {"fecha": str(dia), "ventas": [_venta_dict(venta) for venta in ventas], "total": total, "cantidad": len(ventas)}


@router.get("/facturas/{factura_id}/pdf")
async def descargar_factura(factura_id: int, sesion: SesionDep, usuario: UsuarioActual):
    factura = await sesion.scalar(select(Factura).options(selectinload(Factura.detalles), selectinload(Factura.venta).selectinload(Venta.cliente)).where(Factura.id == factura_id))
    if not factura:
        raise RecursoNoEncontrado("una factura", factura_id)
    if usuario.role.nombre == "cliente" and factura.venta.cliente_id != usuario.id:
        raise PermisoDenegado("No tiene permiso para descargar esta factura.")
    venta = factura.venta
    filas_pdf = [[detalle.nombre, detalle.cantidad, f"${_dinero(detalle.precio_unitario):,.2f}", f"${_dinero(detalle.subtotal):,.2f}"] for detalle in factura.detalles]
    columnas = [("Concepto", 250), ("Cant.", 60), ("Precio unitario", 95), ("Subtotal", 90)]
    subtitulo = f"Factura {factura.numero} | Cliente: {venta.cliente.nombre} {venta.cliente.apellido} | Fecha: {factura.creado_en:%Y-%m-%d}"
    documento = _pdf_documento("Factura de venta", subtitulo, columnas, filas_pdf, [("Estado", factura.estado), ("Subtotal", f"${_dinero(venta.subtotal):,.2f}"), ("Descuento", f"${_dinero(venta.descuento):,.2f}"), ("Impuestos", f"${_dinero(venta.impuestos):,.2f}"), ("Total", f"${_dinero(venta.total):,.2f}")])
    return Response(documento, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={factura.numero}.pdf"})


@router.get("/estadisticas")
async def estadisticas(sesion: SesionDep, usuario: EmpleadoOAdmin, desde: date | None = None, hasta: date | None = None, periodo: str = Query(default="dia", pattern="^(dia|semana|mes)$"), estado: str | None = None, cliente_id: int | None = None, producto_id: int | None = None, servicio_id: int | None = None):
    inicio = datetime.combine(desde or date.today() - timedelta(days=29), time.min, tzinfo=timezone.utc)
    fin = datetime.combine((hasta or date.today()) + timedelta(days=1), time.min, tzinfo=timezone.utc)
    consulta = select(Venta).options(selectinload(Venta.detalles)).where(Venta.creado_en >= inicio, Venta.creado_en < fin)
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
    ventas = (await sesion.scalars(consulta)).unique().all()
    por_dia = {}
    for venta in ventas:
        fecha = venta.creado_en.date()
        if periodo == "semana":
            fecha = fecha - timedelta(days=fecha.weekday())
        elif periodo == "mes":
            fecha = fecha.replace(day=1)
        clave = fecha.isoformat()
        por_dia.setdefault(clave, 0)
        por_dia[clave] += _dinero(venta.total)
    usuarios = await sesion.scalar(select(func.count(User.id)))
    productos = await sesion.scalar(select(func.count(Producto.id)).where(Producto.activo.is_(True)))
    servicios = await sesion.scalar(select(func.count(Servicio.id)).where(Servicio.activo.is_(True)))
    pendientes = await sesion.scalar(select(func.count(PQR.id)).where(PQR.estado.in_(["pendiente", "en_proceso"])))
    return {"indicadores": {"usuarios": usuarios or 0, "productos": productos or 0, "servicios": servicios or 0, "ventas": len(ventas), "facturacion": round(sum(por_dia.values()), 2), "pqrPendientes": pendientes or 0}, "ventasPorDia": [{"fecha": clave, "total": total} for clave, total in sorted(por_dia.items())]}


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
