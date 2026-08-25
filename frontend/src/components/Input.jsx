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
}) {
  return (
    <label className="flex flex-col gap-1.5 text-sm font-medium text-texto">
      <span>
        {label}
        {required && <span className="text-acento"> *</span>}
      </span>
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
        className={`w-full rounded-md border bg-superficie px-3.5 py-2.5 text-[0.95rem] text-texto placeholder:text-texto-suave/60 outline-none transition focus:ring-3 ${
          error
            ? "border-red-400 focus:border-red-400 focus:ring-red-100"
            : "border-borde focus:border-primario-suave focus:ring-primario-suave/15"
        }`}
      />
      {error && (
        <span id={`${name}-error`} className="text-xs font-medium text-red-600">
          {error}
        </span>
      )}
    </label>
  );
}

export default Input;
