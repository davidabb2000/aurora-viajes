// Clases compartidas por el asistente de reservas y por los paneles.
export const CAMPO =
  "w-full rounded-xl border border-primario/12 bg-white/70 px-3 py-2.5 text-sm text-texto shadow-sm shadow-primario/5 outline-none backdrop-blur-sm transition placeholder:text-texto-suave/60 focus:border-primario-suave focus:bg-white/90 focus:ring-3 focus:ring-primario-suave/20 disabled:opacity-60";

/** Tarjeta que se elige (vuelo, hotel, paquete): la activa se marca con tinta y un punto dorado. */
export const tarjetaElegible = (activa, desactivada = false) =>
  `relative w-full rounded-2xl border p-4 text-left transition ${
    desactivada
      ? "cursor-not-allowed border-primario/8 bg-white/30 opacity-60"
      : activa
        ? "border-primario bg-white shadow-lg shadow-primario/10 ring-2 ring-oro/70"
        : "border-primario/12 bg-white/55 hover:-translate-y-0.5 hover:bg-white/85 hover:shadow-md hover:shadow-primario/10"
  }`;

export const ETIQUETA_MONO = "font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-suave";

export const BOTON_VIDRIO = "vidrio rounded-full px-4 py-2 text-sm font-semibold text-primario transition hover:-translate-y-0.5 hover:bg-white/85 disabled:cursor-not-allowed disabled:opacity-50";

export const CAJA_ERROR = "rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm font-medium text-red-700 backdrop-blur-sm";
