import { Link } from "react-router-dom";
import Revelar from "./Revelar";

function Footer() {
  const anioActual = new Date().getFullYear();

  return (
    <footer className="bg-arena text-primario">
      <div className="mx-auto w-[92%] max-w-300 pb-10 pt-20 sm:pt-28">
        <Revelar>
          <p className="antetitulo">Siguiente parada</p>
          <h2 className="mt-5 font-display text-[clamp(2.9rem,8.5vw,6.75rem)] leading-[1.02] tracking-[-0.03em]">
            ¿Listo para tu
            <br />
            próximo <em className="titulo-enfasis">destino</em>?
          </h2>
          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Link to="/reservas" className="boton-tinta px-7 py-4 text-sm font-semibold no-underline">
              Empezar a reservar
            </Link>
            <a
              href="mailto:contacto@auroraviajes.com"
              className="rounded-full border border-primario/25 px-7 py-4 text-sm font-medium text-primario no-underline transition hover:bg-primario/5"
            >
              contacto@auroraviajes.com
            </a>
          </div>
        </Revelar>

        <div className="mt-20 grid grid-cols-1 gap-10 border-t border-primario/15 pt-10 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <p className="flex items-center gap-2.5 font-display text-2xl">
              <span aria-hidden="true" className="grid h-9 w-9 place-items-center rounded-full bg-oro text-base">✦</span>
              Aurora Viajes
            </p>
            <p className="mt-3 max-w-xs text-sm leading-relaxed text-texto-suave">Diseñando itinerarios memorables desde 2015.</p>
          </div>

          <div>
            <p className="mb-3 font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-suave">Contacto</p>
            <div className="space-y-1.5 text-sm">
              <p>contacto@auroraviajes.com</p>
              <p>+57 350 357 6793</p>
              <p>Medellín, Colombia</p>
            </div>
          </div>

          <div>
            <p className="mb-3 font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-suave">Navegación</p>
            <nav className="flex flex-col items-start gap-2 text-sm" aria-label="Navegación del pie de página">
              {[
                ["/", "Inicio"],
                ["/reservas", "Reservar viaje"],
                ["/recomendaciones", "Recomendaciones"],
                ["/quienes-somos", "Quiénes somos"],
                ["/contacto", "Contacto"],
                ["/registro", "Crear cuenta"],
                ["/acceso-personal", "Acceso del personal"],
              ].map(([a, texto]) => (
                <Link key={a} to={a} className="text-primario no-underline transition hover:translate-x-1 hover:text-acento">
                  {texto}
                </Link>
              ))}
            </nav>
          </div>

          <div>
            <p className="mb-3 font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-suave">Síguenos</p>
            <div className="flex flex-col items-start gap-2 text-sm">
              {[
                ["https://www.instagram.com", "Instagram"],
                ["https://www.facebook.com", "Facebook"],
                ["https://wa.me/573503576793", "WhatsApp"],
              ].map(([href, texto]) => (
                <a key={href} href={href} target="_blank" rel="noreferrer" className="text-primario no-underline transition hover:translate-x-1 hover:text-acento">
                  {texto} ↗
                </a>
              ))}
            </div>
          </div>
        </div>

        <p className="mt-14 font-mono text-[0.7rem] uppercase tracking-[0.1em] text-texto-suave">
          © {anioActual} Aurora Viajes · Hecho en Medellín, Colombia
        </p>
      </div>
    </footer>
  );
}

export default Footer;
