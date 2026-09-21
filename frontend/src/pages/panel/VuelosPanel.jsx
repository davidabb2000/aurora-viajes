import { useState } from "react";
import { BOTON_VIDRIO, CAJA_ERROR, CAMPO, ETIQUETA_MONO } from "../../components/reserva/estilos";
import { solicitar } from "../../utils/api";
import { fechaHora } from "../../utils/formato";
import { useCarga } from "../../utils/useCarga";
import { Aviso, EncabezadoDePanel, Paginacion } from "./Encabezado";

const ESTADOS = [
  ["programado", "Programado"],
  ["abordando", "Abordando"],
  ["en_vuelo", "En vuelo"],
  ["aterrizado", "Aterrizado"],
  ["cancelado", "Cancelado"],
];

const VACIO = {
  numeroVuelo: "", aerolineaId: "", modeloAvionId: "", origenId: "", destinoId: "", fechaSalida: "", fechaLlegada: "",
  capacidadMaxima: "", puerta: "", terminal: "", estado: "programado", activo: true,
};

function desdeVuelo(vuelo) {
  return {
    numeroVuelo: vuelo.numeroVuelo, aerolineaId: String(vuelo.aerolineaId), modeloAvionId: String(vuelo.modeloAvionId),
    origenId: String(vuelo.origenId), destinoId: String(vuelo.destinoId), fechaSalida: vuelo.fechaSalida.slice(0, 16),
    fechaLlegada: vuelo.fechaLlegada.slice(0, 16), capacidadMaxima: String(vuelo.capacidadMaxima), puerta: vuelo.puerta || "",
    terminal: vuelo.terminal || "", estado: vuelo.estado, activo: vuelo.activo,
  };
}

function Selector({ etiqueta, name, value, onChange, children, requerido = true }) {
  return (
    <label className="text-sm font-medium text-texto">
      {etiqueta}{requerido && <span className="text-acento"> *</span>}
      <select name={name} value={value} onChange={onChange} required={requerido} className={`${CAMPO} mt-1.5`}>{children}</select>
    </label>
  );
}

