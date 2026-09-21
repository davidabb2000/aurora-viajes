import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AsistenteDeReserva from "../../components/reserva/AsistenteDeReserva";
import DetalleDeReserva, { EstadoDeReserva } from "../../components/reserva/DetalleDeReserva";
import { BOTON_VIDRIO, CAMPO } from "../../components/reserva/estilos";
import { solicitar } from "../../utils/api";
import { fecha, moneda } from "../../utils/formato";
import { useCarga } from "../../utils/useCarga";
import { Aviso, EncabezadoDePanel, Paginacion } from "./Encabezado";

const POR_PAGINA = 8;

/** Cobro en el mostrador sobre una reserva existente: método y comprobante. */
function FormularioDeCobro({ reserva, alTerminar, alCancelar }) {
  const [metodo, setMetodo] = useState("efectivo");
  const [referencia, setReferencia] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const cobrar = async (evento) => {
    evento.preventDefault();
    setGuardando(true);
    setError("");
    try {
      const respuesta = await solicitar(`/reservas/${reserva.id}/pago/manual`, { method: "POST", body: JSON.stringify({ metodo, referencia: referencia.trim() || null }) });
      alTerminar(respuesta.mensaje);
    } catch (requestError) {
      setError(requestError.message);
      setGuardando(false);
    }
  };

  return (
    <form onSubmit={cobrar} className="mt-4 grid gap-3 rounded-2xl border border-primario/12 bg-white/60 p-4 sm:grid-cols-[auto_1fr_auto] sm:items-end">
      <label className="text-sm font-medium text-texto">
        Forma de pago
        <select value={metodo} onChange={(evento) => setMetodo(evento.target.value)} className={`${CAMPO} mt-1.5`}>
          <option value="efectivo">Efectivo</option>
          <option value="transferencia">Transferencia</option>
          <option value="tarjeta">Datáfono</option>
        </select>
      </label>
      <label className="text-sm font-medium text-texto">
        Comprobante <span className="font-normal text-texto-suave">(opcional)</span>
        <input value={referencia} onChange={(evento) => setReferencia(evento.target.value)} maxLength={80} placeholder="Recibo 0042, TRX-778…" className={`${CAMPO} mt-1.5`} />
      </label>
      <div className="flex gap-2">
        <button type="submit" disabled={guardando} className="boton-tinta px-5 py-2.5 text-sm font-semibold">{guardando ? "Registrando…" : `Cobrar ${moneda(reserva.montoTotal)}`}</button>
        <button type="button" onClick={alCancelar} className={BOTON_VIDRIO}>Cancelar</button>
      </div>
      {error && <p role="alert" className="text-sm font-medium text-red-700 sm:col-span-3">{error}</p>}
    </form>
  );
}

