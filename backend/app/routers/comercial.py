from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from io import BytesIO

import httpx
import unicodedata
from fastapi import APIRouter, Query, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.configuracion import configuracion
from app.core.limitador import limitador, limitar
from app.dependencias import EmpleadoOAdmin, SesionDep, UsuarioActual
from app.errores import ConflictoDeNegocio, PermisoDenegado, RecursoNoEncontrado
from app.models.dominio import Conversacion, DetalleFactura, DetalleVenta, EstadoReserva, Factura, Mensaje, PQR, Producto, Reserva, Servicio, User, Venta
from app.schemas.comercial import ChatEntrada, PQRActualizacion, PQREntrada, VentaEntrada
from app.services.catalogos import escapar_like
from app.services.documentos import construir_pdf, construir_xlsx
from app.services.facturas import cargar_factura, pdf_de_factura
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
        "reservaId": venta.reserva_id,
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
async def crear_venta(payload: VentaEntrada, sesion: SesionDep, usuario: EmpleadoOAdmin):
    """Venta de mostrador de productos y servicios; las reservas generan su venta solas.

    Solo el personal puede registrarla: el descuento y el impuesto los fija quien
    llama, y con la ruta abierta un cliente podía crearse una venta «completada»
    de valor cero.
    """
    cliente_id = payload.cliente_id or usuario.id
    cliente = await sesion.get(User, cliente_id)
    if not cliente:
        raise RecursoNoEncontrado("un cliente", cliente_id)

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
        # Los comodines de LIKE se escapan: el texto buscado es literal, no un patrón.
        consulta = consulta.where(Factura.numero.ilike(f"%{escapar_like(numero[:40])}%", escape="\\"))
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
    """Clasifica una linea de factura en paquete, vuelo, hotel o excursion.

    Las lineas las escribe el modulo de reservas con un prefijo fijo, asi que
    basta mirar la primera palabra. Lo que no encaje se agrupa como "otros"
    para que ningun importe se pierda del resumen.
    """
    limpio = unicodedata.normalize("NFKD", nombre or "").encode("ascii", "ignore").decode("ascii").lower()
    if limpio.startswith("paquete"):
        return "paquete"
    if limpio.startswith("vuelo"):
        return "vuelo"
    if limpio.startswith("hotel") or limpio.startswith("alojamiento"):
        return "hotel"
    if limpio.startswith("excursion"):
        return "excursiones"
    return "otros"


def _vigentes(ventas: list[Venta]) -> list[Venta]:
    """Las ventas canceladas se muestran, pero no cuentan como facturación."""
    return [venta for venta in ventas if venta.estado != "cancelada"]


