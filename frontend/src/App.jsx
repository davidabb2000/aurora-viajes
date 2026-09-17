import { Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import ClientLayout from "./layouts/ClientLayout";
import AdminLayout from "./layouts/AdminLayout";
import Index from "./pages/Index";
import QuienesSomos from "./pages/QuienesSomos";
import Contacto from "./pages/Contacto";
import Login from "./pages/Login";
import Panel from "./pages/Panel";
import PagoReserva from "./pages/PagoReserva";
import Reservas from "./pages/Reservas";
import PagoExitoso from "./pages/PagoExitoso";
import Recomendaciones from "./pages/Recomendaciones";
import AvanceCinco from "./pages/AvanceCinco";

function App() {
  const { sesion } = useAuth();
  const location = useLocation();

  // Determinar si estamos en panel
  const esPanel = location.pathname.startsWith("/panel");

  // El panel usa el mismo layout para todos los roles autenticados
  if (esPanel && sesion) {
    return (
      <AdminLayout>
        <Routes>
          <Route path="/panel" element={<Panel />} />
          <Route path="/panel/avance-cinco" element={<AvanceCinco />} />
        </Routes>
      </AdminLayout>
    );
  }

  // Resto de rutas usan ClientLayout
  return (
    <ClientLayout>
      <Routes>
        <Route path="/" element={<Index />} />
        <Route path="/quienes-somos" element={<QuienesSomos />} />
        <Route path="/contacto" element={<Contacto />} />
        <Route path="/login" element={<Login />} />
        <Route path="/reservas" element={<Reservas />} />
        <Route path="/recomendaciones" element={<Recomendaciones />} />
        <Route path="/reservas/pago/:id" element={<PagoReserva />} />
        <Route path="/reservas/pago-exitoso" element={<PagoExitoso />} />
        <Route path="/panel" element={<Panel />} />
        <Route path="/panel/avance-cinco" element={<AvanceCinco />} />
      </Routes>
    </ClientLayout>
  );
}

export default App;
