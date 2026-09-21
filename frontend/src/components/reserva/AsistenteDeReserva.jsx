import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { solicitar } from "../../utils/api";
import { validarTelefono } from "../../utils/validaciones";
import { PasoConfirmar, PasoDestino, PasoExtras, PasoVuelos } from "./Pasos";
import { estadoDePlazas } from "./plazas";
import ResumenDeViaje from "./ResumenDeViaje";
import SelectorDeCliente from "./SelectorDeCliente";
import { BOTON_VIDRIO, CAJA_ERROR } from "./estilos";

const NOMBRE_DE_PASO = { cliente: "Cliente", destino: "Destino", vuelos: "Vuelos", extras: "Hotel y extras", confirmar: "Confirmar" };

/** Estado con el que arranca el asistente: vacío al reservar, o copiado de la reserva al editarla. */
function estadoInicial(reserva, destinoInicial) {
  return {
    cliente: reserva ? { id: reserva.clienteId, nombre: reserva.cliente, correo: reserva.clienteCorreo } : null,
    destinoId: reserva ? String(reserva.destinoId) : destinoInicial,
    modo: reserva?.paqueteId ? "paquete" : reserva ? "carta" : "paquete",
    paqueteId: reserva?.paqueteId ?? null,
    vueloIdaId: reserva?.vueloId ?? null,
    vueloRegresoId: reserva?.vueloRegresoId ?? null,
    regresoAbierto: Boolean(reserva && !reserva.vueloRegresoId && !reserva.paqueteId),
    fechaRegreso: reserva && !reserva.vueloRegresoId && !reserva.paqueteId ? reserva.fechaRegreso : "",
    hotelId: reserva && !reserva.paqueteId ? reserva.hotelId : null,
    excursiones: reserva && !reserva.paqueteId ? Object.fromEntries(reserva.excursiones.map((excursion) => [excursion.id, excursion.cantidad])) : {},
    pasajeros: reserva?.pasajeros ?? 1,
    telefono: reserva?.telefonoContacto ?? "",
    notas: reserva?.notas ?? "",
    pago: { metodo: "pendiente", referencia: "" },
  };
}

/** Cuerpo que entienden POST /reservas/cotizar y POST/PUT /reservas: lo elegido, sin datos de contacto. */
function cuerpoDeViaje(datos) {
  const base = { destinoId: Number(datos.destinoId), pasajeros: datos.pasajeros };
  if (datos.modo === "paquete") return { ...base, paqueteId: datos.paqueteId };
  const cuerpo = {
    ...base,
    vueloId: datos.vueloIdaId,
    excursiones: Object.entries(datos.excursiones).map(([id, cantidad]) => ({ id: Number(id), cantidad })),
  };
  if (datos.vueloRegresoId) cuerpo.vueloRegresoId = datos.vueloRegresoId;
  else cuerpo.fechaRegreso = datos.fechaRegreso;
  if (datos.hotelId) cuerpo.hotelId = datos.hotelId;
  return cuerpo;
}

const esCotizable = (datos) =>
  datos.modo === "paquete"
    ? Boolean(datos.paqueteId)
    : Boolean(datos.vueloIdaId && (datos.vueloRegresoId || (datos.regresoAbierto && datos.fechaRegreso)));

/**
 * Asistente para pedir o crear una reserva, con los mismos pasos para clientes y para el personal:
 *
 *  1. (personal) el cliente, 2. destino, pasajeros y tipo, 3. vuelos, 4. hotel y excursiones, 5. confirmar.
 *
 * El precio de cada momento lo calcula el servidor con POST /reservas/cotizar, así que el navegador no repite
 * ninguna fórmula y lo que se ve es exactamente lo que se cobra. Con `reserva` edita una existente (PUT).
 */
