import { useState } from "react";
import Modal from "./Modal";
import Input from "./Input";
import Select from "./Select";
import Button from "./Button";
import {
  validarNombre,
  validarCorreo,
  validarTipoDocumento,
  validarDocumento,
  validarDireccion,
  validarTelefono,
  validarContrasena,
  validarConfirmacionContrasena,
} from "../utils/validaciones";
import { solicitar } from "../utils/api";

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
};

function validarCampo(nombre, valores) {
  switch (nombre) {
    case "nombre":
      return validarNombre(valores.nombre, "El nombre");
    case "apellido":
      return validarNombre(valores.apellido, "El apellido");
    case "tipoDocumento":
      return validarTipoDocumento(valores.tipoDocumento);
    case "numeroDocumento":
      return validarDocumento(valores.numeroDocumento);
    case "direccion":
      return validarDireccion(valores.direccion);
    case "telefono":
      return validarTelefono(valores.telefono);
    case "correo":
      return validarCorreo(valores.correo);
    case "contrasena":
      return validarContrasena(valores.contrasena);
    case "confirmarContrasena":
      return validarConfirmacionContrasena(valores.confirmarContrasena, valores.contrasena);
    default:
      return "";
  }
}

/**
 * Modal de registro de clientes. Independiente del Login, se abre/cierra
 * mediante las props `abierto` y `alCerrar`.
 */
