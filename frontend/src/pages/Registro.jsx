import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import AuthShell from "../components/auth/AuthShell";
import IndicadorContrasena from "../components/auth/IndicadorContrasena";
import Input from "../components/Input";
import Select from "../components/Select";
import Button from "../components/Button";
import {
  LONGITUD_MAXIMA_CONTRASENA,
  validarConfirmacionContrasena,
  validarContrasena,
  validarCorreo,
  validarDireccion,
  validarDocumento,
  validarNombre,
  validarTelefono,
  validarTipoDocumento,
} from "../utils/validaciones";
import { solicitar } from "../utils/api";
import { useAuth } from "../context/AuthContext";

const TIPOS_DOCUMENTO = [
  { value: "CC", label: "Cédula de ciudadanía" },
  { value: "TI", label: "Tarjeta de identidad" },
  { value: "CE", label: "Cédula de extranjería" },
  { value: "PA", label: "Pasaporte" },
];

const VALORES_INICIALES = {
  nombre: "",
  apellido: "",
  tipoDocumento: "",
  numeroDocumento: "",
  direccion: "",
  telefono: "",
  correo: "",
  contrasena: "",
  confirmarContrasena: "",
  aceptaTratamientoDatos: false,
};

const VALIDADORES = {
  nombre: (valor) => validarNombre(valor, "El nombre"),
  apellido: (valor) => validarNombre(valor, "El apellido"),
  tipoDocumento: validarTipoDocumento,
  numeroDocumento: validarDocumento,
  direccion: validarDireccion,
  telefono: validarTelefono,
  correo: validarCorreo,
  contrasena: (valor, valores) => validarContrasena(valor, { correo: valores.correo, nombre: valores.nombre, apellido: valores.apellido }),
  confirmarContrasena: (valor, valores) => validarConfirmacionContrasena(valor, valores.contrasena),
  aceptaTratamientoDatos: (valor) => (valor ? "" : "Debes autorizar el tratamiento de tus datos para crear la cuenta."),
};

