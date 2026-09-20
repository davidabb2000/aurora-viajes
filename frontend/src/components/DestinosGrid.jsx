import { Link } from "react-router-dom";
import Revelar from "./Revelar";

const precio = (valor) =>
  new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(valor);

/**
 * Cuadrícula asimétrica de destinos: en cada fila una tarjeta ancha y una
 * estrecha, alternando el orden, como en un collage de papel recortado.
 * `items` = { id, imagen, titulo ("Ciudad, País"), descripcion, precioBase? }.
 */
function DestinosGrid({ items }) {
  return (
    <ul className="grid list-none grid-cols-1 gap-5 p-0 md:grid-cols-12 md:gap-6">
      {items.map((destino, indice) => {
        const [ciudad, ...resto] = destino.titulo.split(",");
        const pais = resto.join(",").trim();
        const fila = Math.floor(indice / 2);
        const ancha = (indice % 2 === 0) === (fila % 2 === 0);
        return (
          <li key={destino.id} className={ancha ? "md:col-span-7" : "md:col-span-5"}>
            <Revelar retraso={(indice % 2) * 90} className="h-full">
              <Link
                to={`/reservas?destino=${destino.id}`}
                className="group relative block h-[26rem] overflow-hidden rounded-[2.5rem] bg-marino text-crema no-underline shadow-[0_18px_40px_-30px_rgba(23,21,15,0.5)] transition-shadow duration-350 ease-[cubic-bezier(0.25,0.46,0.45,0.94)] hover:shadow-[0_40px_70px_-32px_rgba(23,21,15,0.6)] md:h-[36rem]"
              >
                <img
                  src={destino.imagen}
                  alt=""
                  loading="lazy"
                  className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-105"
                />
                <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/5 to-black/10" />

                <div className="relative flex h-full flex-col justify-between p-6 sm:p-8">
                  <div className="flex items-start justify-between gap-3">
                    <span className="rounded-full border border-white/40 bg-white/15 px-3.5 py-1.5 font-mono text-[0.68rem] uppercase tracking-[0.12em] backdrop-blur-sm">
                      {String(indice + 1).padStart(2, "0")}
                      {pais && ` · ${pais}`}
                    </span>
                    <span
                      aria-hidden="true"
                      className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-crema text-xl text-primario transition-transform duration-500 ease-resorte group-hover:rotate-45"
                    >
                      →
                    </span>
                  </div>

                  <div>
                    <h3 className="font-display text-[2.6rem] leading-[1.02] sm:text-5xl">{ciudad}</h3>
                    <p className="mt-2 max-w-[36ch] text-sm leading-relaxed text-crema/85">{destino.descripcion}</p>
                    {destino.precioBase > 0 && (
                      <p className="mt-4 font-mono text-xs uppercase tracking-[0.12em] text-oro">
                        Desde {precio(destino.precioBase)} por persona
                      </p>
                    )}
                  </div>
                </div>
                <span className="sr-only">Reservar viaje a {destino.titulo}</span>
              </Link>
            </Revelar>
          </li>
        );
      })}
    </ul>
  );
}

export default DestinosGrid;
