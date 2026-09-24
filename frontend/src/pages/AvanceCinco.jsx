import { useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/useAuth";
import { solicitar } from "../utils/api";
import { useCarga } from "../utils/useCarga";

const API_URL = import.meta.env.VITE_API_URL || "/api";
const dinero = (valor) => `$${Number(valor || 0).toLocaleString("es-CO")}`;
const estadoTexto = (estado) => estado?.replace("_", " ") || "pendiente";
// El personal ve además la analítica de ventas; el cliente, solo lo suyo (el servidor filtra cada dato por su cuenta).
const PESTANAS_PERSONAL = [["resumen", "Resumen"], ["reservas vendidas", "Reservas vendidas"], ["facturas", "Facturas"], ["pqr", "PQR"], ["chatbot", "Chatbot"]];
const PESTANAS_CLIENTE = [["facturas", "Mis facturas"], ["pqr", "Mis PQR"], ["chatbot", "Chatbot"]];
const TIPOS_PQR = { peticion: "Petición", queja: "Queja", reclamo: "Reclamo" };
const CAMPO = "mt-1 w-full rounded-xl border border-primario/12 bg-white/70 px-3 py-2 text-sm text-texto shadow-sm shadow-primario/5 outline-none backdrop-blur-sm transition focus:border-primario-suave focus:bg-white/90 focus:ring-3 focus:ring-primario-suave/20";
const BOTON_VIDRIO = "vidrio rounded-xl px-4 py-2 text-sm font-semibold text-primario transition hover:-translate-y-0.5 hover:bg-white/85";

function Card({ titulo, valor, detalle, variacion }) {
  const sube = typeof variacion === "number" && variacion >= 0;
  return (
    <article className="vidrio vidrio-interactivo rounded-2xl p-5">
      <p className="text-xs font-semibold uppercase tracking-widest text-texto-suave">{titulo}</p>
      <p className="mt-3 font-display text-3xl font-bold text-primario">{valor}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {detalle && <span className="text-xs text-texto-suave">{detalle}</span>}
        {typeof variacion === "number" && (
          <span
            className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
              sube ? "bg-primario/10 text-primario" : "bg-acento/15 text-brillo"
            }`}
          >
            {sube ? "▲" : "▼"} {Math.abs(variacion)}% vs. periodo anterior
          </span>
        )}
      </div>
    </article>
  );
}

function DescargarReportes({ headers, filtros }) {
  const [estado, setEstado] = useState("");
  const descargar = async (formato) => {
    setEstado("");
    const parametros = new URLSearchParams({ formato });
    if (filtros?.desde) parametros.set("desde", filtros.desde);
    if (filtros?.hasta) parametros.set("hasta", filtros.hasta);
    try {
      const respuesta = await fetch(`${API_URL}/reportes/ventas?${parametros}`, { headers });
      if (!respuesta.ok) throw new Error("No se pudo generar el reporte.");
      const archivo = await respuesta.blob();
      const enlace = document.createElement("a");
      enlace.href = URL.createObjectURL(archivo);
      enlace.download = `reporte-reservas.${formato === "xlsx" ? "xlsx" : "pdf"}`;
      enlace.click();
      URL.revokeObjectURL(enlace.href);
    } catch (error) {
      setEstado(error.message);
    }
  };
  return (
    <div className="flex flex-col items-end gap-2">
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => descargar("pdf")} className={BOTON_VIDRIO}>▤ Reporte PDF</button>
        <button type="button" onClick={() => descargar("xlsx")} className={BOTON_VIDRIO}>▦ Reporte Excel</button>
      </div>
      <p className="text-xs text-texto-suave">
        {estado || (filtros?.desde || filtros?.hasta ? "Usa el rango de fechas filtrado." : "Sin rango: se descarga el día de hoy.")}
      </p>
    </div>
  );
}

function DescargarFactura({ id, headers }) {
  const descargar = async () => {
    const respuesta = await fetch(`${API_URL}/facturas/${id}/pdf`, { headers });
    if (!respuesta.ok) throw new Error("No se pudo descargar la factura.");
    const archivo = await respuesta.blob();
    const enlace = document.createElement("a");
    enlace.href = URL.createObjectURL(archivo);
    enlace.download = `factura-${id}.pdf`;
    enlace.click();
    URL.revokeObjectURL(enlace.href);
  };
  return <button type="button" onClick={descargar} className={BOTON_VIDRIO}>▣ Factura PDF</button>;
}

function Graficos({ datos }) {
  const maximo = Math.max(...datos.map((item) => item.total), 1);
  const puntos = datos.map((item, indice) => `${datos.length === 1 ? 300 : 20 + (indice / (datos.length - 1)) * 560},${160 - (item.total / maximo) * 135}`).join(" ");
  const area = datos.length ? `20,165 ${puntos} ${datos.length === 1 ? 300 : 580},165` : "";
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <article className="vidrio rounded-3xl p-6">
        <h2 className="font-display text-xl font-bold text-primario">Reservas vendidas por periodo</h2>
        <p className="mt-1 text-xs text-texto-suave">Máximo del periodo: {dinero(maximo)}</p>
        <div className="mt-6 flex h-44 items-end gap-2 rounded-xl border-b border-l border-primario/12 bg-white/30 px-2 pt-2">
          {datos.map((item) => (
            <div key={item.fecha} className="group flex h-full flex-1 items-end" title={`${item.fecha}: ${dinero(item.total)}`}>
              <div
                className="w-full rounded-t-md bg-primario transition group-hover:bg-acento"
                style={{ height: `${Math.max((item.total / maximo) * 100, 3)}%` }}
              />
            </div>
          ))}
          {datos.length === 0 && <p className="self-center text-sm text-texto-suave">Sin datos en el periodo.</p>}
        </div>
        <div className="mt-2 flex justify-between text-[11px] text-texto-suave">
          <span>{datos[0]?.fecha || ""}</span>
          <span>{datos[datos.length - 1]?.fecha || ""}</span>
        </div>
      </article>

      <article className="vidrio rounded-3xl p-6">
        <h2 className="font-display text-xl font-bold text-primario">Tendencia de facturación</h2>
        <p className="mt-1 text-xs text-texto-suave">{datos.length} punto(s) en la serie</p>
        <svg viewBox="0 0 600 180" className="mt-6 h-44 w-full" role="img" aria-label="Tendencia de facturación">
          <defs>
            <linearGradient id="relleno-tendencia" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-primario)" stopOpacity="0.28" />
              <stop offset="100%" stopColor="var(--color-primario)" stopOpacity="0" />
            </linearGradient>
            <linearGradient id="linea-tendencia" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="var(--color-primario)" />
              <stop offset="100%" stopColor="var(--color-acento)" />
            </linearGradient>
          </defs>
          {area && <polygon fill="url(#relleno-tendencia)" points={area} />}
          <polyline fill="none" stroke="url(#linea-tendencia)" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" points={puntos} />
          {datos.map((item, indice) => (
            <circle
              key={item.fecha}
              cx={datos.length === 1 ? 300 : 20 + (indice / (datos.length - 1)) * 560}
              cy={160 - (item.total / maximo) * 135}
              r="4"
              fill="var(--color-superficie)"
              stroke="var(--color-primario)"
              strokeWidth="2.5"
            >
              <title>{`${item.fecha}: ${dinero(item.total)}`}</title>
            </circle>
          ))}
        </svg>
      </article>
    </div>
  );
}

function ComposicionIngresos({ porConcepto }) {
  const conceptos = [
    ["Paquetes", porConcepto.paquete, "bg-oro"],
    ["Vuelos", porConcepto.vuelo, "bg-primario"],
    ["Hoteles", porConcepto.hotel, "bg-acento"],
    ["Excursiones", porConcepto.excursiones, "bg-primario-suave"],
    ["Otros", porConcepto.otros, "bg-borde"],
  ];
  const total = conceptos.reduce((suma, [, valor]) => suma + Number(valor || 0), 0) || 1;
  return (
    <article className="vidrio rounded-3xl p-6">
      <h2 className="font-display text-xl font-bold text-primario">De dónde viene el dinero</h2>
      <p className="mt-1 text-xs text-texto-suave">Reparto del importe facturado por concepto.</p>
      <div className="mt-5 flex h-3 overflow-hidden rounded-full bg-white/60">
        {conceptos.map(([nombre, valor, degradado]) => (
          <div
            key={nombre}
            className={degradado}
            style={{ width: `${(Number(valor || 0) / total) * 100}%` }}
            title={`${nombre}: ${dinero(valor)}`}
          />
        ))}
      </div>
      <dl className="mt-5 space-y-3 text-sm">
        {conceptos.map(([nombre, valor, degradado]) => (
          <div key={nombre} className="flex items-center justify-between gap-4">
            <dt className="flex items-center gap-2 text-texto-suave">
              <span className={`h-2.5 w-2.5 rounded-full ${degradado}`} aria-hidden="true" />
              {nombre}
            </dt>
            <dd className="font-semibold text-texto">
              {dinero(valor)} <span className="text-xs font-normal text-texto-suave">({Math.round((Number(valor || 0) / total) * 100)}%)</span>
            </dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

function TablaRanking({ titulo, subtitulo, filas, columnas, vacio }) {
  return (
    <article className="vidrio rounded-3xl p-6">
      <h2 className="font-display text-xl font-bold text-primario">{titulo}</h2>
      <p className="mt-1 text-xs text-texto-suave">{subtitulo}</p>
      {filas.length ? (
        <table className="mt-4 w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-texto-suave">
              {columnas.map((columna) => (
                <th key={columna.clave} className={`pb-2 font-semibold ${columna.derecha ? "text-right" : ""}`}>{columna.titulo}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-primario/10">
            {filas.map((fila, indice) => (
              <tr key={fila[columnas[0].clave] ?? indice}>
                {columnas.map((columna) => (
                  <td key={columna.clave} className={`py-2.5 ${columna.derecha ? "text-right font-semibold text-texto" : "text-texto"}`}>
                    {columna.formato ? columna.formato(fila[columna.clave]) : fila[columna.clave]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="mt-4 text-sm text-texto-suave">{vacio}</p>
      )}
    </article>
  );
}

export default function AvanceCinco() {
  const { sesion } = useAuth();
  const [parametros, setParametros] = useSearchParams();
  const rol = sesion?.usuario?.rol;
  const esPersonal = rol === "administrador" || rol === "empleado";
  const pestanas = esPersonal ? PESTANAS_PERSONAL : PESTANAS_CLIENTE;
  // La pestaña sale de la dirección (`?vista=`): la barra lateral y las pestañas cambian lo mismo, y no hay que sincronizar nada.
  const vistaPedida = parametros.get("vista");
  const pestana = pestanas.some(([clave]) => clave === vistaPedida) ? vistaPedida : pestanas[0][0];
  const [filtros, setFiltros] = useState({ desde: "", hasta: "", periodo: "mes", estado: "", producto_id: "", servicio_id: "", cliente_id: "" });
  const [formPqr, setFormPqr] = useState({ tipo: "peticion", asunto: "", descripcion: "" });
  const [pregunta, setPregunta] = useState("");
  const [respuesta, setRespuesta] = useState("");
  const [mensaje, setMensaje] = useState("");
  const headers = { Authorization: `Bearer ${sesion?.token}` };

  const consulta = new URLSearchParams(Object.entries(filtros).filter(([, valor]) => valor)).toString();
  const resumen = useCarga(sesion && esPersonal ? `/estadisticas?${consulta}` : "");
  const historial = useCarga(sesion && esPersonal ? `/ventas?${consulta}` : "");
  const listadoDeFacturas = useCarga(sesion ? "/facturas" : "");
  const solicitudes = useCarga(sesion ? "/pqr" : "");
  // El producto, el servicio y el cliente son catálogos aparte: solo hacen falta para armar los
  // selectores del filtro, y el de cliente requiere administrador (es quien puede listar usuarios).
  const productos = useCarga(sesion && esPersonal ? "/productos" : "");
  const servicios = useCarga(sesion && esPersonal ? "/servicios" : "");
  const usuarios = useCarga(sesion && rol === "administrador" ? "/usuarios" : "");
  const datos = resumen.datos;
  const ventas = historial.datos ?? [];
  const facturas = listadoDeFacturas.datos ?? [];
  const pqr = solicitudes.datos ?? [];
  const clientes = (usuarios.datos ?? []).filter((usuario) => usuario.rol === "cliente");
  const avisoDeCarga = resumen.error || historial.error || listadoDeFacturas.error || solicitudes.error;

  if (!sesion) return <Navigate to="/login" replace />;

  const registrarPqr = async (evento) => {
    evento.preventDefault();
    try { await solicitar("/pqr", { method: "POST", headers, body: JSON.stringify(formPqr) }); solicitudes.recargar(); setFormPqr({ tipo: "peticion", asunto: "", descripcion: "" }); setMensaje("PQR registrada correctamente."); } catch (error) { setMensaje(error.message); }
  };
  const actualizarPqr = async (item, estado) => {
    try { await solicitar(`/pqr/${item.id}`, { method: "PATCH", headers, body: JSON.stringify({ estado, respuesta: item.respuesta || null }) }); solicitudes.recargar(); } catch (error) { setMensaje(error.message); }
  };
  const preguntar = async (evento) => {
    evento.preventDefault();
    try { const resultado = await solicitar("/chatbot", { method: "POST", body: JSON.stringify({ mensaje: pregunta }) }); setRespuesta(resultado.respuesta); setPregunta(""); } catch (error) { setMensaje(error.message); }
  };

  const indicadores = datos?.indicadores;
  return <div className="mx-auto w-[92%] max-w-275 flex-1 py-8 sm:py-12">
    <section className="vidrio flex flex-wrap items-end justify-between gap-5 rounded-3xl p-6 sm:p-8">
      {esPersonal ? (
        <div>
          <span className="antetitulo">Quinto entregable</span>
          <h1 className="mt-3 font-display text-4xl font-bold"><span className="titulo-aurora">Reservas y facturación</span></h1>
          <p className="mt-2 max-w-2xl text-sm text-texto-suave">Cada reserva de viaje se convierte en una venta, factura y registro consultable.</p>
        </div>
      ) : (
        <div>
          <span className="antetitulo">Tu cuenta</span>
          <h1 className="mt-3 font-display text-4xl font-bold"><span className="titulo-aurora">Facturas y atención</span></h1>
          <p className="mt-2 max-w-2xl text-sm text-texto-suave">Descarga las facturas de tus viajes, envíanos peticiones, quejas o reclamos y resuelve tus dudas con el asistente de Aurora.</p>
        </div>
      )}
      <span className="rounded-full border border-primario/12 bg-white/60 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-texto-suave backdrop-blur-sm">Rol: {rol}</span>
    </section>

    {(mensaje || avisoDeCarga) && <p role="alert" className="vidrio mt-5 rounded-2xl p-4 text-sm text-texto">{mensaje || avisoDeCarga}</p>}

    {/* Navegación por pestañas, también accesible sin la barra lateral. */}
    <div className="vidrio-sutil mt-6 flex flex-wrap gap-1.5 rounded-2xl p-1.5" role="tablist" aria-label={esPersonal ? "Secciones comerciales" : "Secciones de tu cuenta"}>
      {pestanas.map(([vista, etiqueta]) => (
        <button
          key={vista}
          type="button"
          role="tab"
          aria-selected={pestana === vista}
          onClick={() => setParametros({ vista }, { replace: true })}
          className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
            pestana === vista
              ? "boton-tinta text-white"
              : "text-texto-suave hover:bg-white/60 hover:text-primario"
          }`}
        >
          {etiqueta}
        </button>
      ))}
    </div>

    {/* Los filtros son de la analítica de ventas: el cliente no los necesita. */}
    {esPersonal && <form className="vidrio mt-5 grid gap-3 rounded-2xl p-4 sm:grid-cols-2 lg:grid-cols-4" onSubmit={(evento) => evento.preventDefault()}>
      <label className="text-xs font-semibold uppercase text-texto-suave">Desde<input type="date" value={filtros.desde} onChange={(evento) => setFiltros({ ...filtros, desde: evento.target.value })} className={CAMPO} /></label>
      <label className="text-xs font-semibold uppercase text-texto-suave">Hasta<input type="date" value={filtros.hasta} onChange={(evento) => setFiltros({ ...filtros, hasta: evento.target.value })} className={CAMPO} /></label>
      <label className="text-xs font-semibold uppercase text-texto-suave">Agrupar<select value={filtros.periodo} onChange={(evento) => setFiltros({ ...filtros, periodo: evento.target.value })} className={CAMPO}><option value="dia">Día</option><option value="semana">Semana</option><option value="mes">Mes</option></select></label>
      <label className="text-xs font-semibold uppercase text-texto-suave">Estado<select value={filtros.estado} onChange={(evento) => setFiltros({ ...filtros, estado: evento.target.value })} className={CAMPO}><option value="">Todos</option><option value="completada">Completada</option><option value="pendiente">Pendiente</option><option value="cancelada">Cancelada</option></select></label>
      {esPersonal && <>
        <label className="text-xs font-semibold uppercase text-texto-suave">
          Producto
          <select value={filtros.producto_id} onChange={(evento) => setFiltros({ ...filtros, producto_id: evento.target.value })} className={CAMPO}>
            <option value="">Todos</option>
            {(productos.datos ?? []).map((producto) => <option key={producto.id} value={producto.id}>{producto.nombre}</option>)}
          </select>
        </label>
        <label className="text-xs font-semibold uppercase text-texto-suave">
          Servicio
          <select value={filtros.servicio_id} onChange={(evento) => setFiltros({ ...filtros, servicio_id: evento.target.value })} className={CAMPO}>
            <option value="">Todos</option>
            {(servicios.datos ?? []).map((servicio) => <option key={servicio.id} value={servicio.id}>{servicio.nombre}</option>)}
          </select>
        </label>
        {rol === "administrador" && (
          <label className="text-xs font-semibold uppercase text-texto-suave">
            Cliente
            <select value={filtros.cliente_id} onChange={(evento) => setFiltros({ ...filtros, cliente_id: evento.target.value })} className={CAMPO}>
              <option value="">Todos</option>
              {clientes.map((cliente) => <option key={cliente.id} value={cliente.id}>{cliente.nombre} {cliente.apellido}</option>)}
            </select>
          </label>
        )}
      </>}
    </form>}

    {pestana === "resumen" && <section className="mt-8 space-y-6">
      {datos ? <>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card titulo="Clientes" valor={indicadores.usuarios} detalle={`${indicadores.reservas} reserva(s) en el periodo`} />
          <Card titulo="Reservas vendidas" valor={indicadores.ventas} detalle={`${indicadores.lineas} línea(s) facturada(s)`} />
          <Card titulo="Facturación" valor={dinero(indicadores.facturacion)} variacion={datos.comparativa?.variacion ?? undefined} detalle={`Anterior: ${dinero(datos.comparativa?.totalAnterior)}`} />
          <Card titulo="PQR pendientes" valor={indicadores.pqrPendientes} detalle={`${indicadores.facturas} factura(s) emitida(s)`} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card titulo="Ticket promedio" valor={dinero(indicadores.ticketPromedio)} detalle="Importe medio por venta" />
          <Card titulo="Pasajeros" valor={indicadores.pasajeros} detalle="Sumados desde las líneas de vuelo" />
          <Card titulo="Catálogo activo" valor={`${indicadores.productos} + ${indicadores.servicios}`} detalle="Productos y servicios publicados" />
        </div>

        <Graficos datos={datos.ventasPorDia} />

        <div className="grid gap-6 lg:grid-cols-2">
          <ComposicionIngresos porConcepto={datos.porConcepto || { paquete: 0, vuelo: 0, hotel: 0, excursiones: 0, otros: 0 }} />
          <TablaRanking
            titulo="Estado de las ventas"
            subtitulo="Cuántas ventas hay en cada estado y cuánto suman."
            filas={datos.porEstado || []}
            columnas={[
              { clave: "estado", titulo: "Estado", formato: estadoTexto },
              { clave: "cantidad", titulo: "Ventas", derecha: true },
              { clave: "total", titulo: "Importe", derecha: true, formato: dinero },
            ]}
            vacio="No hay ventas en el periodo seleccionado."
          />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <TablaRanking
            titulo="Destinos que más venden"
            subtitulo="Calculado sobre las reservas creadas en el periodo."
            filas={datos.topDestinos || []}
            columnas={[
              { clave: "destino", titulo: "Destino" },
              { clave: "reservas", titulo: "Reservas", derecha: true },
              { clave: "pasajeros", titulo: "Pasajeros", derecha: true },
              { clave: "total", titulo: "Importe", derecha: true, formato: dinero },
            ]}
            vacio="Todavía no hay reservas en el periodo."
          />
          <TablaRanking
            titulo="Clientes con mayor facturación"
            subtitulo="Los cinco primeros por importe acumulado."
            filas={datos.topClientes || []}
            columnas={[
              { clave: "cliente", titulo: "Cliente" },
              { clave: "ventas", titulo: "Ventas", derecha: true },
              { clave: "total", titulo: "Importe", derecha: true, formato: dinero },
            ]}
            vacio="No hay ventas con cliente en el periodo."
          />
        </div>
      </> : <p className="vidrio rounded-3xl p-6 text-sm text-texto-suave">El resumen consolidado está disponible para administradores y empleados.</p>}
    </section>}

    {pestana === "reservas vendidas" && <section className="vidrio mt-8 rounded-3xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-2xl font-bold text-primario">Reservas vendidas</h2>
          <p className="mt-1 text-sm text-texto-suave">El historial comercial se alimenta de las reservas de viaje creadas.</p>
        </div>
        <DescargarReportes headers={headers} filtros={filtros} />
      </div>
      <div className="mt-5 divide-y divide-primario/10">
        {ventas.map((item) => <article key={item.id} className="grid gap-3 py-5 sm:grid-cols-[1fr_auto] sm:items-center">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <strong>Reserva / venta #{item.id}</strong>
              <span className="rounded-full border border-primario/12 bg-white/60 px-2.5 py-0.5 text-xs font-semibold capitalize text-primario backdrop-blur-sm">{estadoTexto(item.estado)}</span>
            </div>
            <p className="mt-1 text-sm text-texto">{item.detalles.map((detalle) => detalle.nombre).join(", ")}</p>
            <p className="text-sm text-texto-suave">Cliente: {item.cliente?.nombre} · {item.fecha?.slice(0, 10)} · {item.detalles.reduce((total, detalle) => total + detalle.cantidad, 0)} pasajero(s)</p>
          </div>
          <strong className="font-display text-lg text-primario">{dinero(item.total)}</strong>
        </article>)}
        {ventas.length === 0 && <p className="py-5 text-sm text-texto-suave">Todavía no hay reservas vendidas para los filtros seleccionados.</p>}
      </div>
    </section>}

    {pestana === "facturas" && <section className="vidrio mt-8 rounded-3xl p-6">
      <h2 className="font-display text-2xl font-bold text-primario">{esPersonal ? "Facturas de reservas" : "Mis facturas"}</h2>
      <p className="mt-1 text-sm text-texto-suave">Cada factura detalla el vuelo, el hotel y las excursiones por separado{esPersonal ? "." : "; descárgala en PDF cuando la necesites."}</p>
      <div className="mt-5 divide-y divide-primario/10">
        {facturas.map((item) => <article key={item.id} className="flex flex-wrap items-center justify-between gap-4 py-4">
          <div>
            <strong>{item.numero}</strong>
            <p className="text-sm text-texto-suave">{item.fecha.slice(0, 10)} · {dinero(item.venta.total)} · {estadoTexto(item.estado)}</p>
          </div>
          <DescargarFactura id={item.id} headers={headers} />
        </article>)}
        {facturas.length === 0 && <p className="py-4 text-sm text-texto-suave">{esPersonal ? "No hay facturas disponibles." : "Aún no tienes facturas: se generan al registrar cada reserva."}</p>}
      </div>
    </section>}

    {pestana === "pqr" && <section className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
      <form onSubmit={registrarPqr} className="vidrio rounded-3xl p-6">
        <h2 className="font-display text-2xl font-bold text-primario">Registrar PQR</h2>
        <div className="mt-5 grid gap-3">
          <select value={formPqr.tipo} onChange={(evento) => setFormPqr({ ...formPqr, tipo: evento.target.value })} className={CAMPO}><option value="peticion">Petición</option><option value="queja">Queja</option><option value="reclamo">Reclamo</option></select>
          <input required value={formPqr.asunto} onChange={(evento) => setFormPqr({ ...formPqr, asunto: evento.target.value })} placeholder="Asunto" className={CAMPO} />
          <textarea required value={formPqr.descripcion} onChange={(evento) => setFormPqr({ ...formPqr, descripcion: evento.target.value })} placeholder="Describe tu solicitud" className={`${CAMPO} min-h-28`} />
          <button className="rounded-xl boton-tinta px-4 py-2.5 font-semibold text-white">Enviar solicitud</button>
        </div>
      </form>
      <div className="vidrio rounded-3xl p-6">
        <h2 className="font-display text-2xl font-bold text-primario">{esPersonal ? "Seguimiento de solicitudes" : "Mis solicitudes"}</h2>
        <div className="mt-4 divide-y divide-primario/10">
          {pqr.map((item) => <article key={item.id} className="py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <strong>{item.asunto}</strong>
              <span className="rounded-full border border-primario/12 bg-white/60 px-2.5 py-0.5 text-xs font-semibold capitalize text-primario backdrop-blur-sm">{estadoTexto(item.estado)}</span>
            </div>
            <p className="mt-0.5 text-xs text-texto-suave">{TIPOS_PQR[item.tipo] || item.tipo} · {item.fecha?.slice(0, 10)}{esPersonal && item.cliente ? ` · ${item.cliente}` : ""}</p>
            <p className="mt-1 text-sm text-texto-suave">{item.descripcion}</p>
            {item.respuesta && (
              <p className="mt-2 rounded-xl border-l-4 border-l-acento bg-white/50 px-3 py-2 text-sm text-texto">
                <strong className="text-primario">Respuesta de Aurora:</strong> {item.respuesta}
              </p>
            )}
            {esPersonal && <select value={item.estado} onChange={(evento) => actualizarPqr(item, evento.target.value)} className={`${CAMPO} w-auto`}><option value="pendiente">Pendiente</option><option value="en_proceso">En proceso</option><option value="respondida">Respondida</option><option value="cerrada">Cerrada</option></select>}
          </article>)}
          {pqr.length === 0 && <p className="py-4 text-sm text-texto-suave">No hay solicitudes registradas.</p>}
        </div>
      </div>
    </section>}

    {pestana === "chatbot" && <section className="vidrio mx-auto mt-8 max-w-3xl rounded-3xl p-6 sm:p-8">
      <span className="antetitulo">Atención inteligente</span>
      <h2 className="mt-3 font-display text-3xl font-bold"><span className="titulo-aurora">Chatbot Aurora</span></h2>
      <p className="mt-2 text-sm text-texto-suave">Resuelve dudas sobre destinos, reservas y PQR.</p>
      <form onSubmit={preguntar} className="mt-6 flex flex-wrap gap-2">
        <input required value={pregunta} onChange={(evento) => setPregunta(evento.target.value)} placeholder="Escribe tu pregunta" className={`${CAMPO} min-w-0 flex-1`} />
        <button className="rounded-xl boton-tinta px-5 py-2.5 font-semibold text-white">Enviar</button>
      </form>
      {respuesta && <p className="vidrio-sutil mt-5 rounded-2xl border-l-4 border-l-acento p-4 text-sm leading-6 text-texto">{respuesta}</p>}
    </section>}
  </div>;
}
