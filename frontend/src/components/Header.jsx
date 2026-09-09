import { NavLink } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";

function Header() {
  const { sesion, cerrarSesion } = useAuth();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const menuRef = useRef(null);

  const enlaceClase = ({ isActive }) =>
    `border-b-2 pb-1 text-sm font-medium transition-colors ${
      isActive
        ? "border-acento text-primario"
        : "border-transparent text-texto-suave hover:text-primario"
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
    <header className="sticky top-0 z-20 border-b border-borde bg-superficie/95 backdrop-blur">
      <div className="mx-auto flex w-[92%] max-w-275 flex-col items-center gap-3 py-4 sm:flex-row sm:justify-between">
        <NavLink to="/" className="flex items-center gap-2 font-display text-xl font-bold text-primario no-underline">
          <span className="text-acento">✦</span>
          Aurora Viajes
        </NavLink>

        <nav className="flex flex-wrap items-center justify-center gap-5 sm:gap-7" aria-label="Navegación principal">
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
                className="inline-flex items-center gap-2 rounded-full border border-borde bg-superficie px-4 py-2 text-sm font-semibold text-primario transition hover:border-primario-suave hover:bg-fondo"
                aria-haspopup="menu"
                aria-expanded={menuAbierto}
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primario text-xs font-bold text-white">
                  {sesion.usuario.nombre?.trim()?.charAt(0)?.toUpperCase() || "U"}
                </span>
                <span className="max-w-[14rem] truncate">{sesion.usuario.nombre}</span>
                <span aria-hidden="true" className="text-xs text-texto-suave">
                  ▾
                </span>
              </button>

              {menuAbierto && (
                <div
                  role="menu"
                  aria-label="Menú de usuario"
                  className="absolute right-0 z-30 mt-2 w-52 overflow-hidden rounded-lg border border-borde bg-white shadow-lg"
                >
                  <NavLink
                    to="/panel"
                    role="menuitem"
                    className="block px-4 py-3 text-sm font-medium text-primario transition hover:bg-fondo"
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
                    className="block w-full px-4 py-3 text-left text-sm font-medium text-red-700 transition hover:bg-red-50"
                  >
                    Cerrar sesión
                  </button>
                </div>
              )}
            </div>
          ) : (
            <NavLink to="/login" className="rounded-md bg-primario px-4 py-2 text-sm font-semibold text-white transition hover:bg-primario-oscuro">
              Iniciar sesión
            </NavLink>
          )}
        </nav>
      </div>
    </header>
  );
}

export default Header;
