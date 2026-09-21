import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import AuthShell from "../components/auth/AuthShell";
import Input from "../components/Input";
import Button from "../components/Button";
import { validarCorreo, validarRequerido } from "../utils/validaciones";
import { solicitar } from "../utils/api";
import { useAuth } from "../context/AuthContext";

/**
 * Inicio de sesión de clientes. Al entrar, `SoloInvitados` (en App.jsx) lleva a la página de donde
 * venía o a la del rol; una cuenta con clave provisional va a cambiarla antes que nada.
 */
function Login() {
  const { iniciarSesion } = useAuth();
  const ubicacion = useLocation();
  const [valores, setValores] = useState({ correo: "", contrasena: "" });
  const [errores, setErrores] = useState({});
  const [tocados, setTocados] = useState({});
  const [recordarme, setRecordarme] = useState(false);
  const [mostrarContrasena, setMostrarContrasena] = useState(false);
  const [mensajeError, setMensajeError] = useState("");
  const [cargando, setCargando] = useState(false);

  const validar = (nombre, valor) => (nombre === "correo" ? validarCorreo(valor) : validarRequerido(valor));

  const manejarCambio = (evento) => {
    const { name, value } = evento.target;
    setValores((actual) => ({ ...actual, [name]: value }));
    if (tocados[name]) setErrores((actual) => ({ ...actual, [name]: validar(name, value) }));
  };

  const manejarBlur = (evento) => {
    const { name, value } = evento.target;
    setTocados((actual) => ({ ...actual, [name]: true }));
    setErrores((actual) => ({ ...actual, [name]: validar(name, value) }));
  };

  const manejarEnvio = async (evento) => {
    evento.preventDefault();
    const nuevosErrores = { correo: validar("correo", valores.correo), contrasena: validar("contrasena", valores.contrasena) };
    setErrores(nuevosErrores);
    setTocados({ correo: true, contrasena: true });
    if (Object.values(nuevosErrores).some(Boolean)) return;
    setMensajeError("");
    setCargando(true);
    try {
      const datos = await solicitar("/auth/login", {
        method: "POST",
        body: JSON.stringify({ correo: valores.correo.trim(), contrasena: valores.contrasena }),
      });
      iniciarSesion(datos, recordarme);
    } catch (error) {
      setMensajeError(error.message);
      setCargando(false);
    }
  };

  const estado = ubicacion.state?.desde ? { desde: ubicacion.state.desde } : undefined;

  return (
    <AuthShell
      etiqueta="Bienvenido de vuelta"
      titulo="Inicia sesión"
      subtitulo={ubicacion.state?.desde ? "Inicia sesión para continuar con tu reserva." : "Entra para ver tus reservas y planear tu próximo viaje."}
      pie={
        <>
          ¿No tienes cuenta?{" "}
          <Link to="/registro" state={estado} className="font-semibold text-primario hover:underline">
            Crear una cuenta
          </Link>
          <p className="mt-3 text-xs">
            ¿Eres parte del equipo?{" "}
            <Link to="/acceso-personal" className="font-medium text-primario-suave hover:text-primario hover:underline">
              Acceso del personal
            </Link>
          </p>
        </>
      }
    >
      <form className="flex flex-col gap-5" onSubmit={manejarEnvio} noValidate>
        <Input
          label="Correo electrónico"
          name="correo"
          type="email"
          value={valores.correo}
          onChange={manejarCambio}
          onBlur={manejarBlur}
          error={tocados.correo ? errores.correo : ""}
          required
          placeholder="tucorreo@ejemplo.com"
          autoComplete="email"
          autoFocus
        />
        <Input
          label="Contraseña"
          name="contrasena"
          type={mostrarContrasena ? "text" : "password"}
          value={valores.contrasena}
          onChange={manejarCambio}
          onBlur={manejarBlur}
          error={tocados.contrasena ? errores.contrasena : ""}
          required
          placeholder="Tu contraseña"
          autoComplete="current-password"
          botonContrasena
          mostrarContrasena={mostrarContrasena}
          cambiarVisibilidad={() => setMostrarContrasena((visible) => !visible)}
        />

        <div className="flex items-center justify-between gap-3 text-sm">
          <label className="flex items-center gap-2 text-texto-suave">
            <input
              type="checkbox"
              checked={recordarme}
              onChange={(evento) => setRecordarme(evento.target.checked)}
              className="h-4 w-4 rounded border-primario/12 accent-primario"
            />
            Recordarme en este equipo
          </label>
          <Link to="/recuperar" className="font-medium text-primario-suave hover:text-primario hover:underline">
            ¿Olvidaste tu contraseña?
          </Link>
        </div>

        <Button type="submit" className="w-full" disabled={cargando}>
          {cargando ? "Validando..." : "Iniciar sesión"}
        </Button>
        {mensajeError && (
          <p role="alert" className="rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 text-center text-sm font-medium text-red-700 backdrop-blur-sm">
            {mensajeError}
          </p>
        )}
      </form>
    </AuthShell>
  );
}

export default Login;
