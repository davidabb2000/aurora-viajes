const valores = [
  {
    titulo: "Curaduría honesta",
    texto: "Cada destino del catálogo lo visita primero nuestro equipo antes de ofrecerlo.",
  },
  {
    titulo: "Itinerarios flexibles",
    texto: "Diseñamos rutas que se ajustan a tu tiempo y presupuesto, no al revés.",
  },
  {
    titulo: "Acompañamiento real",
    texto: "Soporte humano antes, durante y después del viaje, en tu idioma.",
  },
];

function QuienesSomos() {
  return (
    <div className="flex-1 py-12 sm:py-16">
      <div className="mx-auto w-[92%] max-w-[760px]">
        <span className="mb-3.5 inline-block text-xs font-semibold uppercase tracking-widest text-primario-suave">
          Nuestra historia
        </span>
        <h1 className="mb-4.5 font-display text-3xl font-bold leading-tight text-primario sm:text-4xl">
          Viajamos para que tú no tengas que improvisar
        </h1>
        <p className="mb-10 text-[1.05rem] leading-relaxed text-texto-suave">
          Aurora Viajes nació en 2015 con una idea simple: planear un viaje no
          debería sentirse como un segundo trabajo. Desde entonces hemos
          acompañado a cientos de viajeros a descubrir destinos con sentido,
          combinando experiencia local y atención cercana.
        </p>

        <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
          {valores.map((valor) => (
            <article key={valor.titulo} className="rounded-md border border-borde bg-superficie p-5">
              <h3 className="mb-2 font-display text-lg font-bold text-primario">{valor.titulo}</h3>
              <p className="text-sm leading-relaxed text-texto-suave">{valor.texto}</p>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}

export default QuienesSomos;
