const API_URL = import.meta.env.VITE_API_URL || "/api";

export async function solicitar(ruta, opciones = {}) {
  const { headers: headersOpcionales = {}, ...opcionesFetch } = opciones;
  // El token de la sesión se adjunta solo; quien llama puede pasar su propia cabecera Authorization.
  const token = tokenActual();
  let respuesta;
  try {
    respuesta = await fetch(`${API_URL}${ruta}`, {
      ...opcionesFetch,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headersOpcionales,
      },
    });
  } catch {
    throw new Error("No se pudo conectar con el backend. Verifica que FastAPI esté ejecutándose.");
  }
  const datos = await respuesta.json().catch(() => ({}));
  const mensaje =
    datos.mensaje ||
    datos.detail ||
    (Array.isArray(datos?.detail)
      ? datos.detail.map((item) => item.msg || item.message || String(item)).join(" ")
      : "");
  const tokenInvalido =
    respuesta.status === 401 &&
    /token.*(inv[aá]lid|expir)|token.*(no es v[aá]lido|inv[aá]lido)/i.test(mensaje);
  if (tokenInvalido) {
    cerrarSesion();
    if (window.location.pathname !== "/login") {
      window.location.assign("/login");
    }
  }
  if (!respuesta.ok) throw new Error(mensaje || "Ocurrió un error en la solicitud.");
  return datos;
}

function tokenActual() {
  try {
    return localStorage.getItem("aurora_token") || sessionStorage.getItem("aurora_token");
  } catch {
    return null;
  }
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
