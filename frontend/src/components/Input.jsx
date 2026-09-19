/**
 * Input reutilizable con label, mensaje de error y estilos Tailwind.
 * Se apoya en el estado y las validaciones que maneja el formulario padre.
 */
function Input({
  label,
  name,
  type = "text",
  value,
  onChange,
  onBlur,
  error,
  placeholder,
  maxLength,
  required = false,
  autoComplete,
  botonContrasena = false,
  mostrarContrasena = false,
  cambiarVisibilidad,
}) {
  return (
    <label className="flex flex-col gap-1.5 text-sm font-medium text-texto">
      <span>
        {label}
        {required && <span className="text-brillo"> *</span>}
      </span>
      <span className="relative block">
        <input
          type={type}
          name={name}
          value={value}
          onChange={onChange}
          onBlur={onBlur}
          placeholder={placeholder}
          maxLength={maxLength}
          autoComplete={autoComplete}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${name}-error` : undefined}
          className={`w-full rounded-xl border bg-white/70 px-3.5 py-2.5 text-[0.95rem] text-texto backdrop-blur-sm placeholder:text-texto-suave/60 outline-none transition focus:bg-white/90 focus:ring-3 ${
            error
              ? "border-red-400 focus:border-red-400 focus:ring-red-100"
              : "border-white/70 shadow-sm shadow-primario/5 focus:border-primario-suave focus:ring-primario-suave/20"
          } ${botonContrasena ? "pr-20" : ""}`}
        />
        {botonContrasena && (
          <button
            type="button"
            onClick={cambiarVisibilidad}
            className="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer text-xs font-semibold text-primario-suave hover:text-primario"
            aria-label={mostrarContrasena ? "Ocultar contraseña" : "Ver contraseña"}
          >
            {mostrarContrasena ? "Ocultar" : "Ver"}
          </button>
        )}
      </span>
      {error && (
        <span id={`${name}-error`} className="text-xs font-medium text-red-600">
          {error}
        </span>
      )}
    </label>
  );
}

export default Input;
