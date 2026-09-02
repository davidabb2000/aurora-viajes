import { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  actualizarUsuarioSesion,
  cerrarSesion as cerrarSesionAlmacenamiento,
  guardarSesion,
  obtenerSesion,
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
    return () => window.removeEventListener("aurora-sesion", actualizar);
  }, []);

  const iniciarSesion = useCallback((datos, persistir = false) => {
    guardarSesion(datos, persistir);
    setSesion(obtenerSesion());
  }, []);

  const cerrarSesion = useCallback(() => {
    cerrarSesionAlmacenamiento();
    setSesion(null);
  }, []);

  const actualizarUsuario = useCallback((usuarioActualizado) => {
    actualizarUsuarioSesion(usuarioActualizado);
    setSesion(obtenerSesion());
  }, []);

  return (
    <AuthContext.Provider value={{ sesion, iniciarSesion, cerrarSesion, actualizarUsuario }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const contexto = useContext(AuthContext);
  if (!contexto) throw new Error("useAuth debe usarse dentro de <AuthProvider>.");
  return contexto;
}
