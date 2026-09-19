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
    <div className="flex-1 py-10 sm:py-14">
      <div className="mx-auto w-[92%] max-w-[860px]">
        <section className="vidrio filo-aurora rounded-3xl p-7 sm:p-10">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/60 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-primario-suave backdrop-blur-sm">
            <span className="h-1.5 w-1.5 rounded-full bg-brillo" aria-hidden="true" />
            Nuestra historia
          </span>
          <h1 className="mb-4.5 mt-3.5 font-display text-3xl font-bold leading-tight sm:text-4xl">
            <span className="titulo-aurora">Viajamos para que tú no tengas que improvisar</span>
          </h1>
          <p className="text-[1.05rem] leading-relaxed text-texto-suave">
            Aurora Viajes nació en 2015 con una idea simple: planear un viaje no
            debería sentirse como un segundo trabajo. Desde entonces hemos
            acompañado a cientos de viajeros a descubrir destinos con sentido,
            combinando experiencia local y atención cercana.
          </p>
        </section>

        <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-3">
          {valores.map((valor) => (
            <article key={valor.titulo} className="vidrio vidrio-interactivo rounded-2xl p-6">
              <span className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-acento-suave via-primario-suave to-brillo text-lg text-white shadow-md shadow-primario/25">
                {valor.icono}
              </span>
              <h3 className="mb-2 mt-4 font-display text-lg font-bold text-primario">{valor.titulo}</h3>
              <p className="text-sm leading-relaxed text-texto-suave">{valor.texto}</p>
            </article>
          ))}
        </div>

        <section className="vidrio mt-8 rounded-3xl p-7 sm:p-9" aria-labelledby="hitos-titulo">
          <h2 id="hitos-titulo" className="font-display text-2xl font-bold text-primario">Nuestra línea de tiempo</h2>
          <ol className="mt-6 space-y-5 border-l-2 border-primario-suave/25 pl-6">
            {hitos.map(([anio, texto]) => (
              <li key={anio} className="relative">
                <span
                  className="absolute -left-[1.95rem] top-1 grid h-4 w-4 place-items-center rounded-full bg-gradient-to-br from-acento to-brillo ring-4 ring-white/70"
                  aria-hidden="true"
                />
                <p className="text-sm font-bold uppercase tracking-widest text-primario-suave">{anio}</p>
                <p className="mt-1 text-sm leading-relaxed text-texto-suave">{texto}</p>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  );
}

export default QuienesSomos;
