import { diaCorto, duracion, hora } from "../../utils/formato";
import { estadoDePlazas } from "./plazas";
import { tarjetaElegible } from "./estilos";

/**
 * Un vuelo como opción elegible: horario, ruta, duración y plazas. `nota` es un texto extra
 * (por ejemplo, las noches de estancia que resultan de elegir este regreso).
 */
function TarjetaDeVuelo({ vuelo, seleccionado, pasajeros, alElegir, nota }) {
  const plazas = estadoDePlazas(vuelo, pasajeros);
  return (
    <button
      type="button"
      role="radio"
      aria-checked={seleccionado}
      disabled={plazas.agotado}
      onClick={() => alElegir(vuelo)}
      className={tarjetaElegible(seleccionado, plazas.agotado)}
    >
      <span className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className="font-mono uppercase tracking-wider text-texto-suave">
          {vuelo.numeroVuelo} · {vuelo.aerolinea} · {vuelo.avion}
        </span>
        <span className="font-semibold text-primario">{diaCorto(vuelo.fechaSalida)}</span>
      </span>

      <span className="mt-3 grid grid-cols-[auto_1fr_auto] items-center gap-3">
        <span>
          <strong className="block font-display text-2xl leading-none text-primario">{hora(vuelo.fechaSalida)}</strong>
          <span className="mt-1 block text-xs text-texto-suave">{vuelo.origen}</span>
        </span>
        <span className="flex flex-col items-center text-[0.7rem] text-texto-suave" aria-hidden="true">
          <span>{duracion(vuelo.fechaSalida, vuelo.fechaLlegada)}</span>
          <span className="my-1 flex w-full items-center gap-1">
            <span className="h-px flex-1 bg-primario/25" />
            <span className="text-primario">✈</span>
            <span className="h-px flex-1 bg-primario/25" />
          </span>
        </span>
        <span className="text-right">
          <strong className="block font-display text-2xl leading-none text-primario">{hora(vuelo.fechaLlegada)}</strong>
          <span className="mt-1 block text-xs text-texto-suave">{vuelo.destino}</span>
        </span>
      </span>

      <span className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs">
        {nota ? <span className="font-medium text-primario-suave">{nota}</span> : <span />}
        {plazas.texto && <span className={`font-semibold ${plazas.tono}`}>{plazas.texto}</span>}
      </span>
    </button>
  );
}

export default TarjetaDeVuelo;
