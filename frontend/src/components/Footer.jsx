import { Link } from "react-router-dom";
import GoogleMap from "./GoogleMap";

function Footer() {
  const anioActual = new Date().getFullYear();

  return (
    <footer className="relative mt-20 overflow-hidden bg-gradient-to-b from-primario-oscuro via-[#1b1350] to-[#120c38] text-[#d9d5f5]">
      {/* Halos de aurora detrás del pie de página */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-70"
        style={{
          background:
            "radial-gradient(38rem 26rem at 12% 0%, rgba(110,231,220,0.28), transparent 65%), radial-gradient(34rem 26rem at 88% 20%, rgba(214,51,108,0.26), transparent 65%)",
        }}
      />

      <div className="relative">
        {/* Sección de mapa */}
        <div className="py-12">
          <div className="mx-auto w-[92%] max-w-[1100px]">
            <h3 className="mb-6 flex items-center gap-3 text-lg font-bold text-white">
              <span className="h-px w-8 bg-gradient-to-r from-acento-suave to-transparent" aria-hidden="true" />
              Encuéntranos
            </h3>
            <GoogleMap />
          </div>
        </div>

        {/* Sección de contenido del footer */}
        <div className="mx-auto grid w-[92%] max-w-[1100px] grid-cols-1 gap-10 py-12 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <p className="mb-3 flex items-center gap-2 font-display text-xl font-bold text-white">
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-acento-suave via-primario-suave to-brillo text-base text-white">✦</span>
              Aurora Viajes
            </p>
            <p className="max-w-xs text-sm leading-relaxed text-[#b7b1e0]">Diseñando itinerarios memorables desde 2015.</p>
          </div>

          <div>
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-acento-suave">Contacto</p>
            <div className="space-y-1.5 text-sm text-[#b7b1e0]"><p>contacto@auroraviajes.com</p><p>+57 3503576793</p></div>
          </div>

          <div>
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-acento-suave">Navegación</p>
            <nav className="flex flex-col items-start gap-2 text-sm text-[#b7b1e0]" aria-label="Navegación del pie de página">
              <Link to="/" className="transition hover:translate-x-1 hover:text-white">Inicio</Link>
              <Link to="/recomendaciones" className="transition hover:translate-x-1 hover:text-white">Recomendaciones</Link>
              <Link to="/quienes-somos" className="transition hover:translate-x-1 hover:text-white">Quiénes somos</Link>
              <Link to="/reservas" className="transition hover:translate-x-1 hover:text-white">Reservas</Link>
              <Link to="/contacto" className="transition hover:translate-x-1 hover:text-white">Contacto</Link>
            </nav>
          </div>

          <div>
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-acento-suave">Síguenos</p>
            <div className="flex flex-col items-start gap-2 text-sm text-[#b7b1e0]">
              <a href="https://www.instagram.com" target="_blank" rel="noreferrer" className="transition hover:translate-x-1 hover:text-white">Instagram</a>
              <a href="https://www.facebook.com" target="_blank" rel="noreferrer" className="transition hover:translate-x-1 hover:text-white">Facebook</a>
              <a href="https://wa.me/573503576793" target="_blank" rel="noreferrer" className="transition hover:translate-x-1 hover:text-white">WhatsApp</a>
            </div>
          </div>
        </div>

        <div className="border-t border-white/10 py-5">
          <p className="mx-auto w-[92%] max-w-[1100px] text-xs text-[#8f89ba]">
            © {anioActual} Aurora Viajes. Todos los derechos reservados.
          </p>
        </div>
      </div>
    </footer>
  );
}

export default Footer;
