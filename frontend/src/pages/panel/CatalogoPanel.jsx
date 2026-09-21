import { useState } from "react";
import { BOTON_VIDRIO, CAJA_ERROR, CAMPO, ETIQUETA_MONO } from "../../components/reserva/estilos";
import { solicitar } from "../../utils/api";
import { fecha, moneda, nochesEntre, sumarDias } from "../../utils/formato";
import { useCarga } from "../../utils/useCarga";
import { Aviso, EncabezadoDePanel } from "./Encabezado";

const PESTANAS = [
  ["paquetes", "Paquetes"],
  ["hoteles", "Hoteles"],
  ["excursiones", "Excursiones"],
  ["destinos", "Destinos"],
  ["lugares", "Lugares"],
];

const SelectorDeCiudad = ({ ciudades, value, onChange, name = "ciudadId" }) => (
  <select name={name} value={value} onChange={onChange} required className={`${CAMPO} mt-1.5`}>
    <option value="">Selecciona una ciudad</option>
    {ciudades.map((ciudad) => <option key={ciudad.id} value={ciudad.id}>{ciudad.nombre}, {ciudad.pais}</option>)}
  </select>
);

/** Estructura común de las cuatro pestañas: lista a la izquierda, formulario a la derecha. */
function Disposicion({ titulo, lista, formulario }) {
  return (
    <div className="mt-6 grid gap-6 xl:grid-cols-[1.3fr_1fr]">
      <section className="vidrio rounded-3xl p-5 sm:p-6">
        <h2 className="text-2xl text-primario">{titulo}</h2>
        <div className="mt-4 space-y-3">{lista}</div>
      </section>
      <div className="xl:sticky xl:top-6 xl:self-start">{formulario}</div>
    </div>
  );
}

