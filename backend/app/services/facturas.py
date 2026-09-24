"""Factura de venta en PDF: la misma para descargarla desde la app y para adjuntarla al correo de pago."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.dominio import Factura, Venta
from app.services.documentos import construir_pdf


def _dinero(valor) -> float:
    return round(float(valor or 0), 2)


async def cargar_factura(sesion: AsyncSession, factura_id: int) -> Factura | None:
    """La factura con todo lo que necesita su PDF (líneas, venta y cliente) ya cargado."""
    return await sesion.scalar(
        select(Factura)
        .options(selectinload(Factura.detalles), selectinload(Factura.venta).selectinload(Venta.cliente))
        .where(Factura.id == factura_id)
    )


def pdf_de_factura(factura: Factura) -> bytes:
    venta = factura.venta
    cliente = venta.cliente
    filas_pdf = [
        [detalle.nombre, detalle.cantidad, f"${_dinero(detalle.precio_unitario):,.2f}", f"${_dinero(detalle.subtotal):,.2f}"]
        for detalle in factura.detalles
    ]
    columnas = [("Concepto", 247), ("Cant.", 55, "der"), ("Precio unitario", 110, "der"), ("Subtotal", 120, "der")]
    totales = ["TOTAL A PAGAR", str(sum(detalle.cantidad for detalle in factura.detalles)), "", f"${_dinero(venta.total):,.2f}"]
    # La factura identifica a quien emite y a quien se le cobra: antes solo llevaba el nombre del cliente
    # metido en el subtitulo.
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
    return construir_pdf(
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
