const VARIANTES = {
  primario:
    "bg-primario text-white hover:bg-primario-oscuro focus-visible:outline-acento disabled:bg-primario-suave/50",
  secundario:
    "bg-transparent text-primario border border-borde hover:bg-fondo focus-visible:outline-acento",
  texto:
    "bg-transparent text-primario-suave hover:text-primario underline-offset-2 hover:underline px-0 py-0",
};

/**
 * Botón reutilizable. variant: "primario" | "secundario" | "texto"
 */
function Button({ children, variant = "primario", type = "button", className = "", ...props }) {
  const base =
    variant === "texto"
      ? "text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2"
      : "rounded-md px-5 py-2.5 text-sm font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed";

  return (
    <button type={type} className={`${base} ${VARIANTES[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}

export default Button;