function ReservasPanel() {
  const [busqueda, setBusqueda] = useState("");
  const [terminoBusqueda, setTerminoBusqueda] = useState("");
  const [estado, setEstado] = useState("");
  const [pago, setPago] = useState("");
  const [pagina, setPagina] = useState(1);
  const [editando, setEditando] = useState(null);
  const [cobrando, setCobrando] = useState(null);
  const [confirmando, setConfirmando] = useState(null);
  const [aviso, setAviso] = useState({ mensaje: "", tipo: "info" });

  // La búsqueda por texto espera a que se deje de escribir.
  useEffect(() => {
    const espera = setTimeout(() => setTerminoBusqueda(busqueda.trim()), 300);
    return () => clearTimeout(espera);
  }, [busqueda]);

  const parametros = new URLSearchParams();
  if (terminoBusqueda) parametros.set("q", terminoBusqueda);
  if (estado) parametros.set("estado", estado);
  if (pago) parametros.set("pago", pago);
  const { datos, cargando, error, recargar } = useCarga(`/reservas?${parametros}`);
  const reservas = datos ?? [];
  const visibles = reservas.slice((pagina - 1) * POR_PAGINA, pagina * POR_PAGINA);

  const avisar = (mensaje, tipo = "info") => setAviso({ mensaje, tipo });
  const filtrar = (cambio) => {
    cambio();
    setPagina(1);
  };

  const cambiarEstado = async (reserva, nuevoEstado) => {
    setConfirmando(null);
    try {
      const respuesta = await solicitar(`/reservas/${reserva.id}/estado`, { method: "PATCH", body: JSON.stringify({ estado: nuevoEstado }) });
      avisar(respuesta.mensaje, respuesta.requiereReembolso ? "error" : "info");
      recargar();
    } catch (requestError) {
      avisar(requestError.message, "error");
    }
  };

  const eliminar = async (reserva) => {
    setConfirmando(null);
    try {
      const respuesta = await solicitar(`/reservas/${reserva.id}`, { method: "DELETE" });
      avisar(respuesta.mensaje);
      recargar();
    } catch (requestError) {
      avisar(requestError.message, "error");
    }
  };

  if (editando) {
    return (
      <div className="mx-auto w-[96%] max-w-350 flex-1 py-8 sm:py-12">
        <EncabezadoDePanel etiqueta={`Reserva #${editando.id}`} titulo="Modificar reserva" descripcion={`Cliente: ${editando.cliente}. El precio se recalcula con las mismas reglas de siempre.`}>
          <button type="button" onClick={() => setEditando(null)} className={BOTON_VIDRIO}>← Volver a la lista</button>
        </EncabezadoDePanel>
        <div className="mt-8">
          <AsistenteDeReserva
            modo="personal"
            reserva={editando}
            alTerminar={() => {
              setEditando(null);
              avisar(`Reserva #${editando.id} actualizada.`);
              recargar();
            }}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-[96%] max-w-350 flex-1 py-8 sm:py-12">
      <EncabezadoDePanel etiqueta="Gestión" titulo="Reservas" descripcion="Solicitudes de los clientes y reservas hechas en el mostrador.">
        <Link to="/panel?vista=nueva" className="boton-tinta px-6 py-3 text-sm font-semibold no-underline">＋ Nueva reserva</Link>
      </EncabezadoDePanel>

      <section className="vidrio mt-8 rounded-3xl p-5 sm:p-6">
        <div className="grid gap-3 md:grid-cols-[1fr_auto_auto]">
          <input type="search" value={busqueda} onChange={(evento) => filtrar(() => setBusqueda(evento.target.value))} placeholder="Buscar por cliente, correo, documento o número de reserva" aria-label="Buscar reservas" className={CAMPO} />
          <select value={estado} onChange={(evento) => filtrar(() => setEstado(evento.target.value))} aria-label="Filtrar por estado" className={CAMPO}>
            <option value="">Todos los estados</option>
            <option value="pendiente">Pendientes</option>
            <option value="confirmada">Confirmadas</option>
            <option value="cancelada">Canceladas</option>
          </select>
          <select value={pago} onChange={(evento) => filtrar(() => setPago(evento.target.value))} aria-label="Filtrar por pago" className={CAMPO}>
            <option value="">Todos los pagos</option>
            <option value="pendiente">Sin pagar</option>
            <option value="pagado">Pagadas</option>
          </select>
        </div>

        <Aviso mensaje={aviso.mensaje} tipo={aviso.tipo} alCerrar={() => avisar("")} />
        <Aviso mensaje={error} tipo="error" />

        <div className="mt-5 space-y-4" aria-busy={cargando}>
          {datos === null && cargando && <p className="text-sm text-texto-suave">Cargando reservas…</p>}
          {datos !== null && reservas.length === 0 && <p className="text-sm text-texto-suave">No hay reservas que coincidan con los filtros.</p>}
          {visibles.map((reserva) => {
            const cancelada = reserva.estado === "cancelada";
            const pagada = reserva.estadoPago === "pagado";
            return (
              <article key={reserva.id} className="vidrio-sutil rounded-2xl p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-widest text-primario-suave">Reserva #{reserva.id}{reserva.creadaPor ? ` · mostrador (${reserva.creadaPor})` : ""}</p>
                    <h2 className="mt-1 text-2xl text-primario">{reserva.cliente}</h2>
                    <p className="text-sm text-texto-suave">
                      {reserva.destino} · {fecha(reserva.fechaSalida, { day: "numeric", month: "short" })} → {fecha(reserva.fechaRegreso, { day: "numeric", month: "short", year: "numeric" })} · {reserva.pasajeros} pasajero{reserva.pasajeros === 1 ? "" : "s"}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-display text-2xl text-primario">{moneda(reserva.montoTotal)}</p>
                    <EstadoDeReserva reserva={reserva} />
                  </div>
                </div>

                <details className="mt-4">
                  <summary className="cursor-pointer text-sm font-semibold text-primario">Ver detalle completo</summary>
                  <div className="mt-4"><DetalleDeReserva reserva={reserva} conCliente /></div>
                </details>

                <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-primario/12 pt-4">
                  {!cancelada && !pagada && <button type="button" onClick={() => setCobrando(cobrando === reserva.id ? null : reserva.id)} className="boton-tinta px-4 py-2 text-sm font-semibold">Registrar pago</button>}
                  {!cancelada && <button type="button" onClick={() => setEditando(reserva)} className={BOTON_VIDRIO}>Modificar</button>}
                  {!cancelada && confirmando !== `cancelar-${reserva.id}` && <button type="button" onClick={() => setConfirmando(`cancelar-${reserva.id}`)} className="rounded-full border border-red-200 bg-red-50/70 px-4 py-2 text-sm font-semibold text-red-700 transition hover:bg-red-100/80">Cancelar</button>}
                  {cancelada && <button type="button" onClick={() => cambiarEstado(reserva, pagada ? "confirmada" : "pendiente")} className={BOTON_VIDRIO}>Reactivar</button>}
                  {!pagada && confirmando !== `eliminar-${reserva.id}` && <button type="button" onClick={() => setConfirmando(`eliminar-${reserva.id}`)} className="px-3 py-2 text-sm font-medium text-texto-suave underline">Eliminar</button>}

                  {confirmando === `cancelar-${reserva.id}` && (
                    <span className="flex flex-wrap items-center gap-2 rounded-2xl border border-red-200 bg-red-50/70 px-4 py-2 text-sm text-red-700">
                      {pagada ? "Está pagada: cancelar no devuelve el dinero. " : ""}¿Cancelar la reserva?
                      <button type="button" onClick={() => cambiarEstado(reserva, "cancelada")} className="font-semibold underline">Sí, cancelar</button>
                      <button type="button" onClick={() => setConfirmando(null)} className="font-semibold">No</button>
                    </span>
                  )}
                  {confirmando === `eliminar-${reserva.id}` && (
                    <span className="flex flex-wrap items-center gap-2 rounded-2xl border border-red-200 bg-red-50/70 px-4 py-2 text-sm text-red-700">
                      Se borra la reserva y su venta y factura quedan anuladas. ¿Continuar?
                      <button type="button" onClick={() => eliminar(reserva)} className="font-semibold underline">Sí, eliminar</button>
                      <button type="button" onClick={() => setConfirmando(null)} className="font-semibold">No</button>
                    </span>
                  )}
                </div>
                {cobrando === reserva.id && (
                  <FormularioDeCobro
                    reserva={reserva}
                    alCancelar={() => setCobrando(null)}
                    alTerminar={(mensaje) => {
                      setCobrando(null);
                      avisar(mensaje);
                      recargar();
                    }}
                  />
                )}
              </article>
            );
          })}
        </div>
        <Paginacion pagina={pagina} total={reservas.length} porPagina={POR_PAGINA} alCambiar={setPagina} />
      </section>
    </div>
  );
}

export default ReservasPanel;
