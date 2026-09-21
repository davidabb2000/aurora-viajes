import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import AuthShell from "../components/auth/AuthShell";
import IndicadorContrasena from "../components/auth/IndicadorContrasena";
import Input from "../components/Input";
import Button from "../components/Button";
import { LONGITUD_MAXIMA_CONTRASENA, validarConfirmacionContrasena, validarContrasena } from "../utils/validaciones";
import { solicitar } from "../utils/api";

/**
 * Segundo paso de la recuperación: el enlace del correo trae el token en la URL. Se guarda en memoria y se
 * quita de la barra de direcciones al instante, para que no quede en el historial ni se filtre por el
 * encabezado Referer; el servidor lo acepta una sola vez.
 */
function RestablecerContrasena() {
  const navigate = useNavigate();
  const [parametros] = useSearchParams();
  const [token] = useState(() => parametros.get("token") || "");
  const [valores, setValores] = useState({ nuevaContrasena: "", confirmarContrasena: "" });
  const [errores, setErrores] = useState({});
  const [mostrar, setMostrar] = useState(false);
  const [mensajeError, setMensajeError] = useState("");
  const [cargando, setCargando] = useState(false);
  const [listo, setListo] = useState(false);

  useEffect(() => {
    if (token) navigate("/restablecer", { replace: true });
  }, [token, navigate]);

  const validar = (nombre, todos) =>
    nombre === "nuevaContrasena" ? validarContrasena(todos.nuevaContrasena) : validarConfirmacionContrasena(todos.confirmarContrasena, todos.nuevaContrasena);

  const cambiar = (evento) => {
    const { name, value } = evento.target;
    const nuevos = { ...valores, [name]: value };
    setValores(nuevos);
    setErrores((actual) => {
      const siguiente = { ...actual };
      for (const campo of Object.keys(actual)) if (actual[campo] !== undefined) siguiente[campo] = validar(campo, nuevos);
      return siguiente;
    });
  };

  const enviar = async (evento) => {
    evento.preventDefault();
    const nuevos = { nuevaContrasena: validar("nuevaContrasena", valores), confirmarContrasena: validar("confirmarContrasena", valores) };
    setErrores(nuevos);
    if (Object.values(nuevos).some(Boolean)) return;
    setCargando(true);
    setMensajeError("");
    try {
      await solicitar("/auth/restablecer", { method: "POST", body: JSON.stringify({ token, nuevaContrasena: valores.nuevaContrasena }) });
      setListo(true);
    } catch (error) {
      setMensajeError(error.message);
    } finally {
      setCargando(false);
    }
  };

  if (!token && !listo) {
    return (
      <AuthShell
        etiqueta="Enlace no válido"
        titulo="No encontramos tu enlace"
        subtitulo="El enlace para crear una nueva contraseña está incompleto, ya se usó o venció. Pide uno nuevo."
        pie={<Link to="/login" className="font-semibold text-primario hover:underline">Volver al inicio de sesión</Link>}
      >
        <Link to="/recuperar" className="boton-tinta inline-block px-6 py-3 text-sm font-semibold no-underline">
          Pedir un enlace nuevo
        </Link>
      </AuthShell>
    );
  }

  if (listo) {
    return (
      <AuthShell etiqueta="Contraseña actualizada" titulo="¡Listo!" subtitulo="Ya puedes entrar con tu nueva contraseña. Cerramos las sesiones que tuvieras abiertas por seguridad.">
        <Link to="/login" className="boton-tinta inline-block px-6 py-3 text-sm font-semibold no-underline">
          Iniciar sesión
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell etiqueta="Recupera tu acceso" titulo="Crea una nueva contraseña" subtitulo="Elige una contraseña que no uses en otros sitios.">
      <form className="flex flex-col gap-5" onSubmit={enviar} noValidate>
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
          autoFocus
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
        <IndicadorContrasena valor={valores.nuevaContrasena} />
        <Button type="submit" className="w-full" disabled={cargando}>
          {cargando ? "Actualizando..." : "Actualizar contraseña"}
        </Button>
        {mensajeError && (
          <p role="alert" className="rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm font-medium text-red-700 backdrop-blur-sm">
            {mensajeError}{" "}
            <Link to="/recuperar" className="underline">Pedir otro enlace</Link>
          </p>
        )}
      </form>
    </AuthShell>
  );
}

export default RestablecerContrasena;
