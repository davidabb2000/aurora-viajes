import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import Input from "../components/Input";
import { useAuth } from "../context/AuthContext";
import { solicitar } from "../utils/api";

function formatearMoneda(valor) {
  if (typeof valor !== "number") return "";
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(valor);
}

function Recomendaciones() {
  const { sesion } = useAuth();
  const [intereses, setIntereses] = useState("");
  const [recomendaciones, setRecomendaciones] = useState([]);
  const [generadaPor, setGeneradaPor] = useState("");
  const [aviso, setAviso] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  if (!sesion) return <Navigate to="/login" replace />;

  const manejarEnvio = async (evento) => {
    evento.preventDefault();
    setError("");
    setAviso("");
    setCargando(true);
    try {
      const datos = await solicitar("/destinos/recomendaciones", {
        method: "POST",
        headers: { Authorization: `Bearer ${sesion.token}` },
        body: JSON.stringify({ intereses }),
      });
      setRecomendaciones(datos.recomendaciones || []);
      setGeneradaPor(datos.generada_por || "");
      setAviso(datos.aviso || "");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setCargando(false);
    }
  };

  return (
    <main className="mx-auto w-[92%] max-w-275 flex-1 py-12 sm:py-16">
      <section className="vidrio filo-aurora rounded-3xl p-7 sm:p-10">
        <div className="max-w-2xl">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/60 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-primario-suave backdrop-blur-sm">
            <span className="h-1.5 w-1.5 rounded-full bg-brillo" aria-hidden="true" />
            IA de viajes
          </span>
          <h1 className="mt-3 font-display text-4xl font-bold sm:text-5xl">
            <span className="titulo-aurora">Recomendaciones de destinos</span>
          </h1>
          <p className="mt-4 text-lg leading-relaxed text-texto-suave">
            Cuéntanos qué tipo de viaje quieres y te sugerimos destinos que encajan con tu estilo.
          </p>
        </div>
      </section>

      <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_1fr]">
        <form onSubmit={manejarEnvio} className="vidrio rounded-3xl p-6 sm:p-8">
          <h2 className="font-display text-2xl font-bold text-primario">Describe tu viaje ideal</h2>
          <div className="mt-6">
            <Input
              label="Intereses"
              name="intereses"
              value={intereses}
              onChange={(evento) => setIntereses(evento.target.value)}
              required
              placeholder="Ej: playa, descanso, cultura, comida local y clima cálido"
            />
          </div>

          <button
            type="submit"
            disabled={cargando || intereses.trim().length < 10}
            className="mt-6 w-full rounded-xl bg-gradient-to-br from-primario-suave via-primario to-primario-oscuro px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-primario/30 transition hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primario/40 disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-60 disabled:shadow-none"
          >
            {cargando ? "Buscando..." : "Obtener recomendaciones"}
          </button>

          {error && <p className="mt-4 rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm font-medium text-red-700 backdrop-blur-sm">{error}</p>}
          {aviso && <p className="vidrio-sutil mt-4 rounded-xl px-4 py-3 text-sm font-medium text-primario">{aviso}</p>}
        </form>

        <aside className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-primario-oscuro via-primario to-[#1b1350] p-7 text-white shadow-xl shadow-primario/30 sm:p-8">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 opacity-80"
            style={{ background: "radial-gradient(24rem 18rem at 100% 0%, rgba(110,231,220,0.3), transparent 60%), radial-gradient(22rem 18rem at 0% 100%, rgba(214,51,108,0.32), transparent 62%)" }}
          />
          <span className="relative inline-flex items-center gap-2 rounded-full border border-white/25 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-acento-suave backdrop-blur-sm">
            Tu asesor virtual
          </span>
          <h2 className="relative mt-4 font-display text-3xl font-bold">
            Destinos pensados para lo que buscas
          </h2>
          <p className="relative mt-5 leading-relaxed text-white/75">
            El sistema mezcla IA con un catálogo local para darte opciones útiles incluso si el proveedor externo no responde.
          </p>
          {generadaPor && (
            <p className="relative mt-5 text-sm text-white/80">
              Fuente: <strong className="text-white">{generadaPor}</strong>
            </p>
          )}
          <p className="relative mt-4 text-sm text-white/70">
            Sesión activa como <strong className="text-white">{sesion.usuario.nombre}</strong>
          </p>
        </aside>
      </div>

      {recomendaciones.length > 0 && (
        <section className="mt-10">
          <h2 className="font-display text-2xl font-bold text-primario">Sugerencias para ti</h2>
          <div className="mt-6 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {recomendaciones.map((destino) => (
              <article key={destino.destino_id} className="vidrio vidrio-interactivo filo-aurora flex flex-col rounded-2xl p-5">
                <p className="text-xs font-semibold uppercase tracking-widest text-primario-suave">
                  {destino.pais}
                </p>
                <h3 className="mt-2 font-display text-xl font-bold text-primario">
                  {destino.nombre}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-texto-suave">
                  {destino.motivo}
                </p>
                <div className="flex-1" />
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm text-texto">
                  {destino.region && (
                    <div>
                      <dt className="font-semibold text-primario">Región</dt>
                      <dd>{destino.region}</dd>
                    </div>
                  )}
                  {destino.tipo && (
                    <div>
                      <dt className="font-semibold text-primario">Tipo</dt>
                      <dd>{destino.tipo}</dd>
                    </div>
                  )}
                  {destino.clima && (
                    <div>
                      <dt className="font-semibold text-primario">Clima</dt>
                      <dd>{destino.clima}</dd>
                    </div>
                  )}
                  {destino.duracion_sugerida && (
                    <div>
                      <dt className="font-semibold text-primario">Duración</dt>
                      <dd>{destino.duracion_sugerida} días</dd>
                    </div>
                  )}
                </dl>
                {typeof destino.precio_estimado === "number" && (
                  <p className="mt-4 text-sm font-semibold text-primario">
                    Desde {formatearMoneda(destino.precio_estimado)}
                  </p>
                )}
                <Link
                  to="/reservas"
                  className="mt-5 inline-flex w-full items-center justify-center rounded-xl bg-gradient-to-br from-primario-suave via-primario to-primario-oscuro px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primario/25 transition hover:-translate-y-0.5 hover:shadow-xl hover:shadow-primario/35 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-acento"
                >
                  Reservar este destino
                </Link>
              </article>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}

export default Recomendaciones;
