import { diaCorto, fecha, hora, moneda } from "../../utils/formato";
import { ETIQUETA_MONO } from "./estilos";

const ICONOS = { paquete: "✦", vuelo: "✈", hotel: "⌂", excursion: "◈" };

function Linea({ etiqueta, children }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2.5 text-sm">
      <dt className="text-texto-suave">{etiqueta}</dt>
      <dd className="text-right font-medium text-texto">{children}</dd>
    </div>
  );
}

/**
 * Resumen del viaje mientras se arma: lo elegido hasta ahora y el precio que calcula el servidor (el mismo
 * cálculo que se cobra, no una estimación hecha en el navegador).
 */
function ResumenDeViaje({ destino, pasajeros, ida, regreso, fechaRegresoAbierta, paquete, hotel, excursiones, cotizacion, cotizando, errorCotizacion, cliente }) {
  const total = cotizacion?.total;
  const seleccion = paquete ? "Paquete" : "A la carta";
  return (
    <aside className="vidrio rounded-3xl p-6" aria-label="Resumen de tu viaje" aria-live="polite">
      <p className={ETIQUETA_MONO}>Tu viaje · {seleccion}</p>
      <h2 className="mt-2 text-2xl leading-tight text-primario">{destino ? destino.nombre : "Elige un destino"}</h2>

      <dl className="mt-3 divide-y divide-primario/10">
        {cliente && <Linea etiqueta="Cliente">{cliente.nombre} {cliente.apellido || ""}</Linea>}
        <Linea etiqueta="Pasajeros">{pasajeros}</Linea>
        {ida && (
          <Linea etiqueta="Ida">
            {diaCorto(ida.fechaSalida)} · {hora(ida.fechaSalida)}
            <span className="block text-xs font-normal text-texto-suave">{ida.numeroVuelo} · {ida.origen} → {ida.destino}</span>
          </Linea>
        )}
        {regreso && (
          <Linea etiqueta="Regreso">
            {diaCorto(regreso.fechaSalida)} · {hora(regreso.fechaSalida)}
            <span className="block text-xs font-normal text-texto-suave">{regreso.numeroVuelo} · {regreso.origen} → {regreso.destino}</span>
          </Linea>
        )}
        {!regreso && fechaRegresoAbierta && <Linea etiqueta="Regreso">{fecha(fechaRegresoAbierta)}<span className="block text-xs font-normal text-texto-suave">Por tu cuenta, sin vuelo</span></Linea>}
        {cotizacion && <Linea etiqueta="Estancia">{cotizacion.noches} noche{cotizacion.noches === 1 ? "" : "s"}</Linea>}
        {hotel && (
          <Linea etiqueta="Hotel">
            {hotel.nombre}
            <span className="block text-xs font-normal text-texto-suave">{"★".repeat(hotel.estrellas || 0)}{cotizacion && !paquete ? ` · ${cotizacion.habitaciones} hab.` : ""}</span>
          </Linea>
        )}
        {excursiones.length > 0 && (
          <Linea etiqueta="Excursiones">
            {excursiones.map((excursion) => (
              <span key={excursion.id} className="block">{excursion.nombre}{excursion.cantidad !== pasajeros ? ` (${excursion.cantidad})` : ""}</span>
            ))}
          </Linea>
        )}
      </dl>

      <div className="mt-4 rounded-2xl bg-primario p-5 text-crema">
        <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-crema/70">Total a pagar</p>
        {total != null && !cotizando ? (
          <p className="mt-1 font-display text-4xl leading-none">{moneda(total)}</p>
        ) : (
          <p className="mt-1 text-sm text-crema/80">
            {cotizando ? "Calculando el precio…" : errorCotizacion ? "No se puede calcular todavía" : "Elige tus vuelos para ver el precio"}
          </p>
        )}
        {cotizacion && !cotizando && (
          <ul className="mt-4 space-y-1.5 border-t border-crema/15 pt-3 text-xs text-crema/80">
            {cotizacion.lineas.filter((linea) => linea.subtotal > 0 || linea.concepto === "paquete").map((linea, indice) => (
              <li key={`${linea.nombre}-${indice}`} className="flex items-start justify-between gap-3">
                <span><span aria-hidden="true">{ICONOS[linea.concepto]} </span>{linea.nombre}{linea.cantidad > 1 ? ` × ${linea.cantidad}` : ""}</span>
                <span className="shrink-0 font-medium text-crema">{moneda(linea.subtotal)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {errorCotizacion && !cotizando && (
        <p role="alert" className="mt-3 rounded-xl border border-red-200 bg-red-50/80 px-3.5 py-2.5 text-xs font-medium text-red-700">
          {errorCotizacion}
        </p>
      )}
      <p className="mt-3 text-xs leading-relaxed text-texto-suave">
        El precio lo calcula el servidor y es el mismo que se cobra. Habitaciones dobles; las excursiones se cobran por persona que las hace.
      </p>
    </aside>
  );
}

export default ResumenDeViaje;
