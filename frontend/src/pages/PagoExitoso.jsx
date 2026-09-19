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
    <section className="vidrio filo-aurora rounded-3xl p-8 sm:p-10">
      <span className="grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-acento-suave via-primario-suave to-brillo text-2xl text-white shadow-lg shadow-primario/25">✓</span>
      <span className="mt-5 inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/60 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-primario-suave backdrop-blur-sm">Pago completado</span>
      <h1 className="mt-3 font-display text-4xl font-bold"><span className="titulo-aurora">Gracias por tu compra</span></h1>
      <p className="mt-4 text-texto-suave">{mensaje}</p>
      {error && <p className="mt-4 rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm font-medium text-red-700 backdrop-blur-sm">{error}</p>}
      <div className="mt-6 flex flex-wrap gap-3">
        <Link to="/panel" className="rounded-xl bg-gradient-to-br from-primario-suave via-primario to-primario-oscuro px-5 py-3 font-semibold text-white shadow-lg shadow-primario/30 transition hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primario/40">Ir al panel</Link>
        <Link to="/reservas" className="vidrio rounded-xl px-5 py-3 font-semibold text-primario transition hover:-translate-y-0.5 hover:bg-white/80">Nueva reserva</Link>
      </div>
    </section>
  </main>;
}

export default PagoExitoso;