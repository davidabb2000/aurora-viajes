import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { solicitar } from "../utils/api";
import { useAuth } from "../context/AuthContext";

function PagoExitoso() {
  const { sesion } = useAuth();
  const [params] = useSearchParams();
  const reservaId = params.get("reserva_id");
  const sessionId = params.get("session_id");
  const [mensaje, setMensaje] = useState("Verificando tu pago...");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!sesion || !reservaId) return;
    const confirmar = async () => {
      try {
        await solicitar(`/reservas/${reservaId}/pago/confirmar`, {
          method: "POST",
          headers: { Authorization: `Bearer ${sesion.token}` },
          body: JSON.stringify({ sessionId }),
        });
        setMensaje("Pago confirmado. Tu reserva ya quedó lista.");
      } catch (requestError) {
        setError(requestError.message);
        setMensaje("No pudimos confirmar el pago automáticamente.");
      }
    };
    confirmar();
  }, [reservaId, sessionId, sesion]);

  return <main className="mx-auto w-[92%] max-w-3xl flex-1 py-12 sm:py-16">
    <section className="rounded-2xl border border-borde bg-superficie p-8 shadow-sm">
      <span className="text-xs font-semibold uppercase tracking-widest text-primario-suave">Pago completado</span>
      <h1 className="mt-2 font-display text-4xl font-bold text-primario">Gracias por tu compra</h1>
      <p className="mt-4 text-texto-suave">{mensaje}</p>
      {error && <p className="mt-4 text-sm font-medium text-red-700">{error}</p>}
      <div className="mt-6 flex gap-3">
        <Link to="/panel" className="rounded-md bg-primario px-5 py-3 font-semibold text-white">Ir al panel</Link>
        <Link to="/reservas" className="rounded-md border border-borde px-5 py-3 font-semibold text-primario">Nueva reserva</Link>
      </div>
    </section>
  </main>;
}

export default PagoExitoso;