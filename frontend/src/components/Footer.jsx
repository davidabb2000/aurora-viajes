import { Link } from "react-router-dom";

function Footer() {
  const anioActual = new Date().getFullYear();

  return (
    <footer className="mt-16 border-t-4 border-acento bg-primario-oscuro text-[#e7e2d4]">
      <div className="mx-auto grid w-[92%] max-w-[1100px] grid-cols-1 gap-10 py-12 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <p className="mb-3 flex items-center gap-2 font-display text-xl font-bold text-white"><span className="text-acento">✦</span>Aurora Viajes</p>
          <p className="max-w-xs text-sm leading-relaxed text-[#cfc9b8]">Diseñando itinerarios memorables desde 2015.</p>
        </div>

        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-acento">Contacto</p>
          <div className="space-y-1.5 text-sm text-[#cfc9b8]"><p>contacto@auroraviajes.com</p><p>+57 3503576793</p></div>
        </div>

        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-acento">Navegación</p>
          <nav className="flex flex-col items-start gap-2 text-sm text-[#cfc9b8]" aria-label="Navegación del pie de página">
            <Link to="/" className="transition hover:translate-x-1 hover:text-white">Inicio</Link>
            <Link to="/recomendaciones" className="transition hover:translate-x-1 hover:text-white">Recomendaciones</Link>
            <Link to="/quienes-somos" className="transition hover:translate-x-1 hover:text-white">Quiénes somos</Link>
            <Link to="/reservas" className="transition hover:translate-x-1 hover:text-white">Reservas</Link>
            <Link to="/contacto" className="transition hover:translate-x-1 hover:text-white">Contacto</Link>
          </nav>
        </div>

        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-acento">Síguenos</p>
          <div className="flex flex-col items-start gap-2 text-sm text-[#cfc9b8]">
            <a href="https://www.instagram.com" target="_blank" rel="noreferrer" className="transition hover:translate-x-1 hover:text-white">Instagram</a>
            <a href="https://www.facebook.com" target="_blank" rel="noreferrer" className="transition hover:translate-x-1 hover:text-white">Facebook</a>
            <a href="https://wa.me/573503576793" target="_blank" rel="noreferrer" className="transition hover:translate-x-1 hover:text-white">WhatsApp</a>
          </div>
        </div>
      </div>

      <div className="border-t border-white/10 py-5">
        <p className="mx-auto w-[92%] max-w-[1100px] text-xs text-[#a9a390]">
          © {anioActual} Aurora Viajes. Todos los derechos reservados.
        </p>
      </div>
    </footer>
  );
}

export default Footer;
