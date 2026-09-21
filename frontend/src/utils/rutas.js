/** Página a la que lleva a cada rol tras iniciar sesión. */
export const inicioDeRol = (rol) => (rol === "cliente" ? "/reservas" : "/panel");

export const esPersonal = (usuario) => usuario?.rol === "administrador" || usuario?.rol === "empleado";
