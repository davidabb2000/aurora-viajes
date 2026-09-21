import { createContext, useContext } from "react";

/** El contexto y su hook viven aparte del proveedor (`AuthContext.jsx`) para que ese archivo solo exporte un componente. */
export const ContextoDeSesion = createContext(null);

export function useAuth() {
  const contexto = useContext(ContextoDeSesion);
  if (!contexto) throw new Error("useAuth debe usarse dentro de <AuthProvider>.");
  return contexto;
}
