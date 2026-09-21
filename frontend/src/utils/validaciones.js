// Reglas de los formularios. Repiten las del backend para avisar mientras se escribe; el servidor
// las vuelve a aplicar siempre, así que estas nunca son la única defensa.
export const REGEX_CORREO = /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;
export const REGEX_NOMBRE = /^[A-Za-zÁÉÍÓÚÜáéíóúüÑñ][A-Za-zÁÉÍÓÚÜáéíóúüÑñ '-]*$/;
export const REGEX_SOLO_NUMEROS = /^[0-9]+$/;
export const REGEX_TELEFONO = /^[0-9]{7,10}$/;
export const REGEX_DIRECCION = /^[A-Za-zÁÉÍÓÚÜáéíóúüÑñ0-9#\-.,°\s]+$/;

export const LONGITUD_MINIMA_CONTRASENA = 8;
export const LONGITUD_MAXIMA_CONTRASENA = 128;

export function validarRequerido(valor) {
  return valor && valor.trim().length > 0 ? "" : "Este campo es obligatorio.";
}

export function validarNombre(valor, etiqueta = "El nombre") {
  const limpio = valor.trim().replace(/\s+/g, " ");
  if (!limpio) return "Este campo es obligatorio.";
  if (limpio.length < 2) return `${etiqueta} debe tener al menos 2 caracteres.`;
  if (limpio.length > 40) return `${etiqueta} no puede superar 40 caracteres.`;
  if (!REGEX_NOMBRE.test(limpio)) return `${etiqueta} solo puede tener letras, espacios, apóstrofes y guiones.`;
  return "";
}

export function validarCorreo(valor) {
  const limpio = valor.trim();
  if (!limpio) return "Este campo es obligatorio.";
  if (limpio.length > 60) return "El correo no puede superar 60 caracteres.";
  if (!REGEX_CORREO.test(limpio)) return "Ingresa un correo electrónico válido.";
  return "";
}

export function validarDocumento(valor) {
  if (!valor.trim()) return "Este campo es obligatorio.";
  if (!REGEX_SOLO_NUMEROS.test(valor)) return "El documento solo debe contener números.";
  if (valor.length < 6 || valor.length > 12) return "El documento debe tener entre 6 y 12 dígitos.";
  return "";
}

/** Documento de un pasajero: 5 a 20 letras o números (un pasaporte puede llevar letras, a diferencia del de una cuenta). */
export function validarDocumentoDePasajero(valor) {
  const limpio = valor.trim();
  if (!limpio) return "Este campo es obligatorio.";
  if (!/^[A-Za-z0-9]+$/.test(limpio)) return "Solo letras y números, sin espacios ni guiones.";
  if (limpio.length < 5 || limpio.length > 20) return "Debe tener entre 5 y 20 caracteres.";
  return "";
}

export function validarTelefono(valor) {
  if (!valor.trim()) return "Este campo es obligatorio.";
  if (!REGEX_TELEFONO.test(valor)) return "Ingresa un teléfono válido (7 a 10 dígitos).";
  return "";
}

export function validarDireccion(valor) {
  const limpio = valor.trim().replace(/\s+/g, " ");
  if (!limpio) return "Este campo es obligatorio.";
  if (limpio.length < 5) return "La dirección debe tener al menos 5 caracteres.";
  if (limpio.length > 80) return "La dirección no puede superar 80 caracteres.";
  if (!REGEX_DIRECCION.test(limpio)) return "La dirección contiene caracteres no permitidos.";
  return "";
}

const simplificar = (texto = "") =>
  texto
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");

/**
 * Lista de reglas de contraseña con su estado, para mostrarlas mientras se escribe.
 * `contexto` permite comprobar que la clave no contenga el correo ni el nombre.
 */
export function reglasDeContrasena(valor = "", { correo = "", nombre = "", apellido = "" } = {}) {
  const simple = simplificar(valor);
  const local = simplificar(correo.split("@")[0]);
  const datosPersonales = [local, simplificar(nombre), simplificar(apellido)].filter((dato) => dato.length >= 4);
  return [
    {
      id: "longitud",
      texto: `Entre ${LONGITUD_MINIMA_CONTRASENA} y ${LONGITUD_MAXIMA_CONTRASENA} caracteres`,
      mensaje: `Debe tener entre ${LONGITUD_MINIMA_CONTRASENA} y ${LONGITUD_MAXIMA_CONTRASENA} caracteres.`,
      cumple: valor.length >= LONGITUD_MINIMA_CONTRASENA && valor.length <= LONGITUD_MAXIMA_CONTRASENA,
    },
    {
      id: "mayusculas",
      texto: "Mayúsculas y minúsculas",
      mensaje: "Debe combinar mayúsculas y minúsculas.",
      cumple: /[a-zñáéíóúü]/.test(valor) && /[A-ZÑÁÉÍÓÚÜ]/.test(valor),
    },
    { id: "numero", texto: "Al menos un número", mensaje: "Debe incluir al menos un número.", cumple: /\d/.test(valor) },
    {
      id: "especial",
      texto: "Al menos un carácter especial",
      mensaje: "Debe incluir al menos un carácter especial.",
      cumple: /[^\p{L}\p{N}]/u.test(valor),
    },
    {
      id: "personal",
      texto: "No contiene tu correo ni tu nombre",
      mensaje: "No puede contener tu correo ni tu nombre.",
      cumple: !datosPersonales.some((dato) => simple.includes(dato)),
    },
  ];
}

export function validarContrasena(valor, contexto) {
  if (!valor) return "Este campo es obligatorio.";
  const incumplida = reglasDeContrasena(valor, contexto).find((regla) => !regla.cumple);
  return incumplida ? incumplida.mensaje : "";
}

/** De 0 (vacía) a 4 (muy robusta): cuenta las reglas cumplidas y premia la longitud. */
export function fortalezaDeContrasena(valor = "", contexto) {
  if (!valor) return { puntaje: 0, etiqueta: "" };
  const cumplidas = reglasDeContrasena(valor, contexto).filter((regla) => regla.cumple).length;
  let puntaje = Math.min(cumplidas - 1, 3);
  if (cumplidas === 5 && valor.length >= 12) puntaje = 4;
  puntaje = Math.max(puntaje, 1);
  return { puntaje, etiqueta: ["", "Débil", "Regular", "Buena", "Muy robusta"][puntaje] };
}

export function validarConfirmacionContrasena(valor, contrasena) {
  if (!valor) return "Este campo es obligatorio.";
  if (valor !== contrasena) return "Las contraseñas no coinciden.";
  return "";
}

export function validarTipoDocumento(valor) {
  return valor ? "" : "Selecciona un tipo de documento.";
}
