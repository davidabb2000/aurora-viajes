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
      <div className="relative h-[360px] overflow-hidden rounded-md bg-primario shadow-[0_20px_40px_-24px_rgba(15,61,62,0.35)] sm:h-[480px]">
        {items.map((item, indice) => (
          <figure
            key={item.id}
            className={`absolute inset-0 m-0 transition-opacity duration-700 ${
              indice === indiceActual ? "opacity-100" : "pointer-events-none opacity-0"
            }`}
            aria-hidden={indice !== indiceActual}
          >
            <img src={item.imagen} alt={item.titulo} className="h-full w-full object-cover" />
            <figcaption className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-[#0d1a18] via-[#0d1a18]/70 to-transparent px-5 pb-7 pt-10 text-[#f7f4ee] sm:px-10 sm:pb-8">
              <span className="mb-2.5 inline-block rounded-full border border-acento/60 px-2.5 py-0.5 text-xs font-semibold tracking-widest text-acento">
                {String(indiceActual + 1).padStart(2, "0")} / {String(totalItems).padStart(2, "0")}
              </span>
              <h3 className="font-display text-2xl font-bold sm:text-3xl">{item.titulo}</h3>
              <p className="mt-1.5 max-w-[46ch] text-sm text-[#e7e2d4] sm:text-[0.95rem]">
                {item.descripcion}
              </p>
            </figcaption>
          </figure>
        ))}

        <button
          type="button"
          onClick={irAAnterior}
          aria-label="Destino anterior"
          className="absolute left-3 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-[#f7f4ee]/90 text-xl text-primario transition hover:bg-acento hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-acento sm:left-[18px] sm:h-11 sm:w-11 sm:text-2xl"
        >
          ‹
        </button>
        <button
          type="button"
          onClick={irASiguiente}
          aria-label="Destino siguiente"
          className="absolute right-3 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-[#f7f4ee]/90 text-xl text-primario transition hover:bg-acento hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-acento sm:right-[18px] sm:h-11 sm:w-11 sm:text-2xl"
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
            className={`h-2.5 w-2.5 rounded-full border transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-acento ${
              indice === indiceActual
                ? "scale-125 border-acento bg-acento"
                : "border-primario-suave bg-transparent"
            }`}
          />
        ))}
      </div>
    </section>
  );
}

export default Carousel;
