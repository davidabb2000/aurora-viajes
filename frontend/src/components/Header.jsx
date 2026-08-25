import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { cerrarSesion, obtenerSesion } from "../utils/api";

function Header() {
  const [sesion, setSesion] = useState(obtenerSesion);

  useEffect(() => {
    const actualizar = () => setSesion(obtenerSesion());
    window.addEventListener("aurora-sesion", actualizar);
    return () => window.removeEventListener("aurora-sesion", actualizar);
  }, []);

  const enlaceClase = ({ isActive }) =>
    `border-b-2 pb-1 text-sm font-medium transition-colors ${
      isActive
        ? "border-acento text-primario"
        : "border-transparent text-texto-suave hover:text-primario"
    }`;

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

          <NavLink to="/quienes-somos" className={enlaceClase}>
            ¿Quiénes Somos?
          </NavLink>
          <NavLink to="/contacto" className={enlaceClase}>
            Contacto
          </NavLink>
          {sesion ? (
            <div className="flex items-center gap-3 text-sm">
              <span className="font-medium text-primario">Bienvenido, {sesion.usuario.nombre}</span>
              <NavLink to="/panel" className="font-semibold text-primario-suave hover:text-primario">Mi panel</NavLink>
              <button type="button" onClick={cerrarSesion} className="font-semibold text-primario-suave hover:text-primario ml-2">
                Cerrar sesión
              </button>
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
