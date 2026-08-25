import { useEffect } from "react";

/**
 * Modal reutilizable. Se cierra con la X, el fondo o la tecla Escape.
 */
function Modal({ abierto, alCerrar, titulo, children }) {
  useEffect(() => {
    if (!abierto) return undefined;

    const manejarTecla = (evento) => {
      if (evento.key === "Escape") alCerrar();
    };

    document.addEventListener("keydown", manejarTecla);
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", manejarTecla);
      document.body.style.overflow = "";
    };
  }, [abierto, alCerrar]);

  if (!abierto) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-primario-oscuro/60 px-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-titulo"
      onClick={alCerrar}
    >
      <div
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-superficie p-6 shadow-2xl sm:p-8"
        onClick={(evento) => evento.stopPropagation()}
      >
        <div className="mb-5 flex items-start justify-between gap-4">
          <h2 id="modal-titulo" className="font-display text-xl font-bold text-primario sm:text-2xl">
            {titulo}
          </h2>
          <button
            type="button"
            onClick={alCerrar}
            aria-label="Cerrar"
            className="shrink-0 rounded-full p-1 text-texto-suave transition hover:bg-fondo hover:text-primario"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export default Modal;
