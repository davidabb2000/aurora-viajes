from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

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


def _filas_reporte(ventas: list[Venta]) -> list[list[str]]:
    filas = [["Venta", "Fecha", "Cliente", "Concepto", "Cantidad", "Valor", "Total", "Estado"]]
    for venta in ventas:
        for detalle in venta.detalles:
            filas.append([str(venta.id), venta.creado_en.strftime("%Y-%m-%d %H:%M"), f"{venta.cliente.nombre} {venta.cliente.apellido}", detalle.nombre, str(detalle.cantidad), f"{_dinero(detalle.subtotal):.2f}", f"{_dinero(venta.total):.2f}", venta.estado])
    return filas


def _xlsx(filas: list[list[str]]) -> bytes:
    rows = "".join(f"<row r=\"{i}\">" + "".join(f"<c t=\"inlineStr\"><is><t>{str(valor).replace('&', '&amp;').replace('<', '&lt;')}</t></is></c>" for valor in fila) + "</row>" for i, fila in enumerate(filas, 1))
    contenido = f"<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"><sheetData>{rows}</sheetData></worksheet>"
    libro = "<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\"><sheets><sheet name=\"Ventas\" sheetId=\"1\" r:id=\"rId1\"/></sheets></workbook>"
    relaciones = "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/></Relationships>"
    tipos = "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/><Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/></Types>"
    salida = BytesIO()
    with ZipFile(salida, "w", ZIP_DEFLATED) as archivo:
        archivo.writestr("[Content_Types].xml", tipos)
        archivo.writestr("_rels/.rels", relaciones)
        archivo.writestr("xl/workbook.xml", libro)
        archivo.writestr("xl/_rels/workbook.xml.rels", relaciones.replace("worksheets/sheet1.xml", "worksheets/sheet1.xml"))
        archivo.writestr("xl/worksheets/sheet1.xml", contenido)
    return salida.getvalue()


def _pdf(lineas: list[str]) -> bytes:
    def escapar(linea: str) -> str:
        texto = unicodedata.normalize("NFKD", str(linea)).encode("ascii", "replace").decode("ascii")
        return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    contenido = "BT /F1 10 Tf 48 760 Td " + " ".join(f"({escapar(linea)}) Tj 0 -16 Td" for linea in lineas) + " ET"
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(contenido.encode('ascii'))} >>\nstream\n{contenido}\nendstream".encode("ascii"),
    ]
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
    if formato == "xlsx":
        return StreamingResponse(BytesIO(_xlsx(filas)), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename=ventas-{dia}.xlsx"})
    if formato == "pdf":
        lineas = [f"Aurora Viajes - Reporte de ventas {dia}", "Venta | Fecha | Cliente | Concepto | Cantidad | Total"]
        lineas.extend(" | ".join(fila[:5] + [fila[6]]) for fila in filas[1:])
        return Response(_pdf(lineas), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=ventas-{dia}.pdf"})
    return {"fecha": str(dia), "ventas": [_venta_dict(venta) for venta in ventas], "total": round(sum(_dinero(venta.total) for venta in ventas), 2), "cantidad": len(ventas)}


@router.get("/facturas/{factura_id}/pdf")
async def descargar_factura(factura_id: int, sesion: SesionDep, usuario: UsuarioActual):
    factura = await sesion.scalar(select(Factura).options(selectinload(Factura.venta).selectinload(Venta.cliente), selectinload(Factura.venta).selectinload(Venta.detalles)).where(Factura.id == factura_id))
    if not factura:
        raise RecursoNoEncontrado("una factura", factura_id)
    if usuario.role.nombre == "cliente" and factura.venta.cliente_id != usuario.id:
        raise PermisoDenegado("No tiene permiso para descargar esta factura.")
    venta = factura.venta
    lineas = [f"Aurora Viajes - Factura {factura.numero}", f"Cliente: {venta.cliente.nombre} {venta.cliente.apellido}", f"Fecha: {factura.creado_en:%Y-%m-%d}"]
    lineas.extend(f"{detalle.nombre} x{detalle.cantidad}: ${_dinero(detalle.subtotal):.2f}" for detalle in venta.detalles)
    lineas.append(f"Total: ${_dinero(venta.total):.2f}")
    return Response(_pdf(lineas), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={factura.numero}.pdf"})


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
