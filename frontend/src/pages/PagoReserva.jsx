import { useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { solicitar } from "../utils/api";
import { useAuth } from "../context/AuthContext";

function PagoReserva() {
  const { sesion } = useAuth();
  const { id } = useParams();
  const navigate = useNavigate();
  const [reserva, setReserva] = useState(null);
  const [checkoutUrl, setCheckoutUrl] = useState("");
  const [demo, setDemo] = useState(false);
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(true);
  const [procesando, setProcesando] = useState(false);

  useEffect(() => {
    if (!sesion) return;
    const headers = { Authorization: `Bearer ${sesion.token}` };
    const cargar = async () => {
      try {
        const datos = await solicitar(`/reservas/${id}`, { headers });
        setReserva(datos);
        const checkout = await solicitar(`/reservas/${id}/pago/checkout`, { method: "POST", headers });
        setCheckoutUrl(checkout.checkoutUrl || "");
        setDemo(Boolean(checkout.demo));
      } catch (requestError) {
        setError(requestError.message);
      } finally {
        setCargando(false);
      }
    };
    cargar();
  }, [id, sesion]);

  if (!sesion) return <Navigate to="/login" replace />;

  const confirmarDemo = async () => {
    setProcesando(true);
    setError("");
    setMensaje("");
    try {
      await solicitar(`/reservas/${id}/pago/confirmar`, {
        method: "POST",
        headers: { Authorization: `Bearer ${sesion.token}` },
        body: JSON.stringify({ sessionId: "demo" }),
      });
      setMensaje("Pago de prueba confirmado correctamente.");
      navigate("/panel");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setProcesando(false);
    }
  };

  if (cargando) {
    return <main className="mx-auto w-[92%] max-w-3xl flex-1 py-12 sm:py-16"><p className="text-sm text-texto-suave">Preparando la pasarela de pago...</p></main>;
  }

  if (!reserva) {
    return <main className="mx-auto w-[92%] max-w-3xl flex-1 py-12 sm:py-16"><p className="text-sm text-red-700">{error || "No se pudo cargar la reserva."}</p></main>;
  }

  return <main className="mx-auto w-[92%] max-w-3xl flex-1 py-12 sm:py-16">
    <section className="rounded-2xl border border-borde bg-superficie p-6 shadow-sm sm:p-8">
      <span className="text-xs font-semibold uppercase tracking-widest text-primario-suave">Checkout seguro</span>
      <h1 className="mt-2 font-display text-4xl font-bold text-primario">Completa el pago de tu reserva</h1>
      <p className="mt-3 text-texto-suave">Tu reserva quedará confirmada cuando el pago se marque como realizado.</p>
      <div className="mt-6 grid gap-4 rounded-xl bg-fondo p-5 text-sm sm:grid-cols-2">
        <div><p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Destino</p><p className="mt-1 font-semibold text-texto">{reserva.destino}</p></div>
        <div><p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Total</p><p className="mt-1 font-semibold text-texto">${Number(reserva.montoTotal || 0).toLocaleString("es-CO")}</p></div>
        <div><p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Estado pago</p><p className="mt-1 font-semibold text-texto">{reserva.estadoPago || "pendiente"}</p></div>
        <div><p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Pasajeros</p><p className="mt-1 font-semibold text-texto">{reserva.pasajeros}</p></div>
      </div>
      <div className="mt-6 flex flex-wrap gap-3">
        <button type="button" onClick={() => window.location.assign(checkoutUrl || `/reservas/pago/${id}`)} className="rounded-md bg-primario px-5 py-3 font-semibold text-white transition hover:bg-primario-oscuro">
          {demo ? "Abrir pago de prueba" : "Ir a Stripe Checkout"}
        </button>
        {demo && (
          <button type="button" onClick={confirmarDemo} disabled={procesando} className="rounded-md border border-borde px-5 py-3 font-semibold text-primario transition hover:bg-fondo disabled:opacity-60">
            {procesando ? "Confirmando..." : "Confirmar pago de prueba"}
          </button>
        )}
      </div>
      {mensaje && <p className="mt-4 text-sm font-medium text-primario">{mensaje}</p>}
      {error && <p className="mt-4 text-sm font-medium text-red-700">{error}</p>}
      <p className="mt-5 text-sm text-texto-suave">Si Stripe no está configurado en el entorno, la app usa un modo de demostración para validar el flujo completo.</p>
    </section>
  </main>;
}

export default PagoReserva;