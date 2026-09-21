import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  actualizarUsuarioSesion,
  cerrarSesion as cerrarSesionAlmacenamiento,
  guardarSesion,
  obtenerSesion,
  reemplazarSesion,
  solicitar,
} from "../utils/api";

const AuthContext = createContext(null);

/**
 * Provee la sesión (token + usuario) a toda la app mediante Context,
 * sincronizada con localStorage/sessionStorage entre pestañas.
 */
export function AuthProvider({ children }) {
  const [sesion, setSesion] = useState(obtenerSesion);

  useEffect(() => {
    const actualizar = () => setSesion(obtenerSesion());
    window.addEventListener("aurora-sesion", actualizar);
    // Otra pestaña que abre o cierra sesión avisa por el evento «storage».
    window.addEventListener("storage", actualizar);
    return () => {
      window.removeEventListener("aurora-sesion", actualizar);
      window.removeEventListener("storage", actualizar);
    };
  }, []);

  const iniciarSesion = useCallback((datos, persistir = false) => {
    guardarSesion(datos, persistir);
    setSesion(obtenerSesion());
  }, []);

  /** Cambia el token y el usuario de la sesión abierta sin cambiar dónde se guarda (p. ej. tras cambiar la contraseña). */
  const renovarSesion = useCallback((datos) => {
    reemplazarSesion(datos);
    setSesion(obtenerSesion());
  }, []);

  const cerrarSesion = useCallback(() => {
    cerrarSesionAlmacenamiento();
    setSesion(null);
  }, []);

  /** Invalida los tokens de todos los dispositivos y cierra también esta sesión. */
  const cerrarTodasLasSesiones = useCallback(async () => {
    try {
      await solicitar("/auth/cerrar-sesiones", { method: "POST" });
    } finally {
      cerrarSesionAlmacenamiento();
      setSesion(null);
    }
  }, []);

  const actualizarUsuario = useCallback((usuarioActualizado) => {
    actualizarUsuarioSesion(usuarioActualizado);
    setSesion(obtenerSesion());
  }, []);

  const valor = useMemo(
    () => ({ sesion, iniciarSesion, renovarSesion, cerrarSesion, cerrarTodasLasSesiones, actualizarUsuario }),
    [sesion, iniciarSesion, renovarSesion, cerrarSesion, cerrarTodasLasSesiones, actualizarUsuario],
  );

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const contexto = useContext(AuthContext);
  if (!contexto) throw new Error("useAuth debe usarse dentro de <AuthProvider>.");
  return contexto;
}
