// Cuántas plazas quedan, como texto y como tono: solo se avisa cuando falta poco o no alcanza.
export function estadoDePlazas(vuelo, pasajeros) {
  const libres = vuelo.plazasLibres;
  if (libres == null) return { agotado: false, texto: "", tono: "" };
  if (libres <= 0) return { agotado: true, texto: "Agotado", tono: "text-red-700" };
  if (libres < pasajeros) return { agotado: true, texto: `Solo ${libres} plaza${libres === 1 ? "" : "s"}`, tono: "text-red-700" };
  if (libres <= 10) return { agotado: false, texto: `Últimas ${libres} plazas`, tono: "text-brillo" };
  return { agotado: false, texto: `${libres} plazas libres`, tono: "text-texto-suave" };
}
