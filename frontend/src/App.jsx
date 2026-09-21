import { useEffect } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import ClientLayout from "./layouts/ClientLayout";
import AdminLayout from "./layouts/AdminLayout";
import { RutaProtegida, SoloInvitados } from "./components/RutaProtegida";
import Index from "./pages/Index";
import QuienesSomos from "./pages/QuienesSomos";
import Contacto from "./pages/Contacto";
import Login from "./pages/Login";
import Registro from "./pages/Registro";
import RecuperarContrasena from "./pages/RecuperarContrasena";
import RestablecerContrasena from "./pages/RestablecerContrasena";
import AccesoPersonal from "./pages/AccesoPersonal";
import CambiarContrasena from "./pages/CambiarContrasena";
import Panel from "./pages/Panel";
import PagoReserva from "./pages/PagoReserva";
import Reservas from "./pages/Reservas";
import PagoExitoso from "./pages/PagoExitoso";
import Recomendaciones from "./pages/Recomendaciones";
import AvanceCinco from "./pages/AvanceCinco";
import NoEncontrada from "./pages/NoEncontrada";

/** Al cambiar de página se vuelve arriba (en una SPA el navegador conserva el desplazamiento), salvo si la dirección trae un ancla. */
function useVolverArriba() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (!hash) window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  }, [pathname, hash]);
}

function App() {
  const { sesion } = useAuth();
  const { pathname } = useLocation();
  useVolverArriba();

  // El panel usa la barra lateral. Una cuenta con clave provisional aún no puede usarlo:
  // `RutaProtegida` la lleva a cambiarla.
  const enPanel = pathname.startsWith("/panel") && sesion && !sesion.usuario.debeCambiarContrasena;
  if (enPanel) {
    return (
      <AdminLayout>
        <Routes>
          <Route path="/panel" element={<Panel />} />
          <Route path="/panel/avance-cinco" element={<AvanceCinco />} />
          <Route path="*" element={<NoEncontrada />} />
        </Routes>
      </AdminLayout>
    );
  }

  return (
    <ClientLayout>
      <Routes>
        <Route path="/" element={<Index />} />
        <Route path="/quienes-somos" element={<QuienesSomos />} />
        <Route path="/contacto" element={<Contacto />} />

        {/* Acceso: quien ya tiene sesión no necesita estas pantallas. */}
        <Route path="/login" element={<SoloInvitados><Login /></SoloInvitados>} />
        <Route path="/registro" element={<SoloInvitados><Registro /></SoloInvitados>} />
        <Route path="/acceso-personal" element={<SoloInvitados><AccesoPersonal /></SoloInvitados>} />
        <Route path="/recuperar" element={<RecuperarContrasena />} />
        <Route path="/restablecer" element={<RestablecerContrasena />} />
        <Route path="/cambiar-contrasena" element={<CambiarContrasena />} />

        {/* Con sesión: los clientes reservan y pagan; el personal, además, entra al panel. */}
        <Route path="/reservas" element={<RutaProtegida><Reservas /></RutaProtegida>} />
        <Route path="/recomendaciones" element={<RutaProtegida><Recomendaciones /></RutaProtegida>} />
        <Route path="/reservas/pago/:id" element={<RutaProtegida><PagoReserva /></RutaProtegida>} />
        <Route path="/reservas/pago-exitoso" element={<RutaProtegida><PagoExitoso /></RutaProtegida>} />
        <Route path="/panel" element={<RutaProtegida><Panel /></RutaProtegida>} />
        <Route path="/panel/avance-cinco" element={<RutaProtegida><AvanceCinco /></RutaProtegida>} />

        <Route path="*" element={<NoEncontrada />} />
      </Routes>
    </ClientLayout>
  );
}

export default App;