function AsistenteDeReserva({ modo = "cliente", reserva = null, destinoInicial = "", alTerminar }) {
  const navigate = useNavigate();
  const esPersonal = modo === "personal";
  const edicion = Boolean(reserva);
  const pasos = useMemo(() => (esPersonal && !edicion ? ["cliente", "destino", "vuelos", "extras", "confirmar"] : ["destino", "vuelos", "extras", "confirmar"]), [esPersonal, edicion]);

  const [datos, setDatos] = useState(() => estadoInicial(reserva, destinoInicial));
  const [indice, setIndice] = useState(0);
  const [destinos, setDestinos] = useState([]);
  const [errorDestinos, setErrorDestinos] = useState("");
  const [opcionesCargadas, setOpcionesCargadas] = useState(null);
  const [cotizacionCargada, setCotizacionCargada] = useState(null);
  const [origenElegido, setOrigenElegido] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [errorEnvio, setErrorEnvio] = useState("");

  const paso = pasos[indice];
  const cambiar = (parcial) => setDatos((actual) => ({ ...actual, ...parcial }));

  // Destinos: públicos y de una sola vez.
  useEffect(() => {
    let activo = true;
    solicitar("/catalogos/destinos")
      .then((lista) => activo && setDestinos(lista))
      .catch((error) => activo && setErrorDestinos(error.message));
    return () => {
      activo = false;
    };
  }, []);

  // Vuelos, hoteles, excursiones y paquetes del destino elegido, en una sola llamada. El estado guarda a qué destino
  // pertenece cada respuesta, y así «cargando» se deduce sin tener que escribir estado dentro del efecto.
  useEffect(() => {
    if (!datos.destinoId) return undefined;
    let activo = true;
    solicitar(`/catalogos/destinos/${datos.destinoId}/opciones`)
      .then((cargadas) => activo && setOpcionesCargadas({ destinoId: datos.destinoId, datos: cargadas }))
      .catch((error) => activo && setOpcionesCargadas({ destinoId: datos.destinoId, error: error.message }));
    return () => {
      activo = false;
    };
  }, [datos.destinoId]);

  const opciones = useMemo(() => {
    if (!opcionesCargadas || opcionesCargadas.destinoId !== datos.destinoId) return null;
    if (!opcionesCargadas.datos) return opcionesCargadas;
    const cargadas = opcionesCargadas.datos;
    // Al editar, lo que la reserva ya incluye puede haber salido de las listas (el vuelo ya salió o está lleno; el hotel,
    // la excursión o el paquete se desactivaron): se conserva para no perderlo, y solo mientras se siga en el mismo destino.
    if (!reserva || String(reserva.destinoId) !== datos.destinoId) return opcionesCargadas;
    const conservar = (lista, item) => (item && !lista.some((otro) => otro.id === item.id) ? [...lista, item] : lista);
    const delPaquete = reserva.paquete
      ? {
          ...reserva.paquete,
          destinoId: reserva.destinoId,
          vuelo: reserva.vuelo,
          vueloRegreso: reserva.vueloRegreso,
          hotel: reserva.hotel,
          excursiones: reserva.excursiones,
          noches: reserva.noches,
          fechaSalida: reserva.fechaSalida,
          fechaRegreso: reserva.fechaRegreso,
          plazasLibres: null,
        }
      : null;
    return {
      ...opcionesCargadas,
      datos: {
        ...cargadas,
        vuelosIda: conservar(cargadas.vuelosIda, reserva.vuelo),
        vuelosRegreso: conservar(cargadas.vuelosRegreso, reserva.vueloRegreso),
        hoteles: conservar(cargadas.hoteles, reserva.hotel),
        excursiones: reserva.excursiones.reduce(conservar, cargadas.excursiones),
        paquetes: conservar(cargadas.paquetes, delPaquete),
      },
    };
  }, [opcionesCargadas, datos.destinoId, reserva]);

  // Precio y disponibilidad del viaje, calculados por el servidor un instante después del último cambio.
  // Al editar se indica la reserva, para que el servidor cotice con las reglas de la edición (precios ya vendidos, vuelos que no cambian).
  const cuerpo = useMemo(() => (esCotizable(datos) ? { ...cuerpoDeViaje(datos), ...(reserva ? { reservaId: reserva.id } : {}) } : null), [datos, reserva]);
  const claveDeCotizacion = cuerpo ? JSON.stringify(cuerpo) : "";
  useEffect(() => {
    if (!claveDeCotizacion) return undefined;
    let activo = true;
    const espera = setTimeout(() => {
      solicitar("/reservas/cotizar", { method: "POST", body: claveDeCotizacion })
        .then((resultado) => activo && setCotizacionCargada({ clave: claveDeCotizacion, resultado }))
        .catch((error) => activo && setCotizacionCargada({ clave: claveDeCotizacion, error: error.message }));
    }, 350);
    return () => {
      activo = false;
      clearTimeout(espera);
    };
  }, [claveDeCotizacion]);
  const cotizacionVigente = cotizacionCargada?.clave === claveDeCotizacion ? cotizacionCargada : null;
  const cotizando = Boolean(claveDeCotizacion) && !cotizacionVigente;
  const cotizacion = cotizacionVigente?.resultado ?? null;
  const errorCotizacion = cotizacionVigente?.error ?? "";

  // Lo elegido, buscado en las listas del destino.
  const destino = destinos.find((item) => String(item.id) === datos.destinoId) ?? null;
  const listas = opciones?.datos;
  const paquete = listas?.paquetes.find((item) => item.id === datos.paqueteId) ?? null;
  const ida = listas?.vuelosIda.find((item) => item.id === datos.vueloIdaId) ?? null;
  const origenes = listas?.origenes ?? [];
  const origenFiltro = origenElegido || (ida ? String(ida.origenId) : String(origenes[0]?.id ?? ""));
  const vuelosIda = (listas?.vuelosIda ?? []).filter((vuelo) => String(vuelo.origenId) === origenFiltro);
  // Solo se puede volver al origen de la ida, y después de que llegue.
  const regresos = ida ? (listas?.vuelosRegreso ?? []).filter((vuelo) => vuelo.destinoId === ida.origenId && vuelo.fechaSalida > ida.fechaLlegada) : [];
  const regreso = listas?.vuelosRegreso.find((item) => item.id === datos.vueloRegresoId) ?? null;
  const hotel = datos.modo === "paquete" ? paquete?.hotel ?? null : listas?.hoteles.find((item) => item.id === datos.hotelId) ?? null;
  const excursiones =
    datos.modo === "paquete"
      ? (paquete?.excursiones ?? []).map((excursion) => ({ ...excursion, cantidad: datos.pasajeros }))
      : (listas?.excursiones ?? []).filter((excursion) => datos.excursiones[excursion.id]).map((excursion) => ({ ...excursion, cantidad: datos.excursiones[excursion.id] }));
  const vueloAgotado = [ida, regreso].some((vuelo) => vuelo && estadoDePlazas(vuelo, datos.pasajeros).agotado);
  const paqueteAgotado = paquete && estadoDePlazas({ plazasLibres: paquete.plazasLibres }, datos.pasajeros).agotado;

  // --- Cambios de la selección: al cambiar algo se descarta lo que dependía de ello. ---
  const reiniciarViaje = { paqueteId: null, vueloIdaId: null, vueloRegresoId: null, regresoAbierto: false, fechaRegreso: "", hotelId: null, excursiones: {} };
  const elegirDestino = (id) => {
    setOrigenElegido("");
    cambiar({ destinoId: String(id), ...reiniciarViaje });
  };
  const elegirModo = (nuevoModo) => cambiar({ modo: nuevoModo, ...reiniciarViaje });
  const cambiarPasajeros = (cantidad) => {
    if (cantidad < 1 || cantidad > 9) return;
    setDatos((actual) => ({ ...actual, pasajeros: cantidad, excursiones: Object.fromEntries(Object.entries(actual.excursiones).map(([id, personas]) => [id, Math.min(personas, cantidad)])) }));
  };
  const elegirPaquete = (elegido) => cambiar({ paqueteId: elegido.id });
  const elegirIda = (vuelo) => cambiar({ vueloIdaId: vuelo.id, vueloRegresoId: null, regresoAbierto: false, fechaRegreso: "" });
  const elegirRegreso = (vuelo) => cambiar({ vueloRegresoId: vuelo.id, regresoAbierto: false, fechaRegreso: "" });
  const alternarExcursion = (id) =>
    setDatos((actual) => {
      const siguiente = { ...actual.excursiones };
      if (siguiente[id]) delete siguiente[id];
      else siguiente[id] = actual.pasajeros;
      return { ...actual, excursiones: siguiente };
    });
  const cambiarCantidad = (id, cantidad) => setDatos((actual) => ({ ...actual, excursiones: { ...actual.excursiones, [id]: Math.max(1, Math.min(cantidad, actual.pasajeros)) } }));

  // --- Avance entre pasos ---
  const puedeAvanzar = () => {
    if (paso === "cliente") return Boolean(datos.cliente);
    if (paso === "destino") return Boolean(datos.destinoId) && !opciones?.error;
    if (paso === "vuelos") return esCotizable(datos) && !vueloAgotado && !paqueteAgotado;
    if (paso === "extras") return !errorCotizacion && !cotizando;
    return validarTelefono(datos.telefono) === "" && Boolean(cotizacion) && !cotizando && !enviando;
  };

  const enviar = async () => {
    setEnviando(true);
    setErrorEnvio("");
    const cuerpoFinal = { ...cuerpoDeViaje(datos), telefonoContacto: datos.telefono, notas: datos.notas.trim() || null };
    try {
      if (edicion) {
        await solicitar(`/reservas/${reserva.id}`, { method: "PUT", body: JSON.stringify(cuerpoFinal) });
        alTerminar?.({ accion: "editada", id: reserva.id });
        return;
      }
      if (esPersonal) {
        cuerpoFinal.clienteId = datos.cliente.id;
        if (datos.pago.metodo !== "pendiente") cuerpoFinal.pago = { metodo: datos.pago.metodo, referencia: datos.pago.referencia.trim() || null };
      }
      const creada = await solicitar("/reservas", { method: "POST", body: JSON.stringify(cuerpoFinal) });
      if (esPersonal) alTerminar?.({ accion: "creada", ...creada, cliente: datos.cliente });
      else navigate(`/reservas/pago/${creada.id}`);
    } catch (error) {
      setErrorEnvio(error.message);
    } finally {
      setEnviando(false);
    }
  };

  const esUltimo = indice === pasos.length - 1;
  const textoFinal = edicion ? "Guardar cambios" : esPersonal ? (datos.pago.metodo === "pendiente" ? "Crear reserva" : "Crear reserva y registrar el pago") : "Solicitar y continuar al pago";

  return (
    <div>
      <nav aria-label="Pasos de la reserva" className="mb-6">
        <ol className="flex flex-wrap gap-2">
          {pasos.map((clave, posicion) => {
            const activo = posicion === indice;
            const hecho = posicion < indice;
            return (
              <li key={clave}>
                <button
                  type="button"
                  disabled={posicion > indice}
                  onClick={() => setIndice(posicion)}
                  aria-current={activo ? "step" : undefined}
                  className={`flex items-center gap-2 rounded-full px-3.5 py-2 text-xs font-semibold transition sm:text-sm ${
                    activo ? "boton-tinta" : hecho ? "vidrio text-primario hover:bg-white/85" : "border border-primario/10 text-texto-suave opacity-70"
                  }`}
                >
                  <span aria-hidden="true" className={`grid h-5 w-5 place-items-center rounded-full text-[0.65rem] ${activo ? "bg-oro text-primario" : hecho ? "bg-primario text-crema" : "bg-primario/10"}`}>
                    {hecho ? "✓" : posicion + 1}
                  </span>
                  {NOMBRE_DE_PASO[clave]}
                </button>
              </li>
            );
          })}
        </ol>
      </nav>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_23rem] lg:items-start">
        <section className="vidrio rounded-3xl p-6 sm:p-8" aria-live="polite">
          {paso === "cliente" && (
            <div>
              <div className="mb-5">
                <p className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-suave">Paso · Cliente</p>
                <h2 className="mt-1.5 text-3xl leading-tight text-primario">¿Para quién es la <em className="titulo-enfasis">reserva</em>?</h2>
              </div>
              <SelectorDeCliente cliente={datos.cliente} alElegir={(cliente) => cambiar({ cliente, telefono: cliente?.telefono || datos.telefono })} />
            </div>
          )}
          {paso === "destino" && (
            <PasoDestino destinos={destinos} datos={datos} cambiarPasajeros={cambiarPasajeros} elegirDestino={elegirDestino} elegirModo={elegirModo} opciones={opciones} errorDestinos={errorDestinos} />
          )}
          {paso === "vuelos" && (
            <PasoVuelos
              datos={datos}
              opciones={opciones}
              ida={ida}
              regresos={regresos}
              vuelosIda={vuelosIda}
              origenFiltro={origenFiltro}
              cambiarOrigen={setOrigenElegido}
              elegirPaquete={elegirPaquete}
              elegirIda={elegirIda}
              elegirRegreso={elegirRegreso}
              cambiar={cambiar}
            />
          )}
          {paso === "extras" && (
            <PasoExtras datos={datos} opciones={opciones} paquete={paquete} alternarExcursion={alternarExcursion} cambiarCantidad={cambiarCantidad} cambiar={cambiar} cotizacion={cotizacion} />
          )}
          {paso === "confirmar" && (
            <PasoConfirmar datos={datos} cambiar={cambiar} esPersonal={esPersonal} edicion={edicion} errorEnvio={errorEnvio} cotizacion={cotizacion} pagada={reserva?.estadoPago === "pagado"} />
          )}

          {(vueloAgotado || paqueteAgotado) && paso !== "destino" && (
            <p role="alert" className={`${CAJA_ERROR} mt-5`}>Con {datos.pasajeros} pasajeros ya no alcanzan las plazas de esa opción. Elige otra o reduce los pasajeros.</p>
          )}
          {errorCotizacion && paso !== "confirmar" && paso !== "destino" && (
            <p role="alert" className={`${CAJA_ERROR} mt-5`}>{errorCotizacion}</p>
          )}

          <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-primario/10 pt-5">
            <button type="button" onClick={() => setIndice((actual) => Math.max(0, actual - 1))} disabled={indice === 0 || enviando} className={BOTON_VIDRIO}>
              ← Atrás
            </button>
            {esUltimo ? (
              <button type="button" onClick={enviar} disabled={!puedeAvanzar()} className="boton-tinta px-7 py-3 text-sm font-semibold">
                {enviando ? "Guardando…" : textoFinal}
              </button>
            ) : (
              <button type="button" onClick={() => setIndice((actual) => Math.min(pasos.length - 1, actual + 1))} disabled={!puedeAvanzar()} className="boton-tinta px-7 py-3 text-sm font-semibold">
                Continuar →
              </button>
            )}
          </div>
        </section>

        <div className="lg:sticky lg:top-24">
          <ResumenDeViaje
            destino={destino}
            pasajeros={datos.pasajeros}
            ida={ida}
            regreso={regreso}
            fechaRegresoAbierta={datos.regresoAbierto ? datos.fechaRegreso : ""}
            paquete={paquete}
            hotel={hotel}
            excursiones={excursiones}
            cotizacion={cotizacion}
            cotizando={cotizando}
            errorCotizacion={errorCotizacion}
            cliente={esPersonal ? datos.cliente : null}
          />
        </div>
      </div>
    </div>
  );
}

export default AsistenteDeReserva;
