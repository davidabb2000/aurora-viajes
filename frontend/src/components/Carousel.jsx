import { useEffect, useRef, useState } from "react";

/**
 * Carousel reutilizable.
 * Recibe un arreglo `items` con objetos { id, imagen, titulo, descripcion }.
 */
function Carousel({ items, autoPlayMs = 5000 }) {
  const [indiceActual, setIndiceActual] = useState(0);
  const totalItems = items.length;
  const timerRef = useRef(null);

  const irASiguiente = () => {
    setIndiceActual((prev) => (prev + 1) % totalItems);
  };

  const irAAnterior = () => {
    setIndiceActual((prev) => (prev - 1 + totalItems) % totalItems);
  };

  const irAIndice = (indice) => {
    setIndiceActual(indice);
  };

  useEffect(() => {
    if (autoPlayMs <= 0) return undefined;
    timerRef.current = setInterval(irASiguiente, autoPlayMs);
    return () => clearInterval(timerRef.current);
  }, [indiceActual, autoPlayMs]);

  if (!items || totalItems === 0) return null;

  return (
    <section aria-roledescription="carrusel" aria-label="Destinos destacados">
      <div className="vidrio relative h-[380px] overflow-hidden rounded-3xl p-1.5 sm:h-[500px]">
        {items.map((item, indice) => (
          <figure
            key={item.id}
            className={`absolute inset-1.5 m-0 overflow-hidden rounded-[1.4rem] transition-opacity duration-700 ${
              indice === indiceActual ? "opacity-100" : "pointer-events-none opacity-0"
            }`}
            aria-hidden={indice !== indiceActual}
          >
            <img src={item.imagen} alt={item.titulo} className="h-full w-full object-cover" />
            <figcaption className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-[#120c38] via-[#120c38]/75 to-transparent px-5 pb-7 pt-12 text-white sm:px-10 sm:pb-8">
              <span className="mb-2.5 inline-block rounded-full border border-white/40 bg-white/15 px-3 py-1 text-xs font-semibold tracking-widest text-acento-suave backdrop-blur-sm">
                {String(indiceActual + 1).padStart(2, "0")} / {String(totalItems).padStart(2, "0")}
              </span>
              <h3 className="font-display text-2xl font-bold sm:text-3xl">{item.titulo}</h3>
              <p className="mt-1.5 max-w-[46ch] text-sm text-white/80 sm:text-[0.95rem]">
                {item.descripcion}
              </p>
            </figcaption>
          </figure>
        ))}

        <button
          type="button"
          onClick={irAAnterior}
          aria-label="Destino anterior"
          className="absolute left-4 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full border border-white/50 bg-white/25 text-xl text-white backdrop-blur-md transition hover:bg-white/90 hover:text-primario focus-visible:outline focus-visible:outline-2 focus-visible:outline-acento sm:left-6 sm:h-12 sm:w-12 sm:text-2xl"
        >
          ‹
        </button>
        <button
          type="button"
          onClick={irASiguiente}
          aria-label="Destino siguiente"
          className="absolute right-4 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full border border-white/50 bg-white/25 text-xl text-white backdrop-blur-md transition hover:bg-white/90 hover:text-primario focus-visible:outline focus-visible:outline-2 focus-visible:outline-acento sm:right-6 sm:h-12 sm:w-12 sm:text-2xl"
        >
          ›
        </button>
      </div>

      <div className="mt-5 flex justify-center gap-2.5" role="tablist" aria-label="Selecciona un destino">
        {items.map((item, indice) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={indice === indiceActual}
            aria-label={`Ir a ${item.titulo}`}
            onClick={() => irAIndice(indice)}
            className={`h-2.5 rounded-full border transition-all focus-visible:outline focus-visible:outline-2 focus-visible:outline-acento ${
              indice === indiceActual
                ? "w-8 border-transparent bg-gradient-to-r from-acento via-primario-suave to-brillo"
                : "w-2.5 border-primario-suave/50 bg-white/50 hover:bg-white"
            }`}
          />
        ))}
      </div>
    </section>
  );
}

export default Carousel;
