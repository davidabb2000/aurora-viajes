const patrocinadores = [
  { nombre: "Airbnb", archivo: "airbnb.webp" },
  { nombre: "Avianca", archivo: "avianca.png" },
  { nombre: "LATAM", archivo: "latam.webp" },
  { nombre: "Copa Airlines", archivo: "copa-airlines.png" },
  { nombre: "Iberia", archivo: "iberia.png" },
  { nombre: "Viator", archivo: "viator.png" },
  { nombre: "National Geographic Expeditions", archivo: "national-geographic-expeditions.png" },
];

function LogoPatrocinador({ patrocinador }) {
  return (
    <div className="group flex h-20 min-w-45 shrink-0 items-center justify-center gap-3 px-5 sm:min-w-55">
      <img
        src={`/logos/patrocinadores/${patrocinador.archivo}`}
        alt={`Logo de ${patrocinador.nombre}`}
        className="max-h-12 max-w-37.5 object-contain grayscale transition duration-300 group-hover:grayscale-0"
        onError={(event) => {
          event.currentTarget.hidden = true;
          event.currentTarget.nextElementSibling.hidden = false;
        }}
      />
      <span className="hidden max-w-42.5 text-center text-sm font-semibold tracking-wide text-primario-suave">
        {patrocinador.nombre}
      </span>
    </div>
  );
}

function Sponsors() {
  return (
    <section className="mt-16 sm:mt-20" aria-labelledby="patrocinadores-titulo">
      <div className="mx-auto w-[92%] max-w-275 overflow-hidden rounded-md border border-borde bg-superficie shadow-[0_18px_45px_-30px_rgba(15,61,62,0.45)]">
        <div className="flex items-center justify-center gap-4 px-5 pb-5 pt-7 sm:gap-6 sm:pt-8">
          <span className="h-px w-10 bg-acento sm:w-16" aria-hidden="true" />
          <h2 id="patrocinadores-titulo" className="text-center text-xs font-semibold uppercase tracking-[0.28em] text-primario">
            Patrocinadores
          </h2>
          <span className="h-px w-10 bg-acento sm:w-16" aria-hidden="true" />
        </div>

        <div className="relative flex overflow-hidden border-t border-borde/70 bg-fondo/55 py-2">
          <div className="flex w-max shrink-0 animate-desplazar-logos will-change-transform hover:[animation-play-state:paused]">
            {[...patrocinadores, ...patrocinadores].map((patrocinador, indice) => (
              <LogoPatrocinador key={`${patrocinador.archivo}-${indice}`} patrocinador={patrocinador} />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export default Sponsors;