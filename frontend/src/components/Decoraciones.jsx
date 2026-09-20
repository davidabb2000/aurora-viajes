/**
 * Piezas decorativas de la portada: papel recortado, sol rayado, sendero de
 * vuelo y un pase de abordar. Todas son aria-hidden: no aportan contenido.
 */

export function IconoPin({ className = "h-4 w-4" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11Z" />
      <circle cx="12" cy="10" r="2.4" />
    </svg>
  );
}

export function IconoAvion({ className = "h-4 w-4" }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M2.5 11.2 21 3.5c.7-.3 1.4.4 1.1 1.1l-7.7 18.5c-.3.7-1.3.7-1.6 0l-2.6-6.9-6.9-2.6c-.7-.3-.7-1.3.2-1.4Z" opacity=".92" />
    </svg>
  );
}

export function Nube({ className = "" }) {
  return (
    <svg viewBox="0 0 240 100" className={className} aria-hidden="true" fill="currentColor">
      <path d="M22 100C8 100 0 90 0 79c0-13 11-24 26-25 3-20 21-34 43-34 14 0 26 7 33 17 6-3 13-5 21-5 20 0 35 14 36 32 3-1 6-2 10-2 14 0 25 11 25 24 0 7-3 14-9 14H22Z" />
    </svg>
  );
}

/** Círculo dorado con rayas diagonales, que gira despacio. */
export function SolRayado({ className = "" }) {
  return (
    <div
      aria-hidden="true"
      className={`animate-girar-lento rounded-full ${className}`}
      style={{
        background:
          "repeating-linear-gradient(-45deg, var(--color-oro) 0 9px, rgba(255, 246, 190, 0.85) 9px 17px)",
        boxShadow: "0 0 0 10px rgba(255, 218, 63, 0.18), 0 0 60px 10px rgba(255, 218, 63, 0.35)",
      }}
    />
  );
}

/** Curva discontinua de un vuelo, con un avión de papel que la recorre. */
export function SenderoDeVuelo({ className = "" }) {
  const ruta = "M8 292 C 120 250, 160 60, 300 96 S 470 210, 592 24";
  const reducido = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  return (
    <svg viewBox="0 0 600 300" className={className} aria-hidden="true" fill="none">
      <path d={ruta} stroke="rgba(255,255,255,0.8)" strokeWidth="2.2" strokeDasharray="7 9" strokeLinecap="round" />
      {reducido ? (
        <path d="M-13 -7 L15 0 L-13 7 L-7 0 Z" fill="#fff9e9" transform="translate(300 96) rotate(-14)" />
      ) : (
        <g fill="#fff9e9">
          <path d="M-13 -7 L15 0 L-13 7 L-7 0 Z" />
          <animateMotion dur="11s" repeatCount="indefinite" rotate="auto" path={ruta} />
        </g>
      )}
    </svg>
  );
}

/** Borde de nubes de papel que une el cielo con la hoja crema. */
export function BordeDeNubes({ className = "" }) {
  return (
    <svg viewBox="0 0 1440 200" preserveAspectRatio="none" className={className} aria-hidden="true" fill="currentColor">
      <path d="M0 200V128c34 0 58-26 104-26 14-28 58-40 94-22 30-30 88-30 118 8 44-14 84 6 96 40 42-10 82 4 100 34 58-40 148-46 204-10 42-36 128-40 172-2 44-24 104-12 128 26 40-6 76 6 96 32 52-22 118-22 160 8 30-28 86-36 118-8V200Z" />
    </svg>
  );
}

/** Pase de abordar de adorno: el equivalente del reproductor de la referencia. */
export function PaseDeAbordar({ className = "" }) {
  return (
    <div
      aria-hidden="true"
      className={`select-none rounded-[1.7rem] bg-crema p-3.5 text-primario shadow-[0_26px_50px_-24px_rgba(3,24,53,0.75),0_0_0_1px_rgba(23,21,15,0.06)] ${className}`}
    >
      <div className="flex items-center justify-between px-1 font-mono text-[0.62rem] uppercase tracking-[0.14em] text-texto-suave">
        <span>Pase de abordar</span>
        <span>AUR 301</span>
      </div>
      <div className="mt-2 flex items-center gap-3 px-1">
        <div>
          <p className="font-display text-[2rem] leading-none">BOG</p>
          <p className="font-mono text-[0.6rem] uppercase tracking-wider text-texto-suave">Bogotá</p>
        </div>
        <div className="relative h-7 flex-1">
          <span className="absolute inset-x-0 top-1/2 border-t-2 border-dashed border-primario/25" />
          <span className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 animate-avanzar text-acento">
            <IconoAvion className="h-5 w-5 rotate-45" />
          </span>
        </div>
        <div className="text-right">
          <p className="font-display text-[2rem] leading-none">CDG</p>
          <p className="font-mono text-[0.6rem] uppercase tracking-wider text-texto-suave">París</p>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between rounded-2xl bg-arena px-3.5 py-2 font-mono text-[0.62rem] uppercase tracking-[0.12em]">
        <span>Puerta A10</span>
        <span>Terminal 1</span>
        <span>Asiento 12A</span>
      </div>
    </div>
  );
}
