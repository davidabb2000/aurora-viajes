import { useState } from "react";
import { Link } from "react-router-dom";
import AuthShell from "../components/auth/AuthShell";
import { validarCorreo, validarRequerido } from "../utils/validaciones";
import { solicitar } from "../utils/api";
import { useAuth } from "../context/AuthContext";

const CAMPO =
  "w-full rounded-xl border border-white/20 bg-white/10 px-3.5 py-2.5 text-[0.95rem] text-white outline-none backdrop-blur-sm transition placeholder:text-white/40 focus:border-oro focus:bg-white/15 focus:ring-3 focus:ring-oro/25";

/**
 * Acceso del equipo (administradores y empleados). Es una pantalla aparte para que el personal no tenga que
 * pasar por el flujo de clientes, y rechaza las cuentas de cliente sin llegar a abrir una sesión con ellas.
 */
function AccesoPersonal() {
  const { iniciarSesion } = useAuth();
  const [valores, setValores] = useState({ correo: "", contrasena: "" });
  const [errores, setErrores] = useState({});
  const [mostrar, setMostrar] = useState(false);
  const [mensajeError, setMensajeError] = useState("");
  const [cargando, setCargando] = useState(false);

  const cambiar = (evento) => {
    const { name, value } = evento.target;
    setValores((actual) => ({ ...actual, [name]: value }));
    setErrores((actual) => ({ ...actual, [name]: "" }));
  };

  const enviar = async (evento) => {
    evento.preventDefault();
    const nuevos = { correo: validarCorreo(valores.correo), contrasena: validarRequerido(valores.contrasena) };
    setErrores(nuevos);
    if (Object.values(nuevos).some(Boolean)) return;
    setCargando(true);
    setMensajeError("");
    try {
      const datos = await solicitar("/auth/login", { method: "POST", body: JSON.stringify({ correo: valores.correo.trim(), contrasena: valores.contrasena }) });
      if (datos.usuario.rol === "cliente") {
        // No se abre sesión: el token de una cuenta de cliente se descarta sin guardarlo.
        setMensajeError("Esta cuenta es de cliente. Entra desde el inicio de sesión de clientes.");
        setCargando(false);
        return;
      }
      iniciarSesion(datos, false);
    } catch (error) {
      setMensajeError(error.message);
      setCargando(false);
    }
  };

  return (
    <AuthShell
      tema="noche"
      etiqueta="Equipo Aurora"
      titulo="Acceso del personal"
      subtitulo="Panel de administración de reservas, vuelos y catálogo. Solo para administradores y empleados."
      pie={
        <>
          ¿Eres cliente?{" "}
          <Link to="/login" className="font-semibold text-oro hover:underline">
            Inicia sesión aquí
          </Link>
        </>
      }
    >
      <form className="flex flex-col gap-5" onSubmit={enviar} noValidate>
        <label className="flex flex-col gap-1.5 text-sm font-medium text-white">
          Correo del trabajo
          <input name="correo" type="email" value={valores.correo} onChange={cambiar} className={CAMPO} placeholder="nombre@auroraviajes.com" autoComplete="username" autoFocus aria-invalid={Boolean(errores.correo)} />
          {errores.correo && <span className="text-xs font-medium text-acento-suave">{errores.correo}</span>}
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium text-white">
          Contraseña
          <span className="relative block">
            <input name="contrasena" type={mostrar ? "text" : "password"} value={valores.contrasena} onChange={cambiar} className={`${CAMPO} pr-20`} placeholder="Tu contraseña" autoComplete="current-password" aria-invalid={Boolean(errores.contrasena)} />
            <button type="button" onClick={() => setMostrar((visible) => !visible)} className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-oro" aria-label={mostrar ? "Ocultar contraseña" : "Ver contraseña"}>
              {mostrar ? "Ocultar" : "Ver"}
            </button>
          </span>
          {errores.contrasena && <span className="text-xs font-medium text-acento-suave">{errores.contrasena}</span>}
        </label>
        <button type="submit" disabled={cargando} className="boton-acento w-full px-6 py-3 text-sm font-semibold">
          {cargando ? "Validando..." : "Entrar al panel"}
        </button>
        {mensajeError && (
          <p role="alert" className="rounded-xl border border-acento-suave/40 bg-acento/15 px-4 py-3 text-center text-sm font-medium text-acento-suave">
            {mensajeError}
          </p>
        )}
        <p className="text-center text-xs text-white/60">
          ¿Olvidaste tu contraseña?{" "}
          <Link to="/recuperar" className="text-white underline">Recupérala aquí</Link>
        </p>
      </form>
    </AuthShell>
  );
}

export default AccesoPersonal;
