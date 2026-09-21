import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import AuthShell from "../components/auth/AuthShell";
import IndicadorContrasena from "../components/auth/IndicadorContrasena";
import Input from "../components/Input";
import Button from "../components/Button";
import { LONGITUD_MAXIMA_CONTRASENA, validarConfirmacionContrasena, validarContrasena, validarRequerido } from "../utils/validaciones";
import { solicitar } from "../utils/api";
import { useAuth } from "../context/useAuth";
import { inicioDeRol } from "../utils/rutas";

/**
 * Cambio de contraseña con la sesión abierta. Es obligatorio cuando la cuenta tiene una clave provisional
 * (la que puso un administrador, o la de ejemplo del primer arranque): hasta cambiarla la API no responde
 * a nada más. Pide la actual, para que un token robado no baste para adueñarse de la cuenta.
 */
function CambiarContrasena() {
  const { sesion, renovarSesion } = useAuth();
  const navigate = useNavigate();
  const [valores, setValores] = useState({ contrasenaActual: "", nuevaContrasena: "", confirmarContrasena: "" });
  const [errores, setErrores] = useState({});
  const [mostrar, setMostrar] = useState(false);
  const [mensajeError, setMensajeError] = useState("");
  const [cargando, setCargando] = useState(false);

  if (!sesion) return <Navigate to="/login" replace />;
  const obligatorio = Boolean(sesion.usuario.debeCambiarContrasena);
  const contexto = { correo: sesion.usuario.correo, nombre: sesion.usuario.nombre, apellido: sesion.usuario.apellido };

  const validar = (nombre, todos) => {
    if (nombre === "contrasenaActual") return validarRequerido(todos.contrasenaActual);
    if (nombre === "nuevaContrasena") {
      return todos.nuevaContrasena === todos.contrasenaActual && todos.nuevaContrasena ? "La nueva contraseña debe ser distinta de la actual." : validarContrasena(todos.nuevaContrasena, contexto);
    }
    return validarConfirmacionContrasena(todos.confirmarContrasena, todos.nuevaContrasena);
  };

  const cambiar = (evento) => {
    const { name, value } = evento.target;
    const nuevos = { ...valores, [name]: value };
    setValores(nuevos);
    setErrores((actual) => Object.fromEntries(Object.keys(actual).map((campo) => [campo, validar(campo, nuevos)])));
  };

  const enviar = async (evento) => {
    evento.preventDefault();
    const nuevos = Object.fromEntries(Object.keys(valores).map((campo) => [campo, validar(campo, valores)]));
    setErrores(nuevos);
    if (Object.values(nuevos).some(Boolean)) return;
    setCargando(true);
    setMensajeError("");
    try {
      const datos = await solicitar("/auth/cambiar-contrasena", {
        method: "POST",
        body: JSON.stringify({ contrasenaActual: valores.contrasenaActual, nuevaContrasena: valores.nuevaContrasena }),
      });
      // El cambio cierra las demás sesiones y el servidor devuelve un token nuevo para esta.
      renovarSesion({ token: datos.token, usuario: datos.usuario });
      navigate(inicioDeRol(datos.usuario.rol), { replace: true });
    } catch (error) {
      setMensajeError(error.message);
      setCargando(false);
    }
  };

  return (
    <AuthShell
      etiqueta={obligatorio ? "Un paso más" : "Tu cuenta"}
      titulo={obligatorio ? "Crea tu contraseña" : "Cambiar contraseña"}
      subtitulo={
        obligatorio
          ? "Tu cuenta tiene una contraseña provisional. Elige una propia para poder continuar."
          : "Al cambiarla cerraremos tus otras sesiones abiertas."
      }
      pie={!obligatorio && <Link to={inicioDeRol(sesion.usuario.rol)} className="font-semibold text-primario hover:underline">← Volver</Link>}
    >
      <form className="flex flex-col gap-5" onSubmit={enviar} noValidate>
        <Input
          label={obligatorio ? "Contraseña provisional" : "Contraseña actual"}
          name="contrasenaActual"
          type={mostrar ? "text" : "password"}
          value={valores.contrasenaActual}
          onChange={cambiar}
          error={errores.contrasenaActual}
          required
          maxLength={LONGITUD_MAXIMA_CONTRASENA}
          autoComplete="current-password"
          autoFocus
        />
        <Input
          label="Nueva contraseña"
          name="nuevaContrasena"
          type={mostrar ? "text" : "password"}
          value={valores.nuevaContrasena}
          onChange={cambiar}
          error={errores.nuevaContrasena}
          required
          maxLength={LONGITUD_MAXIMA_CONTRASENA}
          autoComplete="new-password"
          botonContrasena
          mostrarContrasena={mostrar}
          cambiarVisibilidad={() => setMostrar((visible) => !visible)}
        />
        <Input
          label="Confirmar nueva contraseña"
          name="confirmarContrasena"
          type={mostrar ? "text" : "password"}
          value={valores.confirmarContrasena}
          onChange={cambiar}
          error={errores.confirmarContrasena}
          required
          maxLength={LONGITUD_MAXIMA_CONTRASENA}
          autoComplete="new-password"
        />
        <IndicadorContrasena valor={valores.nuevaContrasena} contexto={contexto} />
        <Button type="submit" className="w-full" disabled={cargando}>
          {cargando ? "Guardando..." : "Guardar contraseña"}
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

export default CambiarContrasena;
