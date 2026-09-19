import { NavLink } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";

function Header() {
  const { sesion, cerrarSesion } = useAuth();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const menuRef = useRef(null);

  const enlaceClase = ({ isActive }) =>
    `relative rounded-full px-3 py-1.5 text-sm font-medium transition ${
      isActive
        ? "bg-white/70 text-primario shadow-sm shadow-primario/10"
        : "text-texto-suave hover:bg-white/50 hover:text-primario"
    }`;

  useEffect(() => {
    const cerrarSiClicFuera = (evento) => {
      if (menuRef.current && !menuRef.current.contains(evento.target)) {
        setMenuAbierto(false);
      }
    };

    const cerrarConEscape = (evento) => {
      if (evento.key === "Escape") {
        setMenuAbierto(false);
      }
    };

    document.addEventListener("mousedown", cerrarSiClicFuera);
    document.addEventListener("keydown", cerrarConEscape);
    return () => {
      document.removeEventListener("mousedown", cerrarSiClicFuera);
      document.removeEventListener("keydown", cerrarConEscape);
    };
  }, []);

  return (
    <header className="sticky top-0 z-20 px-3 pt-3 sm:px-5 sm:pt-4">
      <div className="vidrio mx-auto flex w-full max-w-275 flex-col items-center gap-3 rounded-2xl px-5 py-3 sm:flex-row sm:justify-between sm:px-7">
        <NavLink to="/" className="flex items-center gap-2 font-display text-xl font-bold text-primario no-underline">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-acento-suave via-primario-suave to-brillo text-base text-white shadow-md shadow-primario/25">
            ✦
          </span>
          <span className="titulo-aurora">Aurora Viajes</span>
        </NavLink>

        <nav className="flex flex-wrap items-center justify-center gap-1.5 sm:gap-2" aria-label="Navegación principal">
          <NavLink to="/" end className={enlaceClase}>
            Inicio
          </NavLink>

          <NavLink to="/reservas" end className={enlaceClase}>
            Reservar viaje
          </NavLink>

          <NavLink to="/recomendaciones" className={enlaceClase}>
            Recomendaciones
          </NavLink>

          <NavLink to="/quienes-somos" className={enlaceClase}>
            ¿Quiénes Somos?
          </NavLink>
          <NavLink to="/contacto" className={enlaceClase}>
            Contacto
          </NavLink>
          {sesion ? (
            <div ref={menuRef} className="relative">
              <button
                type="button"
                onClick={() => setMenuAbierto((abierto) => !abierto)}
                className="inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/60 px-3 py-1.5 text-sm font-semibold text-primario backdrop-blur-sm transition hover:bg-white/90"
                aria-haspopup="menu"
                aria-expanded={menuAbierto}
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-primario-suave to-primario-oscuro text-xs font-bold text-white">
                  {sesion.usuario.nombre?.trim()?.charAt(0)?.toUpperCase() || "U"}
                </span>
                <span className="max-w-56 truncate">{sesion.usuario.nombre}</span>
                <span aria-hidden="true" className="text-xs text-texto-suave">
                  ▾
                </span>
              </button>

              {menuAbierto && (
                <div
                  role="menu"
                  aria-label="Menú de usuario"
                  className="vidrio-solido absolute right-0 z-30 mt-2 w-52 overflow-hidden rounded-2xl"
                >
                  <NavLink
                    to="/panel"
                    role="menuitem"
                    className="block px-4 py-3 text-sm font-medium text-primario transition hover:bg-white/70"
                    onClick={() => setMenuAbierto(false)}
                  >
                    Mi perfil
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
                </div>
              )}
            </div>
          ) : (
            <NavLink
              to="/login"
              className="rounded-full bg-gradient-to-br from-primario-suave via-primario to-primario-oscuro px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-primario/30 transition hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primario/40"
            >
              Iniciar sesión
            </NavLink>
          )}
        </nav>
      </div>
    </header>
  );
}

export default Header;
