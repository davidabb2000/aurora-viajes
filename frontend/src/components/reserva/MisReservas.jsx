import { useState } from "react";
import { Link } from "react-router-dom";
import { solicitar } from "../../utils/api";
import { fecha, ubicacion } from "../../utils/formato";
import DetalleDeReserva, { EstadoDeReserva } from "./DetalleDeReserva";
import { BOTON_VIDRIO, CAJA_ERROR } from "./estilos";

/**
 * Las reservas del cliente, con su detalle completo y las dos acciones que le corresponden: pagar
 * lo que está pendiente y cancelar lo que aún no pagó. `reservas` es null mientras carga.
 */
function MisReservas({ reservas, alCambiar }) {
  const [confirmando, setConfirmando] = useState(null);
  const [ocupada, setOcupada] = useState(null);
  const [error, setError] = useState("");

  const cancelar = async (id) => {
    setOcupada(id);
    setError("");
    try {
      await solicitar(`/reservas/${id}/cancelar`, { method: "POST" });
      setConfirmando(null);
      await alCambiar();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setOcupada(null);
    }
  };

  return (
    <section aria-labelledby="mis-reservas-titulo">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <span className="antetitulo">Tu historial</span>
          <h2 id="mis-reservas-titulo" className="mt-3 text-4xl text-primario">Mis reservas</h2>
        </div>
        {reservas && <span className="vidrio rounded-full px-4 py-1.5 text-sm text-texto-suave">{reservas.length} {reservas.length === 1 ? "reserva" : "reservas"}</span>}
      </div>

      {error && <p role="alert" className={`${CAJA_ERROR} mt-4`}>{error}</p>}

      {reservas === null ? (
        <p className="vidrio mt-5 rounded-3xl p-8 text-center text-texto-suave">Cargando tus reservas…</p>
      ) : reservas.length === 0 ? (
        <div className="vidrio mt-5 rounded-3xl border-dashed p-8 text-center text-texto-suave">Todavía no tienes reservas. ¡Arma tu primer viaje arriba!</div>
      ) : (
        <div className="mt-5 space-y-5">
          {reservas.map((reserva) => {
            const cancelada = reserva.estado === "cancelada";
            const pagada = reserva.estadoPago === "pagado";
            return (
              <details key={reserva.id} open={!cancelada} className="vidrio group overflow-hidden rounded-3xl">
                <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-4 border-b border-primario/12 px-5 py-4 marker:hidden sm:px-6">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-widest text-primario-suave">Reserva #{reserva.id}</p>
                    <h3 className="mt-1 text-2xl text-primario">{reserva.paquete?.nombre || reserva.destino}</h3>
                    <p className="mt-1 text-sm text-texto-suave">{ubicacion(reserva.destino, reserva.pais)} · {fecha(reserva.fechaSalida)}</p>
                  </div>
                  <EstadoDeReserva reserva={reserva} />
                </summary>

                <div className="p-5 sm:p-6">
                  <DetalleDeReserva reserva={reserva} alCambiar={alCambiar} />

                  {!cancelada && (
                    <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-primario/12 pt-4">
                      {!pagada && (
                        <Link to={`/reservas/pago/${reserva.id}`} className="boton-tinta px-6 py-2.5 text-sm font-semibold no-underline">
                          Pagar ahora
                        </Link>
                      )}
                      {!pagada && confirmando !== reserva.id && (
                        <button type="button" onClick={() => setConfirmando(reserva.id)} className={BOTON_VIDRIO}>Cancelar solicitud</button>
                      )}
                      {confirmando === reserva.id && (
                        <span className="flex flex-wrap items-center gap-2 rounded-2xl border border-red-200 bg-red-50/70 px-4 py-2 text-sm text-red-700">
                          ¿Cancelar esta solicitud? Se liberan sus plazas.
                          <button type="button" onClick={() => cancelar(reserva.id)} disabled={ocupada === reserva.id} className="font-semibold underline">{ocupada === reserva.id ? "Cancelando…" : "Sí, cancelar"}</button>
                          <button type="button" onClick={() => setConfirmando(null)} className="font-semibold">No</button>
                        </span>
                      )}
                      {pagada && <p className="text-sm text-texto-suave">Para cambiar o cancelar una reserva pagada, escríbenos desde la página de <Link to="/contacto" className="font-semibold text-primario">contacto</Link>.</p>}
                    </div>
                  )}
                </div>
              </details>
            );
          })}
        </div>
      )}
    </section>
  );
}

export default MisReservas;
