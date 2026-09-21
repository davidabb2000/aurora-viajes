import { CAJA_ERROR } from "../../components/reserva/estilos";

/** Cabecera común de las vistas del panel: etiqueta, título y acciones a la derecha. */
export function EncabezadoDePanel({ etiqueta, titulo, descripcion, children }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <span className="antetitulo">{etiqueta}</span>
        <h1 className="mt-3 text-4xl text-primario sm:text-5xl">{titulo}</h1>
        {descripcion && <p className="mt-2 max-w-2xl text-texto-suave">{descripcion}</p>}
      </div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </header>
  );
}

/** Aviso de éxito o de error, con lectura automática para lectores de pantalla. */
export function Aviso({ mensaje, tipo = "info", alCerrar }) {
  if (!mensaje) return null;
  const clase = tipo === "error" ? CAJA_ERROR : "vidrio-sutil rounded-xl px-4 py-3 text-sm font-medium text-primario";
  return (
    <p role={tipo === "error" ? "alert" : "status"} className={`${clase} mt-4 flex items-start justify-between gap-3`}>
      <span>{mensaje}</span>
      {alCerrar && <button type="button" onClick={alCerrar} aria-label="Cerrar aviso" className="shrink-0 font-semibold">×</button>}
    </p>
  );
}

/** Paginación simple sobre una lista ya cargada. */
export function Paginacion({ pagina, total, porPagina = 10, alCambiar }) {
  const paginas = Math.max(1, Math.ceil(total / porPagina));
  if (paginas <= 1) return null;
  return (
    <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-primario/12 pt-4 text-sm">
      <span className="text-texto-suave">Página {pagina} de {paginas} · {total} resultados</span>
      <div className="flex gap-2">
        <button type="button" disabled={pagina === 1} onClick={() => alCambiar(pagina - 1)} className="vidrio rounded-full px-4 py-1.5 font-semibold text-primario transition hover:bg-white/85 disabled:cursor-not-allowed disabled:opacity-40">Anterior</button>
        <button type="button" disabled={pagina >= paginas} onClick={() => alCambiar(pagina + 1)} className="vidrio rounded-full px-4 py-1.5 font-semibold text-primario transition hover:bg-white/85 disabled:cursor-not-allowed disabled:opacity-40">Siguiente</button>
      </div>
    </div>
  );
}
