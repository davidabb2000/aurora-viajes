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
      <section className="max-w-2xl">
        <span className="text-xs font-semibold uppercase tracking-widest text-primario-suave">
          IA de viajes
        </span>
        <h1 className="mt-2 font-display text-4xl font-bold text-primario sm:text-5xl">
          Recomendaciones de destinos
        </h1>
        <p className="mt-4 text-lg leading-relaxed text-texto-suave">
          Cuéntanos qué tipo de viaje quieres y te sugerimos destinos que encajan con tu estilo.
        </p>
      </section>

      <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_1fr]">
        <form onSubmit={manejarEnvio} className="rounded-lg border border-borde bg-superficie p-6 shadow-sm sm:p-8">
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
            className="mt-6 w-full rounded-md bg-primario px-5 py-3 text-sm font-semibold text-white transition hover:bg-primario-oscuro disabled:cursor-not-allowed disabled:opacity-60"
          >
            {cargando ? "Buscando..." : "Obtener recomendaciones"}
          </button>

          {error && <p className="mt-4 text-sm font-medium text-red-700">{error}</p>}
          {aviso && <p className="mt-4 text-sm font-medium text-primario">{aviso}</p>}
        </form>

        <aside className="rounded-lg bg-primario p-7 text-white sm:p-8">
          <span className="text-xs font-semibold uppercase tracking-widest text-acento-suave">
            Tu asesor virtual
          </span>
          <h2 className="mt-4 font-display text-3xl font-bold">
            Destinos pensados para lo que buscas
          </h2>
          <p className="mt-5 leading-relaxed text-white/75">
            El sistema mezcla IA con un catálogo local para darte opciones útiles incluso si el proveedor externo no responde.
          </p>
          {generadaPor && (
            <p className="mt-5 text-sm text-white/80">
              Fuente: <strong className="text-white">{generadaPor}</strong>
            </p>
          )}
          <p className="mt-4 text-sm text-white/70">
            Sesión activa como <strong className="text-white">{sesion.usuario.nombre}</strong>
          </p>
        </aside>
      </div>

      {recomendaciones.length > 0 && (
        <section className="mt-10">
          <h2 className="font-display text-2xl font-bold text-primario">Sugerencias para ti</h2>
          <div className="mt-6 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {recomendaciones.map((destino) => (
              <article key={destino.destino_id} className="rounded-lg border border-borde bg-superficie p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-widest text-primario-suave">
                  {destino.pais}
                </p>
                <h3 className="mt-2 font-display text-xl font-bold text-primario">
                  {destino.nombre}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-texto-suave">
                  {destino.motivo}
                </p>
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
                  className="mt-5 inline-flex w-full items-center justify-center rounded-md border border-borde bg-transparent px-5 py-2.5 text-sm font-semibold text-primario transition hover:bg-fondo focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-acento"
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
