import { useEffect, useRef, useState } from "react";

/**
 * Hace aparecer a su contenido cuando entra en pantalla. La animación vive en
 * la clase `.revelar` de index.css, que solo oculta el contenido si hay JS.
 */
function Revelar({ as: Etiqueta = "div", retraso = 0, className = "", style, children, ...resto }) {
  const ref = useRef(null);
  // Sin IntersectionObserver (navegadores muy antiguos) el contenido se muestra desde el principio.
  const [visible, setVisible] = useState(() => typeof IntersectionObserver === "undefined");

  useEffect(() => {
    const nodo = ref.current;
    if (!nodo) return undefined;
    if (typeof IntersectionObserver === "undefined") return undefined;
    const observador = new IntersectionObserver(
      (entradas) => {
        if (entradas.some((entrada) => entrada.isIntersecting)) {
          setVisible(true);
          observador.disconnect();
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -6% 0px" },
    );
    observador.observe(nodo);
    return () => observador.disconnect();
  }, []);

  return (
    <Etiqueta
      ref={ref}
      className={`revelar ${visible ? "visible" : ""} ${className}`}
      style={{ "--retraso": `${retraso}ms`, ...style }}
      {...resto}
    >
      {children}
    </Etiqueta>
  );
}

export default Revelar;
