import { fecha, fechaCorta, moneda, nochesEntre, sumarDias } from "../../utils/formato";
import { validarTelefono } from "../../utils/validaciones";
import TarjetaDeVuelo from "./TarjetaDeVuelo";
import { estadoDePlazas } from "./plazas";
import { CAJA_ERROR, CAMPO, ETIQUETA_MONO, tarjetaElegible } from "./estilos";

function Titulo({ etiqueta, children }) {
  return (
    <div className="mb-5">
      <p className={ETIQUETA_MONO}>{etiqueta}</p>
      <h2 className="mt-1.5 text-3xl leading-tight text-primario">{children}</h2>
    </div>
  );
}

/** Contador con botones − y +, pensado para pasajeros y personas por excursión. */
export function Contador({ valor, minimo = 1, maximo = 9, alCambiar, etiqueta }) {
  return (
    <div className="inline-flex items-center gap-1 rounded-full border border-primario/15 bg-white/70 p-1" role="group" aria-label={etiqueta}>
      <button type="button" onClick={() => alCambiar(valor - 1)} disabled={valor <= minimo} aria-label={`Menos ${etiqueta.toLowerCase()}`} className="grid h-8 w-8 place-items-center rounded-full text-lg text-primario transition hover:bg-primario/8 disabled:opacity-30">−</button>
      <output className="w-8 text-center text-sm font-semibold text-primario" aria-live="polite">{valor}</output>
      <button type="button" onClick={() => alCambiar(valor + 1)} disabled={valor >= maximo} aria-label={`Más ${etiqueta.toLowerCase()}`} className="grid h-8 w-8 place-items-center rounded-full text-lg text-primario transition hover:bg-primario/8 disabled:opacity-30">+</button>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Paso: destino, pasajeros y tipo de reserva
// ---------------------------------------------------------------------------------------------

export function PasoDestino({ destinos, datos, cambiarPasajeros, elegirDestino, elegirModo, opciones, errorDestinos }) {
  const paquetes = opciones?.datos?.paquetes?.length ?? 0;
  return (
    <div>
      <Titulo etiqueta="Paso · Destino">¿A dónde quieres <em className="titulo-enfasis">viajar</em>?</Titulo>
      {errorDestinos && <p role="alert" className={`${CAJA_ERROR} mb-4`}>{errorDestinos}</p>}
      <div role="radiogroup" aria-label="Destino" className="grid grid-cols-2 gap-3 md:grid-cols-3">
        {destinos.map((destino) => (
          <button
            key={destino.id}
            type="button"
            role="radio"
            aria-checked={String(destino.id) === datos.destinoId}
            onClick={() => elegirDestino(destino.id)}
            className={tarjetaElegible(String(destino.id) === datos.destinoId)}
          >
            <strong className="block font-display text-xl leading-tight text-primario">{destino.ciudad}</strong>
            <span className="block text-xs text-texto-suave">{destino.pais}</span>
            <span className="mt-2 block text-xs font-medium text-primario-suave">desde {moneda(destino.precioBase)} <span className="font-normal">/ persona</span></span>
          </button>
        ))}
      </div>

      <div className="mt-8 grid gap-6 sm:grid-cols-[auto_1fr] sm:items-start">
        <div>
          <p className="mb-2 text-sm font-semibold text-texto">Pasajeros</p>
          <Contador valor={datos.pasajeros} alCambiar={cambiarPasajeros} etiqueta="Pasajeros" />
          <p className="mt-2 max-w-[22ch] text-xs text-texto-suave">Hasta 9 por reserva. Habitaciones dobles.</p>
        </div>
        <div>
          <p className="mb-2 text-sm font-semibold text-texto">¿Cómo quieres reservar?</p>
          <div role="radiogroup" aria-label="Tipo de reserva" className="grid gap-3 sm:grid-cols-2">
            {[
              ["paquete", "✦ Paquete listo", "Vuelos de ida y regreso, hotel y excursiones a un precio cerrado."],
              ["carta", "◈ A la carta", "Tú eliges los vuelos, el hotel y las excursiones."],
            ].map(([valor, titulo, texto]) => (
              <button key={valor} type="button" role="radio" aria-checked={datos.modo === valor} onClick={() => elegirModo(valor)} className={tarjetaElegible(datos.modo === valor)}>
                <strong className="block text-sm text-primario">{titulo}</strong>
                <span className="mt-1 block text-xs leading-relaxed text-texto-suave">{texto}</span>
                {valor === "paquete" && datos.destinoId && opciones && (
                  <span className="mt-2 block text-xs font-semibold text-primario-suave">{paquetes ? `${paquetes} disponible${paquetes === 1 ? "" : "s"}` : "Sin paquetes por ahora"}</span>
                )}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Paso: vuelos (o paquete)
// ---------------------------------------------------------------------------------------------

function TarjetaDePaquete({ paquete, seleccionado, pasajeros, alElegir }) {
  const plazas = estadoDePlazas({ plazasLibres: paquete.plazasLibres }, pasajeros);
  return (
    <button type="button" role="radio" aria-checked={seleccionado} disabled={plazas.agotado} onClick={() => alElegir(paquete)} className={tarjetaElegible(seleccionado, plazas.agotado)}>
      <span className="flex flex-wrap items-start justify-between gap-3">
        <span>
          <strong className="block font-display text-xl leading-tight text-primario">{paquete.nombre}</strong>
          <span className="mt-1 block text-xs text-texto-suave">
            {fecha(paquete.fechaSalida, { day: "numeric", month: "short" })} → {fecha(paquete.fechaRegreso, { day: "numeric", month: "short", year: "numeric" })} · {paquete.noches} noches
          </span>
        </span>
        <span className="text-right">
          <strong className="block text-lg text-primario">{moneda(paquete.precioBase)}</strong>
          <span className="text-xs text-texto-suave">por persona</span>
        </span>
      </span>
      <span className="mt-3 grid gap-1 text-xs text-texto-suave sm:grid-cols-2">
        <span>✈ {paquete.vuelo.numeroVuelo}{paquete.vueloRegreso ? ` · regreso ${paquete.vueloRegreso.numeroVuelo}` : ""}</span>
        <span>⌂ {paquete.hotel.nombre} {"★".repeat(paquete.hotel.estrellas)}</span>
        <span>◈ {paquete.excursiones.length} excursiones incluidas</span>
        {plazas.texto && <span className={`font-semibold ${plazas.tono}`}>{plazas.texto}</span>}
      </span>
    </button>
  );
}

export function PasoVuelos({ datos, opciones, ida, regresos, elegirPaquete, elegirIda, elegirRegreso, cambiar, origenFiltro, cambiarOrigen, vuelosIda }) {
  if (!opciones) return <p className="text-sm text-texto-suave">Cargando las opciones del destino…</p>;
  if (opciones.error) return <p role="alert" className={CAJA_ERROR}>{opciones.error}</p>;

  if (datos.modo === "paquete") {
    const paquetes = opciones.datos.paquetes;
    return (
      <div>
        <Titulo etiqueta="Paso · Paquete">Elige tu <em className="titulo-enfasis">paquete</em></Titulo>
        {paquetes.length === 0 ? (
          <p className="vidrio-sutil rounded-2xl p-5 text-sm text-texto-suave">Este destino no tiene paquetes con salida próxima. Puedes armar tu viaje «a la carta».</p>
        ) : (
          <div role="radiogroup" aria-label="Paquete" className="grid gap-3">
            {paquetes.map((paquete) => (
              <TarjetaDePaquete key={paquete.id} paquete={paquete} seleccionado={datos.paqueteId === paquete.id} pasajeros={datos.pasajeros} alElegir={elegirPaquete} />
            ))}
          </div>
        )}
      </div>
    );
  }

  const origenes = opciones.datos.origenes;
  return (
    <div>
      <Titulo etiqueta="Paso · Vuelos">Elige tus <em className="titulo-enfasis">vuelos</em></Titulo>

      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <h3 className="text-lg text-primario">Vuelo de ida</h3>
        {origenes.length > 1 && (
          <label className="text-sm font-medium text-texto">
            <span className="mr-2 text-texto-suave">Sales desde</span>
            <select value={origenFiltro} onChange={(evento) => cambiarOrigen(evento.target.value)} className={`${CAMPO} inline-block w-auto`}>
              {origenes.map((origen) => <option key={origen.id} value={origen.id}>{origen.nombre}</option>)}
            </select>
          </label>
        )}
      </div>
      {vuelosIda.length === 0 ? (
        <p className="vidrio-sutil rounded-2xl p-5 text-sm text-texto-suave">No hay vuelos de ida con salida próxima desde ese origen.</p>
      ) : (
        <div role="radiogroup" aria-label="Vuelo de ida" className="grid max-h-[26rem] gap-3 overflow-y-auto pr-1 md:grid-cols-2">
          {vuelosIda.map((vuelo) => (
            <TarjetaDeVuelo key={vuelo.id} vuelo={vuelo} seleccionado={datos.vueloIdaId === vuelo.id} pasajeros={datos.pasajeros} alElegir={elegirIda} />
          ))}
        </div>
      )}

      {ida && (
        <div className="mt-8">
          <h3 className="mb-3 text-lg text-primario">Vuelo de regreso</h3>
          <div role="radiogroup" aria-label="Vuelo de regreso" className="grid max-h-[26rem] gap-3 overflow-y-auto pr-1 md:grid-cols-2">
            {regresos.map((vuelo) => (
              <TarjetaDeVuelo
                key={vuelo.id}
                vuelo={vuelo}
                seleccionado={datos.vueloRegresoId === vuelo.id}
                pasajeros={datos.pasajeros}
                alElegir={elegirRegreso}
                nota={`${nochesEntre(ida.fechaSalida, vuelo.fechaSalida)} noches de estancia`}
              />
            ))}
            <button
              type="button"
              role="radio"
              aria-checked={datos.regresoAbierto}
              onClick={() => cambiar({ regresoAbierto: true, vueloRegresoId: null })}
              className={tarjetaElegible(datos.regresoAbierto)}
            >
              <strong className="block text-sm text-primario">Regreso por mi cuenta</strong>
              <span className="mt-1 block text-xs leading-relaxed text-texto-suave">Sin vuelo de regreso con Aurora. Solo indicas el día para calcular las noches de hotel.</span>
            </button>
          </div>
          {regresos.length === 0 && <p className="mt-3 text-sm text-texto-suave">No hay vuelos de regreso publicados para esa salida; puedes elegir «regreso por mi cuenta».</p>}
          {datos.regresoAbierto && (
            <label className="mt-4 block max-w-xs text-sm font-medium text-texto">
              Fecha de regreso
              <input
                type="date"
                value={datos.fechaRegreso}
                min={sumarDias(ida.fechaSalida, 1)}
                max={sumarDias(ida.fechaSalida, 365)}
                onChange={(evento) => cambiar({ fechaRegreso: evento.target.value })}
                className={`${CAMPO} mt-1.5`}
              />
              {datos.fechaRegreso && <span className="mt-1 block text-xs font-normal text-texto-suave">{nochesEntre(ida.fechaSalida, datos.fechaRegreso)} noches · {fechaCorta(datos.fechaRegreso)}</span>}
            </label>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Paso: hotel y excursiones
// ---------------------------------------------------------------------------------------------

export function PasoExtras({ datos, opciones, paquete, alternarExcursion, cambiarCantidad, cambiar, cotizacion }) {
  if (!opciones?.datos) return <p className="text-sm text-texto-suave">Cargando las opciones del destino…</p>;

  if (datos.modo === "paquete") {
    return (
      <div>
        <Titulo etiqueta="Paso · Incluido">Todo esto ya viene <em className="titulo-enfasis">incluido</em></Titulo>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="vidrio-sutil rounded-2xl p-5">
            <p className={ETIQUETA_MONO}>Alojamiento</p>
            <p className="mt-2 text-lg font-semibold text-primario">{paquete?.hotel.nombre}</p>
            <p className="text-sm text-texto-suave">{"★".repeat(paquete?.hotel.estrellas || 0)} · {paquete?.noches} noches</p>
          </div>
          <div className="vidrio-sutil rounded-2xl p-5">
            <p className={ETIQUETA_MONO}>Excursiones</p>
            <ul className="mt-2 space-y-1.5 text-sm text-texto">
              {paquete?.excursiones.map((excursion) => <li key={excursion.id}>◈ {excursion.nombre} <span className="text-texto-suave">· {excursion.duracionHoras} h</span></li>)}
            </ul>
          </div>
        </div>
        <p className="mt-4 text-sm text-texto-suave">El precio del paquete ya las incluye para todos los pasajeros: no se cobra nada aparte.</p>
      </div>
    );
  }

  const { hoteles, excursiones } = opciones.datos;
  const noches = cotizacion?.noches;
  return (
    <div>
      <Titulo etiqueta="Paso · Hotel y extras">Hotel y <em className="titulo-enfasis">excursiones</em></Titulo>

      <h3 className="mb-3 text-lg text-primario">Alojamiento <span className="text-sm font-normal text-texto-suave">(opcional)</span></h3>
      <div role="radiogroup" aria-label="Hotel" className="grid gap-3 md:grid-cols-2">
        <button type="button" role="radio" aria-checked={!datos.hotelId} onClick={() => cambiar({ hotelId: null })} className={tarjetaElegible(!datos.hotelId)}>
          <strong className="block text-sm text-primario">Sin alojamiento</strong>
          <span className="mt-1 block text-xs text-texto-suave">Solo vuelos y excursiones.</span>
        </button>
        {hoteles.map((hotel) => (
          <button key={hotel.id} type="button" role="radio" aria-checked={datos.hotelId === hotel.id} onClick={() => cambiar({ hotelId: hotel.id })} className={tarjetaElegible(datos.hotelId === hotel.id)}>
            <span className="flex items-start justify-between gap-2">
              <strong className="text-sm text-primario">{hotel.nombre}</strong>
              <span className="text-xs text-oro" aria-label={`${hotel.estrellas} estrellas`}>{"★".repeat(hotel.estrellas)}</span>
            </span>
            <span className="mt-1 block text-xs text-texto-suave">{moneda(hotel.precioNoche)} por noche y habitación{noches ? ` · ${noches} noche${noches === 1 ? "" : "s"}` : ""}</span>
          </button>
        ))}
      </div>

      <h3 className="mb-3 mt-8 text-lg text-primario">Excursiones <span className="text-sm font-normal text-texto-suave">(opcional, se cobran por persona)</span></h3>
      {excursiones.length === 0 ? (
        <p className="vidrio-sutil rounded-2xl p-5 text-sm text-texto-suave">Este destino aún no tiene excursiones publicadas.</p>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {excursiones.map((excursion) => {
            const cantidad = datos.excursiones[excursion.id];
            const activa = Boolean(cantidad);
            return (
              <li key={excursion.id} className={tarjetaElegible(activa)}>
                <label className="flex cursor-pointer items-start gap-3">
                  <input type="checkbox" checked={activa} onChange={() => alternarExcursion(excursion.id)} className="mt-1 h-4 w-4 shrink-0 accent-primario" />
                  <span className="flex-1">
                    <strong className="block text-sm text-primario">{excursion.nombre}</strong>
                    <span className="block text-xs text-texto-suave">{excursion.duracionHoras} h · {moneda(excursion.precio)} por persona</span>
                  </span>
                </label>
                {activa && datos.pasajeros > 1 && (
                  <div className="mt-3 flex items-center justify-between gap-2 border-t border-primario/10 pt-3 text-xs text-texto-suave">
                    <span>Personas que la hacen</span>
                    <Contador valor={cantidad} maximo={datos.pasajeros} alCambiar={(valor) => cambiarCantidad(excursion.id, valor)} etiqueta={`Personas en ${excursion.nombre}`} />
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Paso: confirmar (y cobrar, si lo hace el personal)
// ---------------------------------------------------------------------------------------------

const FORMAS_DE_PAGO = [
  ["pendiente", "Pagará después", "La reserva queda pendiente; el cliente paga en línea desde su cuenta."],
  ["efectivo", "Efectivo", "Cobrado ahora en el mostrador."],
  ["transferencia", "Transferencia", "Con el número de comprobante."],
  ["tarjeta", "Datáfono", "Cobrado ahora con tarjeta."],
];

export function PasoConfirmar({ datos, cambiar, esPersonal, edicion, errorEnvio, cotizacion, pagada }) {
  const errorTelefono = datos.telefono ? validarTelefono(datos.telefono) : "";
  return (
    <div>
      <Titulo etiqueta="Paso · Confirmar">{edicion ? "Revisa y guarda los " : "Casi "}<em className="titulo-enfasis">{edicion ? "cambios" : "listo"}</em></Titulo>

      <div className="grid gap-5 sm:grid-cols-2">
        <label className="text-sm font-medium text-texto">
          Teléfono de contacto <span className="text-acento">*</span>
          <input
            value={datos.telefono}
            onChange={(evento) => cambiar({ telefono: evento.target.value.replace(/\D/g, "").slice(0, 10) })}
            inputMode="tel"
            maxLength={10}
            placeholder="3000000000"
            aria-invalid={Boolean(errorTelefono)}
            className={`${CAMPO} mt-1.5 ${errorTelefono ? "border-red-400" : ""}`}
          />
          <span className={`mt-1 block text-xs ${errorTelefono ? "font-medium text-red-600" : "font-normal text-texto-suave"}`}>
            {errorTelefono || "Para avisarte de cualquier cambio en el viaje."}
          </span>
        </label>
        <label className="text-sm font-medium text-texto sm:col-span-2">
          Notas para el equipo <span className="font-normal text-texto-suave">(opcional)</span>
          <textarea value={datos.notas} onChange={(evento) => cambiar({ notas: evento.target.value })} maxLength={300} rows={3} placeholder="Preferencias de asiento, alergias, celebraciones…" className={`${CAMPO} mt-1.5 resize-y`} />
          <span className="mt-1 block text-right text-xs font-normal text-texto-suave">{datos.notas.length}/300</span>
        </label>
      </div>

      {esPersonal && !edicion && (
        <fieldset className="mt-6">
          <legend className="mb-2 text-sm font-semibold text-texto">Cobro</legend>
          <div role="radiogroup" aria-label="Forma de pago" className="grid gap-3 sm:grid-cols-2">
            {FORMAS_DE_PAGO.map(([valor, titulo, texto]) => (
              <button key={valor} type="button" role="radio" aria-checked={datos.pago.metodo === valor} onClick={() => cambiar({ pago: { ...datos.pago, metodo: valor } })} className={tarjetaElegible(datos.pago.metodo === valor)}>
                <strong className="block text-sm text-primario">{titulo}</strong>
                <span className="mt-1 block text-xs text-texto-suave">{texto}</span>
              </button>
            ))}
          </div>
          {datos.pago.metodo !== "pendiente" && (
            <label className="mt-4 block max-w-sm text-sm font-medium text-texto">
              Referencia o comprobante <span className="font-normal text-texto-suave">(opcional)</span>
              <input value={datos.pago.referencia} onChange={(evento) => cambiar({ pago: { ...datos.pago, referencia: evento.target.value } })} maxLength={80} placeholder="Recibo 0042, TRX-778…" className={`${CAMPO} mt-1.5`} />
            </label>
          )}
        </fieldset>
      )}

      {edicion && pagada && (
        <p className="vidrio-sutil mt-6 rounded-xl px-4 py-3 text-sm text-texto-suave">
          Esta reserva ya está pagada: puedes cambiar vuelos, notas o teléfono si el precio no cambia. Para cambiar el precio, cancélala y crea una nueva.
        </p>
      )}
      {cotizacion && (
        <p className="mt-6 text-sm text-texto-suave">
          Total de la reserva: <strong className="text-primario">{moneda(cotizacion.total)}</strong>
          {esPersonal && !edicion && datos.pago.metodo !== "pendiente" ? " · se registrará como pagado." : ""}
        </p>
      )}
      {errorEnvio && <p role="alert" className={`${CAJA_ERROR} mt-4`}>{errorEnvio}</p>}
    </div>
  );
}
