import { useEffect, useState } from "react";
import { Navigate, useParams } from "react-router-dom";
import { solicitar } from "../utils/api";
import { useAuth } from "../context/AuthContext";

function PagoReserva() {
  const { sesion } = useAuth();
  const { id } = useParams();
  const [reserva, setReserva] = useState(null);
  const [checkoutUrl, setCheckoutUrl] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    if (!sesion) return;
    const headers = { Authorization: `Bearer ${sesion.token}` };
    const cargar = async () => {
      try {
        const datos = await solicitar(`/reservas/${id}`, { headers });
        setReserva(datos);
        const checkout = await solicitar(`/reservas/${id}/pago/checkout`, { method: "POST", headers });
        setCheckoutUrl(checkout.checkoutUrl || "");
      } catch (requestError) {
        setError(requestError.message);
      } finally {
        setCargando(false);
      }
    };
    cargar();
  }, [id, sesion]);

  if (!sesion) return <Navigate to="/login" replace />;

  if (cargando) {
    return (
      <main className="mx-auto w-[92%] max-w-3xl flex-1 py-12 sm:py-16">
        <p className="vidrio rounded-2xl p-6 text-sm text-texto-suave">Preparando la pasarela de pago...</p>
      </main>
    );
  }

  if (!reserva) {
    return (
      <main className="mx-auto w-[92%] max-w-3xl flex-1 py-12 sm:py-16">
        <p className="vidrio rounded-2xl border-red-200 p-6 text-sm text-red-700">{error || "No se pudo cargar la reserva."}</p>
      </main>
    );
  }

  return (
    <main className="mx-auto w-[92%] max-w-3xl flex-1 py-12 sm:py-16">
      <section className="vidrio filo-aurora rounded-3xl p-6 sm:p-9">
        <span className="inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/60 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-primario-suave backdrop-blur-sm"><span className="h-1.5 w-1.5 rounded-full bg-acento" aria-hidden="true" />Checkout seguro</span>
        <h1 className="mt-3 font-display text-4xl font-bold"><span className="titulo-aurora">Completa el pago de tu reserva</span></h1>
        <p className="mt-3 text-texto-suave">Tu reserva quedará confirmada cuando Stripe marque el pago como realizado.</p>
        <div className="mt-6 grid gap-4 text-sm sm:grid-cols-2">
          <div className="vidrio-sutil rounded-2xl p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Destino</p>
            <p className="mt-1 font-semibold text-texto">{reserva.destino}</p>
          </div>
          <div className="vidrio-sutil rounded-2xl p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Total</p>
            <p className="mt-1 text-lg font-bold text-primario">${Number(reserva.montoTotal || 0).toLocaleString("es-CO")}</p>
          </div>
          <div className="vidrio-sutil rounded-2xl p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Estado pago</p>
            <p className="mt-1 font-semibold capitalize text-texto">{reserva.estadoPago || "pendiente"}</p>
          </div>
          <div className="vidrio-sutil rounded-2xl p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Pasajeros</p>
            <p className="mt-1 font-semibold text-texto">{reserva.pasajeros}</p>
          </div>
        </div>
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => window.location.assign(checkoutUrl)}
            disabled={!checkoutUrl}
            className="rounded-xl bg-gradient-to-br from-primario-suave via-primario to-primario-oscuro px-5 py-3 font-semibold text-white shadow-lg shadow-primario/30 transition hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primario/40 disabled:translate-y-0 disabled:opacity-60 disabled:shadow-none"
          >
            Ir a Stripe Checkout
          </button>
        </div>
        {mensaje && <p className="mt-4 text-sm font-medium text-primario">{mensaje}</p>}
        {error && <p className="mt-4 rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm font-medium text-red-700 backdrop-blur-sm">{error}</p>}
        <p className="mt-5 text-sm text-texto-suave">Al volver desde Stripe, la reserva se confirma automáticamente.</p>
      </section>
    </main>
  );
}

export default PagoReserva;
