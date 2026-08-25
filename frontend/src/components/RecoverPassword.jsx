import { useState } from "react";
import Input from "./Input";
import Button from "./Button";
import { validarCorreo } from "../utils/validaciones";
import { solicitar } from "../utils/api";

/**
 * Componente independiente de recuperación de contraseña.
 * Gestiona su propio estado y validaciones mediante Hooks.
 * Prop `alVolver`: callback para regresar al formulario de inicio de sesión.
 */
function RecoverPassword({ alVolver }) {
  const [correo, setCorreo] = useState("");
  const [error, setError] = useState("");
  const [tocado, setTocado] = useState(false);
  const [enviado, setEnviado] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [mensajeError, setMensajeError] = useState("");

  const manejarCambio = (evento) => {
    const valor = evento.target.value;
    setCorreo(valor);
    if (tocado) setError(validarCorreo(valor));
  };

  const manejarBlur = () => {
    setTocado(true);
    setError(validarCorreo(correo));
  };

  const manejarEnvio = async (evento) => {
    evento.preventDefault();
    setTocado(true);
    const errorActual = validarCorreo(correo);
    setError(errorActual);
    if (!errorActual) {
      setCargando(true);
      setMensajeError("");
      try {
        await solicitar("/auth/recuperar", { method: "POST", body: JSON.stringify({ correo }) });
        setEnviado(true);
      } catch (requestError) { setMensajeError(requestError.message); } finally { setCargando(false); }
    }
  };

  if (enviado) {
    return (
      <div className="flex flex-col gap-4 text-center">
        <p className="text-sm leading-relaxed text-texto-suave">
          Si <span className="font-semibold text-texto">{correo}</span> está
          registrado, te enviaremos un enlace para restablecer tu contraseña.
        </p>
        <Button variant="secundario" onClick={alVolver} className="self-center">
          Volver al inicio de sesión
        </Button>
      </div>
    );
  }

  return (
    <form className="flex flex-col gap-5" onSubmit={manejarEnvio} noValidate>
      <p className="text-sm text-texto-suave">
        Ingresa tu correo electrónico y te enviaremos las instrucciones para
        recuperar tu contraseña.
      </p>

      <Input
        label="Correo electrónico"
        name="correo-recuperar"
        type="email"
        value={correo}
        onChange={manejarCambio}
        onBlur={manejarBlur}
        error={tocado ? error : ""}
        required
        placeholder="tucorreo@ejemplo.com"
        autoComplete="email"
      />

      <Button type="submit" className="w-full">
        {cargando ? "Enviando..." : "Recuperar contraseña"}
      </Button>
      {mensajeError && <p className="text-sm text-red-700">{mensajeError}</p>}

      <Button type="button" variant="texto" onClick={alVolver} className="self-center">
        ← Regresar al inicio de sesión
      </Button>
    </form>
  );
}

export default RecoverPassword;