function RegisterModal({ abierto, alCerrar }) {
  const [valores, setValores] = useState(VALORES_INICIALES);
  const [errores, setErrores] = useState({});
  const [tocados, setTocados] = useState({});
  const [registrado, setRegistrado] = useState(false);
  const [mensajeError, setMensajeError] = useState("");
  const [cargando, setCargando] = useState(false);

  const manejarCambio = (evento) => {
    const { name, value } = evento.target;
    const nuevosValores = { ...valores, [name]: value };
    setValores(nuevosValores);

    if (tocados[name]) {
      setErrores((prev) => ({ ...prev, [name]: validarCampo(name, nuevosValores) }));
    }
    // La confirmación depende de la contraseña: revalidar si ya fue tocada.
    if (name === "contrasena" && tocados.confirmarContrasena) {
      setErrores((prev) => ({
        ...prev,
        confirmarContrasena: validarConfirmacionContrasena(
          nuevosValores.confirmarContrasena,
          nuevosValores.contrasena
        ),
      }));
    }
  };

  const manejarBlur = (evento) => {
    const { name } = evento.target;
    setTocados((prev) => ({ ...prev, [name]: true }));
    setErrores((prev) => ({ ...prev, [name]: validarCampo(name, valores) }));
  };

  const cerrarYReiniciar = () => {
    setValores(VALORES_INICIALES);
    setErrores({});
    setTocados({});
    setRegistrado(false);
    setMensajeError("");
    alCerrar();
  };

  const manejarEnvio = async (evento) => {
    evento.preventDefault();

    const camposNuevosErrores = {};
    Object.keys(valores).forEach((campo) => {
      camposNuevosErrores[campo] = validarCampo(campo, valores);
    });
    setErrores(camposNuevosErrores);
    setTocados(
      Object.keys(valores).reduce((acc, campo) => ({ ...acc, [campo]: true }), {})
    );

    const hayErrores = Object.values(camposNuevosErrores).some(Boolean);
    if (hayErrores) return;
    setMensajeError("");
    setCargando(true);
    try {
      await solicitar("/usuarios/registro", {
        method: "POST",
        body: JSON.stringify(valores),
      });
      setRegistrado(true);
    } catch (error) {
      setMensajeError(error.message);
    } finally {
      setCargando(false);
    }
  };

  return (
    <Modal abierto={abierto} alCerrar={cerrarYReiniciar} titulo="Crear una cuenta">
      {registrado ? (
        <div className="flex flex-col items-center gap-4 py-4 text-center">
          <p className="text-2xl">✅</p>
          <p className="text-sm text-texto-suave">
            ¡Listo, <span className="font-semibold text-texto">{valores.nombre}</span>! Tu
            cuenta fue creada correctamente. Ya puedes iniciar sesión.
          </p>
          <Button onClick={cerrarYReiniciar}>Ir a iniciar sesión</Button>
        </div>
      ) : (
        <form className="flex flex-col gap-4" onSubmit={manejarEnvio} noValidate>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              label="Nombre"
              name="nombre"
              value={valores.nombre}
              onChange={manejarCambio}
              onBlur={manejarBlur}
              error={tocados.nombre ? errores.nombre : ""}
              required
              maxLength={40}
              placeholder="Ana (máx. 40 caracteres)"
            />
            <Input
              label="Apellido"
              name="apellido"
              value={valores.apellido}
              onChange={manejarCambio}
              onBlur={manejarBlur}
              error={tocados.apellido ? errores.apellido : ""}
              required
              maxLength={40}
              placeholder="Gómez (máx. 40 caracteres)"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Select
              label="Tipo de documento"
              name="tipoDocumento"
              value={valores.tipoDocumento}
              onChange={manejarCambio}
              onBlur={manejarBlur}
              error={tocados.tipoDocumento ? errores.tipoDocumento : ""}
              options={TIPOS_DOCUMENTO}
              required
            />
            <Input
              label="Número de documento"
              name="numeroDocumento"
              value={valores.numeroDocumento}
              onChange={manejarCambio}
              onBlur={manejarBlur}
              error={tocados.numeroDocumento ? errores.numeroDocumento : ""}
              required
              maxLength={12}
              placeholder="1000000000 (máx. 12 dígitos)"
            />
          </div>

          <Input
            label="Dirección"
            name="direccion"
            value={valores.direccion}
            onChange={manejarCambio}
            onBlur={manejarBlur}
            error={tocados.direccion ? errores.direccion : ""}
            required
            maxLength={80}
            placeholder="Calle 10 # 20-30 (máx. 80 caracteres)"
          />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              label="Teléfono"
              name="telefono"
              value={valores.telefono}
              onChange={manejarCambio}
              onBlur={manejarBlur}
              error={tocados.telefono ? errores.telefono : ""}
              required
              maxLength={10}
              placeholder="3000000000 (máx. 10 dígitos)"
            />
            <Input
              label="Correo electrónico"
              name="correo"
              type="email"
              value={valores.correo}
              onChange={manejarCambio}
              onBlur={manejarBlur}
              error={tocados.correo ? errores.correo : ""}
              required
              maxLength={60}
              placeholder="tucorreo@ejemplo.com (máx. 60 caracteres)"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              label="Contraseña"
              name="contrasena"
              type="password"
              value={valores.contrasena}
              onChange={manejarCambio}
              onBlur={manejarBlur}
              error={tocados.contrasena ? errores.contrasena : ""}
              required
              maxLength={20}
              placeholder="Mín. 8, máx. 20 caracteres"
            />
            <Input
              label="Confirmar contraseña"
              name="confirmarContrasena"
              type="password"
              value={valores.confirmarContrasena}
              onChange={manejarCambio}
              onBlur={manejarBlur}
              error={tocados.confirmarContrasena ? errores.confirmarContrasena : ""}
              required
              maxLength={20}
              placeholder="Repite la contraseña (máx. 20 caracteres)"
            />
          </div>

          <p className="vidrio-sutil rounded-xl px-4 py-3 text-xs leading-relaxed text-texto-suave">
            La contraseña debe tener entre 8 y 20 caracteres, con al menos una
            mayúscula, una minúscula, un número y un carácter especial.
          </p>

          <div className="mt-2 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Button type="button" variant="secundario" onClick={cerrarYReiniciar}>
              Cancelar
            </Button>
            <Button type="submit" disabled={cargando}>{cargando ? "Creando..." : "Crear cuenta"}</Button>
          </div>
          {mensajeError && <p className="rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm font-medium text-red-700 backdrop-blur-sm">{mensajeError}</p>}
        </form>
      )}
    </Modal>
  );
}

export default RegisterModal;
