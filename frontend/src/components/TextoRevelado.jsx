import { useEffect, useMemo, useRef } from "react";

/**
 * Párrafo cuyas palabras se encienden a medida que se hace scroll.
 * `partes` es una lista de { texto, negrita }. Con movimiento reducido, o si
 * el navegador no ofrece matchMedia, todo el texto se ve desde el principio.
 * Las palabras apagadas siguen en el DOM, así que un lector de pantalla lo lee entero.
 */
function TextoRevelado({ partes, className = "" }) {
  const ref = useRef(null);

  const palabras = useMemo(
    () =>
      partes.flatMap((parte, i) =>
        parte.texto
          .split(/\s+/)
          .filter(Boolean)
          .map((palabra, j) => ({ palabra, negrita: Boolean(parte.negrita), clave: `${i}-${j}` })),
      ),
    [partes],
  );

  useEffect(() => {
    const contenedor = ref.current;
    if (!contenedor) return undefined;
    const nodos = contenedor.querySelectorAll("[data-palabra]");
    const reducido = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? true;
    if (reducido) {
      nodos.forEach((nodo) => {
        nodo.style.opacity = "1";
      });
      return undefined;
    }

    let pendiente = false;
    const actualizar = () => {
      pendiente = false;
      const caja = contenedor.getBoundingClientRect();
      const alto = window.innerHeight;
      // 0 cuando el párrafo asoma por abajo; 1 cuando su final llega a media pantalla.
      const progreso = Math.min(1, Math.max(0, (alto * 0.88 - caja.top) / (caja.height + alto * 0.43)));
      const encendidas = Math.round(progreso * nodos.length);
      nodos.forEach((nodo, indice) => {
        nodo.style.opacity = indice < encendidas ? "1" : "0.16";
      });
    };
    const alMover = () => {
      if (!pendiente) {
        pendiente = true;
        requestAnimationFrame(actualizar);
      }
    };

    actualizar();
    window.addEventListener("scroll", alMover, { passive: true });
    window.addEventListener("resize", alMover);
    return () => {
      window.removeEventListener("scroll", alMover);
      window.removeEventListener("resize", alMover);
    };
  }, [palabras]);

  return (
    <p ref={ref} className={className}>
      {palabras.map((item) => (
        <span
          key={item.clave}
          data-palabra=""
          className={`transition-opacity duration-300 ${item.negrita ? "font-bold" : ""}`}
          style={{ opacity: 0.16 }}
        >
          {item.palabra}{" "}
        </span>
      ))}
    </p>
  );
}

export default TextoRevelado;
