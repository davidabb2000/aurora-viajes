/** Página a la que lleva cada rol tras iniciar sesión: todos tienen su panel (el del cliente muestra solo lo suyo). */
export const inicioDeRol = () => "/panel";

export const esPersonal = (usuario) => usuario?.rol === "administrador" || usuario?.rol === "empleado";
