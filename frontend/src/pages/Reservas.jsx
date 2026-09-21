import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import AsistenteDeReserva from "../components/reserva/AsistenteDeReserva";
import MisReservas from "../components/reserva/MisReservas";
import { solicitar } from "../utils/api";
import { useAuth } from "../context/useAuth";
import { esPersonal } from "../utils/rutas";

/**
 * Página de reservas del cliente: el asistente para pedir un viaje y, debajo, sus reservas.
 * El acceso ya lo controla `RutaProtegida` (App.jsx). El personal, que reserva a nombre de un cliente,
 * usa la vista «Nueva reserva» de su panel.
 */
function Reservas() {
  const { sesion } = useAuth();
  const [parametros] = useSearchParams();
  const [reservas, setReservas] = useState(null);
  const [error, setError] = useState("");

  const cargar = useCallback(async () => {
    try {
      setReservas(await solicitar("/reservas/mias"));
      setError("");
    } catch (requestError) {
      setError(requestError.message);
      setReservas((actual) => actual ?? []);
    }
  }, []);

  useEffect(() => {
    let activo = true;
    solicitar("/reservas/mias")
      .then((datos) => activo && setReservas(datos))
      .catch((requestError) => {
        if (!activo) return;
        setError(requestError.message);
        setReservas([]);
      });
    return () => {
      activo = false;
    };
  }, []);

  return (
    <div className="mx-auto w-[92%] max-w-300 flex-1 py-10 sm:py-14">
      <section className="mb-8 max-w-2xl">
        <span className="antetitulo">Planea con Aurora</span>
        <h1 className="mt-4 text-[clamp(2.6rem,6vw,4.4rem)] leading-[1.03] tracking-[-0.03em]">
          <span className="titulo-aurora">Reserva tu próxima <em className="titulo-enfasis">historia</em></span>
        </h1>
        <p className="mt-4 text-lg leading-relaxed text-texto-suave">
          Elige destino, vuelos de ida y regreso, hotel y excursiones. Ves el precio final en cada paso, antes de confirmar.
        </p>
        {esPersonal(sesion.usuario) && (
          <p className="vidrio-sutil mt-4 rounded-xl px-4 py-3 text-sm text-texto-suave">
            Eres parte del equipo: para reservar a nombre de un cliente usa <strong className="text-primario">Nueva reserva</strong> en tu panel.
          </p>
        )}
      </section>

      <AsistenteDeReserva modo="cliente" destinoInicial={parametros.get("destino") || ""} />

      <div className="mt-16">
        {error && <p role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm font-medium text-red-700">{error}</p>}
        <MisReservas reservas={reservas} alCambiar={cargar} />
      </div>
    </div>
  );
}

export default Reservas;
