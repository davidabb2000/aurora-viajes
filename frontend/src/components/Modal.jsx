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
      className="fixed inset-0 z-50 flex items-center justify-center bg-primario-oscuro/50 px-4 backdrop-blur-md"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-titulo"
      onClick={alCerrar}
    >
      <div
        className="vidrio-solido filo-aurora max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-3xl p-6 sm:p-8"
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
            className="shrink-0 rounded-full border border-white/60 bg-white/50 p-1.5 text-texto-suave transition hover:bg-white hover:text-primario"
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
