import { useState } from "react";
import Input from "./Input";
import Button from "./Button";
import { validarCorreo, validarContrasena, validarConfirmacionContrasena } from "../utils/validaciones";
import { solicitar } from "../utils/api";

/**
 * Componente independiente de recuperación de contraseña.
 * Paso 1: solicita el código al backend. Paso 2: define la nueva contraseña.
 * Prop `alVolver`: callback para regresar al formulario de inicio de sesión.
 */
function RecoverPassword({ alVolver }) {
  const [paso, setPaso] = useState("solicitar"); // "solicitar" | "restablecer" | "listo"
  const [correo, setCorreo] = useState("");
  const [error, setError] = useState("");
  const [tocado, setTocado] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [mensajeError, setMensajeError] = useState("");

  const [token, setToken] = useState("");
  const [nuevaContrasena, setNuevaContrasena] = useState("");
  const [confirmarContrasena, setConfirmarContrasena] = useState("");
  const [erroresRestablecer, setErroresRestablecer] = useState({});

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
    if (errorActual) return;
    setCargando(true);
    setMensajeError("");
    try {
      const datos = await solicitar("/auth/recuperar", { method: "POST", body: JSON.stringify({ correo }) });
      if (datos.token) setToken(datos.token);
      setPaso("restablecer");
    } catch (requestError) {
      setMensajeError(requestError.message);
    } finally {
      setCargando(false);
    }
  };

  const manejarCambioRestablecer = (evento) => {
    const { name, value } = evento.target;
    if (name === "token") setToken(value);
    if (name === "nuevaContrasena") {
      setNuevaContrasena(value);
      if (erroresRestablecer.nuevaContrasena) {
        setErroresRestablecer((prev) => ({ ...prev, nuevaContrasena: validarContrasena(value) }));
      }
    }
    if (name === "confirmarContrasena") {
      setConfirmarContrasena(value);
      if (erroresRestablecer.confirmarContrasena) {
        setErroresRestablecer((prev) => ({
          ...prev,
          confirmarContrasena: validarConfirmacionContrasena(value, nuevaContrasena),
        }));
      }
    }
  };

  const manejarEnvioRestablecer = async (evento) => {
    evento.preventDefault();
    const nuevosErrores = {
      nuevaContrasena: validarContrasena(nuevaContrasena),
      confirmarContrasena: validarConfirmacionContrasena(confirmarContrasena, nuevaContrasena),
    };
    setErroresRestablecer(nuevosErrores);
    if (Object.values(nuevosErrores).some(Boolean)) return;
    setCargando(true);
    setMensajeError("");
    try {
      await solicitar("/auth/restablecer", {
        method: "POST",
        body: JSON.stringify({ correo, token, nuevaContrasena }),
      });
      setPaso("listo");
    } catch (requestError) {
      setMensajeError(requestError.message);
    } finally {
      setCargando(false);
    }
  };

  if (paso === "listo") {
    return (
      <div className="flex flex-col gap-4 text-center">
        <p className="text-sm leading-relaxed text-texto-suave">
          Tu contraseña se actualizó correctamente. Ya puedes iniciar sesión con{" "}
          <span className="font-semibold text-texto">{correo}</span>.
        </p>
        <Button variant="secundario" onClick={alVolver} className="self-center">
          Volver al inicio de sesión
        </Button>
      </div>
    );
  }

  if (paso === "restablecer") {
    return (
      <form className="flex flex-col gap-5" onSubmit={manejarEnvioRestablecer} noValidate>
        <p className="text-sm text-texto-suave">
          Ingresa el código de verificación generado para{" "}
          <span className="font-semibold text-texto">{correo}</span> y define tu nueva contraseña.
        </p>

        <Input
          label="Código de verificación"
          name="token"
          value={token}
          onChange={manejarCambioRestablecer}
          required
          placeholder="Pega aquí el código recibido"
        />

        <Input
          label="Nueva contraseña"
          name="nuevaContrasena"
          type="password"
          value={nuevaContrasena}
          onChange={manejarCambioRestablecer}
          error={erroresRestablecer.nuevaContrasena}
          required
          maxLength={20}
          placeholder="Mín. 8, máx. 20 caracteres"
        />

        <Input
          label="Confirmar nueva contraseña"
          name="confirmarContrasena"
          type="password"
          value={confirmarContrasena}
          onChange={manejarCambioRestablecer}
          error={erroresRestablecer.confirmarContrasena}
          required
          maxLength={20}
          placeholder="Repite la nueva contraseña"
        />

        <Button type="submit" className="w-full">
          {cargando ? "Actualizando..." : "Actualizar contraseña"}
        </Button>
        {mensajeError && <p className="text-sm text-red-700">{mensajeError}</p>}

        <Button type="button" variant="texto" onClick={alVolver} className="self-center">
          ← Regresar al inicio de sesión
        </Button>
      </form>
    );
  }

  return (
    <form className="flex flex-col gap-5" onSubmit={manejarEnvio} noValidate>
      <p className="text-sm text-texto-suave">
        Ingresa tu correo electrónico y generaremos un código para recuperar tu contraseña.
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