function Insignia({ activo }) {
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${activo ? "bg-primario/8 text-primario" : "bg-arena text-texto-suave"}`}>{activo ? "Activo" : "Inactivo"}</span>;
}

// ---------------------------------------------------------------------------------------------
// Hoteles y excursiones: el mismo patrón, con un campo propio cada uno
// ---------------------------------------------------------------------------------------------

function FormularioDeElemento({ tipo, elemento, ciudades, alGuardar, alCancelar }) {
  const esHotel = tipo === "hoteles";
  const [valores, setValores] = useState(() =>
    elemento
      ? { nombre: elemento.nombre, ciudadId: String(elemento.ciudadId), numero: String(esHotel ? elemento.estrellas : elemento.duracionHoras), precio: String(esHotel ? elemento.precioNoche : elemento.precio), descripcion: elemento.descripcion || "", activo: elemento.activo }
      : { nombre: "", ciudadId: "", numero: "", precio: "", descripcion: "", activo: true },
  );
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const cambiar = (evento) => {
    const { name, value, type, checked } = evento.target;
    setValores((actual) => ({ ...actual, [name]: type === "checkbox" ? checked : value }));
  };

  const guardar = async (evento) => {
    evento.preventDefault();
    setGuardando(true);
    setError("");
    const cuerpo = esHotel
      ? { nombre: valores.nombre, ciudadId: Number(valores.ciudadId), estrellas: Number(valores.numero), precioNoche: Number(valores.precio), descripcion: valores.descripcion || null, activo: valores.activo }
      : { nombre: valores.nombre, ciudadId: Number(valores.ciudadId), duracionHoras: Number(valores.numero), precio: Number(valores.precio), descripcion: valores.descripcion || null, activo: valores.activo };
    try {
      await solicitar(elemento ? `/${tipo}/${elemento.id}` : `/${tipo}`, { method: elemento ? "PUT" : "POST", body: JSON.stringify(cuerpo) });
      alGuardar(elemento ? "Cambios guardados." : esHotel ? "Hotel creado." : "Excursión creada.");
    } catch (requestError) {
      setError(requestError.message);
      setGuardando(false);
    }
  };

  return (
    <form onSubmit={guardar} className="vidrio rounded-3xl p-6">
      <h2 className="text-2xl text-primario">{elemento ? "Modificar" : "Agregar"} {esHotel ? "hotel" : "excursión"}</h2>
      <div className="mt-4 grid gap-4">
        <label className="text-sm font-medium text-texto">Nombre <span className="text-acento">*</span><input name="nombre" required minLength={2} maxLength={120} value={valores.nombre} onChange={cambiar} className={`${CAMPO} mt-1.5`} /></label>
        <label className="text-sm font-medium text-texto">Ciudad <span className="text-acento">*</span><SelectorDeCiudad ciudades={ciudades} value={valores.ciudadId} onChange={cambiar} /></label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-medium text-texto">{esHotel ? "Estrellas (1 a 5)" : "Duración en horas (1 a 48)"} <span className="text-acento">*</span>
            <input name="numero" type="number" required min="1" max={esHotel ? 5 : 48} value={valores.numero} onChange={cambiar} className={`${CAMPO} mt-1.5`} />
          </label>
          <label className="text-sm font-medium text-texto">{esHotel ? "Precio por noche" : "Precio por persona"} <span className="text-acento">*</span>
            <input name="precio" type="number" required min="0" step="1000" value={valores.precio} onChange={cambiar} className={`${CAMPO} mt-1.5`} />
          </label>
        </div>
        <label className="text-sm font-medium text-texto">Descripción<textarea name="descripcion" rows={3} maxLength={1000} value={valores.descripcion} onChange={cambiar} className={`${CAMPO} mt-1.5 resize-y`} /></label>
        <label className="flex items-center gap-2 text-sm font-medium text-texto"><input type="checkbox" name="activo" checked={valores.activo} onChange={cambiar} className="h-4 w-4 accent-primario" /> Visible para los clientes</label>
      </div>
      {error && <p role="alert" className={`${CAJA_ERROR} mt-4`}>{error}</p>}
      <div className="mt-5 flex gap-3">
        <button type="submit" disabled={guardando} className="boton-tinta px-6 py-2.5 text-sm font-semibold">{guardando ? "Guardando…" : elemento ? "Guardar cambios" : "Crear"}</button>
        {elemento && <button type="button" onClick={alCancelar} className={BOTON_VIDRIO}>Cancelar</button>}
      </div>
    </form>
  );
}

function PestanaDeElementos({ tipo, ciudades, avisar }) {
  const carga = useCarga(`/${tipo}`);
  const [editando, setEditando] = useState(null);
  const [reinicio, setReinicio] = useState(0);
  const [filtro, setFiltro] = useState("");
  const esHotel = tipo === "hoteles";
  const lista = (carga.datos ?? []).filter((item) => !filtro || `${item.nombre} ${item.ciudad} ${item.pais}`.toLowerCase().includes(filtro.toLowerCase()));

  const desactivar = async (item) => {
    try {
      await solicitar(`/${tipo}/${item.id}`, { method: "DELETE" });
      avisar(`${item.nombre} desactivado.`);
      carga.recargar();
    } catch (error) {
      avisar(error.message, "error");
    }
  };

  return (
    <Disposicion
      titulo={esHotel ? "Hoteles" : "Excursiones"}
      lista={
        <>
          <input type="search" value={filtro} onChange={(evento) => setFiltro(evento.target.value)} placeholder="Filtrar por nombre o ciudad" aria-label="Filtrar" className={CAMPO} />
          <Aviso mensaje={carga.error} tipo="error" />
          {carga.datos === null && <p className="text-sm text-texto-suave">Cargando…</p>}
          {lista.map((item) => (
            <article key={item.id} className="vidrio-sutil flex flex-wrap items-center justify-between gap-3 rounded-2xl p-4">
              <div>
                <p className="font-semibold text-texto">{item.nombre} <Insignia activo={item.activo} /></p>
                <p className="text-xs text-texto-suave">
                  {item.ciudad}, {item.pais} · {esHotel ? `${"★".repeat(item.estrellas)} · ${moneda(item.precioNoche)} / noche` : `${item.duracionHoras} h · ${moneda(item.precio)} / persona`}
                </p>
              </div>
              <div className="flex gap-2">
                <button type="button" onClick={() => setEditando(item)} className={BOTON_VIDRIO}>Modificar</button>
                {item.activo && <button type="button" onClick={() => desactivar(item)} className="px-3 py-2 text-sm font-medium text-red-700 underline">Desactivar</button>}
              </div>
            </article>
          ))}
        </>
      }
      formulario={
        <FormularioDeElemento
          key={`${tipo}-${editando?.id ?? "nuevo"}-${reinicio}`}
          tipo={tipo}
          elemento={editando}
          ciudades={ciudades}
          alCancelar={() => setEditando(null)}
          alGuardar={(mensaje) => {
            setEditando(null);
            setReinicio((actual) => actual + 1);
            avisar(mensaje);
            carga.recargar();
          }}
        />
      }
    />
  );
}

// ---------------------------------------------------------------------------------------------
// Paquetes
// ---------------------------------------------------------------------------------------------

function FormularioDePaquete({ paquete, destinos, hoteles, excursiones, vuelos, alGuardar, alCancelar }) {
  const [valores, setValores] = useState(() =>
    paquete
      ? { nombre: paquete.nombre, destinoId: String(paquete.destinoId), vueloId: String(paquete.vueloId), vueloRegresoId: paquete.vueloRegresoId ? String(paquete.vueloRegresoId) : "", hotelId: String(paquete.hotelId), excursionIds: paquete.excursiones.map((e) => e.id), noches: String(paquete.noches), precioBase: String(paquete.precioBase), activo: paquete.activo }
      : { nombre: "", destinoId: "", vueloId: "", vueloRegresoId: "", hotelId: "", excursionIds: [], noches: "5", precioBase: "", activo: true },
  );
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const destino = destinos.find((item) => String(item.id) === valores.destinoId);
  const ahora = new Date().toISOString().slice(0, 19);

  // Todo se filtra por la ciudad del destino: es la misma regla que aplica el servidor.
  const idas = destino ? vuelos.filter((v) => v.destinoId === destino.ciudadId && v.estado === "programado" && v.activo && (v.fechaSalida > ahora || String(v.id) === valores.vueloId)) : [];
  const ida = idas.find((v) => String(v.id) === valores.vueloId);
  const regresos = ida ? vuelos.filter((v) => v.origenId === destino.ciudadId && v.destinoId === ida.origenId && v.fechaSalida > ida.fechaLlegada && v.activo && v.estado === "programado") : [];
  const regreso = regresos.find((v) => String(v.id) === valores.vueloRegresoId);
  const hotelesDelDestino = destino ? hoteles.filter((h) => h.ciudadId === destino.ciudadId && (h.activo || String(h.id) === valores.hotelId)) : [];
  const excursionesDelDestino = destino ? excursiones.filter((e) => e.ciudadId === destino.ciudadId && (e.activo || valores.excursionIds.includes(e.id))) : [];
  const nochesDelPaquete = regreso ? nochesEntre(ida.fechaSalida, regreso.fechaSalida) : Number(valores.noches);

  const cambiar = (evento) => {
    const { name, value, type, checked } = evento.target;
    setValores((actual) => {
      const siguiente = { ...actual, [name]: type === "checkbox" ? checked : value };
      // Al cambiar de destino se descarta lo que ya no le corresponde.
      if (name === "destinoId") Object.assign(siguiente, { vueloId: "", vueloRegresoId: "", hotelId: "", excursionIds: [] });
      if (name === "vueloId") siguiente.vueloRegresoId = "";
      return siguiente;
    });
  };
  const alternarExcursion = (id) => setValores((actual) => ({ ...actual, excursionIds: actual.excursionIds.includes(id) ? actual.excursionIds.filter((item) => item !== id) : [...actual.excursionIds, id] }));

  const guardar = async (evento) => {
    evento.preventDefault();
    setGuardando(true);
    setError("");
    const cuerpo = {
      nombre: valores.nombre, destinoId: Number(valores.destinoId), vueloId: Number(valores.vueloId),
      vueloRegresoId: valores.vueloRegresoId ? Number(valores.vueloRegresoId) : null, hotelId: Number(valores.hotelId),
      excursionIds: valores.excursionIds, noches: valores.vueloRegresoId ? null : Number(valores.noches),
      precioBase: Number(valores.precioBase), activo: valores.activo,
    };
    try {
      await solicitar(paquete ? `/paquetes/${paquete.id}` : "/paquetes", { method: paquete ? "PUT" : "POST", body: JSON.stringify(cuerpo) });
      alGuardar(paquete ? "Paquete actualizado." : "Paquete publicado.");
    } catch (requestError) {
      setError(requestError.message);
      setGuardando(false);
    }
  };

  const formatoVuelo = (v) => `${v.numeroVuelo} · ${fecha(v.fechaSalida, { day: "numeric", month: "short", year: "numeric" })} · ${v.plazasLibres} libres`;
  return (
    <form onSubmit={guardar} className="vidrio rounded-3xl p-6">
      <h2 className="text-2xl text-primario">{paquete ? "Modificar paquete" : "Publicar paquete"}</h2>
      <p className="mt-1 text-sm text-texto-suave">Une un vuelo de ida, uno de regreso, un hotel y excursiones a un precio cerrado por pasajero.</p>
      <div className="mt-4 grid gap-4">
        <label className="text-sm font-medium text-texto">Nombre <span className="text-acento">*</span><input name="nombre" required minLength={3} maxLength={140} value={valores.nombre} onChange={cambiar} className={`${CAMPO} mt-1.5`} /></label>
        <label className="text-sm font-medium text-texto">Destino <span className="text-acento">*</span>
          <select name="destinoId" required value={valores.destinoId} onChange={cambiar} className={`${CAMPO} mt-1.5`}><option value="">Selecciona</option>{destinos.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select>
        </label>
        <label className="text-sm font-medium text-texto">Vuelo de ida <span className="text-acento">*</span>
          <select name="vueloId" required disabled={!destino} value={valores.vueloId} onChange={cambiar} className={`${CAMPO} mt-1.5`}>
            <option value="">{destino ? (idas.length ? "Selecciona" : "No hay vuelos de ida programados a este destino") : "Elige primero el destino"}</option>
            {idas.map((v) => <option key={v.id} value={v.id}>{formatoVuelo(v)}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium text-texto">Vuelo de regreso
          <select name="vueloRegresoId" disabled={!ida} value={valores.vueloRegresoId} onChange={cambiar} className={`${CAMPO} mt-1.5`}>
            <option value="">{ida ? "Sin vuelo de regreso (indico las noches)" : "Elige primero la ida"}</option>
            {regresos.map((v) => <option key={v.id} value={v.id}>{formatoVuelo(v)} · {nochesEntre(ida.fechaSalida, v.fechaSalida)} noches</option>)}
          </select>
        </label>
        {!valores.vueloRegresoId && (
          <label className="text-sm font-medium text-texto">Noches del paquete <span className="text-acento">*</span><input name="noches" type="number" min="1" max="90" required value={valores.noches} onChange={cambiar} className={`${CAMPO} mt-1.5`} /></label>
        )}
        <label className="text-sm font-medium text-texto">Hotel <span className="text-acento">*</span>
          <select name="hotelId" required disabled={!destino} value={valores.hotelId} onChange={cambiar} className={`${CAMPO} mt-1.5`}><option value="">Selecciona</option>{hotelesDelDestino.map((h) => <option key={h.id} value={h.id}>{h.nombre} {"★".repeat(h.estrellas)}</option>)}</select>
        </label>
        <fieldset>
          <legend className="text-sm font-medium text-texto">Excursiones incluidas</legend>
          <div className="mt-1.5 grid gap-1.5">
            {excursionesDelDestino.map((e) => (
              <label key={e.id} className="flex items-center gap-2 text-sm text-texto"><input type="checkbox" checked={valores.excursionIds.includes(e.id)} onChange={() => alternarExcursion(e.id)} className="h-4 w-4 accent-primario" />{e.nombre} <span className="text-xs text-texto-suave">· {e.duracionHoras} h</span></label>
            ))}
            {destino && excursionesDelDestino.length === 0 && <p className="text-xs text-texto-suave">Este destino no tiene excursiones activas.</p>}
          </div>
        </fieldset>
        <label className="text-sm font-medium text-texto">Precio por pasajero <span className="text-acento">*</span><input name="precioBase" type="number" min="0" step="1000" required value={valores.precioBase} onChange={cambiar} className={`${CAMPO} mt-1.5`} /></label>
        <label className="flex items-center gap-2 text-sm font-medium text-texto"><input type="checkbox" name="activo" checked={valores.activo} onChange={cambiar} className="h-4 w-4 accent-primario" /> Publicado (visible para los clientes)</label>
        {ida && <p className="vidrio-sutil rounded-xl px-4 py-3 text-xs text-texto-suave">Saldrá el {fecha(ida.fechaSalida)} y regresará el {fecha(regreso ? regreso.fechaSalida : sumarDias(ida.fechaSalida, nochesDelPaquete))} ({nochesDelPaquete} noches).</p>}
      </div>
      {error && <p role="alert" className={`${CAJA_ERROR} mt-4`}>{error}</p>}
      <div className="mt-5 flex gap-3">
        <button type="submit" disabled={guardando} className="boton-tinta px-6 py-2.5 text-sm font-semibold">{guardando ? "Guardando…" : paquete ? "Guardar cambios" : "Publicar paquete"}</button>
        {paquete && <button type="button" onClick={alCancelar} className={BOTON_VIDRIO}>Cancelar</button>}
      </div>
    </form>
  );
}

function PestanaDePaquetes({ avisar }) {
  const paquetes = useCarga("/paquetes");
  const destinos = useCarga("/catalogos/destinos");
  const hoteles = useCarga("/hoteles");
  const excursiones = useCarga("/excursiones");
  const vuelos = useCarga("/vuelos");
  const [editando, setEditando] = useState(null);
  const [reinicio, setReinicio] = useState(0);

  const desactivar = async (item) => {
    try {
      await solicitar(`/paquetes/${item.id}`, { method: "DELETE" });
      avisar(`${item.nombre} desactivado.`);
      paquetes.recargar();
    } catch (error) {
      avisar(error.message, "error");
    }
  };

  return (
    <Disposicion
      titulo="Paquetes publicados"
      lista={
        <>
          <Aviso mensaje={paquetes.error} tipo="error" />
          {paquetes.datos === null && <p className="text-sm text-texto-suave">Cargando…</p>}
          {(paquetes.datos ?? []).map((item) => (
            <article key={item.id} className="vidrio-sutil rounded-2xl p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-semibold text-texto">{item.nombre}</p>
                  <p className="text-xs text-texto-suave">{item.destino} · {fecha(item.fechaSalida, { day: "numeric", month: "short" })} → {fecha(item.fechaRegreso, { day: "numeric", month: "short", year: "numeric" })} · {item.noches} noches</p>
                  <p className="mt-1 text-xs text-texto-suave">✈ {item.vuelo.numeroVuelo}{item.vueloRegreso ? ` / ${item.vueloRegreso.numeroVuelo}` : " (sin regreso)"} · ⌂ {item.hotel.nombre} · ◈ {item.excursiones.length} excursiones · {item.plazasLibres} plazas libres</p>
                </div>
                <div className="text-right">
                  <p className="font-display text-xl text-primario">{moneda(item.precioBase)}</p>
                  <p className="text-xs text-texto-suave">por pasajero</p>
                </div>
              </div>
              <div className="mt-3 flex gap-2">
                <button type="button" onClick={() => setEditando(item)} className={BOTON_VIDRIO}>Modificar</button>
                <button type="button" onClick={() => desactivar(item)} className="px-3 py-2 text-sm font-medium text-red-700 underline">Desactivar</button>
              </div>
            </article>
          ))}
        </>
      }
      formulario={
        <FormularioDePaquete
          key={`${editando?.id ?? "nuevo"}-${reinicio}`}
          paquete={editando}
          destinos={destinos.datos ?? []}
          hoteles={hoteles.datos ?? []}
          excursiones={excursiones.datos ?? []}
          vuelos={vuelos.datos ?? []}
          alCancelar={() => setEditando(null)}
          alGuardar={(mensaje) => {
            setEditando(null);
            setReinicio((actual) => actual + 1);
            avisar(mensaje);
            paquetes.recargar();
          }}
        />
      }
    />
  );
}

// ---------------------------------------------------------------------------------------------
// Destinos: las ciudades que se venden
// ---------------------------------------------------------------------------------------------

function FormularioDeDestino({ destino, ciudades, ocupadas, alGuardar, alCancelar }) {
  const [valores, setValores] = useState(() =>
    destino
      ? { ciudadId: String(destino.ciudadId), descripcion: destino.descripcion || "", precioBase: String(destino.precioBase), activo: destino.activo }
      : { ciudadId: "", descripcion: "", precioBase: "", activo: true },
  );
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const cambiar = (evento) => {
    const { name, value, type, checked } = evento.target;
    setValores((actual) => ({ ...actual, [name]: type === "checkbox" ? checked : value }));
  };

  const guardar = async (evento) => {
    evento.preventDefault();
    setGuardando(true);
    setError("");
    const cuerpo = {
      ciudadId: Number(valores.ciudadId),
      descripcion: valores.descripcion || null,
      precioBase: Number(valores.precioBase),
      // La ilustración de los destinos de ejemplo no se edita aquí: se conserva la que ya tenían.
      imagenSlug: destino?.imagenSlug ?? null,
      activo: valores.activo,
    };
    try {
      await solicitar(destino ? `/destinos/${destino.id}` : "/destinos", { method: destino ? "PUT" : "POST", body: JSON.stringify(cuerpo) });
      alGuardar(destino ? "Cambios guardados." : "Destino creado.");
    } catch (requestError) {
      setError(requestError.message);
      setGuardando(false);
    }
  };

  const disponibles = ciudades.filter((ciudad) => !ocupadas.has(ciudad.id) || ciudad.id === destino?.ciudadId);
  return (
    <form onSubmit={guardar} className="vidrio rounded-3xl p-6">
      <h2 className="text-2xl text-primario">{destino ? "Modificar" : "Agregar"} destino</h2>
      {!destino && <p className="mt-1 text-sm text-texto-suave">Elige una ciudad que aún no sea destino (si falta, agrégala en «Lugares»). Después dale vuelos, hoteles y excursiones.</p>}
      <div className="mt-4 grid gap-4">
        <label className="text-sm font-medium text-texto">Ciudad <span className="text-acento">*</span>
          <select name="ciudadId" required value={valores.ciudadId} onChange={cambiar} className={`${CAMPO} mt-1.5`}>
            <option value="">Selecciona una ciudad</option>
            {disponibles.map((ciudad) => <option key={ciudad.id} value={ciudad.id}>{ciudad.nombre}, {ciudad.pais}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium text-texto">Tarifa aérea por pasajero <span className="text-acento">*</span>
          <input name="precioBase" type="number" required min="1000" step="1000" value={valores.precioBase} onChange={cambiar} className={`${CAMPO} mt-1.5`} />
        </label>
        <label className="text-sm font-medium text-texto">Descripción<textarea name="descripcion" rows={4} maxLength={2000} value={valores.descripcion} onChange={cambiar} className={`${CAMPO} mt-1.5 resize-y`} /></label>
        <label className="flex items-center gap-2 text-sm font-medium text-texto"><input type="checkbox" name="activo" checked={valores.activo} onChange={cambiar} className="h-4 w-4 accent-primario" /> Visible para los clientes</label>
      </div>
      {error && <p role="alert" className={`${CAJA_ERROR} mt-4`}>{error}</p>}
      <div className="mt-5 flex gap-3">
        <button type="submit" disabled={guardando} className="boton-tinta px-6 py-2.5 text-sm font-semibold">{guardando ? "Guardando…" : destino ? "Guardar cambios" : "Crear"}</button>
        {destino && <button type="button" onClick={alCancelar} className={BOTON_VIDRIO}>Cancelar</button>}
      </div>
    </form>
  );
}

function PestanaDeDestinos({ ciudades, avisar }) {
  const carga = useCarga("/destinos");
  const [editando, setEditando] = useState(null);
  const [reinicio, setReinicio] = useState(0);
  const destinos = carga.datos ?? [];

  const desactivar = async (destino) => {
    try {
      await solicitar(`/destinos/${destino.id}`, { method: "DELETE" });
      avisar(`${destino.nombre} desactivado: ya no se ofrece a los clientes.`);
      carga.recargar();
    } catch (error) {
      avisar(error.message, "error");
    }
  };

  return (
    <Disposicion
      titulo="Destinos"
      lista={
        <>
          <Aviso mensaje={carga.error} tipo="error" />
          {carga.datos === null && <p className="text-sm text-texto-suave">Cargando…</p>}
          {destinos.map((destino) => (
            <article key={destino.id} className="vidrio-sutil flex flex-wrap items-center justify-between gap-3 rounded-2xl p-4">
              <div>
                <p className="font-semibold text-texto">{destino.nombre} <Insignia activo={destino.activo} /></p>
                <p className="text-xs text-texto-suave">Desde {moneda(destino.precioBase)} por pasajero{destino.descripcion ? ` · ${destino.descripcion.slice(0, 90)}${destino.descripcion.length > 90 ? "…" : ""}` : ""}</p>
              </div>
              <div className="flex gap-2">
                <button type="button" onClick={() => setEditando(destino)} className={BOTON_VIDRIO}>Modificar</button>
                {destino.activo && <button type="button" onClick={() => desactivar(destino)} className="px-3 py-2 text-sm font-medium text-red-700 underline">Desactivar</button>}
              </div>
            </article>
          ))}
        </>
      }
      formulario={
        <FormularioDeDestino
          key={`destino-${editando?.id ?? "nuevo"}-${reinicio}`}
          destino={editando}
          ciudades={ciudades}
          ocupadas={new Set(destinos.map((destino) => destino.ciudadId))}
          alCancelar={() => setEditando(null)}
          alGuardar={(mensaje) => {
            setEditando(null);
            setReinicio((actual) => actual + 1);
            avisar(mensaje);
            carga.recargar();
          }}
        />
      }
    />
  );
}

// ---------------------------------------------------------------------------------------------
// Lugares
// ---------------------------------------------------------------------------------------------

function PestanaDeLugares({ ciudades, recargarCiudades, avisar }) {
  const [valores, setValores] = useState({ nombre: "", pais: "" });
  const [error, setError] = useState("");
  const paises = [...new Set(ciudades.map((ciudad) => ciudad.pais))];

  const crear = async (evento) => {
    evento.preventDefault();
    setError("");
    try {
      await solicitar("/ciudades", { method: "POST", body: JSON.stringify(valores) });
      avisar(`${valores.nombre} agregada.`);
      setValores({ nombre: "", pais: "" });
      recargarCiudades();
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  return (
    <Disposicion
      titulo="Ciudades"
      lista={paises.map((pais) => (
        <div key={pais} className="vidrio-sutil rounded-2xl p-4">
          <p className={ETIQUETA_MONO}>{pais}</p>
          <p className="mt-1 text-sm text-texto">{ciudades.filter((ciudad) => ciudad.pais === pais).map((ciudad) => ciudad.nombre).join(" · ")}</p>
        </div>
      ))}
      formulario={
        <form onSubmit={crear} className="vidrio rounded-3xl p-6">
          <h2 className="text-2xl text-primario">Agregar ciudad</h2>
          <p className="mt-1 text-sm text-texto-suave">Cada ciudad se escribe una sola vez: los vuelos, hoteles y excursiones la eligen de esta lista, así los nombres nunca se desincronizan.</p>
          <div className="mt-4 grid gap-4">
            <label className="text-sm font-medium text-texto">Ciudad<input required minLength={2} maxLength={80} value={valores.nombre} onChange={(evento) => setValores({ ...valores, nombre: evento.target.value })} className={`${CAMPO} mt-1.5`} /></label>
            <label className="text-sm font-medium text-texto">País<input required minLength={2} maxLength={80} list="paises-existentes" value={valores.pais} onChange={(evento) => setValores({ ...valores, pais: evento.target.value })} className={`${CAMPO} mt-1.5`} /></label>
            <datalist id="paises-existentes">{paises.map((pais) => <option key={pais} value={pais} />)}</datalist>
          </div>
          {error && <p role="alert" className={`${CAJA_ERROR} mt-4`}>{error}</p>}
          <button type="submit" className="boton-tinta mt-5 px-6 py-2.5 text-sm font-semibold">Agregar</button>
        </form>
      }
    />
  );
}

function CatalogoPanel() {
  const [pestana, setPestana] = useState("paquetes");
  const [aviso, setAviso] = useState({ mensaje: "", tipo: "info" });
  const ciudades = useCarga("/ciudades");
  const avisar = (mensaje, tipo = "info") => setAviso({ mensaje, tipo });

  return (
    <div className="mx-auto w-[96%] max-w-350 flex-1 py-8 sm:py-12">
      <EncabezadoDePanel etiqueta="Administración" titulo="Catálogo" descripcion="Paquetes, hoteles, excursiones y lugares. Cada pieza pertenece a una ciudad, y solo se combinan piezas de la misma ciudad." />
      <div role="tablist" aria-label="Catálogo" className="mt-6 flex flex-wrap gap-2">
        {PESTANAS.map(([clave, texto]) => (
          <button key={clave} type="button" role="tab" aria-selected={pestana === clave} onClick={() => { setPestana(clave); avisar(""); }} className={`rounded-full px-5 py-2.5 text-sm font-semibold transition ${pestana === clave ? "boton-tinta" : "vidrio text-texto-suave hover:text-primario"}`}>{texto}</button>
        ))}
      </div>
      <Aviso mensaje={aviso.mensaje} tipo={aviso.tipo} alCerrar={() => avisar("")} />

      {pestana === "paquetes" && <PestanaDePaquetes avisar={avisar} />}
      {pestana === "hoteles" && <PestanaDeElementos tipo="hoteles" ciudades={ciudades.datos ?? []} avisar={avisar} />}
      {pestana === "excursiones" && <PestanaDeElementos tipo="excursiones" ciudades={ciudades.datos ?? []} avisar={avisar} />}
      {pestana === "destinos" && <PestanaDeDestinos ciudades={ciudades.datos ?? []} avisar={avisar} />}
      {pestana === "lugares" && <PestanaDeLugares ciudades={ciudades.datos ?? []} recargarCiudades={ciudades.recargar} avisar={avisar} />}
    </div>
  );
}

export default CatalogoPanel;
