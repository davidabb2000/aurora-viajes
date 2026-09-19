import { useState } from "react";
import { NavLink } from "react-router-dom";
import Input from "../components/Input";
import Button from "../components/Button";
import RecoverPassword from "../components/RecoverPassword";
import RegisterModal from "../components/RegisterModal";
import { validarCorreo, validarRequerido } from "../utils/validaciones";
import { solicitar } from "../utils/api";
import { useAuth } from "../context/AuthContext";

const VALORES_INICIALES = { correo: "", contrasena: "" };

function Login() {
  const { iniciarSesion } = useAuth();
  const [vista, setVista] = useState("login"); // "login" | "recuperar"
  const [registroAbierto, setRegistroAbierto] = useState(false);

  const [valores, setValores] = useState(VALORES_INICIALES);
  const [errores, setErrores] = useState({});
  const [tocados, setTocados] = useState({});
  const [recordarme, setRecordarme] = useState(false);
  const [sesionIniciada, setSesionIniciada] = useState(false);
  const [mensajeError, setMensajeError] = useState("");
  const [cargando, setCargando] = useState(false);
  const [mostrarContrasena, setMostrarContrasena] = useState(false);

  const manejarCambio = (evento) => {
    const { name, value } = evento.target;
    const nuevosValores = { ...valores, [name]: value };
    setValores(nuevosValores);

    if (tocados[name]) {
      const error = name === "correo" ? validarCorreo(value) : validarRequerido(value);
      setErrores((prev) => ({ ...prev, [name]: error }));
    }
  };

  const manejarBlur = (evento) => {
    const { name, value } = evento.target;
    setTocados((prev) => ({ ...prev, [name]: true }));
    const error = name === "correo" ? validarCorreo(value) : validarRequerido(value);
    setErrores((prev) => ({ ...prev, [name]: error }));
  };

  const manejarEnvio = async (evento) => {
    evento.preventDefault();
    const nuevosErrores = {
      correo: validarCorreo(valores.correo),
      contrasena: validarRequerido(valores.contrasena),
    };
    setErrores(nuevosErrores);
    setTocados({ correo: true, contrasena: true });

    const hayErrores = Object.values(nuevosErrores).some(Boolean);
    if (hayErrores) return;
    setMensajeError("");
    setCargando(true);
    try {
      const datos = await solicitar("/auth/login", {
        method: "POST",
        body: JSON.stringify(valores),
      });
      iniciarSesion(datos, recordarme);
      setSesionIniciada(true);
    } catch (error) {
      setMensajeError(error.message);
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-14">
      <div className="vidrio filo-aurora w-full max-w-md rounded-3xl p-7 sm:p-9">
        <NavLink to="/" className="mb-6 flex items-center justify-center gap-2 font-display text-2xl font-bold no-underline">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-acento-suave via-primario-suave to-brillo text-lg text-white shadow-md shadow-primario/25">✦</span>
          <span className="titulo-aurora">Aurora Viajes</span>
        </NavLink>
        <span className="inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/60 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-primario-suave backdrop-blur-sm">
          Bienvenido de vuelta
        </span>
        <h1 className="mb-6 mt-3 font-display text-2xl font-bold sm:text-3xl">
          <span className="titulo-aurora">{vista === "login" ? "Inicia sesión" : "Recuperar contraseña"}</span>
        </h1>

        {vista === "recuperar" ? (
          <RecoverPassword alVolver={() => setVista("login")} />
        ) : sesionIniciada ? (
          <div className="flex flex-col items-center gap-4 py-4 text-center">
            <p className="text-2xl">👋</p>
            <p className="text-sm text-texto-suave">
              ¡Sesión iniciada correctamente con{" "}
              <span className="font-semibold text-texto">{valores.correo}</span>!
            </p>
            <Button
              variant="secundario"
              onClick={() => {
                setSesionIniciada(false);
                setValores(VALORES_INICIALES);
                setTocados({});
              }}
            >
              Cerrar sesión
            </Button>
          </div>
        ) : (
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

            <div className="flex items-center justify-between text-sm">
              <label className="flex items-center gap-2 text-texto-suave">
                <input
                  type="checkbox"
                  checked={recordarme}
                  onChange={(evento) => setRecordarme(evento.target.checked)}
                  className="h-4 w-4 rounded border-white/70 accent-primario"
                />
                Recordarme
              </label>
              <button
                type="button"
                onClick={() => setVista("recuperar")}
                className="font-medium text-primario-suave hover:text-primario hover:underline"
              >
                ¿Olvidaste tu contraseña?
              </button>
            </div>

            <Button type="submit" className="w-full">
              {cargando ? "Validando..." : "Iniciar sesión"}
            </Button>
            {mensajeError && <p className="rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 text-center text-sm font-medium text-red-700 backdrop-blur-sm">{mensajeError}</p>}

            <p className="text-center text-sm text-texto-suave">
              ¿No tienes cuenta?{" "}
              <button
                type="button"
                onClick={() => setRegistroAbierto(true)}
                className="font-semibold text-primario hover:underline"
              >
                Crear una cuenta
              </button>
            </p>
          </form>
        )}
      </div>

      <RegisterModal abierto={registroAbierto} alCerrar={() => setRegistroAbierto(false)} />
    </div>
  );
}

export default Login;
