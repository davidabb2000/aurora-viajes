import { Link } from "react-router-dom";

const BENEFICIOS = [
  ["✦", "Reserva en minutos", "Elige vuelo, hotel y excursiones y ve el precio final antes de confirmar."],
  ["◈", "Todo en un solo lugar", "Tus reservas, facturas y pagos, siempre a la vista en tu panel."],
  ["◌", "Pagos seguros", "Cobramos con Stripe: nunca guardamos los datos de tu tarjeta."],
];

/**
 * Marco común de las pantallas de acceso: marca, titular y, en pantallas anchas, un panel lateral
 * con los beneficios de tener cuenta. `tema="noche"` es el del acceso del personal.
 */
function AuthShell({ etiqueta, titulo, subtitulo, children, pie, ancho = "max-w-md", conBeneficios = false, tema = "claro" }) {
  const noche = tema === "noche";
  return (
    <div className={`flex flex-1 items-center justify-center px-4 py-12 sm:py-16 ${noche ? "bg-gradient-to-br from-marino via-marino-profundo to-[#020a17]" : ""}`}>
      <div className={`grid w-full gap-6 ${conBeneficios ? "max-w-5xl lg:grid-cols-[0.8fr_1.2fr]" : ancho}`}>
        {conBeneficios && (
          <aside className="relative hidden overflow-hidden rounded-[2rem] bg-gradient-to-br from-marino via-marino-profundo to-[#020a17] p-9 text-white lg:flex lg:flex-col lg:justify-between">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 opacity-80"
              style={{ background: "radial-gradient(24rem 20rem at 100% 0%, rgba(208,81,42,0.34), transparent 62%), radial-gradient(20rem 18rem at 0% 100%, rgba(255,255,255,0.10), transparent 62%)" }}
            />
            <div className="relative">
              <p className="flex items-center gap-2.5 font-display text-2xl">
                <span aria-hidden="true" className="grid h-9 w-9 place-items-center rounded-full bg-oro text-base text-primario">✦</span>
                Aurora Viajes
              </p>
              <h2 className="mt-10 text-4xl leading-tight">
                Viajar se siente distinto cuando todo está <em className="italic text-acento-suave">pensado para ti</em>.
              </h2>
            </div>
            <ul className="relative mt-10 space-y-5">
              {BENEFICIOS.map(([icono, nombre, texto]) => (
                <li key={nombre} className="flex gap-4">
                  <span aria-hidden="true" className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-full border border-white/25 bg-white/10 text-sm">{icono}</span>
                  <span>
                    <strong className="block text-sm font-semibold">{nombre}</strong>
                    <span className="mt-0.5 block text-sm leading-relaxed text-white/70">{texto}</span>
                  </span>
                </li>
              ))}
            </ul>
          </aside>
        )}

        <div className={`${noche ? "vidrio-noche text-white" : "vidrio"} rounded-3xl p-7 sm:p-9`}>
          {!conBeneficios && (
            <Link to="/" className="mb-6 flex items-center justify-center gap-2.5 font-display text-2xl no-underline">
              <span aria-hidden="true" className="grid h-10 w-10 place-items-center rounded-full bg-oro text-lg text-primario">✦</span>
              <span className={noche ? "text-white" : "titulo-aurora"}>Aurora Viajes</span>
            </Link>
          )}
          <span className={`antetitulo ${noche ? "!text-white/70" : ""}`}>{etiqueta}</span>
          <h1 className="mb-2 mt-3 text-3xl sm:text-4xl">
            <span className={noche ? "text-white" : "titulo-aurora"}>{titulo}</span>
          </h1>
          {subtitulo && <p className={`mb-6 text-sm leading-relaxed ${noche ? "text-white/70" : "text-texto-suave"}`}>{subtitulo}</p>}
          {children}
          {pie && <div className={`mt-6 border-t pt-5 text-center text-sm ${noche ? "border-white/15 text-white/70" : "border-primario/10 text-texto-suave"}`}>{pie}</div>}
        </div>
      </div>
    </div>
  );
}

export default AuthShell;
