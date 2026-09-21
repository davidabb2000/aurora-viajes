import { useEffect, useRef, useState } from "react";

const DIRECCION = "Medellín, Colombia";
const URL_INCRUSTADA = `https://www.google.com/maps?q=${encodeURIComponent(DIRECCION)}&z=13&hl=es&output=embed`;

/**
 * Mapa de Google con la ubicación de la empresa. Usa la vista embebida pública, que no necesita clave de API.
 * Vive en el pie de todas las páginas, así que el marco solo se carga cuando queda cerca de la pantalla: en las
 * páginas en las que nadie llega hasta abajo no se le pide nada a Google. `className` fija la altura.
 */
function GoogleMap({ className = "h-80" }) {
  const contenedor = useRef(null);
  // Sin IntersectionObserver (navegadores muy antiguos) el mapa se carga desde el principio.
  const [cerca, setCerca] = useState(() => typeof IntersectionObserver === "undefined");

  useEffect(() => {
    const nodo = contenedor.current;
    if (cerca || !nodo) return undefined;
    const observador = new IntersectionObserver(
      (entradas) => {
        if (entradas.some((entrada) => entrada.isIntersecting)) setCerca(true);
      },
      { rootMargin: "300px" },
    );
    observador.observe(nodo);
    return () => observador.disconnect();
  }, [cerca]);

  return (
    <div ref={contenedor} className={`vidrio w-full overflow-hidden rounded-[2.1rem] p-1.5 ${className}`}>
      {cerca && (
        <iframe
          width="100%"
          height="100%"
          style={{ border: 0, borderRadius: "1.65rem" }}
          allowFullScreen
          referrerPolicy="no-referrer-when-downgrade"
          src={URL_INCRUSTADA}
          title="Ubicación de Aurora Viajes"
        />
      )}
    </div>
  );
}

export default GoogleMap;
