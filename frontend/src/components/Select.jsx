/**
 * Select reutilizable con label y mensaje de error, estilo consistente con Input.
 */
function Select({ label, name, value, onChange, onBlur, error, options, required = false }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm font-medium text-texto">
      <span>
        {label}
        {required && <span className="text-acento"> *</span>}
      </span>
      <select
        name={name}
        value={value}
        onChange={onChange}
        onBlur={onBlur}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${name}-error` : undefined}
        className={`w-full rounded-md border bg-superficie px-3.5 py-2.5 text-[0.95rem] text-texto outline-none transition focus:ring-3 ${
          error
            ? "border-red-400 focus:border-red-400 focus:ring-red-100"
            : "border-borde focus:border-primario-suave focus:ring-primario-suave/15"
        }`}
      >
        <option value="">Selecciona una opción</option>
        {options.map((opcion) => (
          <option key={opcion.value} value={opcion.value}>
            {opcion.label}
          </option>
        ))}
      </select>
      {error && (
        <span id={`${name}-error`} className="text-xs font-medium text-red-600">
          {error}
        </span>
      )}
    </label>
  );
}

export default Select;
