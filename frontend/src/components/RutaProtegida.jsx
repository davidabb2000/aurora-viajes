import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { inicioDeRol } from "../utils/rutas";

/**
 * Exige sesión (y, si se indica, uno de los roles). Sin sesión lleva al login y recuerda a dónde
 * volver; con una clave provisional lleva a cambiarla, porque hasta entonces la API no responde.
 */
export function RutaProtegida({ children, roles }) {
  const { sesion } = useAuth();
  const ubicacion = useLocation();
  if (!sesion) return <Navigate to="/login" state={{ desde: ubicacion.pathname + ubicacion.search }} replace />;
  if (sesion.usuario.debeCambiarContrasena) return <Navigate to="/cambiar-contrasena" replace />;
  if (roles && !roles.includes(sesion.usuario.rol)) return <Navigate to={inicioDeRol(sesion.usuario.rol)} replace />;
  return children;
}

/** Páginas de acceso (login, registro): quien ya tiene sesión va directamente a su espacio. */
export function SoloInvitados({ children }) {
  const { sesion } = useAuth();
  const ubicacion = useLocation();
  if (!sesion) return children;
  if (sesion.usuario.debeCambiarContrasena) return <Navigate to="/cambiar-contrasena" replace />;
  return <Navigate to={ubicacion.state?.desde || inicioDeRol(sesion.usuario.rol)} replace />;
}
