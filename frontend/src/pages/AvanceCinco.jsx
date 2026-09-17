import { useEffect, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { solicitar } from "../utils/api";

const API_URL = import.meta.env.VITE_API_URL || "/api";
const dinero = (valor) => `$${Number(valor || 0).toLocaleString("es-CO")}`;
const estadoTexto = (estado) => estado?.replace("_", " ") || "pendiente";

function Card({ titulo, valor }) {
  return <article className="border border-borde bg-superficie p-5"><p className="text-xs font-semibold uppercase tracking-widest text-texto-suave">{titulo}</p><p className="mt-3 font-display text-3xl font-bold text-primario">{valor}</p></article>;
}

function DescargarReportes({ headers }) {
  const descargar = async (formato) => {
    const respuesta = await fetch(`${API_URL}/reportes/ventas?formato=${formato}`, { headers });
    if (!respuesta.ok) throw new Error("No se pudo generar el reporte.");
    const archivo = await respuesta.blob();
    const enlace = document.createElement("a");
    enlace.href = URL.createObjectURL(archivo);
    enlace.download = `reporte-reservas.${formato}`;
    enlace.click();
    URL.revokeObjectURL(enlace.href);
  };
  return <div className="flex flex-wrap gap-2"><button type="button" onClick={() => descargar("pdf")} className="border border-borde px-4 py-2 text-sm font-semibold text-primario">Reporte PDF</button><button type="button" onClick={() => descargar("xlsx")} className="border border-borde px-4 py-2 text-sm font-semibold text-primario">Reporte Excel</button></div>;
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
  return <button type="button" onClick={descargar} className="border border-borde px-4 py-2 text-sm font-semibold text-primario">Factura PDF</button>;
}

function Graficos({ datos }) {
  const maximo = Math.max(...datos.map((item) => item.total), 1);
  const puntos = datos.map((item, indice) => `${datos.length === 1 ? 300 : 20 + (indice / (datos.length - 1)) * 560},${160 - (item.total / maximo) * 135}`).join(" ");
  return <div className="grid gap-8 lg:grid-cols-2"><article className="border border-borde bg-superficie p-6"><h2 className="font-display text-xl font-bold text-primario">Reservas vendidas por periodo</h2><div className="mt-6 flex h-44 items-end gap-2 border-b border-l border-borde px-2">{datos.map((item) => <div key={item.fecha} className="flex h-full flex-1 items-end" title={`${item.fecha}: ${dinero(item.total)}`}><div className="w-full bg-acento" style={{ height: `${Math.max((item.total / maximo) * 100, 3)}%` }} /></div>)}</div></article><article className="border border-borde bg-superficie p-6"><h2 className="font-display text-xl font-bold text-primario">Tendencia de facturación</h2><svg viewBox="0 0 600 180" className="mt-6 h-44 w-full" role="img" aria-label="Tendencia de facturación"><polyline fill="none" stroke="currentColor" strokeWidth="4" className="text-acento" points={puntos} /></svg></article></div>;
}

export default function AvanceCinco() {
  const { sesion } = useAuth();
  const [parametros] = useSearchParams();
  const [pestana, setPestana] = useState(parametros.get("vista") || "resumen");
  const [datos, setDatos] = useState(null);
  const [ventas, setVentas] = useState([]);
  const [facturas, setFacturas] = useState([]);
  const [pqr, setPqr] = useState([]);
  const [filtros, setFiltros] = useState({ desde: "", hasta: "", periodo: "mes", estado: "" });
  const [formPqr, setFormPqr] = useState({ tipo: "peticion", asunto: "", descripcion: "" });
  const [pregunta, setPregunta] = useState("");
  const [respuesta, setRespuesta] = useState("");
  const [mensaje, setMensaje] = useState("");
  const rol = sesion?.usuario?.rol;
  const esPersonal = rol === "administrador" || rol === "empleado";
  const headers = { Authorization: `Bearer ${sesion?.token}` };

  const cargar = async () => {
    const parametros = new URLSearchParams(Object.entries(filtros).filter(([, valor]) => valor));
    try {
      const [resumen, historial, listadoFacturas, solicitudes] = await Promise.all([
        esPersonal ? solicitar(`/estadisticas?${parametros}`, { headers }) : Promise.resolve(null),
        solicitar(`/ventas?${parametros}`, { headers }),
        solicitar("/facturas", { headers }),
        solicitar("/pqr", { headers }),
      ]);
      setDatos(resumen); setVentas(historial); setFacturas(listadoFacturas); setPqr(solicitudes);
    } catch (error) { setMensaje(error.message); }
  };

  useEffect(() => { if (sesion) cargar(); }, [sesion, filtros]);
  useEffect(() => {
    const vistaSolicitada = parametros.get("vista");
    if (vistaSolicitada && pestanas.includes(vistaSolicitada)) setPestana(vistaSolicitada);
  }, [parametros]);
  if (!sesion) return <Navigate to="/login" replace />;

  const registrarPqr = async (evento) => {
    evento.preventDefault();
    try { const creada = await solicitar("/pqr", { method: "POST", headers, body: JSON.stringify(formPqr) }); setPqr((actuales) => [creada, ...actuales]); setFormPqr({ tipo: "peticion", asunto: "", descripcion: "" }); setMensaje("PQR registrada correctamente."); } catch (error) { setMensaje(error.message); }
  };
  const actualizarPqr = async (item, estado) => {
    try { await solicitar(`/pqr/${item.id}`, { method: "PATCH", headers, body: JSON.stringify({ estado, respuesta: item.respuesta || null }) }); setPqr((actuales) => actuales.map((actual) => actual.id === item.id ? { ...actual, estado } : actual)); } catch (error) { setMensaje(error.message); }
  };
  const preguntar = async (evento) => {
    evento.preventDefault();
    try { const resultado = await solicitar("/chatbot", { method: "POST", body: JSON.stringify({ mensaje: pregunta }) }); setRespuesta(resultado.respuesta); setPregunta(""); } catch (error) { setMensaje(error.message); }
  };

  const pestanas = ["resumen", "reservas vendidas", "facturas", "pqr", "chatbot"];
  return <main className="mx-auto w-[92%] max-w-275 flex-1 py-10 sm:py-14">
    <div className="flex flex-wrap items-end justify-between gap-5"><div><span className="text-xs font-semibold uppercase tracking-widest text-primario-suave">Quinto entregable</span><h1 className="mt-2 font-display text-4xl font-bold text-primario">Reservas y facturación</h1><p className="mt-2 max-w-2xl text-sm text-texto-suave">Cada reserva de viaje se convierte en una venta, factura y registro consultable.</p></div><span className="border border-borde bg-superficie px-3 py-2 text-xs font-semibold uppercase tracking-wide text-texto-suave">Rol: {rol}</span></div>
    {mensaje && <p className="mt-5 border border-borde bg-superficie p-3 text-sm text-texto">{mensaje}</p>}
    <form className="mt-6 grid gap-3 border border-borde bg-superficie p-4 sm:grid-cols-2 lg:grid-cols-4" onSubmit={(evento) => evento.preventDefault()}><label className="text-xs font-semibold uppercase text-texto-suave">Desde<input type="date" value={filtros.desde} onChange={(evento) => setFiltros({ ...filtros, desde: evento.target.value })} className="mt-1 w-full border border-borde bg-fondo px-3 py-2 text-sm" /></label><label className="text-xs font-semibold uppercase text-texto-suave">Hasta<input type="date" value={filtros.hasta} onChange={(evento) => setFiltros({ ...filtros, hasta: evento.target.value })} className="mt-1 w-full border border-borde bg-fondo px-3 py-2 text-sm" /></label><label className="text-xs font-semibold uppercase text-texto-suave">Agrupar<select value={filtros.periodo} onChange={(evento) => setFiltros({ ...filtros, periodo: evento.target.value })} className="mt-1 w-full border border-borde bg-fondo px-3 py-2 text-sm"><option value="dia">Día</option><option value="semana">Semana</option><option value="mes">Mes</option></select></label><label className="text-xs font-semibold uppercase text-texto-suave">Estado<select value={filtros.estado} onChange={(evento) => setFiltros({ ...filtros, estado: evento.target.value })} className="mt-1 w-full border border-borde bg-fondo px-3 py-2 text-sm"><option value="">Todos</option><option value="completada">Completada</option><option value="pendiente">Pendiente</option><option value="cancelada">Cancelada</option></select></label></form>
    {pestana === "resumen" && <section className="mt-8 space-y-8">{datos ? <><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><Card titulo="Clientes" valor={datos.indicadores.usuarios} /><Card titulo="Reservas vendidas" valor={datos.indicadores.ventas} /><Card titulo="Facturación" valor={dinero(datos.indicadores.facturacion)} /><Card titulo="PQR pendientes" valor={datos.indicadores.pqrPendientes} /></div><Graficos datos={datos.ventasPorDia} /></> : <p className="border border-borde bg-superficie p-6 text-sm text-texto-suave">El resumen consolidado está disponible para administradores y empleados.</p>}</section>}
    {pestana === "reservas vendidas" && <section className="mt-8 border border-borde bg-superficie p-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-display text-2xl font-bold text-primario">Reservas vendidas</h2><p className="mt-1 text-sm text-texto-suave">El historial comercial se alimenta de las reservas de viaje creadas.</p></div><DescargarReportes headers={headers} /></div><div className="mt-5 divide-y divide-borde">{ventas.map((item) => <article key={item.id} className="grid gap-3 py-5 sm:grid-cols-[1fr_auto] sm:items-center"><div><div className="flex flex-wrap gap-3"><strong>Reserva / venta #{item.id}</strong><span className="capitalize text-sm text-primario">{estadoTexto(item.estado)}</span></div><p className="mt-1 text-sm text-texto">{item.detalles.map((detalle) => detalle.nombre).join(", ")}</p><p className="text-sm text-texto-suave">Cliente: {item.cliente?.nombre} · {item.fecha?.slice(0, 10)} · {item.detalles.reduce((total, detalle) => total + detalle.cantidad, 0)} pasajero(s)</p></div><strong className="text-lg text-primario">{dinero(item.total)}</strong></article>)}{ventas.length === 0 && <p className="py-5 text-sm text-texto-suave">Todavía no hay reservas vendidas para los filtros seleccionados.</p>}</div></section>}
    {pestana === "facturas" && <section className="mt-8 border border-borde bg-superficie p-6"><h2 className="font-display text-2xl font-bold text-primario">Facturas de reservas</h2><div className="mt-5 divide-y divide-borde">{facturas.map((item) => <article key={item.id} className="flex flex-wrap items-center justify-between gap-4 py-4"><div><strong>{item.numero}</strong><p className="text-sm text-texto-suave">{item.fecha.slice(0, 10)} · {dinero(item.venta.total)} · {estadoTexto(item.estado)}</p></div><DescargarFactura id={item.id} headers={headers} /></article>)}{facturas.length === 0 && <p className="py-4 text-sm text-texto-suave">No hay facturas disponibles.</p>}</div></section>}
    {pestana === "pqr" && <section className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]"><form onSubmit={registrarPqr} className="border border-borde bg-superficie p-6"><h2 className="font-display text-2xl font-bold text-primario">Registrar PQR</h2><div className="mt-5 grid gap-3"><select value={formPqr.tipo} onChange={(evento) => setFormPqr({ ...formPqr, tipo: evento.target.value })} className="border border-borde bg-fondo px-3 py-2"><option value="peticion">Petición</option><option value="queja">Queja</option><option value="reclamo">Reclamo</option></select><input required value={formPqr.asunto} onChange={(evento) => setFormPqr({ ...formPqr, asunto: evento.target.value })} placeholder="Asunto" className="border border-borde bg-fondo px-3 py-2" /><textarea required value={formPqr.descripcion} onChange={(evento) => setFormPqr({ ...formPqr, descripcion: evento.target.value })} placeholder="Describe tu solicitud" className="min-h-28 border border-borde bg-fondo px-3 py-2" /><button className="bg-primario px-4 py-2 font-semibold text-white">Enviar solicitud</button></div></form><div className="border border-borde bg-superficie p-6"><h2 className="font-display text-2xl font-bold text-primario">Seguimiento de solicitudes</h2><div className="mt-4 divide-y divide-borde">{pqr.map((item) => <article key={item.id} className="py-4"><div className="flex flex-wrap justify-between gap-3"><strong>{item.asunto}</strong><span className="capitalize text-sm text-primario">{estadoTexto(item.estado)}</span></div><p className="mt-1 text-sm text-texto-suave">{item.descripcion}</p>{esPersonal && <select value={item.estado} onChange={(evento) => actualizarPqr(item, evento.target.value)} className="mt-3 border border-borde bg-fondo px-3 py-2 text-sm"><option value="pendiente">Pendiente</option><option value="en_proceso">En proceso</option><option value="respondida">Respondida</option><option value="cerrada">Cerrada</option></select>}</article>)}{pqr.length === 0 && <p className="py-4 text-sm text-texto-suave">No hay solicitudes registradas.</p>}</div></div></section>}
    {pestana === "chatbot" && <section className="mx-auto mt-8 max-w-3xl border border-borde bg-superficie p-6"><span className="text-xs font-semibold uppercase tracking-widest text-primario-suave">Atención inteligente</span><h2 className="mt-2 font-display text-3xl font-bold text-primario">Chatbot Aurora</h2><p className="mt-2 text-sm text-texto-suave">Resuelve dudas sobre destinos, reservas y PQR.</p><form onSubmit={preguntar} className="mt-6 flex gap-2"><input required value={pregunta} onChange={(evento) => setPregunta(evento.target.value)} placeholder="Escribe tu pregunta" className="min-w-0 flex-1 border border-borde bg-fondo px-3 py-2" /><button className="bg-primario px-5 py-2 font-semibold text-white">Enviar</button></form>{respuesta && <p className="mt-5 border-l-4 border-acento bg-fondo p-4 text-sm leading-6 text-texto">{respuesta}</p>}</section>}
  </main>;
}