/** Formulario de alta y edición. Aerolíneas, modelos y ciudades salen de catálogos: no se escriben a mano. */
function FormularioDeVuelo({ vuelo, catalogos, alGuardar, alCancelar }) {
  const [valores, setValores] = useState(() => (vuelo ? desdeVuelo(vuelo) : VACIO));
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const modelo = catalogos.modelos.find((item) => String(item.id) === valores.modeloAvionId);

  const cambiar = (evento) => {
    const { name, value, type, checked } = evento.target;
    setValores((actual) => ({ ...actual, [name]: type === "checkbox" ? checked : value }));
  };

  const guardar = async (evento) => {
    evento.preventDefault();
    setError("");
    if (valores.origenId === valores.destinoId) return setError("El origen y el destino no pueden ser la misma ciudad.");
    if (valores.fechaLlegada <= valores.fechaSalida) return setError("La llegada debe ser posterior a la salida.");
    setGuardando(true);
    try {
      const cuerpo = {
        numeroVuelo: valores.numeroVuelo.trim() || null,
        aerolineaId: Number(valores.aerolineaId), modeloAvionId: Number(valores.modeloAvionId),
        origenId: Number(valores.origenId), destinoId: Number(valores.destinoId),
        fechaSalida: valores.fechaSalida, fechaLlegada: valores.fechaLlegada,
        capacidadMaxima: valores.capacidadMaxima ? Number(valores.capacidadMaxima) : null,
        puerta: valores.puerta.trim() || null, terminal: valores.terminal.trim() || null,
        estado: valores.estado, activo: valores.activo,
      };
      const guardado = await solicitar(vuelo ? `/vuelos/${vuelo.id}` : "/vuelos", { method: vuelo ? "PUT" : "POST", body: JSON.stringify(cuerpo) });
      alGuardar(guardado, vuelo ? "Vuelo actualizado." : "Vuelo creado.");
    } catch (requestError) {
      setError(requestError.message);
      setGuardando(false);
    }
  };

  const ciudades = catalogos.ciudades;
  return (
    <form onSubmit={guardar} className="vidrio mt-8 rounded-3xl p-6 sm:p-8">
      <h2 className="text-2xl text-primario">{vuelo ? `Modificar el vuelo ${vuelo.numeroVuelo}` : "Agregar vuelo"}</h2>
      <p className="mt-1 text-sm text-texto-suave">Las horas son las del aeropuerto de cada ciudad. Si dejas el número vacío se asigna uno automáticamente.</p>
      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <label className="text-sm font-medium text-texto">Número de vuelo<input name="numeroVuelo" value={valores.numeroVuelo} onChange={cambiar} maxLength={20} placeholder="AUR301 (opcional)" className={`${CAMPO} mt-1.5`} /></label>
        <Selector etiqueta="Aerolínea" name="aerolineaId" value={valores.aerolineaId} onChange={cambiar}>
          <option value="">Selecciona</option>
          {catalogos.aerolineas.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}
        </Selector>
        <Selector etiqueta="Modelo de avión" name="modeloAvionId" value={valores.modeloAvionId} onChange={cambiar}>
          <option value="">Selecciona</option>
          {catalogos.modelos.map((item) => <option key={item.id} value={item.id}>{item.nombre} · {item.capacidad} plazas</option>)}
        </Selector>
        <Selector etiqueta="Origen" name="origenId" value={valores.origenId} onChange={cambiar}>
          <option value="">Selecciona</option>
          {ciudades.map((item) => <option key={item.id} value={item.id}>{item.nombre}, {item.pais}</option>)}
        </Selector>
        <Selector etiqueta="Destino" name="destinoId" value={valores.destinoId} onChange={cambiar}>
          <option value="">Selecciona</option>
          {ciudades.filter((item) => String(item.id) !== valores.origenId).map((item) => <option key={item.id} value={item.id}>{item.nombre}, {item.pais}</option>)}
        </Selector>
        <label className="text-sm font-medium text-texto">
          Plazas a la venta
          <input name="capacidadMaxima" type="number" min="1" max={modelo?.capacidad || 1000} value={valores.capacidadMaxima} onChange={cambiar} placeholder={modelo ? `${modelo.capacidad} (todas)` : "Según el avión"} className={`${CAMPO} mt-1.5`} />
          <span className="mt-1 block text-xs font-normal text-texto-suave">Como máximo las del avión; menos si la agencia solo tiene un cupo.</span>
        </label>
        <label className="text-sm font-medium text-texto">Salida <span className="text-acento">*</span><input required type="datetime-local" name="fechaSalida" value={valores.fechaSalida} onChange={cambiar} className={`${CAMPO} mt-1.5`} /></label>
        <label className="text-sm font-medium text-texto">Llegada <span className="text-acento">*</span><input required type="datetime-local" name="fechaLlegada" value={valores.fechaLlegada} min={valores.fechaSalida} onChange={cambiar} className={`${CAMPO} mt-1.5`} /></label>
        <Selector etiqueta="Estado" name="estado" value={valores.estado} onChange={cambiar}>
          {ESTADOS.map(([valor, texto]) => <option key={valor} value={valor}>{texto}</option>)}
        </Selector>
        <label className="text-sm font-medium text-texto">Puerta<input name="puerta" value={valores.puerta} onChange={cambiar} maxLength={10} placeholder="A12" className={`${CAMPO} mt-1.5`} /></label>
        <label className="text-sm font-medium text-texto">Terminal<input name="terminal" value={valores.terminal} onChange={cambiar} maxLength={20} placeholder="1" className={`${CAMPO} mt-1.5`} /></label>
        <label className="flex items-center gap-2 self-end pb-2.5 text-sm font-medium text-texto">
          <input type="checkbox" name="activo" checked={valores.activo} onChange={cambiar} className="h-4 w-4 accent-primario" /> Vuelo activo (visible para los clientes)
        </label>
      </div>
      {error && <p role="alert" className={`${CAJA_ERROR} mt-5`}>{error}</p>}
      <div className="mt-6 flex flex-wrap gap-3">
        <button type="submit" disabled={guardando} className="boton-tinta px-6 py-2.5 text-sm font-semibold">{guardando ? "Guardando…" : vuelo ? "Guardar cambios" : "Crear vuelo"}</button>
        {vuelo && <button type="button" onClick={alCancelar} className={BOTON_VIDRIO}>Cancelar</button>}
      </div>
    </form>
  );
}

