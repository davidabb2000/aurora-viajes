import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { solicitar } from "../utils/api";
import { useAuth } from "../context/AuthContext";

function PagoExitoso() {
  const { sesion } = useAuth();
  const token = sesion?.token;
  const [params] = useSearchParams();
  const reservaId = params.get("reserva_id");
  const sessionId = params.get("session_id");
  const [mensaje, setMensaje] = useState("Verificando tu pago...");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token || !reservaId) return undefined;
    let activo = true;
    const confirmar = async () => {
      try {
        await solicitar(`/reservas/${reservaId}/pago/confirmar`, {
          method: "POST",
          body: JSON.stringify({ sessionId }),
        });
        if (activo) setMensaje("Pago confirmado. Tu reserva ya quedó lista.");
      } catch (requestError) {
        if (!activo) return;
        setError(requestError.message);
        // Stripe también avisa al servidor por su cuenta, así que una demora aquí no significa que el cobro se perdió.
        setMensaje("Aún no podemos confirmar el pago desde esta página. Si Stripe ya te cobró, tu reserva se confirmará sola en unos minutos; revisa su estado en tu panel.");
      }
    };
    confirmar();
    return () => {
      activo = false;
    };
  }, [reservaId, sessionId, token]);

  return (
    <main className="mx-auto w-[92%] max-w-3xl flex-1 py-12 sm:py-16">
      <section className="vidrio rounded-3xl p-8 sm:p-10">
        <span className="grid h-14 w-14 place-items-center rounded-full bg-oro text-2xl text-primario">✓</span>
        <span className="antetitulo mt-6">Pago completado</span>
        <h1 className="mt-3 text-4xl sm:text-5xl">
          <span className="titulo-aurora">Gracias por tu compra</span>
        </h1>
        <p className="mt-4 text-texto-suave">
          {sesion ? mensaje : "Inicia sesión para ver el estado de tu pago. Si ya pagaste, tu reserva se confirma sola."}
        </p>
        {error && <p className="mt-4 rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm font-medium text-red-700 backdrop-blur-sm">{error}</p>}
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to={sesion ? "/panel" : "/login"} className="boton-tinta px-6 py-3 font-semibold no-underline">
            {sesion ? "Ir al panel" : "Iniciar sesión"}
          </Link>
          <Link to="/reservas" className="rounded-full border border-primario/25 px-6 py-3 font-semibold text-primario no-underline transition hover:bg-primario/5">
            Nueva reserva
          </Link>
        </div>
      </section>
    </main>
  );
}

export default PagoExitoso;
