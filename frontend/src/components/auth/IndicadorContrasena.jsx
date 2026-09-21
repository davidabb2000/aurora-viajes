import { fortalezaDeContrasena, reglasDeContrasena } from "../../utils/validaciones";

const COLORES = ["bg-primario/10", "bg-acento", "bg-oro", "bg-primario-suave", "bg-primario"];

/**
 * Medidor y lista de reglas de una contraseña, en vivo. Es una ayuda para quien escribe:
 * la validación que cuenta es la del servidor.
 */
function IndicadorContrasena({ valor, contexto }) {
  if (!valor) {
    return (
      <p className="vidrio-sutil rounded-xl px-4 py-3 text-xs leading-relaxed text-texto-suave">
        Usa entre 8 y 128 caracteres, con mayúsculas, minúsculas, un número y un carácter especial. Una frase larga funciona muy bien.
      </p>
    );
  }
  const reglas = reglasDeContrasena(valor, contexto);
  const { puntaje, etiqueta } = fortalezaDeContrasena(valor, contexto);
  return (
    <div className="vidrio-sutil rounded-xl px-4 py-3" aria-live="polite">
      <div className="flex items-center gap-3">
        <div className="flex flex-1 gap-1" aria-hidden="true">
          {[1, 2, 3, 4].map((tramo) => (
            <span key={tramo} className={`h-1.5 flex-1 rounded-full transition-colors ${tramo <= puntaje ? COLORES[puntaje] : "bg-primario/10"}`} />
          ))}
        </div>
        <span className="w-24 text-right text-xs font-semibold text-primario">{etiqueta}</span>
      </div>
      <ul className="mt-3 grid gap-1 text-xs sm:grid-cols-2">
        {reglas.map((regla) => (
          <li key={regla.id} className={`flex items-center gap-2 ${regla.cumple ? "text-primario" : "text-texto-suave"}`}>
            <span aria-hidden="true" className={`grid h-4 w-4 place-items-center rounded-full text-[10px] ${regla.cumple ? "bg-primario text-crema" : "border border-primario/25"}`}>
              {regla.cumple ? "✓" : ""}
            </span>
            <span className="sr-only">{regla.cumple ? "Cumple:" : "Falta:"}</span>
            {regla.texto}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default IndicadorContrasena;