function Registro() {
  const { iniciarSesion } = useAuth();
  const ubicacion = useLocation();
  const [valores, setValores] = useState(VALORES_INICIALES);
  const [errores, setErrores] = useState({});
  const [tocados, setTocados] = useState({});
  const [mostrarContrasena, setMostrarContrasena] = useState(false);
  const [mensajeError, setMensajeError] = useState("");
  const [cargando, setCargando] = useState(false);

  const validarCampo = (nombre, todos) => VALIDADORES[nombre](todos[nombre], todos);

  // Al escribir se revalidan los campos ya tocados. La contraseña depende del correo y del nombre, y su
  // confirmación depende de ella, así que un cambio en uno puede corregir o crear un error en otro.
  const DEPENDIENTES = { contrasena: ["confirmarContrasena"], correo: ["contrasena"], nombre: ["contrasena"], apellido: ["contrasena"] };

  const manejarCambio = (evento) => {
    const { name, value, type, checked } = evento.target;
    const nuevos = { ...valores, [name]: type === "checkbox" ? checked : value };
    setValores(nuevos);
    const afectados = [name, ...(DEPENDIENTES[name] || [])].filter((campo) => tocados[campo]);
    if (afectados.length) {
      setErrores((actual) => ({ ...actual, ...Object.fromEntries(afectados.map((campo) => [campo, validarCampo(campo, nuevos)])) }));
    }
  };

  const manejarBlur = (evento) => {
    const { name } = evento.target;
    setTocados((actual) => ({ ...actual, [name]: true }));
    setErrores((actual) => ({ ...actual, [name]: validarCampo(name, valores) }));
  };

  const manejarEnvio = async (evento) => {
    evento.preventDefault();
    const nuevosErrores = Object.fromEntries(Object.keys(VALIDADORES).map((campo) => [campo, validarCampo(campo, valores)]));
    setErrores(nuevosErrores);
    setTocados(Object.fromEntries(Object.keys(VALIDADORES).map((campo) => [campo, true])));
    if (Object.values(nuevosErrores).some(Boolean)) {
      setMensajeError("Revisa los campos marcados en rojo.");
      return;
    }
    setMensajeError("");
    setCargando(true);
    const cuerpo = {
      nombre: valores.nombre.trim(),
      apellido: valores.apellido.trim(),
      tipoDocumento: valores.tipoDocumento,
      numeroDocumento: valores.numeroDocumento,
      direccion: valores.direccion.trim(),
      telefono: valores.telefono,
      correo: valores.correo.trim(),
      contrasena: valores.contrasena,
      aceptaTratamientoDatos: valores.aceptaTratamientoDatos,
    };
    try {
      await solicitar("/usuarios/registro", { method: "POST", body: JSON.stringify(cuerpo) });
      // La cuenta ya existe: se entra directamente, sin obligar a escribir otra vez los mismos datos.
      const sesion = await solicitar("/auth/login", { method: "POST", body: JSON.stringify({ correo: cuerpo.correo, contrasena: cuerpo.contrasena }) });
      iniciarSesion(sesion, false);
    } catch (error) {
      // Cada problema que detectó el servidor se muestra junto a su campo.
      const delServidor = Object.fromEntries((error.detalles || []).filter((detalle) => detalle.campo in VALIDADORES).map((detalle) => [detalle.campo, detalle.problema]));
      if (Object.keys(delServidor).length) {
        setErrores((actual) => ({ ...actual, ...delServidor }));
        setTocados((actual) => ({ ...actual, ...Object.fromEntries(Object.keys(delServidor).map((campo) => [campo, true])) }));
      }
      setMensajeError(error.estado === 409 ? `${error.message} Si ya tienes cuenta, inicia sesión.` : error.message);
      setCargando(false);
    }
  };

  const campo = (nombre) => ({ name: nombre, value: valores[nombre], onChange: manejarCambio, onBlur: manejarBlur, error: tocados[nombre] ? errores[nombre] : "" });
  const estado = ubicacion.state?.desde ? { desde: ubicacion.state.desde } : undefined;

  return (
    <AuthShell
      conBeneficios
      etiqueta="Crea tu cuenta"
      titulo="Empieza a viajar con Aurora"
      subtitulo="Con tu cuenta puedes reservar, pagar y seguir tus viajes. Solo te pediremos lo necesario."
      pie={
        <>
          ¿Ya tienes cuenta?{" "}
          <Link to="/login" state={estado} className="font-semibold text-primario hover:underline">
            Inicia sesión
          </Link>
        </>
      }
    >
      <form className="flex flex-col gap-6" onSubmit={manejarEnvio} noValidate>
        <fieldset className="flex flex-col gap-4">
          <legend className="mb-1 font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-suave">1 · Tus datos</legend>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Nombre" {...campo("nombre")} required maxLength={40} autoComplete="given-name" placeholder="Ana" />
            <Input label="Apellido" {...campo("apellido")} required maxLength={40} autoComplete="family-name" placeholder="Gómez" />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Select label="Tipo de documento" {...campo("tipoDocumento")} options={TIPOS_DOCUMENTO} required />
            <Input label="Número de documento" {...campo("numeroDocumento")} required maxLength={12} inputMode="numeric" placeholder="1000000000" />
          </div>
        </fieldset>

        <fieldset className="flex flex-col gap-4">
          <legend className="mb-1 font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-suave">2 · Cómo contactarte</legend>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Correo electrónico" {...campo("correo")} type="email" required maxLength={60} autoComplete="email" placeholder="tucorreo@ejemplo.com" />
            <Input label="Teléfono" {...campo("telefono")} required maxLength={10} inputMode="tel" autoComplete="tel-national" placeholder="3000000000" />
          </div>
          <Input label="Dirección" {...campo("direccion")} required maxLength={80} autoComplete="street-address" placeholder="Calle 10 # 20-30" />
        </fieldset>

        <fieldset className="flex flex-col gap-4">
          <legend className="mb-1 font-mono text-[0.7rem] uppercase tracking-[0.14em] text-texto-suave">3 · Tu contraseña</legend>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Contraseña"
              {...campo("contrasena")}
              type={mostrarContrasena ? "text" : "password"}
              required
              maxLength={LONGITUD_MAXIMA_CONTRASENA}
              autoComplete="new-password"
              botonContrasena
              mostrarContrasena={mostrarContrasena}
              cambiarVisibilidad={() => setMostrarContrasena((visible) => !visible)}
            />
            <Input
              label="Confirmar contraseña"
              {...campo("confirmarContrasena")}
              type={mostrarContrasena ? "text" : "password"}
              required
              maxLength={LONGITUD_MAXIMA_CONTRASENA}
              autoComplete="new-password"
            />
          </div>
          <IndicadorContrasena valor={valores.contrasena} contexto={{ correo: valores.correo, nombre: valores.nombre, apellido: valores.apellido }} />
        </fieldset>

        <div>
          <label className="flex items-start gap-3 text-sm leading-relaxed text-texto-suave">
            <input
              type="checkbox"
              name="aceptaTratamientoDatos"
              checked={valores.aceptaTratamientoDatos}
              onChange={manejarCambio}
              onBlur={manejarBlur}
              aria-invalid={Boolean(tocados.aceptaTratamientoDatos && errores.aceptaTratamientoDatos)}
              className="mt-1 h-4 w-4 shrink-0 rounded border-primario/12 accent-primario"
            />
            <span>
              Autorizo a Aurora Viajes a usar mis datos personales para gestionar mis reservas y contactarme sobre ellas.
              <span className="text-acento"> *</span>
            </span>
          </label>
          {tocados.aceptaTratamientoDatos && errores.aceptaTratamientoDatos && (
            <p className="mt-1.5 text-xs font-medium text-red-600">{errores.aceptaTratamientoDatos}</p>
          )}
        </div>

        <Button type="submit" className="w-full" disabled={cargando}>
          {cargando ? "Creando tu cuenta..." : "Crear cuenta"}
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

export default Registro;
