// Expresiones regulares reutilizadas en los formularios.
export const REGEX_CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
export const REGEX_SOLO_LETRAS = /^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$/;
export const REGEX_SOLO_NUMEROS = /^[0-9]+$/;
export const REGEX_TELEFONO = /^[0-9]{7,10}$/;
export const REGEX_DIRECCION = /^[A-Za-zÁÉÍÓÚáéíóúÑñ0-9#\-.,\s]+$/;
// Mínimo 8 caracteres, al menos una mayúscula, una minúscula, un número y un símbolo.
export const REGEX_CONTRASENA = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,20}$/;

export function validarRequerido(valor) {
  return valor && valor.trim().length > 0 ? "" : "Este campo es obligatorio.";
}

export function validarNombre(valor, etiqueta = "El nombre") {
  if (!valor.trim()) return "Este campo es obligatorio.";
  if (valor.trim().length < 2) return `${etiqueta} debe tener al menos 2 caracteres.`;
  if (valor.trim().length > 40) return `${etiqueta} no puede superar 40 caracteres.`;
  if (!REGEX_SOLO_LETRAS.test(valor)) return `${etiqueta} solo puede contener letras.`;
  return "";
}

export function validarCorreo(valor) {
  if (!valor.trim()) return "Este campo es obligatorio.";
  if (valor.length > 60) return "El correo no puede superar 60 caracteres.";
  if (!REGEX_CORREO.test(valor)) return "Ingresa un correo electrónico válido.";
  return "";
}

export function validarDocumento(valor) {
  if (!valor.trim()) return "Este campo es obligatorio.";
  if (!REGEX_SOLO_NUMEROS.test(valor)) return "El documento solo debe contener números.";
  if (valor.length < 6 || valor.length > 12) return "El documento debe tener entre 6 y 12 dígitos.";
  return "";
}

export function validarTelefono(valor) {
  if (!valor.trim()) return "Este campo es obligatorio.";
  if (!REGEX_TELEFONO.test(valor)) return "Ingresa un teléfono válido (7 a 10 dígitos).";
  return "";
}

export function validarDireccion(valor) {
  if (!valor.trim()) return "Este campo es obligatorio.";
  if (valor.trim().length < 5) return "La dirección debe tener al menos 5 caracteres.";
  if (valor.length > 80) return "La dirección no puede superar 80 caracteres.";
  if (!REGEX_DIRECCION.test(valor)) return "La dirección contiene caracteres no permitidos.";
  return "";
}

export function validarContrasena(valor) {
  if (!valor) return "Este campo es obligatorio.";
  if (valor.length < 8 || valor.length > 20) return "Debe tener entre 8 y 20 caracteres.";
  if (!REGEX_CONTRASENA.test(valor)) {
    return "Debe incluir mayúscula, minúscula, número y un carácter especial.";
  }
  return "";
}

export function validarConfirmacionContrasena(valor, contrasena) {
  if (!valor) return "Este campo es obligatorio.";
  if (valor !== contrasena) return "Las contraseñas no coinciden.";
  return "";
}

export function validarTipoDocumento(valor) {
  return valor ? "" : "Selecciona un tipo de documento.";
}
