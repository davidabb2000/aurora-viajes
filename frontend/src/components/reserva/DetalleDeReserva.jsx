import { etiquetaEstado, fecha, fechaHora, moneda, ubicacion } from "../../utils/formato";
import { ETIQUETA_MONO } from "./estilos";

const METODOS = { stripe: "Tarjeta en línea (Stripe)", efectivo: "Efectivo en mostrador", transferencia: "Transferencia", tarjeta: "Datáfono" };

export function EstadoDeReserva({ reserva }) {
  const cancelada = reserva.estado === "cancelada";
  const pagada = reserva.estadoPago === "pagado";
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs sm:text-sm">
      <span className={`rounded-full px-3 py-1 font-semibold capitalize ${cancelada ? "bg-red-100 text-red-700" : reserva.estado === "confirmada" ? "bg-primario text-crema" : "bg-oro/70 text-primario"}`}>
        {etiquetaEstado(reserva.estado)}
      </span>
      <span className={`rounded-full border px-3 py-1 capitalize backdrop-blur-sm ${pagada ? "border-primario/30 bg-white/70 text-primario" : "border-primario/12 bg-white/60 text-texto-suave"}`}>
        {pagada ? "Pagada" : "Pago pendiente"}
      </span>
    </div>
  );
}

function Vuelo({ etiqueta, vuelo }) {
  if (!vuelo) return null;
  return (
    <div>
      <dt className="text-texto-suave">{etiqueta}</dt>
      <dd className="font-semibold text-texto">
        {vuelo.numeroVuelo} · {vuelo.origen} → {vuelo.destino}
        <span className="block text-xs font-normal text-texto-suave">
          {fechaHora(vuelo.fechaSalida)} → {fechaHora(vuelo.fechaLlegada)} · {vuelo.aerolinea}
        </span>
        {(vuelo.terminal || vuelo.puerta) && <span className="block text-xs font-normal text-texto-suave">Terminal {vuelo.terminal || "—"} · Puerta {vuelo.puerta || "—"} · {vuelo.estado}</span>}
      </dd>
    </div>
  );
}

/**
 * Todo lo de una reserva en un solo bloque: viaje, vuelos, alojamiento, excursiones con su cantidad y precio,
 * desglose del total y datos del pago. Lo usan la cuenta del cliente y el panel del personal.
 */
