import { Route, Routes } from "react-router-dom";
import Header from "./components/Header";
import Footer from "./components/Footer";
import Index from "./pages/Index";
import QuienesSomos from "./pages/QuienesSomos";
import Contacto from "./pages/Contacto";
import Login from "./pages/Login";
import Panel from "./pages/Panel";
import PagoReserva from "./pages/PagoReserva";
import Reservas from "./pages/Reservas";
import PagoExitoso from "./pages/PagoExitoso";
import Recomendaciones from "./pages/Recomendaciones";
import WhatsAppButton from "./components/WhatsAppButton";

function App() {
  return (
    <>
      <Header />
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
      </Routes>
      <Footer />
      <WhatsAppButton />
    </>
  );
}

export default App;
