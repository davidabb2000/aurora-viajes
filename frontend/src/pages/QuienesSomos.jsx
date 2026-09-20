import Revelar from "../components/Revelar";

const valores = [
  {
    titulo: "Curaduría honesta",
    texto: "Cada destino del catálogo lo visita primero nuestro equipo antes de ofrecerlo.",
    icono: "◎",
  },
  {
    titulo: "Itinerarios flexibles",
    texto: "Diseñamos rutas que se ajustan a tu tiempo y presupuesto, no al revés.",
    icono: "◇",
  },
  {
    titulo: "Acompañamiento real",
    texto: "Soporte humano antes, durante y después del viaje, en tu idioma.",
    icono: "✧",
  },
];

const hitos = [
  ["2015", "Nace Aurora Viajes con tres destinos y un equipo de cuatro personas."],
  ["2019", "Abrimos la operación de vuelos propios y alianzas con hoteles locales."],
  ["2024", "Sumamos excursiones guiadas y reservas en línea de extremo a extremo."],
];

function QuienesSomos() {
  return (
    <div className="flex-1">
      <section className="bg-fondo pb-20 pt-8 sm:pb-28 sm:pt-16">
        <Revelar className="mx-auto w-[92%] max-w-300">
          <span className="antetitulo">Nuestra historia</span>
          <h1 className="mt-5 max-w-[15ch] text-[clamp(3rem,8.4vw,6.8rem)] leading-[1.02] tracking-[-0.03em]">
            <span className="titulo-aurora">
              Viajamos para que tú no tengas que <em className="titulo-enfasis">improvisar</em>
            </span>
          </h1>
          <p className="mt-9 max-w-[54ch] text-lg leading-relaxed text-texto-suave sm:text-xl">
            Aurora Viajes nació en 2015 con una idea simple: planear un viaje no
            debería sentirse como un segundo trabajo. Desde entonces hemos
            acompañado a cientos de viajeros a descubrir destinos con sentido,
            combinando experiencia local y atención cercana.
          </p>
        </Revelar>
      </section>

      <section className="bg-arena py-20 sm:py-28" aria-label="Nuestros valores">
        <div className="mx-auto grid w-[92%] max-w-300 grid-cols-1 gap-6 md:grid-cols-3">
          {valores.map((valor, indice) => (
            <Revelar as="article" key={valor.titulo} retraso={indice * 110} className="rounded-[2.1rem] bg-fondo p-8 shadow-[0_1px_0_rgba(255,255,255,0.9)_inset,0_30px_50px_-36px_rgba(23,21,15,0.45)]">
              <span className="grid h-12 w-12 place-items-center rounded-full bg-oro text-xl text-primario">{valor.icono}</span>
              <h3 className="mb-3 mt-6 font-display text-[1.9rem] leading-tight text-primario">{valor.titulo}</h3>
              <p className="leading-relaxed text-texto-suave">{valor.texto}</p>
            </Revelar>
          ))}
        </div>
      </section>

      <section className="bg-fondo py-20 sm:py-28" aria-labelledby="hitos-titulo">
        <div className="mx-auto w-[92%] max-w-245">
          <Revelar>
            <span className="antetitulo">Línea de tiempo</span>
            <h2 id="hitos-titulo" className="mt-4 text-[clamp(2.4rem,5vw,3.8rem)] leading-[1.05] tracking-[-0.03em] text-primario">
              Diez años de trayecto
            </h2>
          </Revelar>
          <ol className="mt-12 list-none space-y-10 border-l border-primario/20 p-0 pl-8">
            {hitos.map(([anio, texto], indice) => (
              <Revelar as="li" key={anio} retraso={indice * 100} className="relative">
                <span
                  className="absolute -left-[2.55rem] top-2 h-4 w-4 rounded-full bg-oro ring-4 ring-fondo"
                  aria-hidden="true"
                />
                <p className="font-display text-5xl leading-none text-acento">{anio}</p>
                <p className="mt-3 max-w-[50ch] text-lg leading-relaxed text-texto-suave">{texto}</p>
              </Revelar>
            ))}
          </ol>
        </div>
      </section>
    </div>
  );
}

export default QuienesSomos;
