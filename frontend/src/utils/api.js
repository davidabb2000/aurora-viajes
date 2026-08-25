const API_URL = import.meta.env.VITE_API_URL || "http://localhost:3000/api";

export async function solicitar(ruta, opciones = {}) {
  const { headers: headersOpcionales = {}, ...opcionesFetch } = opciones;
  const respuesta = await fetch(`${API_URL}${ruta}`, {
    ...opcionesFetch,
    headers: { "Content-Type": "application/json", ...headersOpcionales },
  });
  const datos = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok) throw new Error(datos.mensaje || "Ocurrió un error en la solicitud.");
  return datos;
}

export function guardarSesion(datos, persistir = false) {
  const almacenamiento = persistir ? localStorage : sessionStorage;
  almacenamiento.setItem("aurora_token", datos.token);
  almacenamiento.setItem("aurora_usuario", JSON.stringify(datos.usuario));
  window.dispatchEvent(new Event("aurora-sesion"));
}

export function obtenerSesion() {
  const token = localStorage.getItem("aurora_token") || sessionStorage.getItem("aurora_token");
  const usuario = localStorage.getItem("aurora_usuario") || sessionStorage.getItem("aurora_usuario");
  return token && usuario ? { token, usuario: JSON.parse(usuario) } : null;
}

export function cerrarSesion() {
  localStorage.removeItem("aurora_token");
  localStorage.removeItem("aurora_usuario");
  sessionStorage.removeItem("aurora_token");
  sessionStorage.removeItem("aurora_usuario");
  window.dispatchEvent(new Event("aurora-sesion"));
}

export function actualizarUsuarioSesion(usuarioActualizado) {
  [localStorage, sessionStorage].forEach((almacenamiento) => {
    const usuario = almacenamiento.getItem("aurora_usuario");
    if (usuario) almacenamiento.setItem("aurora_usuario", JSON.stringify({ ...JSON.parse(usuario), ...usuarioActualizado }));
  });
  window.dispatchEvent(new Event("aurora-sesion"));
}
