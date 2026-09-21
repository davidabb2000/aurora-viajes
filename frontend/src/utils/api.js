const API_URL = import.meta.env.VITE_API_URL || "/api";

// Páginas donde no tiene sentido redirigir a otra pantalla de acceso.
const RUTAS_DE_ACCESO = ["/login", "/registro", "/recuperar", "/restablecer", "/acceso-personal", "/cambiar-contrasena"];

/**
 * Error de la API: además del mensaje legible lleva el estado HTTP, el código del backend
 * y los problemas por campo, para poder pintarlos junto a cada input.
 */
export class ErrorApi extends Error {
  constructor(mensaje, { estado = 0, codigo = "", detalles = null } = {}) {
    super(mensaje);
    this.name = "ErrorApi";
    this.estado = estado;
    this.codigo = codigo;
    this.detalles = detalles;
  }

  /** Problema que el servidor detectó en un campo concreto, o "" si no hubo. */
  deCampo(campo) {
    return this.detalles?.find((detalle) => detalle.campo === campo)?.problema || "";
  }
}

const SERVICIO_NO_DISPONIBLE = "El servicio no está disponible en este momento. Inténtalo de nuevo en unos minutos.";
const SIN_INTERNET = "No tienes conexión a internet. Revisa tu red e inténtalo de nuevo.";

/**
 * Cuando el servidor está caído la plataforma responde con un 502 sin cabeceras CORS, y el navegador lo cuenta como un
 * fallo de red: por eso solo se culpa a la conexión de quien navega si de verdad no tiene internet.
 */
function errorDeRed() {
  const sinInternet = typeof navigator !== "undefined" && navigator.onLine === false;
  return new ErrorApi(sinInternet ? SIN_INTERNET : SERVICIO_NO_DISPONIBLE, { codigo: sinInternet ? "sin_conexion" : "servicio_no_disponible" });
}

const enRutaDeAcceso = () => RUTAS_DE_ACCESO.includes(window.location.pathname);

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
    throw errorDeRed();
  }
  const datos = await respuesta.json().catch(() => ({}));
  const mensaje = (typeof datos.mensaje === "string" && datos.mensaje) || (typeof datos.detail === "string" && datos.detail) || "";

  // Una sesión vencida o revocada (cambio de contraseña, «cerrar todas las sesiones») responde 401 a cualquier
  // petición que llevara token; el login es la excepción: allí un 401 solo significa credenciales incorrectas.
  if (respuesta.status === 401 && token && ruta !== "/auth/login") {
    cerrarSesion();
    if (!enRutaDeAcceso()) window.location.assign("/login");
  }
  // Cuentas con una clave provisional: hasta cambiarla solo pueden usar la pantalla de cambio.
  if (respuesta.status === 403 && datos.codigo === "cambio_de_contrasena_requerido" && window.location.pathname !== "/cambiar-contrasena") {
    window.location.assign("/cambiar-contrasena");
  }
  if (!respuesta.ok) {
    const caido = [502, 503, 504].includes(respuesta.status);
    throw new ErrorApi(caido ? mensaje || SERVICIO_NO_DISPONIBLE : mensaje || "Ocurrió un error en la solicitud.", {
      estado: respuesta.status,
      codigo: datos.codigo || (caido ? "servicio_no_disponible" : ""),
      detalles: Array.isArray(datos.detalles) ? datos.detalles : null,
    });
  }
  return datos;
}

/** Descarga un archivo protegido (factura, reporte): hace falta el token, así que no vale un simple enlace. */
export async function descargarArchivo(ruta, nombreDeArchivo) {
  const token = tokenActual();
  let respuesta;
  try {
    respuesta = await fetch(`${API_URL}${ruta}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  } catch {
    throw errorDeRed();
  }
  if (!respuesta.ok) throw new ErrorApi([502, 503, 504].includes(respuesta.status) ? SERVICIO_NO_DISPONIBLE : "No se pudo descargar el archivo.", { estado: respuesta.status });
  const archivo = await respuesta.blob();
  const enlace = document.createElement("a");
  enlace.href = URL.createObjectURL(archivo);
  enlace.download = nombreDeArchivo;
  enlace.click();
  URL.revokeObjectURL(enlace.href);
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

/** Sustituye el token y los datos de la sesión abierta, en el mismo almacenamiento donde estaban (p. ej. tras cambiar la contraseña). */
export function reemplazarSesion(datos) {
  const almacenamiento = localStorage.getItem("aurora_token") ? localStorage : sessionStorage;
  almacenamiento.setItem("aurora_token", datos.token);
  almacenamiento.setItem("aurora_usuario", JSON.stringify(datos.usuario));
  window.dispatchEvent(new Event("aurora-sesion"));
}

export function obtenerSesion() {
  try {
    const token = localStorage.getItem("aurora_token") || sessionStorage.getItem("aurora_token");
    const usuario = localStorage.getItem("aurora_usuario") || sessionStorage.getItem("aurora_usuario");
    return token && usuario ? { token, usuario: JSON.parse(usuario) } : null;
  } catch {
    return null;
  }
}

export function cerrarSesion() {
  try {
    localStorage.removeItem("aurora_token");
    localStorage.removeItem("aurora_usuario");
    sessionStorage.removeItem("aurora_token");
    sessionStorage.removeItem("aurora_usuario");
  } catch {
    // Sin almacenamiento disponible no hay sesión que cerrar.
  }
  window.dispatchEvent(new Event("aurora-sesion"));
}

export function actualizarUsuarioSesion(usuarioActualizado) {
  [localStorage, sessionStorage].forEach((almacenamiento) => {
    const usuario = almacenamiento.getItem("aurora_usuario");
    if (usuario) almacenamiento.setItem("aurora_usuario", JSON.stringify({ ...JSON.parse(usuario), ...usuarioActualizado }));
  });
  window.dispatchEvent(new Event("aurora-sesion"));
}
