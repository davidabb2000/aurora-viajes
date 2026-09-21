import { useState } from "react";
import { Link } from "react-router-dom";
import AuthShell from "../components/auth/AuthShell";
import Input from "../components/Input";
import Button from "../components/Button";
import { validarCorreo } from "../utils/validaciones";
import { solicitar } from "../utils/api";

/**
 * Primer paso de la recuperación: se pide el correo y siempre se responde lo mismo, exista o no la cuenta,
 * para que la página no sirva para averiguar qué correos están registrados.
 */
function RecuperarContrasena() {
  const [correo, setCorreo] = useState("");
  const [error, setError] = useState("");
  const [tocado, setTocado] = useState(false);
  const [estado, setEstado] = useState("formulario"); // "formulario" | "enviado"
  const [cargando, setCargando] = useState(false);
  const [mensajeError, setMensajeError] = useState("");

  const enviar = async (evento) => {
    evento.preventDefault();
    setTocado(true);
    const problema = validarCorreo(correo);
    setError(problema);
    if (problema) return;
    setCargando(true);
    setMensajeError("");
    try {
      await solicitar("/auth/recuperar", { method: "POST", body: JSON.stringify({ correo: correo.trim() }) });
      setEstado("enviado");
    } catch (requestError) {
      setMensajeError(requestError.message);
    } finally {
      setCargando(false);
    }
  };

  if (estado === "enviado") {
    return (
      <AuthShell
        etiqueta="Revisa tu correo"
        titulo="Te enviamos las instrucciones"
        pie={
          <Link to="/login" className="font-semibold text-primario hover:underline">
            Volver al inicio de sesión
          </Link>
        }
      >
        <div className="flex flex-col gap-4 text-sm leading-relaxed text-texto-suave" role="status">
          <p>
            Si <strong className="text-texto">{correo.trim()}</strong> está registrado, en unos minutos recibirás un correo con un enlace para crear una nueva contraseña.
          </p>
          <ul className="vidrio-sutil space-y-1.5 rounded-xl px-4 py-3 text-xs">
            <li>· El enlace vence en 1 hora y solo se puede usar una vez.</li>
            <li>· Si no lo ves, revisa la carpeta de correo no deseado.</li>
            <li>· Por seguridad, no confirmamos si un correo tiene cuenta.</li>
          </ul>
          <button type="button" onClick={() => setEstado("formulario")} className="self-start font-semibold text-primario hover:underline">
            Usar otro correo
          </button>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      etiqueta="Recupera tu acceso"
      titulo="¿Olvidaste tu contraseña?"
      subtitulo="Escribe el correo de tu cuenta y te enviaremos un enlace para crear una nueva."
      pie={
        <Link to="/login" className="font-semibold text-primario hover:underline">
          ← Volver al inicio de sesión
        </Link>
      }
    >
      <form className="flex flex-col gap-5" onSubmit={enviar} noValidate>
        <Input
          label="Correo electrónico"
          name="correo"
          type="email"
          value={correo}
          onChange={(evento) => {
            setCorreo(evento.target.value);
            if (tocado) setError(validarCorreo(evento.target.value));
          }}
          onBlur={() => {
            setTocado(true);
            setError(validarCorreo(correo));
          }}
          error={tocado ? error : ""}
          required
          placeholder="tucorreo@ejemplo.com"
          autoComplete="email"
          autoFocus
        />
        <Button type="submit" className="w-full" disabled={cargando}>
          {cargando ? "Enviando..." : "Enviar enlace"}
        </Button>
        {mensajeError && (
          <p role="alert" className="rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm font-medium text-red-700 backdrop-blur-sm">
            {mensajeError}
          </p>
        )}
      </form>
    </AuthShell>
  );
}

export default RecuperarContrasena;