function VuelosPanel({ esAdmin }) {
  const [verPasados, setVerPasados] = useState(false);
  const [busqueda, setBusqueda] = useState("");
  const [pagina, setPagina] = useState(1);
  const [editando, setEditando] = useState(null);
  const [confirmando, setConfirmando] = useState(null);
  const [reinicio, setReinicio] = useState(0);
  const [aviso, setAviso] = useState({ mensaje: "", tipo: "info" });
  const vuelos = useCarga(`/vuelos?pasados=${verPasados}`);
  const aerolineas = useCarga("/aerolineas");
  const modelos = useCarga("/modelos-avion");
  const ciudades = useCarga("/ciudades");

  const catalogos = { aerolineas: aerolineas.datos ?? [], modelos: modelos.datos ?? [], ciudades: ciudades.datos ?? [] };
  const texto = busqueda.trim().toLowerCase();
  const filtrados = (vuelos.datos ?? []).filter((vuelo) => !texto || [vuelo.numeroVuelo, vuelo.aerolinea, vuelo.origen, vuelo.destino, vuelo.estado, vuelo.fechaSalida.slice(0, 10)].join(" ").toLowerCase().includes(texto));
  const visibles = filtrados.slice((pagina - 1) * 10, pagina * 10);

  const eliminar = async (vuelo) => {
    setConfirmando(null);
    try {
      await solicitar(`/vuelos/${vuelo.id}`, { method: "DELETE" });
      setAviso({ mensaje: `Vuelo ${vuelo.numeroVuelo} eliminado.`, tipo: "info" });
      vuelos.recargar();
    } catch (error) {
      setAviso({ mensaje: error.message, tipo: "error" });
    }
  };

  return (
    <div className="mx-auto w-[96%] max-w-350 flex-1 py-8 sm:py-12">
      <EncabezadoDePanel etiqueta="Operaciones" titulo="Vuelos" descripcion="Salidas programadas de ida y de regreso, con las plazas vendidas y libres de cada una.">
        <label className="vidrio flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium text-primario">
          <input type="checkbox" checked={verPasados} onChange={(evento) => { setVerPasados(evento.target.checked); setPagina(1); }} className="h-4 w-4 accent-primario" /> Ver también los que ya salieron
        </label>
      </EncabezadoDePanel>

      <section className="vidrio mt-8 rounded-3xl p-5 sm:p-6">
        <input type="search" value={busqueda} onChange={(evento) => { setBusqueda(evento.target.value); setPagina(1); }} placeholder="Buscar por número, aerolínea, ruta, estado o fecha (2026-10-05)" aria-label="Buscar vuelos" className={CAMPO} />
        <Aviso mensaje={aviso.mensaje} tipo={aviso.tipo} alCerrar={() => setAviso({ mensaje: "", tipo: "info" })} />
        <Aviso mensaje={vuelos.error} tipo="error" />
        <div className="mt-5 space-y-3">
          {vuelos.datos === null && vuelos.cargando && <p className="text-sm text-texto-suave">Cargando vuelos…</p>}
          {vuelos.datos !== null && filtrados.length === 0 && <p className="text-sm text-texto-suave">No hay vuelos que coincidan.</p>}
          {visibles.map((vuelo) => {
            const ocupadas = vuelo.plazasOcupadas ?? 0;
            const porcentaje = Math.min(100, Math.round((ocupadas / vuelo.capacidadMaxima) * 100));
            return (
              <article key={vuelo.id} className="vidrio-sutil rounded-2xl p-4">
                <div className="grid gap-4 text-sm md:grid-cols-[1.2fr_1.3fr_1fr_auto] md:items-center">
                  <div>
                    <p className={ETIQUETA_MONO}>{vuelo.aerolinea} · {vuelo.avion}</p>
                    <p className="mt-1 font-display text-2xl text-primario">{vuelo.numeroVuelo}</p>
                    <p className="text-xs text-texto-suave">Puerta {vuelo.puerta || "—"} · Terminal {vuelo.terminal || "—"}</p>
                  </div>
                  <div>
                    <p className="font-semibold text-texto">{vuelo.origen} → {vuelo.destino}</p>
                    <p className="text-xs text-texto-suave">{fechaHora(vuelo.fechaSalida)} → {fechaHora(vuelo.fechaLlegada)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-texto-suave">Plazas: <strong className="text-texto">{ocupadas}</strong> vendidas de {vuelo.capacidadMaxima} · <strong className="text-texto">{vuelo.plazasLibres}</strong> libres</p>
                    <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-primario/10" aria-hidden="true"><div className={`h-full rounded-full ${porcentaje >= 90 ? "bg-acento" : "bg-primario"}`} style={{ width: `${porcentaje}%` }} /></div>
                    <p className="mt-2 text-xs"><span className={`rounded-full px-2.5 py-0.5 font-semibold capitalize ${vuelo.estado === "cancelado" ? "bg-red-100 text-red-700" : "bg-primario/8 text-primario"}`}>{vuelo.estado.replace("_", " ")}</span>{!vuelo.activo && <span className="ml-2 rounded-full bg-arena px-2.5 py-0.5 font-semibold text-texto-suave">Inactivo</span>}</p>
                  </div>
                  {esAdmin && (
                    <div className="flex flex-wrap gap-2 md:justify-end">
                      <button type="button" onClick={() => { setEditando(vuelo); window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }); }} className={BOTON_VIDRIO}>Modificar</button>
                      {confirmando === vuelo.id ? (
                        <span className="flex items-center gap-2 text-sm text-red-700">¿Eliminar? <button type="button" onClick={() => eliminar(vuelo)} className="font-semibold underline">Sí</button> <button type="button" onClick={() => setConfirmando(null)} className="font-semibold">No</button></span>
                      ) : (
                        <button type="button" onClick={() => setConfirmando(vuelo.id)} className="px-3 py-2 text-sm font-medium text-red-700 underline">Eliminar</button>
                      )}
                    </div>
                  )}
                </div>
              </article>
            );
          })}
        </div>
        <Paginacion pagina={pagina} total={filtrados.length} alCambiar={setPagina} />
      </section>

      {esAdmin && (
        <FormularioDeVuelo
          key={`${editando?.id ?? "nuevo"}-${reinicio}`}
          vuelo={editando}
          catalogos={catalogos}
          alCancelar={() => setEditando(null)}
          alGuardar={(guardado, mensaje) => {
            setEditando(null);
            setReinicio((actual) => actual + 1);
            setAviso({ mensaje: guardado.advertencia ? `${mensaje} ${guardado.advertencia}` : mensaje, tipo: guardado.advertencia ? "error" : "info" });
            vuelos.recargar();
          }}
        />
      )}
    </div>
  );
}

export default VuelosPanel;
