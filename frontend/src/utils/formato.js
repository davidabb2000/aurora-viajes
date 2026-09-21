// Formatos compartidos. Las fechas del backend llegan sin zona horaria («2026-10-05T07:30:00»):
// son la hora local del aeropuerto, y así se muestran, sin conversiones.

export const moneda = (valor) =>
  Number(valor || 0).toLocaleString("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });

const comoFecha = (valor) => (valor && valor.length === 10 ? new Date(`${valor}T00:00:00`) : new Date(valor));

export const fecha = (valor, opciones = { day: "numeric", month: "long", year: "numeric" }) =>
  valor ? comoFecha(valor).toLocaleDateString("es-CO", opciones) : "Sin definir";

export const fechaCorta = (valor) => fecha(valor, { day: "numeric", month: "short" });

export const fechaHora = (valor) => (valor ? comoFecha(valor).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" }) : "Sin definir");

export const hora = (valor) => (valor ? comoFecha(valor).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }) : "");

export const diaCorto = (valor) => (valor ? comoFecha(valor).toLocaleDateString("es-CO", { weekday: "short", day: "numeric", month: "short" }) : "");

/** Duración de un vuelo, como «11 h 45 min». */
export function duracion(salida, llegada) {
  if (!salida || !llegada) return "";
  const minutos = Math.round((new Date(llegada) - new Date(salida)) / 60000);
  if (minutos <= 0) return "";
  const horas = Math.floor(minutos / 60);
  const resto = minutos % 60;
  return resto ? `${horas} h ${resto} min` : `${horas} h`;
}

/** Noches entre dos fechas ISO (solo la parte de la fecha). */
export function nochesEntre(salida, regreso) {
  if (!salida || !regreso) return 0;
  const dias = Math.round((new Date(`${regreso.slice(0, 10)}T00:00:00`) - new Date(`${salida.slice(0, 10)}T00:00:00`)) / 86400000);
  return Math.max(0, dias);
}

export const etiquetaEstado = (valor) => String(valor || "pendiente").replaceAll("_", " ");

export const hoyISO = () => {
  const ahora = new Date();
  return `${ahora.getFullYear()}-${String(ahora.getMonth() + 1).padStart(2, "0")}-${String(ahora.getDate()).padStart(2, "0")}`;
};

export const sumarDias = (fechaISO, dias) => {
  const base = new Date(`${fechaISO.slice(0, 10)}T00:00:00`);
  base.setDate(base.getDate() + dias);
  return `${base.getFullYear()}-${String(base.getMonth() + 1).padStart(2, "0")}-${String(base.getDate()).padStart(2, "0")}`;
};

/** «París, Francia» a partir de «París» y «Francia», sin repetir el país si ya viene en el nombre. */
export const ubicacion = (nombre, pais) => {
  if (!pais) return nombre;
  const limpiar = (texto) => texto.trim().normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  return limpiar(nombre).endsWith(`, ${limpiar(pais)}`) ? nombre : `${nombre}, ${pais}`;
};