function DetalleDeReserva({ reserva, conCliente = false }) {
  const desglose = reserva.desglose || {};
  const esPaquete = Boolean(reserva.paqueteId);
  return (
    <div className="grid gap-4 text-sm lg:grid-cols-2">
      <section className="vidrio-sutil rounded-2xl p-4">
        <h4 className={ETIQUETA_MONO}>Viaje</h4>
        <dl className="mt-3 grid gap-3 sm:grid-cols-2">
          {conCliente && <div className="sm:col-span-2"><dt className="text-texto-suave">Cliente</dt><dd className="font-semibold text-texto">{reserva.cliente}{reserva.clienteCorreo ? ` · ${reserva.clienteCorreo}` : ""}</dd></div>}
          <div><dt className="text-texto-suave">Destino</dt><dd className="font-semibold text-texto">{ubicacion(reserva.destino, reserva.pais)}</dd></div>
          <div><dt className="text-texto-suave">Pasajeros</dt><dd className="font-semibold text-texto">{reserva.pasajeros}</dd></div>
          <div><dt className="text-texto-suave">Salida</dt><dd className="font-semibold text-texto">{fecha(reserva.fechaSalida)}</dd></div>
          <div><dt className="text-texto-suave">Regreso</dt><dd className="font-semibold text-texto">{fecha(reserva.fechaRegreso)}{!reserva.vueloRegreso && <span className="block text-xs font-normal text-texto-suave">Por su cuenta</span>}</dd></div>
          <div><dt className="text-texto-suave">Estancia</dt><dd className="font-semibold text-texto">{reserva.noches} noche{reserva.noches === 1 ? "" : "s"}</dd></div>
          {esPaquete && <div><dt className="text-texto-suave">Paquete</dt><dd className="font-semibold text-texto">{reserva.paquete?.nombre}</dd></div>}
        </dl>
      </section>

      <section className="vidrio-sutil rounded-2xl p-4">
        <h4 className={ETIQUETA_MONO}>Vuelos</h4>
        <dl className="mt-3 grid gap-3">
          <Vuelo etiqueta="Ida" vuelo={reserva.vuelo} />
          <Vuelo etiqueta="Regreso" vuelo={reserva.vueloRegreso} />
          {!reserva.vuelo && <p className="text-texto-suave">Vuelo pendiente de asignar.</p>}
        </dl>
      </section>

      <section className="vidrio-sutil rounded-2xl p-4">
        <h4 className={ETIQUETA_MONO}>Alojamiento</h4>
        {reserva.hotel ? (
          <dl className="mt-3 grid gap-3 sm:grid-cols-2">
            <div><dt className="text-texto-suave">Hotel</dt><dd className="font-semibold text-texto">{reserva.hotel.nombre}</dd></div>
            <div><dt className="text-texto-suave">Categoría</dt><dd className="font-semibold text-texto">{"★".repeat(reserva.hotel.estrellas)}</dd></div>
            <div><dt className="text-texto-suave">Ubicación</dt><dd className="font-semibold text-texto">{[reserva.hotel.ciudad, reserva.hotel.pais].filter(Boolean).join(", ")}</dd></div>
            <div><dt className="text-texto-suave">Tarifa por noche</dt><dd className="font-semibold text-texto">{esPaquete ? "Incluida en el paquete" : moneda(reserva.hotel.precioNoche)}</dd></div>
          </dl>
        ) : (
          <p className="mt-3 text-texto-suave">Sin alojamiento.</p>
        )}
      </section>

      <section className="vidrio-sutil rounded-2xl p-4">
        <h4 className={ETIQUETA_MONO}>Excursiones</h4>
        {reserva.excursiones?.length ? (
          <ul className="mt-3 divide-y divide-primario/10">
            {reserva.excursiones.map((excursion) => (
              <li key={excursion.id} className="flex items-start justify-between gap-3 py-2 first:pt-0 last:pb-0">
                <span>
                  <strong className="text-texto">{excursion.nombre}</strong>
                  <span className="block text-xs text-texto-suave">{excursion.duracionHoras} h · {excursion.cantidad} persona{excursion.cantidad === 1 ? "" : "s"}</span>
                </span>
                <span className="shrink-0 font-semibold text-texto">{esPaquete ? "Incluida" : moneda(excursion.subtotal)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-texto-suave">Sin excursiones.</p>
        )}
      </section>

      <section className="rounded-2xl border border-primario/12 bg-white/60 p-4 lg:col-span-2">
        <div className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-end">
          <dl className="grid gap-3 sm:grid-cols-3">
            {esPaquete ? (
              <div className="sm:col-span-3"><dt className="text-texto-suave">Cómo se compone</dt><dd className="font-semibold text-texto">Paquete cerrado: el precio ya incluye vuelos, hotel y excursiones.</dd></div>
            ) : (
              <>
                <div><dt className="text-texto-suave">Vuelos</dt><dd className="font-semibold text-texto">{moneda(desglose.vuelo)}</dd></div>
                <div><dt className="text-texto-suave">Hotel</dt><dd className="font-semibold text-texto">{moneda(desglose.hotel)}</dd></div>
                <div><dt className="text-texto-suave">Excursiones</dt><dd className="font-semibold text-texto">{moneda(desglose.excursiones)}</dd></div>
              </>
            )}
            <div><dt className="text-texto-suave">Teléfono de contacto</dt><dd className="font-semibold text-texto">{reserva.telefonoContacto || "No registrado"}</dd></div>
            <div>
              <dt className="text-texto-suave">Pago</dt>
              <dd className="font-semibold text-texto">
                {reserva.estadoPago === "pagado" ? (METODOS[reserva.metodoPago] || reserva.metodoPago) : "Pendiente"}
                {reserva.pagoReferencia && <span className="block text-xs font-normal text-texto-suave">Comprobante: {reserva.pagoReferencia}</span>}
                {reserva.pagadoEn && <span className="block text-xs font-normal text-texto-suave">{fechaHora(reserva.pagadoEn)}{reserva.pagoRegistradoPor ? ` · ${reserva.pagoRegistradoPor}` : ""}</span>}
              </dd>
            </div>
            {reserva.creadaPor && <div><dt className="text-texto-suave">Registrada por</dt><dd className="font-semibold text-texto">{reserva.creadaPor}</dd></div>}
          </dl>
          <div className="text-right">
            <p className={ETIQUETA_MONO}>Total</p>
            <p className="font-display text-3xl text-primario">{moneda(reserva.montoTotal)}</p>
          </div>
        </div>
        {reserva.notas && <p className="vidrio-sutil mt-4 rounded-xl p-3 text-texto"><span className="font-semibold">Notas:</span> {reserva.notas}</p>}
      </section>
    </div>
  );
}

export default DetalleDeReserva;
