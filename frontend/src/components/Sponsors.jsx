import Revelar from "./Revelar";

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
        className="max-h-12 max-w-37.5 object-contain opacity-70 grayscale transition duration-300 group-hover:opacity-100 group-hover:grayscale-0"
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
    <section className="bg-fondo py-20 sm:py-28" aria-labelledby="patrocinadores-titulo">
      <Revelar className="mx-auto w-[92%] max-w-300">
        <p className="antetitulo">Nuestros aliados</p>
        <h2 id="patrocinadores-titulo" className="mt-4 max-w-[16ch] font-display text-[clamp(2.3rem,5vw,3.9rem)] leading-[1.04] tracking-[-0.03em]">
          Volamos y dormimos con los mejores
        </h2>
      </Revelar>

      <div className="relative mt-12 flex overflow-hidden border-y border-primario/12 py-3 [mask-image:linear-gradient(90deg,transparent,#000_8%,#000_92%,transparent)]">
        <div className="flex w-max shrink-0 animate-desplazar-logos will-change-transform hover:[animation-play-state:paused]">
          {[...patrocinadores, ...patrocinadores].map((patrocinador, indice) => (
            <LogoPatrocinador key={`${patrocinador.archivo}-${indice}`} patrocinador={patrocinador} />
          ))}
        </div>
      </div>
    </section>
  );
}

export default Sponsors;
