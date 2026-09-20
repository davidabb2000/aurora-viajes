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
  const destinoNormalizado = destino.trim().normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const paisNormalizado = pais.trim().normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  return destinoNormalizado.endsWith(`, ${paisNormalizado}`) ? destino : `${destino}, ${pais}`;
};
// Dos personas por habitación, igual que el cálculo del backend.
const habitacionesPara = (pasajeros) => Math.ceil(Number(pasajeros || 1) / 2);
const nochesEntre = (salida, regreso) => {
  if (!salida || !regreso) return 0;
  const dias = Math.round((new Date(`${regreso}T00:00:00`) - new Date(`${salida}T00:00:00`)) / 86400000);
  return Math.max(1, dias);
};

const CAMPO = "mt-2 w-full rounded-xl border border-primario/12 bg-white/70 px-3 py-3 font-normal text-texto shadow-sm shadow-primario/5 outline-none backdrop-blur-sm transition focus:border-primario-suave focus:bg-white/90 focus:ring-3 focus:ring-primario-suave/20";

function Reservas() {
  const { sesion } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [destinosCatalogo, setDestinosCatalogo] = useState([]);
  const [vuelos, setVuelos] = useState([]);
  const [paquetes, setPaquetes] = useState([]);
  const [misReservas, setMisReservas] = useState([]);
  // "paquete" reserva una oferta cerrada; "carta" arma vuelo + hotel + excursiones.
  const [modo, setModo] = useState("paquete");
  const [opciones, setOpciones] = useState(null);
  const [cargandoOpciones, setCargandoOpciones] = useState(false);
  const [formulario, setFormulario] = useState({
    origen: "",
    destinoId: new URLSearchParams(location.search).get("destino") || "",
    fechaSalida: "",
    fechaRegreso: "",
    vueloId: "",
    paqueteId: "",
    hotelId: "",
    excursionIds: [],
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
      // Los destinos son públicos y van solos: si fallan, se cae al listado estático;
      // si falla cualquier otra llamada, los destinos ya cargados se conservan.
      try {
        const destinos = await solicitar("/catalogos/destinos");
        if (activo) setDestinosCatalogo(destinos);
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
      if (!sesion) return;
      const cabecera = { headers: { Authorization: `Bearer ${sesion.token}` } };
      const [vuelosCatalogo, paquetesCatalogo, reservasUsuario] = await Promise.all([
        solicitar("/vuelos", cabecera).catch(() => null),
        solicitar("/paquetes", cabecera).catch(() => null),
        solicitar("/reservas/mias", cabecera).catch(() => null),
      ]);
      if (!activo) return;
      if (vuelosCatalogo) setVuelos(vuelosCatalogo);
      if (paquetesCatalogo) setPaquetes(paquetesCatalogo);
      if (reservasUsuario) setMisReservas(reservasUsuario);
    };
    cargarCatalogo();
    return () => {
      activo = false;
    };
  }, [sesion]);

  // En modo a la carta pedimos vuelos, hoteles y excursiones del destino en
  // una sola llamada, ya filtrados por el backend.
  useEffect(() => {
    if (modo !== "carta" || !formulario.destinoId) {
      setOpciones(null);
      return undefined;
    }
    let activo = true;
    setCargandoOpciones(true);
    solicitar(`/catalogos/destinos/${formulario.destinoId}/opciones`, {
      headers: sesion ? { Authorization: `Bearer ${sesion.token}` } : {},
    })
      .then((datos) => { if (activo) setOpciones(datos); })
      .catch((requestError) => { if (activo) { setOpciones(null); setError(requestError.message); } })
      .finally(() => { if (activo) setCargandoOpciones(false); });
    return () => { activo = false; };
  }, [modo, formulario.destinoId, sesion]);

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

  const vuelosDisponibles = useMemo(
    () => vuelos.filter((vuelo) => vuelo.activo && ["programado", "abordando"].includes(vuelo.estado)
      && new Date(vuelo.fechaSalida) >= new Date()
      && (vuelo.pasajerosDisponibles == null || vuelo.pasajerosDisponibles >= formulario.pasajeros)),
    [formulario.pasajeros, vuelos],
  );

  const paqueteElegido = paquetes.find((paquete) => paquete.id === Number(formulario.paqueteId)) || null;
  const destinoSeleccionado = destinosDisponibles.find((destino) => Number(destino.id) === Number(formulario.destinoId));
  const paquetesDisponibles = useMemo(
    () => paquetes.filter((paquete) => paquete.activo
      && Number(paquete.destinoId) === Number(formulario.destinoId)
      && (paquete.vuelo?.pasajerosDisponibles == null || paquete.vuelo?.pasajerosDisponibles >= formulario.pasajeros)),
    [paquetes, formulario.destinoId, formulario.pasajeros],
  );

  // Vuelos del destino que además tienen cupo para los pasajeros pedidos.
  const vuelosDelDestino = useMemo(() => {
    if (!opciones?.vuelos) return [];
    const cupos = new Map(vuelosDisponibles.map((vuelo) => [vuelo.id, vuelo.pasajerosDisponibles]));
    return opciones.vuelos
      .filter((vuelo) => vuelo.activo && ["programado", "abordando"].includes(vuelo.estado))
      .filter((vuelo) => new Date(vuelo.fechaSalida) >= new Date())
      .map((vuelo) => ({ ...vuelo, pasajerosDisponibles: cupos.get(vuelo.id) }))
      .filter((vuelo) => vuelo.pasajerosDisponibles == null || vuelo.pasajerosDisponibles >= formulario.pasajeros);
  }, [opciones, vuelosDisponibles, formulario.pasajeros]);

  const hotelElegido = opciones?.hoteles?.find((hotel) => Number(hotel.id) === Number(formulario.hotelId)) || null;
  const excursionesElegidas = useMemo(
    () => (opciones?.excursiones || []).filter((excursion) => formulario.excursionIds.includes(excursion.id)),
    [opciones, formulario.excursionIds],
  );

  // Estimación con la misma fórmula del backend: vuelo por pasajero, hotel por
  // noche y habitación, excursiones por pasajero. El precio final lo fija el servidor.
  const desglose = useMemo(() => {
    const pasajeros = Number(formulario.pasajeros || 1);
    const noches = nochesEntre(formulario.fechaSalida, formulario.fechaRegreso);
    const vuelo = Number(opciones?.destino?.precioBase || destinoSeleccionado?.precioBase || 0) * pasajeros;
    const hotel = hotelElegido ? Number(hotelElegido.precioNoche || 0) * noches * habitacionesPara(pasajeros) : 0;
    const excursion = excursionesElegidas.reduce((total, item) => total + Number(item.precio || 0) * pasajeros, 0);
    return { vuelo, hotel, excursiones: excursion, noches, total: vuelo + hotel + excursion };
  }, [formulario.pasajeros, formulario.fechaSalida, formulario.fechaRegreso, opciones, destinoSeleccionado, hotelElegido, excursionesElegidas]);

  if (!sesion) return <Navigate to="/login" state={{ desde: location.pathname + location.search }} replace />;

  const cambiar = (evento) => {
    const { name, value } = evento.target;
    if (name === "destinoId") {
      setFormulario((actual) => ({
        ...actual,
        destinoId: value,
        paqueteId: "",
        vueloId: "",
        hotelId: "",
        excursionIds: [],
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
    if (name === "vueloId") {
      // El vuelo manda la fecha de salida y el origen: el backend exige que coincidan.
      const vuelo = vuelosDelDestino.find((item) => item.id === Number(value));
      setFormulario((actual) => ({
        ...actual,
        vueloId: Number(value) || "",
        origen: vuelo?.origen || "",
        fechaSalida: vuelo?.fechaSalida?.slice(0, 10) || "",
      }));
      return;
    }
    setFormulario((actual) => ({
      ...actual,
      [name]: name === "pasajeros" ? Number(value) : value,
    }));
  };

  const alternarExcursion = (id) => {
    setFormulario((actual) => ({
      ...actual,
      excursionIds: actual.excursionIds.includes(id)
        ? actual.excursionIds.filter((item) => item !== id)
        : [...actual.excursionIds, id],
    }));
  };

  const cambiarModo = (nuevoModo) => {
    setModo(nuevoModo);
    setError("");
    setMensaje("");
    setFormulario((actual) => ({ ...actual, paqueteId: "", vueloId: "", hotelId: "", excursionIds: [], origen: "", fechaSalida: "" }));
  };

  const reservar = async (evento) => {
    evento.preventDefault();
    setMensaje("");
    setError("");
    if (new Date(formulario.fechaRegreso) < new Date(formulario.fechaSalida)) {
      setError("La fecha de regreso debe ser posterior a la fecha de salida.");
      return;
    }
    if (modo === "paquete" && !formulario.paqueteId) {
      setError("Selecciona una reserva disponible para continuar.");
      return;
    }
    if (modo === "carta" && !formulario.vueloId) {
      setError("Selecciona el vuelo con el que quieres viajar.");
      return;
    }
    setCargando(true);
    try {
      const destinoElegido = destinosDisponibles.find(
        (destino) => Number(destino.id) === Number(formulario.destinoId),
      );
      const cuerpo = {
        destinoId: Number(formulario.destinoId),
        origen: formulario.origen,
        vueloId: Number(formulario.vueloId),
        destino: destinoElegido?.nombre || "",
        fechaSalida: formulario.fechaSalida,
        fechaRegreso: formulario.fechaRegreso,
        pasajeros: Number(formulario.pasajeros),
        telefonoContacto: formulario.telefonoContacto,
        notas: formulario.notas,
      };
      if (modo === "paquete") {
        cuerpo.paqueteId = Number(formulario.paqueteId);
      } else {
        if (formulario.hotelId) cuerpo.hotelId = Number(formulario.hotelId);
        cuerpo.excursionIds = formulario.excursionIds;
      }
      const reserva = await solicitar("/reservas", {
        method: "POST",
        headers: { Authorization: `Bearer ${sesion.token}` },
        body: JSON.stringify(cuerpo),
      });
      setMensaje("Tu solicitud fue registrada. Ahora completa el pago para confirmar la reserva.");
      setFormulario((actual) => ({
        ...actual,
        fechaSalida: "",
        fechaRegreso: "",
        origen: "",
        vueloId: "",
        hotelId: "",
        excursionIds: [],
        notas: "",
      }));
      navigate(`/reservas/pago/${reserva.id}`);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setCargando(false);
    }
  };

  const pestanaClase = (activa) =>
    `flex-1 rounded-xl px-4 py-2.5 text-sm font-semibold transition ${
      activa
        ? "boton-tinta text-white"
        : "text-texto-suave hover:bg-white/60 hover:text-primario"
    }`;

  return (
    <main className="mx-auto w-[92%] max-w-275 flex-1 py-10 sm:py-14">
      <section className="vidrio rounded-3xl p-7 sm:p-10">
        <div className="max-w-2xl">
          <span className="antetitulo">Planea con Aurora</span>
          <h1 className="mt-3 font-display text-4xl font-bold sm:text-5xl">
            <span className="titulo-aurora">Reserva tu próxima historia</span>
          </h1>
          <p className="mt-4 text-lg leading-relaxed text-texto-suave">
            Elige un destino, cuéntanos cuándo viajas y nos encargamos de preparar el resto.
          </p>
        </div>
      </section>

      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_0.85fr]">
        <form onSubmit={reservar} className="vidrio rounded-3xl p-6 sm:p-8">
          <h2 className="font-display text-2xl font-bold text-primario">Datos del viaje</h2>

          {/* Dos maneras de reservar: la oferta cerrada o el viaje armado pieza por pieza. */}
          <div className="vidrio-sutil mt-5 flex gap-2 rounded-2xl p-1.5" role="tablist" aria-label="Forma de reservar">
            <button type="button" role="tab" aria-selected={modo === "paquete"} onClick={() => cambiarModo("paquete")} className={pestanaClase(modo === "paquete")}>
              ✦ Paquete listo
            </button>
            <button type="button" role="tab" aria-selected={modo === "carta"} onClick={() => cambiarModo("carta")} className={pestanaClase(modo === "carta")}>
              ◈ A la carta
            </button>
          </div>
          <p className="mt-3 text-xs leading-relaxed text-texto-suave">
            {modo === "paquete"
              ? "Un paquete ya trae vuelo, hotel y excursiones a un precio cerrado."
              : "Eliges el vuelo, el hotel y las excursiones que quieras; se cobran por separado."}
          </p>

          <div className="mt-6 grid gap-5 sm:grid-cols-2">
            <label className="text-sm font-semibold text-texto sm:col-span-2">
              País y ciudad de destino
              <select
                required
                name="destinoId"
                value={formulario.destinoId}
                onChange={cambiar}
                className={CAMPO}
              >
                <option value="">Selecciona un destino</option>
                {destinosDisponibles.map((destino) => (
                  <option key={destino.id} value={destino.id}>{destino.nombre}</option>
                ))}
              </select>
            </label>

            {modo === "paquete" ? (
              <>
                <label className="text-sm font-semibold text-texto sm:col-span-2">
                  Reserva disponible
                  <select
                    required
                    name="paqueteId"
                    value={formulario.paqueteId}
                    onChange={cambiar}
                    disabled={paquetesDisponibles.length === 0}
                    className={`${CAMPO} disabled:opacity-60`}
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
                  <div className="vidrio-sutil grid gap-3 rounded-2xl p-4 text-sm sm:col-span-2 sm:grid-cols-3">
                    <p><span className="block text-xs font-semibold uppercase tracking-wide text-texto-suave">Salida</span><strong>{formulario.origen}</strong></p>
                    <p><span className="block text-xs font-semibold uppercase tracking-wide text-texto-suave">Destino</span><strong>{destinoSeleccionado?.nombre}</strong></p>
                    <p><span className="block text-xs font-semibold uppercase tracking-wide text-texto-suave">Hotel</span><strong>{paqueteElegido?.hotel?.nombre}</strong></p>
                    <p><span className="block text-xs font-semibold uppercase tracking-wide text-texto-suave">Fecha de salida</span><strong>{formulario.fechaSalida}</strong></p>
                    <p className="sm:col-span-2">
                      <span className="block text-xs font-semibold uppercase tracking-wide text-texto-suave">Precio del paquete</span>
                      <strong>
                        {formatearMoneda(paqueteElegido?.precioBase)} por persona · {formatearMoneda(Number(paqueteElegido?.precioBase || 0) * Number(formulario.pasajeros))} en total
                      </strong>
                    </p>
                  </div>
                )}
              </>
            ) : (
              <>
                <label className="text-sm font-semibold text-texto sm:col-span-2">
                  Vuelo
                  <select
                    required
                    name="vueloId"
                    value={formulario.vueloId}
                    onChange={cambiar}
                    disabled={!formulario.destinoId || vuelosDelDestino.length === 0}
                    className={`${CAMPO} disabled:opacity-60`}
                  >
                    <option value="">
                      {!formulario.destinoId
                        ? "Elige primero el destino"
                        : cargandoOpciones
                          ? "Buscando vuelos..."
                          : vuelosDelDestino.length
                            ? "Selecciona el vuelo"
                            : "No hay vuelos con cupo para este destino"}
                    </option>
                    {vuelosDelDestino.map((vuelo) => (
                      <option key={vuelo.id} value={vuelo.id}>
                        {vuelo.numeroVuelo} · {vuelo.aerolinea} · {vuelo.origen} → {vuelo.destino} · {formatearFechaHora(vuelo.fechaSalida)}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="text-sm font-semibold text-texto sm:col-span-2">
                  Hotel <span className="font-normal text-texto-suave">(opcional)</span>
                  <select
                    name="hotelId"
                    value={formulario.hotelId}
                    onChange={cambiar}
                    disabled={!formulario.destinoId || !opciones?.hoteles?.length}
                    className={`${CAMPO} disabled:opacity-60`}
                  >
                    <option value="">
                      {opciones?.hoteles?.length ? "Sin alojamiento" : "No hay hoteles en este destino"}
                    </option>
                    {(opciones?.hoteles || []).map((hotel) => (
                      <option key={hotel.id} value={hotel.id}>
                        {hotel.nombre} · {"★".repeat(hotel.estrellas || 0)} · {formatearMoneda(hotel.precioNoche)} / noche
                      </option>
                    ))}
                  </select>
                </label>

                <fieldset className="text-sm font-semibold text-texto sm:col-span-2">
                  <legend>Excursiones <span className="font-normal text-texto-suave">(opcional, se cobran por pasajero)</span></legend>
                  {opciones?.excursiones?.length ? (
                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      {opciones.excursiones.map((excursion) => {
                        const activa = formulario.excursionIds.includes(excursion.id);
                        return (
                          <label
                            key={excursion.id}
                            className={`flex cursor-pointer items-start gap-3 rounded-2xl border p-3 text-sm font-normal transition ${
                              activa
                                ? "border-primario-suave/60 bg-white/85 shadow-md shadow-primario/15"
                                : "border-primario/12 bg-white/45 hover:bg-white/70"
                            }`}
                          >
                            <input
                              type="checkbox"
                              checked={activa}
                              onChange={() => alternarExcursion(excursion.id)}
                              className="mt-0.5 h-4 w-4 rounded border-primario/12 accent-primario"
                            />
                            <span>
                              <strong className="block text-texto">{excursion.nombre}</strong>
                              <span className="block text-xs text-texto-suave">{excursion.duracionHoras} h · {formatearMoneda(excursion.precio)} por pasajero</span>
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="mt-2 text-sm font-normal text-texto-suave">
                      {formulario.destinoId ? "Este destino aún no tiene excursiones publicadas." : "Elige primero el destino."}
                    </p>
                  )}
                </fieldset>

                {formulario.vueloId && (
                  <div className="vidrio-sutil grid gap-3 rounded-2xl p-4 text-sm sm:col-span-2 sm:grid-cols-3">
                    <p><span className="block text-xs font-semibold uppercase tracking-wide text-texto-suave">Origen</span><strong>{formulario.origen}</strong></p>
                    <p><span className="block text-xs font-semibold uppercase tracking-wide text-texto-suave">Destino</span><strong>{destinoSeleccionado?.nombre}</strong></p>
                    <p><span className="block text-xs font-semibold uppercase tracking-wide text-texto-suave">Fecha de salida</span><strong>{formulario.fechaSalida}</strong></p>
                  </div>
                )}
              </>
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
                className={CAMPO}
              />
            </label>
            <label className="text-sm font-semibold text-texto">
              Pasajeros
              <select
                name="pasajeros"
                value={formulario.pasajeros}
                onChange={cambiar}
                className={CAMPO}
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
                className={CAMPO}
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
                className={`${CAMPO} resize-y`}
                placeholder="Cuéntanos alguna preferencia (opcional)"
              />
            </label>
          </div>
          <button
            type="submit"
            disabled={cargando}
            className="mt-6 w-full rounded-xl boton-tinta px-5 py-3 font-semibold text-white disabled:opacity-60"
          >
            {cargando ? "Enviando solicitud..." : "Solicitar y continuar al pago"}
          </button>
          {mensaje && <p className="vidrio-sutil mt-4 rounded-xl px-4 py-3 text-sm font-medium text-primario">{mensaje}</p>}
          {error && <p className="mt-4 rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm font-medium text-red-700 backdrop-blur-sm">{error}</p>}
        </form>

        <div className="flex flex-col gap-6">
          {/* Desglose en vivo: el cliente ve por qué paga lo que paga antes de enviar. */}
          {modo === "carta" && formulario.destinoId && (
            <section className="vidrio rounded-3xl p-6 sm:p-7" aria-live="polite">
              <h2 className="font-display text-xl font-bold text-primario">Desglose estimado</h2>
              <dl className="mt-4 space-y-3 text-sm">
                <div className="flex items-baseline justify-between gap-4">
                  <dt className="text-texto-suave">Vuelo · {formulario.pasajeros} pasajero(s)</dt>
                  <dd className="font-semibold text-texto">{formatearMoneda(desglose.vuelo)}</dd>
                </div>
                <div className="flex items-baseline justify-between gap-4">
                  <dt className="text-texto-suave">
                    Hotel{hotelElegido ? ` · ${desglose.noches} noche(s) × ${habitacionesPara(formulario.pasajeros)} hab.` : ""}
                  </dt>
                  <dd className="font-semibold text-texto">{formatearMoneda(desglose.hotel)}</dd>
                </div>
                <div className="flex items-baseline justify-between gap-4">
                  <dt className="text-texto-suave">Excursiones · {excursionesElegidas.length} elegida(s)</dt>
                  <dd className="font-semibold text-texto">{formatearMoneda(desglose.excursiones)}</dd>
                </div>
                <div className="flex items-baseline justify-between gap-4 border-t border-primario/12 pt-3">
                  <dt className="font-semibold text-primario">Total estimado</dt>
                  <dd className="font-display text-2xl font-bold text-primario">{formatearMoneda(desglose.total)}</dd>
                </div>
              </dl>
              <p className="mt-3 text-xs leading-relaxed text-texto-suave">
                El precio definitivo lo confirma el servidor al registrar la reserva.
              </p>
            </section>
          )}

          <aside className="relative flex-1 overflow-hidden rounded-3xl bg-gradient-to-br from-marino via-marino-profundo to-[#020a17] p-7 text-white sm:p-8">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 opacity-80"
              style={{ background: "radial-gradient(26rem 20rem at 100% 0%, rgba(208,81,42,0.34), transparent 62%), radial-gradient(22rem 18rem at 0% 100%, rgba(255,255,255,0.10), transparent 62%)" }}
            />
            <span className="relative inline-flex items-center gap-2 rounded-full border border-white/25 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-acento-suave backdrop-blur-sm">
              Tu experiencia empieza aquí
            </span>
            <h2 className="relative mt-4 font-display text-3xl font-bold">
              Viajar se siente distinto cuando todo está pensado para ti.
            </h2>
            <p className="relative mt-5 leading-relaxed text-white/75">
              Recibiremos tu solicitud, verificaremos disponibilidad y actualizaremos el estado de tu reserva desde tu panel personal.
            </p>
            <div className="relative mt-8 border-t border-white/20 pt-5 text-sm text-white/75">
              Sesión activa como <strong className="text-white">{sesion.usuario.nombre}</strong>
            </div>
          </aside>
        </div>
      </div>

      <section className="mt-12" aria-labelledby="mis-reservas-titulo">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <span className="text-xs font-semibold uppercase tracking-widest text-primario-suave">Tu historial</span>
            <h2 id="mis-reservas-titulo" className="mt-2 font-display text-3xl font-bold text-primario">Mis reservas</h2>
          </div>
          <span className="vidrio rounded-full px-4 py-1.5 text-sm text-texto-suave">
            {misReservas.length} {misReservas.length === 1 ? "reserva" : "reservas"}
          </span>
        </div>

        {misReservas.length === 0 ? (
          <div className="vidrio mt-5 rounded-3xl border-dashed p-8 text-center text-texto-suave">
            Todavía no tienes reservas registradas.
          </div>
        ) : (
          <div className="mt-5 space-y-5">
            {misReservas.map((reserva) => {
              const hotel = reserva.hotel || reserva.paquete?.hotel;
              const vuelo = reserva.vuelo || reserva.paquete?.vuelo;
              const excursiones = reserva.excursiones?.length ? reserva.excursiones : reserva.paquete?.excursiones;
              const desgloseReserva = reserva.desglose || {};
              const tieneDesglose = Boolean(desgloseReserva.vuelo || desgloseReserva.hotel || desgloseReserva.excursiones);
              return (
                <details key={reserva.id} open className="vidrio group overflow-hidden rounded-3xl">
                  <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-4 border-b border-primario/12 px-5 py-4 marker:hidden sm:px-6">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-widest text-primario-suave">Reserva #{reserva.id}</p>
                      <h3 className="mt-1 font-display text-2xl font-bold text-primario">{reserva.paquete?.nombre || reserva.destino}</h3>
                      <p className="mt-1 text-sm text-texto-suave">{formatearUbicacion(reserva.destino, reserva.pais)} · {formatearFecha(reserva.fechaSalida)}</p>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <span className="rounded-full bg-primario px-3 py-1 font-semibold capitalize text-white">{etiquetaEstado(reserva.estado)}</span>
                      <span className="rounded-full border border-primario/12 bg-white/60 px-3 py-1 capitalize text-texto-suave backdrop-blur-sm">Pago: {etiquetaEstado(reserva.estadoPago)}</span>
                    </div>
                  </summary>

                  <div className="grid gap-5 p-5 sm:p-6 lg:grid-cols-2">
                    <div className="vidrio-sutil rounded-2xl p-4">
                      <h4 className="font-semibold text-primario">Resumen del viaje</h4>
                      <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                        <div><dt className="text-texto-suave">Destino</dt><dd className="font-semibold text-texto">{formatearUbicacion(reserva.destino, reserva.pais)}</dd></div>
                        <div><dt className="text-texto-suave">Pasajeros</dt><dd className="font-semibold text-texto">{reserva.pasajeros}</dd></div>
                        <div><dt className="text-texto-suave">Salida</dt><dd className="font-semibold text-texto">{formatearFecha(reserva.fechaSalida)}</dd></div>
                        <div><dt className="text-texto-suave">Regreso</dt><dd className="font-semibold text-texto">{formatearFecha(reserva.fechaRegreso)}</dd></div>
                        <div><dt className="text-texto-suave">Origen</dt><dd className="font-semibold text-texto">{reserva.origen || vuelo?.origen || "Sin definir"}</dd></div>
                        <div><dt className="text-texto-suave">Total</dt><dd className="font-semibold text-texto">{formatearMoneda(reserva.montoTotal || reserva.paquete?.precioBase)}</dd></div>
                      </dl>
                      {tieneDesglose && reserva.paqueteId && (
                        <div className="mt-4 border-t border-primario/12 pt-3 text-sm">
                          <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Cómo se compone</p>
                          <p className="mt-2 text-texto-suave">
                            Paquete cerrado: el precio ya incluye vuelo, hotel y excursiones.
                          </p>
                        </div>
                      )}
                      {tieneDesglose && !reserva.paqueteId && (
                        <div className="mt-4 border-t border-primario/12 pt-3 text-sm">
                          <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Cómo se compone</p>
                          <div className="mt-2 grid gap-1.5 sm:grid-cols-3">
                            <p><span className="block text-texto-suave">Vuelo</span><strong className="text-texto">{formatearMoneda(desgloseReserva.vuelo)}</strong></p>
                            <p><span className="block text-texto-suave">Hotel</span><strong className="text-texto">{formatearMoneda(desgloseReserva.hotel)}</strong></p>
                            <p><span className="block text-texto-suave">Excursiones</span><strong className="text-texto">{formatearMoneda(desgloseReserva.excursiones)}</strong></p>
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="vidrio-sutil rounded-2xl p-4">
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

                    <div className="vidrio-sutil rounded-2xl p-4">
                      <h4 className="font-semibold text-primario">Alojamiento</h4>
                      {hotel ? (
                        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                          <div><dt className="text-texto-suave">Hotel</dt><dd className="font-semibold text-texto">{hotel.nombre}</dd></div>
                          <div><dt className="text-texto-suave">Ubicación</dt><dd className="font-semibold text-texto">{[hotel.ciudad, hotel.pais].filter(Boolean).join(", ") || "Sin definir"}</dd></div>
                          <div><dt className="text-texto-suave">Categoría</dt><dd className="font-semibold text-texto">{hotel.estrellas} estrellas</dd></div>
                          <div><dt className="text-texto-suave">Precio por noche</dt><dd className="font-semibold text-texto">{formatearMoneda(hotel.precioNoche)}</dd></div>
                        </dl>
                      ) : <p className="mt-3 text-sm text-texto-suave">Sin hotel asociado.</p>}
                    </div>

                    <div className="vidrio-sutil rounded-2xl p-4">
                      <h4 className="font-semibold text-primario">Excursiones incluidas</h4>
                      {excursiones?.length ? (
                        <ul className="mt-3 divide-y divide-primario/10 text-sm">
                          {excursiones.map((excursion) => (
                            <li key={excursion.id} className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
                              <span><strong className="text-texto">{excursion.nombre}</strong><span className="block text-texto-suave">{[[excursion.ciudad, excursion.pais].filter(Boolean).join(", "), `${excursion.duracionHoras} horas`].filter(Boolean).join(" · ")}</span></span>
                              <span className="font-semibold text-texto">{formatearMoneda(excursion.precio)}</span>
                            </li>
                          ))}
                        </ul>
                      ) : <p className="mt-3 text-sm text-texto-suave">No incluye excursiones.</p>}
                    </div>

                    <div className="border-t border-primario/12 pt-4 text-sm lg:col-span-2">
                      <div className="grid gap-3 sm:grid-cols-3">
                        <p><span className="block text-texto-suave">Teléfono de contacto</span><strong className="text-texto">{reserva.telefonoContacto || "No registrado"}</strong></p>
                        <p><span className="block text-texto-suave">Método de pago</span><strong className="capitalize text-texto">{reserva.metodoPago || "Pendiente"}</strong></p>
                        <p><span className="block text-texto-suave">Estado del pago</span><strong className="capitalize text-texto">{etiquetaEstado(reserva.estadoPago)}</strong></p>
                      </div>
                      {reserva.notas && <p className="vidrio-sutil mt-4 rounded-xl p-3 text-texto"><span className="font-semibold">Notas:</span> {reserva.notas}</p>}
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
