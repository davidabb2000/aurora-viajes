import { Fragment, useState, useEffect, useRef } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../context/useAuth";
import { esPersonal } from "../utils/rutas";

function Sidebar() {
  const { sesion, cerrarSesion } = useAuth();
  const [sidebarAbierto, setSidebarAbierto] = useState(false);
  const menuRef = useRef(null);
  const location = useLocation();

  const rol = sesion?.usuario?.rol;
  const esPersonalUsuario = esPersonal(sesion?.usuario);
  const enComercial = location.pathname === "/panel/avance-cinco";
  // Sin `?vista=`, cada página abre en su primera vista: la misma que marca aquí la barra.
  const vistaActiva =
    new URLSearchParams(location.search).get("vista") || (enComercial ? (esPersonalUsuario ? "resumen" : "facturas") : "reservas");

  const aPanel = (vista, etiqueta, icono) => ({
    a: `/panel?vista=${vista}`, etiqueta, icono, activo: location.pathname === "/panel" && vistaActiva === vista,
  });
  const aComercial = (vista, etiqueta, icono) => ({
    a: `/panel/avance-cinco?vista=${encodeURIComponent(vista)}`, etiqueta, icono, activo: enComercial && vistaActiva === vista,
  });
  // El personal gestiona la agencia; el cliente solo ve lo suyo (el servidor filtra cada dato por su cuenta).
  const secciones = esPersonalUsuario
    ? [
        {
          titulo: "Gestión",
          enlaces: [
            aPanel("reservas", "Reservas", "▤"),
            aPanel("nueva", "Nueva reserva", "＋"),
            aPanel("vuelos", "Vuelos", "✈"),
            ...(rol === "administrador"
              ? [aPanel("catalogo", "Catálogo", "✦"), aPanel("usuarios", "Usuarios", "♙"), aPanel("mensajes", "Mensajes", "✉")]
              : []),
          ],
        },
        {
          titulo: "Comercial",
          enlaces: [
            aComercial("resumen", "Resumen", "◌"),
            aComercial("reservas vendidas", "Reservas vendidas", "▥"),
            aComercial("facturas", "Facturas", "▣"),
            aComercial("pqr", "PQR", "?"),
            aComercial("chatbot", "Chatbot", "✦"),
          ],
        },
      ]
    : [
        { titulo: "Mi cuenta", enlaces: [aPanel("reservas", "Mis reservas", "▤"), aComercial("facturas", "Mis facturas", "▣")] },
        { titulo: "Atención", enlaces: [aComercial("pqr", "Mis PQR", "?"), aComercial("chatbot", "Chatbot", "✦")] },
      ];

  const enlaceClase = (activo) =>
    `group flex items-center justify-between rounded-xl px-3 py-2.5 text-sm font-medium transition-all ${
      activo
        ? "border border-white/25 bg-white/15 text-white shadow-lg shadow-black/25 backdrop-blur-sm"
        : "border border-transparent text-[#a7b6c4] hover:border-white/15 hover:bg-white/10 hover:text-white"
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
        className="fixed left-4 top-4 z-40 rounded-xl border border-white/20 bg-primario/90 p-2 text-white backdrop-blur-sm md:hidden"
        aria-label="Abrir menú"
      >
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      {sidebarAbierto && (
        <div
          className="fixed inset-0 z-20 bg-primario-oscuro/50 backdrop-blur-sm md:hidden"
          onClick={() => setSidebarAbierto(false)}
        />
      )}

      <aside
        ref={menuRef}
        className={`fixed left-0 top-0 z-30 h-screen w-72 transform overflow-y-auto border-r border-white/10 bg-gradient-to-b from-marino via-marino-profundo to-[#020a17] text-[#c3cfda] shadow-2xl shadow-black/30 transition-transform duration-300 ease-in-out md:translate-x-0 ${
          sidebarAbierto ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Halos de aurora que el vidrio de las tarjetas refracta */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-80"
          style={{
            background:
              "radial-gradient(24rem 20rem at 100% 0%, rgba(208,81,42,0.30), transparent 62%), radial-gradient(20rem 18rem at 0% 84%, rgba(255,255,255,0.08), transparent 62%)",
          }}
        />

        <div className="relative flex h-full flex-col">
          <div className="border-b border-white/10 px-6 pb-6 pt-7">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-acento font-display text-xl font-bold text-white">A</span>
              <div>
                <p className="font-display text-xl font-bold tracking-tight text-white">Aurora</p>
                <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-acento-suave">Viajes</p>
              </div>
            </div>
            <div className="vidrio-noche mt-6 flex items-center justify-between rounded-xl px-3 py-2.5">
              <span className="text-xs font-semibold uppercase tracking-wider text-[#a7b6c4]">Panel</span>
              <span className="rounded-full border border-acento-suave/30 bg-acento-suave/15 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-acento-suave">{rol}</span>
            </div>
          </div>

          <nav className="flex-1 space-y-1 px-4 py-6">
            {secciones.map((seccion, indice) => (
              <Fragment key={seccion.titulo}>
                <p className={`mb-3 ${indice > 0 ? "mt-8 " : ""}px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-[#6f8090]`}>{seccion.titulo}</p>
                {seccion.enlaces.map((enlace) => (
                  <NavLink key={enlace.a} to={enlace.a} className={() => enlaceClase(enlace.activo)} onClick={() => setSidebarAbierto(false)}>
                    <span className="flex items-center gap-3"><span className="text-base">{enlace.icono}</span> {enlace.etiqueta}</span>
                    <span className="text-xs opacity-60">→</span>
                  </NavLink>
                ))}
              </Fragment>
            ))}

            <p className="mb-3 mt-8 px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-[#6f8090]">Acceso rápido</p>
            <NavLink
              to="/"
              className={() => enlaceClase(location.pathname === "/" && !location.search)}
              onClick={() => setSidebarAbierto(false)}
            >
              <span className="flex items-center gap-3"><span className="text-base">⌂</span> Ir al inicio</span>
              <span className="text-xs opacity-60">→</span>
            </NavLink>
            {!esPersonalUsuario && (
              <NavLink to="/reservas" className={() => enlaceClase(false)} onClick={() => setSidebarAbierto(false)}>
                <span className="flex items-center gap-3"><span className="text-base">✈</span> Reservar un viaje</span>
                <span className="text-xs opacity-60">→</span>
              </NavLink>
            )}
            <NavLink to="/cambiar-contrasena" className={() => enlaceClase(location.pathname === "/cambiar-contrasena")} onClick={() => setSidebarAbierto(false)}>
              <span className="flex items-center gap-3"><span className="text-base">⚿</span> Cambiar contraseña</span>
              <span className="text-xs opacity-60">→</span>
            </NavLink>
          </nav>

          <div className="border-t border-white/10 p-4">
            <div className="vidrio-noche rounded-2xl p-3">
              <div className="flex items-center gap-3">
                <span className="grid h-9 w-9 place-items-center rounded-full bg-white/15 text-sm font-bold text-white">{sesion?.usuario?.nombre?.charAt(0).toUpperCase()}</span>
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-white">{sesion?.usuario?.nombre}</p>
                  <p className="truncate text-xs text-[#a7b6c4]">{sesion?.usuario?.correo}</p>
                </div>
              </div>
              <button
                onClick={() => {
                  cerrarSesion();
                  setSidebarAbierto(false);
                }}
                className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-acento/50 bg-acento/15 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-acento-suave transition-colors hover:bg-acento hover:text-white"
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
