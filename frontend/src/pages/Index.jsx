import Carousel from "../components/Carousel";
import destinos from "../data/destinos";

function Index() {
  return (
    <div className="flex-1 py-12 sm:py-16">
      <div className="mx-auto w-[92%] max-w-[1100px]">
        <section className="mb-10 max-w-[640px]">
          <span className="mb-3.5 inline-block text-xs font-semibold uppercase tracking-widest text-primario-suave">
            Aurora Viajes
          </span>
          <h1 className="mb-4.5 font-display text-4xl font-bold leading-tight text-primario sm:text-5xl">
            10 destinos que <em className="text-acento not-italic">merecen</em> tu próximo viaje
          </h1>
          <p className="max-w-[52ch] text-[1.05rem] leading-relaxed text-texto-suave">
            Seleccionamos experiencias con propósito: cultura, naturaleza y buena
            comida en cada parada. Desliza el carrusel para conocer a dónde te
            llevamos primero.
          </p>
        </section>

        <Carousel items={destinos} />
      </div>
    </div>
  );
}

export default Index;
