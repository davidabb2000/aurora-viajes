import { useEffect, useMemo, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import destinosBase from "../data/destinos";
import { solicitar } from "../utils/api";
import { useAuth } from "../context/AuthContext";

const formatearMoneda = (valor) => Number(valor || 0).toLocaleString("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });
const formatearFecha = (valor) => valor ? new Date(`${valor}T00:00:00`).toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric" }) : "Sin definir";
const formatearFechaHora = (valor) => valor ? new Date(valor).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" }) : "Sin definir";
const etiquetaEstado = (valor) => String(valor || "pendiente").replaceAll("_", " ");
const formatearUbicacion = (destino, pais) => {
  if (!pais) return destino;
  const destinoNormalizado = destino.trim().normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const paisNormalizado = pais.trim().normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  return destinoNormalizado.endsWith(`, ${paisNormalizado}`) ? destino : `${destino}, ${pais}`;
};

function Reservas() {
  const { sesion } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [destinosCatalogo, setDestinosCatalogo] = useState([]);
  const [vuelos, setVuelos] = useState([]);
  const [paquetes, setPaquetes] = useState([]);
  const [misReservas, setMisReservas] = useState([]);
  const [formulario, setFormulario] = useState({
    origen: "",
    destinoId: "",
    fechaSalida: "",
    fechaRegreso: "",
    vueloId: "",
    paqueteId: "",
    pasajeros: 1,
    telefonoContacto: "",
    notas: "",
  });
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    let activo = true;
    const cargarCatalogo = async () => {
      try {
        const destinos = await solicitar("/catalogos/destinos");
        if (activo) setDestinosCatalogo(destinos);
          const vuelosCatalogo = await solicitar("/vuelos", {
            headers: sesion ? { Authorization: `Bearer ${sesion.token}` } : {},
          });
          if (activo) setVuelos(vuelosCatalogo);
          const paquetesCatalogo = await solicitar("/paquetes", {
            headers: sesion ? { Authorization: `Bearer ${sesion.token}` } : {},
          });
          if (activo) setPaquetes(paquetesCatalogo);
          const reservasUsuario = await solicitar("/reservas/mias", {
            headers: sesion ? { Authorization: `Bearer ${sesion.token}` } : {},
          });
          if (activo) setMisReservas(reservasUsuario);
      } catch {
        if (activo) {
          setDestinosCatalogo(
            destinosBase.map((destino) => ({
              id: destino.id,
              nombre: destino.titulo,
              pais: "",
            })),
          );
        }
      }
    };
    cargarCatalogo();
    return () => {
      activo = false;
    };
  }, [sesion]);

  const destinosDisponibles = useMemo(
    () =>
      destinosCatalogo.length
        ? destinosCatalogo
        : destinosBase.map((destino) => ({
            id: destino.id,
            nombre: destino.titulo,
            pais: "",
          })),
    [destinosCatalogo],
  );

  const normalizarTexto = (valor) =>
    valor.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();

  const vuelosDisponibles = useMemo(
    () => vuelos.filter((vuelo) => vuelo.activo && ["programado", "abordando"].includes(vuelo.estado)
      && new Date(vuelo.fechaSalida) >= new Date()
      && (vuelo.pasajerosDisponibles == null || vuelo.pasajerosDisponibles >= formulario.pasajeros)),
    [formulario.pasajeros, vuelos],
  );

  const destinoSeleccionado = destinosDisponibles.find((destino) => Number(destino.id) === Number(formulario.destinoId));
  const paquetesDisponibles = useMemo(
    () => paquetes.filter((paquete) => paquete.activo
      && Number(paquete.destinoId) === Number(formulario.destinoId)
      && (paquete.vuelo?.pasajerosDisponibles == null || paquete.vuelo?.pasajerosDisponibles >= formulario.pasajeros)),
    [paquetes, formulario.destinoId, formulario.pasajeros],
  );

  if (!sesion) return <Navigate to="/login" state={{ desde: location.pathname }} replace />;

  const cambiar = (evento) => {
    const { name, value } = evento.target;
    if (name === "destinoId") {
      setFormulario((actual) => ({
        ...actual,
        destinoId: value,
        paqueteId: "",
        vueloId: "",
        origen: "",
        fechaSalida: "",
      }));
      return;
    }
    if (name === "paqueteId") {
      const paquete = paquetes.find((item) => item.id === Number(value));
      const vuelo = paquete?.vuelo;
      setFormulario((actual) => ({
        ...actual,
        paqueteId: Number(value),
        vueloId: vuelo?.id || "",
        origen: vuelo?.origen || "",
        destinoId: paquete?.destinoId || "",
        fechaSalida: paquete?.fechaSalida || "",
      }));
      return;
    }
    setFormulario((actual) => ({
      ...actual,
      [name]: name === "pasajeros" ? Number(value) : value,
    }));
  };

  const reservar = async (evento) => {
    evento.preventDefault();
    setMensaje("");
    setError("");
    if (new Date(formulario.fechaRegreso) < new Date(formulario.fechaSalida)) {
      setError("La fecha de regreso debe ser posterior a la fecha de salida.");
      return;
    }
    if (!formulario.paqueteId) {
      setError("Selecciona una reserva disponible para continuar.");
      return;
    }
    setCargando(true);
    try {
      const destinoSeleccionado = destinosDisponibles.find(
        (destino) => Number(destino.id) === Number(formulario.destinoId),
      );
      const reserva = await solicitar("/reservas", {
        method: "POST",
        headers: { Authorization: `Bearer ${sesion.token}` },
        body: JSON.stringify({
          destinoId: Number(formulario.destinoId),
          origen: formulario.origen,
          vueloId: Number(formulario.vueloId),
                    paqueteId: Number(formulario.paqueteId),
          destino: destinoSeleccionado?.nombre || "",
          fechaSalida: formulario.fechaSalida,
          fechaRegreso: formulario.fechaRegreso,
          pasajeros: Number(formulario.pasajeros),
          telefonoContacto: formulario.telefonoContacto,
          notas: formulario.notas,
        }),
      });
      setMensaje("Tu solicitud fue registrada. Ahora completa el pago para confirmar la reserva.");
      setFormulario((actual) => ({
        ...actual,
        fechaSalida: "",
        fechaRegreso: "",
        origen: "",
        vueloId: "",
        notas: "",
      }));
      navigate(`/reservas/pago/${reserva.id}`);
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
          Planea con Aurora
        </span>
        <h1 className="mt-2 font-display text-4xl font-bold text-primario sm:text-5xl">
          Reserva tu próxima historia
        </h1>
        <p className="mt-4 text-lg leading-relaxed text-texto-suave">
          Elige un destino, cuéntanos cuándo viajas y nos encargamos de preparar el resto.
        </p>
      </section>
      <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_0.85fr]">
        <form onSubmit={reservar} className="rounded-lg border border-borde bg-superficie p-6 shadow-sm sm:p-8">
          <h2 className="font-display text-2xl font-bold text-primario">Datos del viaje</h2>
          <div className="mt-6 grid gap-5 sm:grid-cols-2">
            <label className="text-sm font-semibold text-texto sm:col-span-2">
              País y ciudad de destino
              <select
                required
                name="destinoId"
                value={formulario.destinoId}
                onChange={cambiar}
                className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-3 font-normal outline-none focus:border-primario"
              >
                <option value="">Selecciona un destino</option>
                {destinosDisponibles.map((destino) => (
                  <option key={destino.id} value={destino.id}>{destino.nombre}</option>
                ))}
              </select>
            </label>
            <label className="text-sm font-semibold text-texto sm:col-span-2">
              Reserva disponible
              <select
                required
                name="paqueteId"
                value={formulario.paqueteId}
                onChange={cambiar}
                disabled={paquetesDisponibles.length === 0}
                className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-3 font-normal outline-none focus:border-primario disabled:opacity-60"
              >
                <option value="">{paquetesDisponibles.length ? "Selecciona el paquete de viaje" : "No hay reservas disponibles"}</option>
                {paquetesDisponibles.map((paquete) => (
                  <option key={paquete.id} value={paquete.id}>
                    {paquete.nombre} · {paquete.destino} · {paquete.vuelo?.numeroVuelo} · {paquete.fechaSalida}
                  </option>
                ))}
              </select>
            </label>
            {formulario.paqueteId && (
              <div className="grid gap-3 rounded-md bg-fondo p-4 text-sm sm:col-span-2 sm:grid-cols-3">
                <p><span className="block text-xs font-semibold uppercase tracking-wide text-texto-suave">Salida</span><strong>{formulario.origen}</strong></p>
                <p><span className="block text-xs font-semibold uppercase tracking-wide text-texto-suave">Destino</span><strong>{destinoSeleccionado?.nombre}</strong></p>
                <p><span className="block text-xs font-semibold uppercase tracking-wide text-texto-suave">Hotel</span><strong>{paquetes.find((paquete) => paquete.id === Number(formulario.paqueteId))?.hotel?.nombre}</strong></p>
                <p><span className="block text-xs font-semibold uppercase tracking-wide text-texto-suave">Fecha de salida</span><strong>{formulario.fechaSalida}</strong></p>
              </div>
            )}
            <label className="text-sm font-semibold text-texto">
              Fecha de regreso
              <input
                required
                type="date"
                name="fechaRegreso"
                value={formulario.fechaRegreso}
                onChange={cambiar}
                min={formulario.fechaSalida || new Date().toISOString().split("T")[0]}
                className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-3 font-normal outline-none focus:border-primario"
              />
            </label>
            <label className="text-sm font-semibold text-texto">
              Pasajeros
              <select
                name="pasajeros"
                value={formulario.pasajeros}
                onChange={cambiar}
                className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-3 font-normal outline-none focus:border-primario"
              >
                {Array.from({ length: 9 }, (_, indice) => (
                  <option key={indice + 1} value={indice + 1}>{indice + 1}</option>
                ))}
              </select>
            </label>
            <label className="text-sm font-semibold text-texto">
              Teléfono de contacto
              <input
                required
                pattern="[0-9]{7,10}"
                maxLength={10}
                name="telefonoContacto"
                value={formulario.telefonoContacto}
                onChange={cambiar}
                className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-3 font-normal outline-none focus:border-primario"
                placeholder="3000000000"
              />
            </label>
            <label className="text-sm font-semibold text-texto sm:col-span-2">
              Notas para el equipo
              <textarea
                maxLength={300}
                name="notas"
                value={formulario.notas}
                onChange={cambiar}
                rows="3"
                className="mt-2 w-full resize-y rounded-md border border-borde bg-fondo px-3 py-3 font-normal outline-none focus:border-primario"
                placeholder="Cuéntanos alguna preferencia (opcional)"
              />
            </label>
          </div>
          <button
            type="submit"
            disabled={cargando}
            className="mt-6 w-full rounded-md bg-primario px-5 py-3 font-semibold text-white transition hover:bg-primario-oscuro disabled:opacity-60"
          >
            {cargando ? "Enviando solicitud..." : "Solicitar y continuar al pago"}
          </button>
          {mensaje && <p className="mt-4 text-sm font-medium text-primario">{mensaje}</p>}
          {error && <p className="mt-4 text-sm font-medium text-red-700">{error}</p>}
        </form>
        <aside className="rounded-lg bg-primario p-7 text-white sm:p-8">
          <span className="text-xs font-semibold uppercase tracking-widest text-acento-suave">
            Tu experiencia empieza aquí
          </span>
          <h2 className="mt-4 font-display text-3xl font-bold">
            Viajar se siente distinto cuando todo está pensado para ti.
          </h2>
          <p className="mt-5 leading-relaxed text-white/75">
            Recibiremos tu solicitud, verificaremos disponibilidad y actualizaremos el estado de tu reserva desde tu panel personal.
          </p>
          <div className="mt-8 border-t border-white/20 pt-5 text-sm text-white/75">
            Sesión activa como <strong className="text-white">{sesion.usuario.nombre}</strong>
          </div>
        </aside>
      </div>

      <section className="mt-12" aria-labelledby="mis-reservas-titulo">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <span className="text-xs font-semibold uppercase tracking-widest text-primario-suave">Tu historial</span>
            <h2 id="mis-reservas-titulo" className="mt-2 font-display text-3xl font-bold text-primario">Mis reservas</h2>
          </div>
          <span className="rounded-full border border-borde bg-superficie px-3 py-1 text-sm text-texto-suave">
            {misReservas.length} {misReservas.length === 1 ? "reserva" : "reservas"}
          </span>
        </div>

        {misReservas.length === 0 ? (
          <div className="mt-5 rounded-lg border border-dashed border-borde bg-superficie p-8 text-center text-texto-suave">
            Todavía no tienes reservas registradas.
          </div>
        ) : (
          <div className="mt-5 space-y-5">
            {misReservas.map((reserva) => {
              const hotel = reserva.paquete?.hotel;
              const vuelo = reserva.vuelo || reserva.paquete?.vuelo;
              return (
                <details key={reserva.id} open className="group overflow-hidden rounded-lg border border-borde bg-superficie shadow-sm">
                  <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-4 border-b border-borde/70 px-5 py-4 marker:hidden sm:px-6">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-widest text-primario-suave">Reserva #{reserva.id}</p>
                      <h3 className="mt-1 font-display text-2xl font-bold text-primario">{reserva.paquete?.nombre || reserva.destino}</h3>
                      <p className="mt-1 text-sm text-texto-suave">{formatearUbicacion(reserva.destino, reserva.pais)} · {formatearFecha(reserva.fechaSalida)}</p>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <span className="rounded-full bg-primario px-3 py-1 font-semibold capitalize text-white">{etiquetaEstado(reserva.estado)}</span>
                      <span className="rounded-full border border-borde px-3 py-1 capitalize text-texto-suave">Pago: {etiquetaEstado(reserva.estadoPago)}</span>
                    </div>
                  </summary>

                  <div className="grid gap-5 p-5 sm:p-6 lg:grid-cols-2">
                    <div className="rounded-md bg-fondo p-4">
                      <h4 className="font-semibold text-primario">Resumen del viaje</h4>
                      <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                        <div><dt className="text-texto-suave">Destino</dt><dd className="font-semibold text-texto">{formatearUbicacion(reserva.destino, reserva.pais)}</dd></div>
                        <div><dt className="text-texto-suave">Pasajeros</dt><dd className="font-semibold text-texto">{reserva.pasajeros}</dd></div>
                        <div><dt className="text-texto-suave">Salida</dt><dd className="font-semibold text-texto">{formatearFecha(reserva.fechaSalida)}</dd></div>
                        <div><dt className="text-texto-suave">Regreso</dt><dd className="font-semibold text-texto">{formatearFecha(reserva.fechaRegreso)}</dd></div>
                        <div><dt className="text-texto-suave">Origen</dt><dd className="font-semibold text-texto">{reserva.origen || vuelo?.origen || "Sin definir"}</dd></div>
                        <div><dt className="text-texto-suave">Total</dt><dd className="font-semibold text-texto">{formatearMoneda(reserva.montoTotal || reserva.paquete?.precioBase)}</dd></div>
                      </dl>
                    </div>

                    <div className="rounded-md bg-fondo p-4">
                      <h4 className="font-semibold text-primario">Vuelo</h4>
                      {vuelo ? (
                        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                          <div><dt className="text-texto-suave">Número</dt><dd className="font-semibold text-texto">{vuelo.numeroVuelo}</dd></div>
                          <div><dt className="text-texto-suave">Aerolínea</dt><dd className="font-semibold text-texto">{vuelo.aerolinea}</dd></div>
                          <div><dt className="text-texto-suave">Avión</dt><dd className="font-semibold text-texto">{vuelo.avion}</dd></div>
                          <div><dt className="text-texto-suave">Ruta</dt><dd className="font-semibold text-texto">{vuelo.origen} → {vuelo.destino}</dd></div>
                          <div><dt className="text-texto-suave">Salida</dt><dd className="font-semibold text-texto">{formatearFechaHora(vuelo.fechaSalida)}</dd></div>
                          <div><dt className="text-texto-suave">Llegada</dt><dd className="font-semibold text-texto">{formatearFechaHora(vuelo.fechaLlegada)}</dd></div>
                          <div><dt className="text-texto-suave">Terminal</dt><dd className="font-semibold text-texto">{vuelo.terminal || "Sin definir"}</dd></div>
                          <div><dt className="text-texto-suave">Puerta</dt><dd className="font-semibold text-texto">{vuelo.puerta || "Sin definir"}</dd></div>
                        </dl>
                      ) : <p className="mt-3 text-sm text-texto-suave">Información de vuelo pendiente.</p>}
                    </div>

                    <div className="rounded-md border border-borde p-4">
                      <h4 className="font-semibold text-primario">Alojamiento</h4>
                      {hotel ? (
                        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                          <div><dt className="text-texto-suave">Hotel</dt><dd className="font-semibold text-texto">{hotel.nombre}</dd></div>
                          <div><dt className="text-texto-suave">Ubicación</dt><dd className="font-semibold text-texto">{hotel.ciudad}, {hotel.pais}</dd></div>
                          <div><dt className="text-texto-suave">Categoría</dt><dd className="font-semibold text-texto">{hotel.estrellas} estrellas</dd></div>
                          <div><dt className="text-texto-suave">Precio por noche</dt><dd className="font-semibold text-texto">{formatearMoneda(hotel.precioNoche)}</dd></div>
                        </dl>
                      ) : <p className="mt-3 text-sm text-texto-suave">Sin hotel asociado.</p>}
                    </div>

                    <div className="rounded-md border border-borde p-4">
                      <h4 className="font-semibold text-primario">Excursiones incluidas</h4>
                      {reserva.paquete?.excursiones?.length ? (
                        <ul className="mt-3 divide-y divide-borde text-sm">
                          {reserva.paquete.excursiones.map((excursion) => (
                            <li key={excursion.id} className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
                              <span><strong className="text-texto">{excursion.nombre}</strong><span className="block text-texto-suave">{excursion.ciudad}, {excursion.pais} · {excursion.duracionHoras} horas</span></span>
                              <span className="font-semibold text-texto">{formatearMoneda(excursion.precio)}</span>
                            </li>
                          ))}
                        </ul>
                      ) : <p className="mt-3 text-sm text-texto-suave">No incluye excursiones.</p>}
                    </div>

                    <div className="border-t border-borde pt-4 text-sm lg:col-span-2">
                      <div className="grid gap-3 sm:grid-cols-3">
                        <p><span className="block text-texto-suave">Teléfono de contacto</span><strong className="text-texto">{reserva.telefonoContacto || "No registrado"}</strong></p>
                        <p><span className="block text-texto-suave">Método de pago</span><strong className="capitalize text-texto">{reserva.metodoPago || "Pendiente"}</strong></p>
                        <p><span className="block text-texto-suave">Estado del pago</span><strong className="capitalize text-texto">{etiquetaEstado(reserva.estadoPago)}</strong></p>
                      </div>
                      {reserva.notas && <p className="mt-4 rounded-md bg-fondo p-3 text-texto"><span className="font-semibold">Notas:</span> {reserva.notas}</p>}
                    </div>
                  </div>
                </details>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}

export default Reservas;
