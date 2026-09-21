import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../context/useAuth";
import { IconoPin } from "./Decoraciones";
import { esPersonal } from "../utils/rutas";

const ENLACES = [
  { a: "/recomendaciones", texto: "Recomendaciones" },
  { a: "/quienes-somos", texto: "Quiénes somos" },
  { a: "/contacto", texto: "Contacto" },
];

const ENLACES_MOVIL = [
  { a: "/", texto: "Inicio", fin: true },
  { a: "/#destinos", texto: "Destinos" },
  { a: "/reservas", texto: "Reservar viaje" },
  ...ENLACES,
];

function Header() {
  const { sesion, cerrarSesion, cerrarTodasLasSesiones } = useAuth();
  const { pathname } = useLocation();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [movilAbierto, setMovilAbierto] = useState(false);
  const [desplazado, setDesplazado] = useState(false);
  const menuRef = useRef(null);

  // Sobre el cielo de la portada la barra es de vidrio claro; en cualquier otro
  // sitio, o tras bajar un poco, pasa a tinta para que se lea sobre el papel.
  const enPortada = pathname === "/";
  const oscura = !enPortada || desplazado;
  const tinta = oscura ? "text-primario" : "text-white";

  useEffect(() => {
    const alDesplazar = () => setDesplazado(window.scrollY > 40);
    alDesplazar();
    window.addEventListener("scroll", alDesplazar, { passive: true });
    return () => window.removeEventListener("scroll", alDesplazar);
  }, []);

  useEffect(() => {
    const cerrarSiClicFuera = (evento) => {
      if (menuRef.current && !menuRef.current.contains(evento.target)) setMenuAbierto(false);
    };
    const cerrarConEscape = (evento) => {
      if (evento.key === "Escape") {
        setMenuAbierto(false);
        setMovilAbierto(false);
      }
    };
    document.addEventListener("mousedown", cerrarSiClicFuera);
    document.addEventListener("keydown", cerrarConEscape);
    return () => {
      document.removeEventListener("mousedown", cerrarSiClicFuera);
      document.removeEventListener("keydown", cerrarConEscape);
    };
  }, []);

  // Al cambiar de página se cierran los menús (se ajusta el estado durante el render, sin efecto).
  const [rutaPrevia, setRutaPrevia] = useState(pathname);
  if (rutaPrevia !== pathname) {
    setRutaPrevia(pathname);
    setMenuAbierto(false);
    setMovilAbierto(false);
  }

  useEffect(() => {
    document.body.style.overflow = movilAbierto ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [movilAbierto]);

  const enlaceClase = ({ isActive }) =>
    `rounded-full px-3.5 py-2 text-sm font-medium no-underline transition-colors ${
      isActive ? "bg-white/25" : "hover:bg-white/15"
    }`;

  const inicial = sesion?.usuario?.nombre?.trim()?.charAt(0)?.toUpperCase() || "U";

  return (
    <>
      <header className="pointer-events-none sticky top-0 z-40 h-20">
        <div className="mx-auto grid h-full max-w-350 grid-cols-[1fr_auto_1fr] items-center gap-3 px-4 sm:px-8">
          <p className={`hidden items-center gap-2 font-mono text-xs uppercase tracking-[0.1em] transition-colors lg:flex ${tinta}`}>
            <IconoPin />
            Medellín, CO
          </p>

          <nav
            className="pildora-nav pointer-events-auto col-start-2 flex items-center gap-1 rounded-full p-1.5 sm:p-2"
            data-oscura={oscura}
            aria-label="Navegación principal"
          >
            <Link
              to="/"
              aria-label="Aurora Viajes, ir al inicio"
              className="mr-1 grid h-10 w-10 shrink-0 place-items-center rounded-full bg-oro text-lg text-primario no-underline transition-transform duration-500 ease-resorte hover:rotate-12"
            >
              ✦
            </Link>

            <div className="hidden items-center gap-0.5 md:flex">
              <Link to="/#destinos" className="rounded-full px-3.5 py-2 text-sm font-medium no-underline transition-colors hover:bg-white/15">
                Destinos
              </Link>
              {ENLACES.map((enlace) => (
                <NavLink key={enlace.a} to={enlace.a} className={enlaceClase}>
                  {enlace.texto}
                </NavLink>
              ))}
              <Link to="/reservas" className="boton-claro ml-1 px-4 py-2 text-sm font-semibold no-underline">
                Reservar viaje
              </Link>
            </div>

            <span className="px-2 font-display text-lg md:hidden">Aurora Viajes</span>
            <button
              type="button"
              onClick={() => setMovilAbierto(true)}
              aria-label="Abrir el menú"
              aria-expanded={movilAbierto}
              className="ml-1 grid h-10 w-10 place-items-center rounded-full bg-white/15 md:hidden"
            >
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <path d="M4 8h16M4 16h16" />
              </svg>
            </button>
          </nav>

          <div className="pointer-events-auto col-start-3 hidden justify-self-end md:block">
            {sesion ? (
              <div ref={menuRef} className="relative">
                <button
                  type="button"
                  onClick={() => setMenuAbierto((abierto) => !abierto)}
                  className={`inline-flex items-center gap-2 rounded-full border py-1.5 pl-1.5 pr-3.5 text-sm font-medium backdrop-blur-md transition-colors ${
                    oscura ? "border-primario/15 bg-white/70 text-primario" : "border-white/50 bg-white/20 text-white"
                  }`}
                  aria-haspopup="menu"
                  aria-expanded={menuAbierto}
                >
                  <span className="grid h-8 w-8 place-items-center rounded-full bg-primario text-xs font-bold text-crema">{inicial}</span>
                  <span className="max-w-40 truncate">{sesion.usuario.nombre}</span>
                  <span aria-hidden="true" className="text-xs opacity-70">▾</span>
                </button>

                {menuAbierto && (
                  <div role="menu" aria-label="Menú de usuario" className="vidrio-solido absolute right-0 z-50 mt-2 w-64 overflow-hidden rounded-2xl">
                    <div className="border-b border-primario/10 px-4 py-3">
                      <p className="truncate text-sm font-semibold text-primario">{sesion.usuario.nombre} {sesion.usuario.apellido}</p>
                      <p className="truncate text-xs text-texto-suave">{sesion.usuario.correo}</p>
                    </div>
                    <NavLink
                      to={esPersonal(sesion.usuario) ? "/panel" : "/reservas"}
                      role="menuitem"
                      className="block px-4 py-3 text-sm font-medium text-primario no-underline transition hover:bg-arena/60"
                    >
                      {esPersonal(sesion.usuario) ? "Mi panel" : "Mis reservas"}
                    </NavLink>
                    <NavLink
                      to="/cambiar-contrasena"
                      role="menuitem"
                      className="block px-4 py-3 text-sm font-medium text-primario no-underline transition hover:bg-arena/60"
                    >
                      Cambiar contraseña
                    </NavLink>
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setMenuAbierto(false);
                        cerrarSesion();
                      }}
                      className="block w-full px-4 py-3 text-left text-sm font-medium text-red-700 transition hover:bg-red-50/80"
                    >
                      Cerrar sesión
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setMenuAbierto(false);
                        cerrarTodasLasSesiones();
                      }}
                      className="block w-full border-t border-primario/10 px-4 py-2.5 text-left text-xs text-texto-suave transition hover:bg-arena/60"
                    >
                      Cerrar sesión en todos los dispositivos
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-1">
                <Link
                  to="/login"
                  className={`rounded-full px-4 py-2 text-sm font-medium no-underline transition-colors ${
                    oscura ? "text-primario hover:bg-primario/8" : "text-white hover:bg-white/15"
                  }`}
                >
                  Iniciar sesión
                </Link>
                <Link to="/registro" className={`${oscura ? "boton-tinta" : "boton-claro"} px-4 py-2 text-sm font-semibold no-underline`}>
                  Crear cuenta
                </Link>
              </div>
            )}
          </div>
        </div>
      </header>

      {movilAbierto && (
        <div className="fixed inset-0 z-50 flex flex-col bg-fondo px-6 pb-8 pt-5 md:hidden" role="dialog" aria-modal="true" aria-label="Menú">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs uppercase tracking-[0.1em] text-texto-suave">Aurora Viajes · Medellín, CO</span>
            <button
              type="button"
              onClick={() => setMovilAbierto(false)}
              aria-label="Cerrar el menú"
              className="grid h-11 w-11 place-items-center rounded-full bg-primario text-crema"
            >
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <path d="M6 6l12 12M18 6 6 18" />
              </svg>
            </button>
          </div>

          <nav className="mt-10 flex flex-1 flex-col gap-1" aria-label="Menú móvil">
            {ENLACES_MOVIL.map((enlace) => (
              <Link
                key={enlace.a}
                to={enlace.a}
                onClick={() => setMovilAbierto(false)}
                className="border-b border-primario/10 py-3 font-display text-[2.4rem] leading-tight text-primario no-underline"
              >
                {enlace.texto}
              </Link>
            ))}
          </nav>

          {sesion ? (
            <div className="flex items-center justify-between gap-3">
              <Link
                to={esPersonal(sesion.usuario) ? "/panel" : "/reservas"}
                onClick={() => setMovilAbierto(false)}
                className="boton-tinta px-6 py-3 text-sm font-semibold no-underline"
              >
                {esPersonal(sesion.usuario) ? "Mi panel" : "Mis reservas"}
              </Link>
              <button
                type="button"
                onClick={() => {
                  setMovilAbierto(false);
                  cerrarSesion();
                }}
                className="px-3 py-3 text-sm font-medium text-red-700"
              >
                Cerrar sesión
              </button>
            </div>
          ) : (
            <div className="flex gap-3">
              <Link to="/login" onClick={() => setMovilAbierto(false)} className="flex-1 rounded-full border border-primario/25 px-6 py-3 text-center text-sm font-semibold text-primario no-underline">
                Iniciar sesión
              </Link>
              <Link to="/registro" onClick={() => setMovilAbierto(false)} className="boton-tinta flex-1 px-6 py-3 text-center text-sm font-semibold no-underline">
                Crear cuenta
              </Link>
            </div>
          )}
        </div>
      )}
    </>
  );
}

export default Header;
