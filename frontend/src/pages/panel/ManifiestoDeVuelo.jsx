import { BOTON_VIDRIO, CAJA_ERROR, ETIQUETA_MONO } from "../../components/reserva/estilos";
import { etiquetaEstado, fechaHora } from "../../utils/formato";
import { useCarga } from "../../utils/useCarga";

/** Una celda de CSV. Si empieza por un carácter que Excel toma por fórmula (=, +, -, @) se le antepone un apóstrofe. */
function celdaCsv(valor) {
  const texto = String(valor ?? "");
  const seguro = /^[=+\-@\t\r]/.test(texto) ? `'${texto}` : texto;
  return `"${seguro.replaceAll('"', '""')}"`;
}

/** Una fila por pasajero con datos y una «pendiente» por cada plaza sin completar, para ver de un vistazo qué falta. */
function filasDelManifiesto(manifiesto) {
  const filas = [["Vuelo", "Salida", "Reserva", "Tramo", "Estado", "Pago", "Cliente", "Teléfono", "Apellido", "Nombre", "Tipo de documento", "Número de documento"]];
  const { vuelo } = manifiesto;
  for (const reserva of manifiesto.reservas) {
    const base = [vuelo.numeroVuelo, vuelo.fechaSalida, reserva.reservaId, reserva.tramo, reserva.estado, reserva.estadoPago, reserva.cliente, reserva.telefono];
    for (const pasajero of reserva.datosDePasajeros) filas.push([...base, pasajero.apellido, pasajero.nombre, pasajero.tipoDocumento, pasajero.numeroDocumento]);
    for (let faltante = 0; faltante < reserva.faltan; faltante += 1) filas.push([...base, "(pendiente)", "", "", ""]);
  }
  return filas;
}

function descargarCsv(manifiesto) {
  const contenido = filasDelManifiesto(manifiesto).map((fila) => fila.map(celdaCsv).join(",")).join("\r\n");
  // El BOM inicial hace que Excel abra las tildes bien.
  const archivo = new Blob([`﻿${contenido}`], { type: "text/csv;charset=utf-8" });
  const enlace = document.createElement("a");
  enlace.href = URL.createObjectURL(archivo);
  enlace.download = `manifiesto-${manifiesto.vuelo.numeroVuelo}-${manifiesto.vuelo.fechaSalida.slice(0, 10)}.csv`;
  enlace.click();
  URL.revokeObjectURL(enlace.href);
}

function Dato({ etiqueta, valor, alerta = false }) {
  return (
    <div className="rounded-xl bg-white/60 px-3 py-2">
      <p className={ETIQUETA_MONO}>{etiqueta}</p>
      <p className={`font-display text-xl ${alerta ? "text-brillo" : "text-primario"}`}>{valor}</p>
    </div>
  );
}

/** Quién viaja en un vuelo: las reservas activas con los datos de sus pasajeros, y lo que falta por completar. */
function ManifiestoDeVuelo({ vuelo }) {
  const { datos, cargando, error } = useCarga(`/vuelos/${vuelo.id}/manifiesto`);

  return (
    <div className="mt-4 rounded-2xl border border-primario/10 bg-white/50 p-4" aria-live="polite">
      {error && <p role="alert" className={CAJA_ERROR}>{error}</p>}
      {datos === null && cargando && <p className="text-sm text-texto-suave">Cargando el manifiesto…</p>}
      {datos && (
        <>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Dato etiqueta="Reservas" valor={datos.resumen.reservas} />
              <Dato etiqueta="Plazas" valor={datos.resumen.plazas} />
              <Dato etiqueta="Con datos" valor={datos.resumen.conDatos} />
              <Dato etiqueta="Faltan datos" valor={datos.resumen.faltanDatos} alerta={datos.resumen.faltanDatos > 0} />
            </div>
            {datos.reservas.length > 0 && (
              <button type="button" onClick={() => descargarCsv(datos)} className={BOTON_VIDRIO}>▦ Descargar CSV</button>
            )}
          </div>

          {datos.reservas.length === 0 ? (
            <p className="mt-4 text-sm text-texto-suave">Todavía no hay reservas activas en este vuelo.</p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-160 text-left text-sm">
                <thead>
                  <tr className="border-b border-primario/12 text-texto-suave">
                    <th className="pb-2 font-medium">Reserva</th><th className="pb-2 font-medium">Cliente</th><th className="pb-2 font-medium">Estado</th><th className="pb-2 font-medium">Pasajeros</th>
                  </tr>
                </thead>
                <tbody>
                  {datos.reservas.map((reserva) => (
                    <tr key={`${reserva.reservaId}-${reserva.tramo}`} className="border-b border-primario/8 align-top">
                      <td className="py-2.5 font-semibold text-texto">#{reserva.reservaId}<span className="block text-xs font-normal capitalize text-texto-suave">{reserva.tramo}</span></td>
                      <td className="py-2.5 text-texto">{reserva.cliente}<span className="block text-xs text-texto-suave">{reserva.telefono}</span></td>
                      <td className="py-2.5 text-xs text-texto">{etiquetaEstado(reserva.estado)}<span className="block text-texto-suave">{reserva.estadoPago === "pagado" ? "Pagada" : "Sin pagar"}</span></td>
                      <td className="py-2.5 text-texto">
                        {reserva.datosDePasajeros.map((pasajero) => (
                          <span key={pasajero.id} className="block">{pasajero.apellido}, {pasajero.nombre} <span className="text-xs text-texto-suave">· {pasajero.tipoDocumento} {pasajero.numeroDocumento}</span></span>
                        ))}
                        {reserva.faltan > 0 && (
                          <span className="mt-1 inline-block rounded-full bg-oro/70 px-2.5 py-0.5 text-xs font-semibold text-primario">
                            {reserva.registrados === 0 ? `Sin datos de ${reserva.pasajeros} pasajero${reserva.pasajeros === 1 ? "" : "s"}` : `Faltan ${reserva.faltan}`}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-3 text-xs text-texto-suave">Salida: {fechaHora(datos.vuelo.fechaSalida)} · {datos.vuelo.origen} → {datos.vuelo.destino}. No incluye las reservas canceladas.</p>
        </>
      )}
    </div>
  );
}

export default ManifiestoDeVuelo;