def _resumen_de_ventas(ventas: list[Venta]) -> dict:
    """Totales que acompanan al detalle en los reportes y en el panel."""
    vigentes = _vigentes(ventas)
    lineas = [detalle for venta in vigentes for detalle in venta.detalles]
    total = round(sum(_dinero(venta.total) for venta in vigentes), 2)
    por_concepto: dict[str, float] = {"paquete": 0.0, "vuelo": 0.0, "hotel": 0.0, "excursiones": 0.0, "otros": 0.0}
    for detalle in lineas:
        por_concepto[_concepto_de(detalle.nombre)] += _dinero(detalle.subtotal)
    # El desglose por estado sí incluye las canceladas: es donde se ve lo que se perdió.
    por_estado: dict[str, dict] = {}
    for venta in ventas:
        registro = por_estado.setdefault(venta.estado, {"cantidad": 0, "total": 0.0})
        registro["cantidad"] += 1
        registro["total"] += _dinero(venta.total)
    pasajeros = sum(detalle.cantidad for detalle in lineas if _concepto_de(detalle.nombre) in ("vuelo", "paquete"))
    return {
        "ventas": len(vigentes),
        "lineas": len(lineas),
        "total": total,
        "ticketPromedio": round(total / len(vigentes), 2) if vigentes else 0.0,
        "pasajeros": pasajeros,
        "porConcepto": {clave: round(valor, 2) for clave, valor in por_concepto.items()},
        "porEstado": {clave: {"cantidad": valor["cantidad"], "total": round(valor["total"], 2)} for clave, valor in por_estado.items()},
    }


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
    # Las ventas canceladas aparecen en el listado JSON, pero no en los archivos ni en los totales.
    vigentes = _vigentes(ventas)
    filas = _filas_reporte(vigentes)
    resumen = _resumen_de_ventas(ventas)
    total = resumen["total"]
    periodo = inicio_dia.isoformat() if inicio_dia == fin_dia else f"{inicio_dia.isoformat()} a {fin_dia.isoformat()}"
    nombre_archivo = f"ventas-{inicio_dia}" if inicio_dia == fin_dia else f"ventas-{inicio_dia}_{fin_dia}"

    agrupado: dict[str, list] = {}
    for venta in vigentes:
        clave = venta.creado_en.date().isoformat()
        registro = agrupado.setdefault(clave, [0, 0.0])
        registro[0] += 1
        registro[1] += _dinero(venta.total)
    por_dia = [(clave, valor[0], round(valor[1], 2)) for clave, valor in sorted(agrupado.items())]

    if formato == "xlsx":
        return StreamingResponse(
            BytesIO(construir_xlsx(filas, periodo, resumen, por_dia)),
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
            f"Composicion de los ingresos: paquetes ${conceptos['paquete']:,.2f} | vuelos ${conceptos['vuelo']:,.2f} | hoteles ${conceptos['hotel']:,.2f} | "
            f"excursiones ${conceptos['excursiones']:,.2f} | otros ${conceptos['otros']:,.2f}. "
            f"Ticket promedio ${resumen['ticketPromedio']:,.2f} sobre {resumen['ventas']} venta(s)."
        )
        documento = construir_pdf(
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
    factura = await cargar_factura(sesion, factura_id)
    if not factura:
        raise RecursoNoEncontrado("una factura", factura_id)
    if usuario.role.nombre == "cliente" and factura.venta.cliente_id != usuario.id:
        raise PermisoDenegado("No tiene permiso para descargar esta factura.")
    return Response(pdf_de_factura(factura), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={factura.numero}.pdf"})


@router.get("/estadisticas")
async def estadisticas(sesion: SesionDep, usuario: EmpleadoOAdmin, desde: date | None = None, hasta: date | None = None, periodo: str = Query(default="dia", pattern="^(dia|semana|mes)$"), estado: str | None = None, cliente_id: int | None = None, producto_id: int | None = None, servicio_id: int | None = None):
    """Resumen del panel: indicadores, evolucion y composicion del negocio.

    Antes solo devolvia cuatro contadores y una serie de totales por dia, con
    lo que el panel no podia decir de donde sale el dinero, que destinos tiran
    del negocio ni si el periodo va mejor o peor que el anterior.
    """
    # «Hoy» es el día en UTC, como las fechas que se guardan: con la del sistema, un servidor en otra zona horaria
    # dejaba fuera las ventas de las últimas horas del día.
    hoy = datetime.now(timezone.utc).date()
    dia_inicial = desde or hoy - timedelta(days=29)
    dia_final = hasta or hoy
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
    vigentes = _vigentes(list(ventas))

    por_dia: dict[str, dict] = {}
    for venta in vigentes:
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
    total_previo = round(sum(_dinero(venta.total) for venta in _vigentes(list(ventas_previas))), 2)
    variacion = round((resumen["total"] - total_previo) / total_previo * 100, 1) if total_previo else None

    por_cliente: dict[str, dict] = {}
    for venta in vigentes:
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
        .where(
            Reserva.creado_en >= inicio,
            Reserva.creado_en < fin,
            Reserva.estado_id != select(EstadoReserva.id).where(EstadoReserva.codigo == "cancelada").scalar_subquery(),
        )
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
        select(func.count(Factura.id)).where(Factura.creado_en >= inicio, Factura.creado_en < fin, Factura.estado != "anulada")
    )

    return {
        "periodo": {"desde": dia_inicial.isoformat(), "hasta": dia_final.isoformat(), "dias": dias, "agrupacion": periodo},
        "indicadores": {
            "usuarios": usuarios or 0,
            "productos": productos or 0,
            "servicios": servicios or 0,
            "ventas": len(vigentes),
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


MAX_MENSAJES_POR_CONVERSACION = 200
MENSAJES_DE_CONTEXTO = 10


@router.post("/chatbot")
async def chatbot(payload: ChatEntrada, peticion: Request, sesion: SesionDep, usuario: UsuarioActual):
    """Asistente conversacional.

    Exige sesión y limita el uso, porque cada llamada consume una petición del
    proveedor de IA y escribe en la base. El contexto sale de los mensajes que el
    propio servidor guardó: el cliente ya no puede inyectar turnos con el rol que
    quiera, ni escribir en la conversación de otra persona.
    """
    await limitar(peticion, "chatbot-ip", maximo=60, ventana_segundos=600)
    await limitador.registrar(f"chatbot-usuario:{usuario.id}", maximo=20, ventana_segundos=600)

    respuesta_local = "Puedo orientarte sobre destinos, reservas, productos, servicios y PQR. Para crear una PQR, escribe el asunto y la descripción desde el módulo de atención."
    historial: list[dict[str, str]] = []
    if payload.conversacion_id:
        conversacion_id = await sesion.scalar(
            select(Conversacion.id).where(Conversacion.id == payload.conversacion_id, Conversacion.cliente_id == usuario.id)
        )
        if conversacion_id is None:
            raise RecursoNoEncontrado("una conversación", payload.conversacion_id)
        total = await sesion.scalar(select(func.count(Mensaje.id)).where(Mensaje.conversacion_id == conversacion_id))
        if (total or 0) >= MAX_MENSAJES_POR_CONVERSACION:
            raise ConflictoDeNegocio("La conversación alcanzó su límite de mensajes. Inicia una nueva.")
        filas = (await sesion.execute(
            select(Mensaje.rol, Mensaje.contenido)
            .where(Mensaje.conversacion_id == conversacion_id)
            .order_by(Mensaje.id.desc())
            .limit(MENSAJES_DE_CONTEXTO)
        )).all()
        historial = [{"role": "user" if rol == "usuario" else "assistant", "content": contenido} for rol, contenido in reversed(filas)]
    else:
        conversacion = Conversacion(cliente_id=usuario.id)
        sesion.add(conversacion)
        await sesion.flush()
        conversacion_id = conversacion.id

    try:
        async with httpx.AsyncClient(timeout=configuracion.proveedor_ia_timeout) as cliente:
            servicio = ServicioDeRecomendaciones(cliente)
            respuesta = await servicio.conversar(payload.mensaje, historial)
            fuente = "groq"
    except ProveedorNoDisponible:
        respuesta = respuesta_local
        fuente = "faq"
    sesion.add_all([Mensaje(conversacion_id=conversacion_id, rol="usuario", contenido=payload.mensaje), Mensaje(conversacion_id=conversacion_id, rol="asistente", contenido=respuesta)])
    await sesion.commit()
    return {"respuesta": respuesta, "fuente": fuente, "conversacion_id": conversacion_id}
