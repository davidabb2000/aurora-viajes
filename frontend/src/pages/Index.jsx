import { Link } from "react-router-dom";
import Carousel from "../components/Carousel";
import Sponsors from "../components/Sponsors";
import destinos from "../data/destinos";

const ventajas = [
  { icono: "✈", titulo: "Vuelos incluidos", texto: "Cada reserva sale con su vuelo asignado y su tarifa por pasajero." },
  { icono: "◈", titulo: "Hoteles curados", texto: "Alojamiento verificado en el destino, con noches y habitaciones calculadas." },
  { icono: "✦", titulo: "Excursiones locales", texto: "Actividades guiadas que sumas al viaje y se cobran por separado." },
];

function Index() {
  return (
    <div className="flex-1 py-10 sm:py-14">
      <div className="mx-auto w-[92%] max-w-[1100px]">
        <section className="vidrio filo-aurora mb-10 overflow-hidden rounded-3xl p-7 sm:p-10">
          <div className="max-w-[640px]">
            <span className="inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/60 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-primario-suave backdrop-blur-sm">
              <span className="h-1.5 w-1.5 rounded-full bg-acento" aria-hidden="true" />
              Aurora Viajes
            </span>
            <h1 className="mb-4.5 mt-3.5 font-display text-4xl font-bold leading-tight sm:text-5xl">
              <span className="titulo-aurora">10 destinos que</span>{" "}
              <em className="not-italic text-brillo">merecen</em>{" "}
              <span className="titulo-aurora">tu próximo viaje</span>
            </h1>
            <p className="max-w-[52ch] text-[1.05rem] leading-relaxed text-texto-suave">
              Seleccionamos experiencias con propósito: cultura, naturaleza y buena
              comida en cada parada. Desliza el carrusel para conocer a dónde te
              llevamos primero.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link
                to="/reservas"
                className="rounded-xl bg-gradient-to-br from-primario-suave via-primario to-primario-oscuro px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-primario/30 transition hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primario/40"
              >
                Reservar un viaje
              </Link>
              <Link
                to="/recomendaciones"
                className="vidrio rounded-xl px-5 py-3 text-sm font-semibold text-primario transition hover:-translate-y-0.5 hover:bg-white/80"
              >
                Pedir recomendaciones
              </Link>
            </div>
          </div>
        </section>

        <Carousel items={destinos} />

        <section className="mt-12 grid gap-5 sm:grid-cols-3" aria-label="Qué incluye cada reserva">
          {ventajas.map((ventaja) => (
            <article key={ventaja.titulo} className="vidrio vidrio-interactivo rounded-2xl p-6">
              <span className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-acento-suave via-primario-suave to-brillo text-lg text-white shadow-md shadow-primario/25">
                {ventaja.icono}
              </span>
              <h3 className="mt-4 font-display text-lg font-bold text-primario">{ventaja.titulo}</h3>
              <p className="mt-2 text-sm leading-relaxed text-texto-suave">{ventaja.texto}</p>
            </article>
          ))}
        </section>
      </div>

      <Sponsors />
    </div>
  );
}

export default Index;
