const VARIANTES = {
  primario:
    "bg-gradient-to-br from-primario-suave via-primario to-primario-oscuro text-white shadow-lg shadow-primario/30 hover:shadow-xl hover:shadow-primario/40 hover:-translate-y-0.5 focus-visible:outline-acento disabled:from-primario-suave/40 disabled:via-primario/40 disabled:to-primario/40 disabled:shadow-none disabled:translate-y-0",
  secundario:
    "vidrio text-primario hover:-translate-y-0.5 hover:bg-white/80 focus-visible:outline-acento disabled:opacity-60 disabled:translate-y-0",
  acento:
    "bg-gradient-to-br from-acento-suave via-acento to-primario text-white shadow-lg shadow-acento/30 hover:shadow-xl hover:shadow-acento/40 hover:-translate-y-0.5 focus-visible:outline-primario disabled:opacity-60 disabled:translate-y-0",
  texto:
    "bg-transparent text-primario-suave hover:text-primario underline-offset-2 hover:underline px-0 py-0",
};

/**
 * Botón reutilizable. variant: "primario" | "secundario" | "acento" | "texto"
 */
function Button({ children, variant = "primario", type = "button", className = "", ...props }) {
  const base =
    variant === "texto"
      ? "text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2"
      : "rounded-xl px-5 py-2.5 text-sm font-semibold transition duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed";

  return (
    <button type={type} className={`${base} ${VARIANTES[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}

export default Button;
