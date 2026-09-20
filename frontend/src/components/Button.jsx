const VARIANTES = {
  primario: "boton-tinta focus-visible:outline-acento",
  secundario:
    "border border-primario/25 bg-transparent text-primario hover:bg-primario/5 focus-visible:outline-primario disabled:opacity-60",
  acento: "boton-acento focus-visible:outline-primario disabled:opacity-60",
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
      : "rounded-full px-6 py-2.5 text-sm font-semibold transition duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed";

  return (
    <button type={type} className={`${base} ${VARIANTES[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}

export default Button;
