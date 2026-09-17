import { useState, useEffect, useRef } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

function Sidebar() {
  const { sesion, cerrarSesion } = useAuth();
  const [sidebarAbierto, setSidebarAbierto] = useState(false);
  const menuRef = useRef(null);
  const location = useLocation();

  const rol = sesion?.usuario?.rol;
  const vistaActiva = new URLSearchParams(location.search).get("vista") || "reservas";

  const enlaceClase = (activo) =>
    `group flex items-center justify-between rounded-lg px-3 py-3 text-sm font-medium transition-all ${
      activo
        ? "bg-acento text-white shadow-lg shadow-black/10"
        : "text-[#c8d2c9] hover:bg-white/10 hover:text-white"
    }`;

  useEffect(() => {
    const cerrarSiClicFuera = (evento) => {
      if (menuRef.current && !menuRef.current.contains(evento.target)) {
        setSidebarAbierto(false);
      }
    };

    document.addEventListener("mousedown", cerrarSiClicFuera);
    return () => document.removeEventListener("mousedown", cerrarSiClicFuera);
  }, []);

  return (
    <>
      <button
        onClick={() => setSidebarAbierto(!sidebarAbierto)}
        className="fixed left-4 top-4 z-40 rounded-lg bg-primario p-2 text-white shadow-lg md:hidden"
        aria-label="Abrir menú"
      >
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      {sidebarAbierto && (
        <div
          className="fixed inset-0 z-20 bg-black/50 md:hidden"
          onClick={() => setSidebarAbierto(false)}
        />
      )}

      <aside
        ref={menuRef}
        className={`fixed left-0 top-0 z-30 h-screen w-72 transform overflow-y-auto bg-primario-oscuro text-[#e7e2d4] shadow-2xl shadow-black/20 transition-transform duration-300 ease-in-out md:translate-x-0 ${
          sidebarAbierto ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-full flex-col">
          <div className="border-b border-white/10 px-6 pb-6 pt-7">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-acento font-display text-xl font-bold text-primario-oscuro">A</span>
              <div>
                <h1 className="font-display text-xl font-bold tracking-tight text-white">Aurora</h1>
                <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-[#a9beb0]">Viajes</p>
              </div>
            </div>
            <div className="mt-6 flex items-center justify-between rounded-lg border border-white/10 bg-white/5 px-3 py-2.5">
              <span className="text-xs font-semibold uppercase tracking-wider text-[#a9beb0]">Panel</span>
              <span className="rounded-full bg-acento/20 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-acento-suave">{rol}</span>
            </div>
          </div>

          <nav className="flex-1 space-y-1 px-4 py-6">
            <p className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-[#78917f]">Gestión</p>
            <NavLink
              to="/panel?vista=reservas"
              className={() => enlaceClase(vistaActiva === "reservas")}
              onClick={() => setSidebarAbierto(false)}
            >
              <span className="flex items-center gap-3"><span className="text-base">▤</span> Solicitudes</span>
              <span className="text-xs opacity-60">→</span>
            </NavLink>

            <NavLink
              to="/panel?vista=vuelos"
              className={() => enlaceClase(vistaActiva === "vuelos")}
              onClick={() => setSidebarAbierto(false)}
            >
              <span className="flex items-center gap-3"><span className="text-base">✈</span> Vuelos</span>
              <span className="text-xs opacity-60">→</span>
            </NavLink>

            {rol === "administrador" && (
              <>
                <NavLink
                  to="/panel?vista=paquetes"
                  className={() => enlaceClase(vistaActiva === "paquetes")}
                  onClick={() => setSidebarAbierto(false)}
                >
                  <span className="flex items-center gap-3"><span className="text-base">✦</span> Reservas publicadas</span>
                  <span className="text-xs opacity-60">→</span>
                </NavLink>
                <NavLink
                  to="/panel?vista=usuarios"
                  className={() => enlaceClase(vistaActiva === "usuarios")}
                  onClick={() => setSidebarAbierto(false)}
                >
                  <span className="flex items-center gap-3"><span className="text-base">♙</span> Usuarios</span>
                  <span className="text-xs opacity-60">→</span>
                </NavLink>
                <NavLink
                  to="/panel?vista=mensajes"
                  className={() => enlaceClase(vistaActiva === "mensajes")}
                  onClick={() => setSidebarAbierto(false)}
                >
                  <span className="flex items-center gap-3"><span className="text-base">✉</span> Mensajes</span>
                  <span className="text-xs opacity-60">→</span>
                </NavLink>
                <NavLink
                  to="/panel?vista=crear"
                  className={() => enlaceClase(vistaActiva === "crear")}
                  onClick={() => setSidebarAbierto(false)}
                >
                  <span className="flex items-center gap-3"><span className="text-base">＋</span> Agregar usuario</span>
                  <span className="text-xs opacity-60">→</span>
                </NavLink>
              </>
            )}

            <NavLink
              to="/panel/avance-cinco"
              className={() => enlaceClase(location.pathname === "/panel/avance-cinco")}
              onClick={() => setSidebarAbierto(false)}
            >
              <span className="flex items-center gap-3"><span className="text-base">◈</span> Quinto entregable</span>
              <span className="text-xs opacity-60">→</span>
            </NavLink>

            <p className="mb-3 mt-8 px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-[#78917f]">Acceso rápido</p>
            <NavLink
              to="/"
              className={() => enlaceClase(location.pathname === "/" && !location.search)}
              onClick={() => setSidebarAbierto(false)}
            >
              <span className="flex items-center gap-3"><span className="text-base">⌂</span> Ir al inicio</span>
              <span className="text-xs opacity-60">→</span>
            </NavLink>
          </nav>

          <div className="border-t border-white/10 p-4">
            <div className="rounded-xl border border-white/10 bg-white/5 p-3">
              <div className="flex items-center gap-3">
                <span className="grid h-9 w-9 place-items-center rounded-full bg-[#d9e4d9] text-sm font-bold text-primario-oscuro">{sesion?.usuario?.nombre?.charAt(0).toUpperCase()}</span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-white">{sesion?.usuario?.nombre}</p>
                  <p className="truncate text-xs text-[#a9beb0]">{sesion?.usuario?.correo}</p>
                </div>
              </div>
              <button
                onClick={() => {
                  cerrarSesion();
                  setSidebarAbierto(false);
                }}
                className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-acento/50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-acento-suave transition-colors hover:bg-acento hover:text-primario-oscuro"
              >
                <span>↪</span> Cerrar sesión
              </button>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}

export default Sidebar;
