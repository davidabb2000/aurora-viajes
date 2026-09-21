import { useState } from "react";
import IndicadorContrasena from "../../components/auth/IndicadorContrasena";
import Input from "../../components/Input";
import Select from "../../components/Select";
import { BOTON_VIDRIO, CAMPO } from "../../components/reserva/estilos";
import { useAuth } from "../../context/useAuth";
import { solicitar } from "../../utils/api";
import { fecha } from "../../utils/formato";
import {
  LONGITUD_MAXIMA_CONTRASENA,
  validarContrasena,
  validarCorreo,
  validarDireccion,
  validarDocumento,
  validarNombre,
  validarTelefono,
  validarTipoDocumento,
} from "../../utils/validaciones";
import { useCarga } from "../../utils/useCarga";
import { Aviso, EncabezadoDePanel, Paginacion } from "./Encabezado";

const TIPOS_DOCUMENTO = [
  { value: "CC", label: "Cédula de ciudadanía" },
  { value: "TI", label: "Tarjeta de identidad" },
  { value: "CE", label: "Cédula de extranjería" },
  { value: "PA", label: "Pasaporte" },
];
const ROLES = [
  { value: "cliente", label: "Cliente" },
  { value: "empleado", label: "Empleado" },
  { value: "administrador", label: "Administrador" },
];
const VACIO = { nombre: "", apellido: "", tipoDocumento: "CC", numeroDocumento: "", direccion: "", telefono: "", correo: "", contrasena: "", rol: "empleado" };

const VALIDADORES = {
  nombre: (valor) => validarNombre(valor, "El nombre"),
  apellido: (valor) => validarNombre(valor, "El apellido"),
  tipoDocumento: validarTipoDocumento,
  numeroDocumento: validarDocumento,
  direccion: validarDireccion,
  telefono: validarTelefono,
  correo: validarCorreo,
  contrasena: (valor, valores) => validarContrasena(valor, { correo: valores.correo, nombre: valores.nombre, apellido: valores.apellido }),
};

function FormularioDeUsuario({ alCrear }) {
  const [valores, setValores] = useState(VACIO);
  const [errores, setErrores] = useState({});
  const [error, setError] = useState("");
  const [mostrar, setMostrar] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const cambiar = (evento) => {
    const { name, value } = evento.target;
    const nuevos = { ...valores, [name]: value };
    setValores(nuevos);
    setErrores((actual) => Object.fromEntries(Object.keys(actual).map((campo) => [campo, VALIDADORES[campo] ? VALIDADORES[campo](nuevos[campo], nuevos) : ""])));
  };

  const crear = async (evento) => {
    evento.preventDefault();
    const nuevos = Object.fromEntries(Object.entries(VALIDADORES).map(([campo, validar]) => [campo, validar(valores[campo], valores)]));
    setErrores(nuevos);
    if (Object.values(nuevos).some(Boolean)) return;
    setGuardando(true);
    setError("");
    try {
      await solicitar("/usuarios", { method: "POST", body: JSON.stringify({ ...valores, nombre: valores.nombre.trim(), apellido: valores.apellido.trim(), correo: valores.correo.trim() }) });
      setValores(VACIO);
      setErrores({});
      alCrear();
    } catch (requestError) {
      const delServidor = Object.fromEntries((requestError.detalles || []).map((detalle) => [detalle.campo, detalle.problema]));
      setErrores((actual) => ({ ...actual, ...delServidor }));
      setError(requestError.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <form onSubmit={crear} noValidate className="vidrio rounded-3xl p-6 sm:p-8">
      <h2 className="text-2xl text-primario">Agregar usuario</h2>
      <p className="mt-1 text-sm text-texto-suave">Elige una contraseña provisional y compártela con la persona: al entrar por primera vez tendrá que cambiarla.</p>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <Input label="Nombre" name="nombre" value={valores.nombre} onChange={cambiar} error={errores.nombre} required maxLength={40} />
        <Input label="Apellido" name="apellido" value={valores.apellido} onChange={cambiar} error={errores.apellido} required maxLength={40} />
        <Select label="Tipo de documento" name="tipoDocumento" value={valores.tipoDocumento} onChange={cambiar} options={TIPOS_DOCUMENTO} required />
        <Input label="Número de documento" name="numeroDocumento" value={valores.numeroDocumento} onChange={cambiar} error={errores.numeroDocumento} required maxLength={12} inputMode="numeric" />
        <Input label="Correo electrónico" name="correo" type="email" value={valores.correo} onChange={cambiar} error={errores.correo} required maxLength={60} />
        <Input label="Teléfono" name="telefono" value={valores.telefono} onChange={cambiar} error={errores.telefono} required maxLength={10} inputMode="tel" />
        <div className="sm:col-span-2"><Input label="Dirección" name="direccion" value={valores.direccion} onChange={cambiar} error={errores.direccion} required maxLength={80} /></div>
        <Select label="Rol" name="rol" value={valores.rol} onChange={cambiar} options={ROLES} required />
        <Input label="Contraseña provisional" name="contrasena" type={mostrar ? "text" : "password"} value={valores.contrasena} onChange={cambiar} error={errores.contrasena} required maxLength={LONGITUD_MAXIMA_CONTRASENA} autoComplete="new-password" botonContrasena mostrarContrasena={mostrar} cambiarVisibilidad={() => setMostrar((visible) => !visible)} />
        <div className="sm:col-span-2"><IndicadorContrasena valor={valores.contrasena} contexto={{ correo: valores.correo, nombre: valores.nombre, apellido: valores.apellido }} /></div>
      </div>
      {error && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm font-medium text-red-700">{error}</p>}
      <button type="submit" disabled={guardando} className="boton-tinta mt-5 px-6 py-2.5 text-sm font-semibold">{guardando ? "Creando…" : "Crear usuario"}</button>
    </form>
  );
}

function UsuariosPanel() {
  const { sesion } = useAuth();
  const usuarios = useCarga("/usuarios");
  const [busqueda, setBusqueda] = useState("");
  const [rol, setRol] = useState("");
  const [pagina, setPagina] = useState(1);
  const [confirmando, setConfirmando] = useState(null);
  const [aviso, setAviso] = useState({ mensaje: "", tipo: "info" });

  const texto = busqueda.trim().toLowerCase();
  const filtrados = (usuarios.datos ?? []).filter((usuario) => (!rol || usuario.rol === rol) && (!texto || `${usuario.nombre} ${usuario.apellido} ${usuario.correo} ${usuario.numeroDocumento}`.toLowerCase().includes(texto)));
  const avisar = (mensaje, tipo = "info") => setAviso({ mensaje, tipo });

  const ejecutar = async (accion, exito) => {
    setConfirmando(null);
    try {
      await accion();
      avisar(exito);
      usuarios.recargar();
    } catch (error) {
      avisar(error.message, "error");
    }
  };

  return (
    <div className="mx-auto w-[96%] max-w-350 flex-1 py-8 sm:py-12">
      <EncabezadoDePanel etiqueta="Administración" titulo="Usuarios" descripcion="Cuentas de clientes y del personal. Debe quedar siempre al menos un administrador activo." />

      <section className="vidrio mt-8 rounded-3xl p-5 sm:p-6">
        <div className="grid gap-3 md:grid-cols-[1fr_auto]">
          <input type="search" value={busqueda} onChange={(evento) => { setBusqueda(evento.target.value); setPagina(1); }} placeholder="Buscar por nombre, correo o documento" aria-label="Buscar usuarios" className={CAMPO} />
          <select value={rol} onChange={(evento) => { setRol(evento.target.value); setPagina(1); }} aria-label="Filtrar por rol" className={CAMPO}>
            <option value="">Todos los roles</option>
            {ROLES.map((item) => <option key={item.value} value={item.value}>{item.label}s</option>)}
          </select>
        </div>
        <Aviso mensaje={aviso.mensaje} tipo={aviso.tipo} alCerrar={() => avisar("")} />
        <Aviso mensaje={usuarios.error} tipo="error" />

        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-190 text-left text-sm">
            <thead>
              <tr className="border-b border-primario/12 text-texto-suave">
                <th className="pb-3 font-medium">Usuario</th><th className="pb-3 font-medium">Rol</th><th className="pb-3 font-medium">Estado</th><th className="pb-3 font-medium">Alta</th><th className="pb-3" />
              </tr>
            </thead>
            <tbody>
              {filtrados.slice((pagina - 1) * 10, pagina * 10).map((usuario) => {
                const esYo = usuario.id === sesion.usuario.id;
                return (
                  <tr key={usuario.id} className="border-b border-primario/8 align-top">
                    <td className="py-3">
                      <strong className="block text-texto">{usuario.nombre} {usuario.apellido}{esYo && <span className="ml-2 rounded-full bg-oro/60 px-2 py-0.5 text-[0.65rem] font-semibold text-primario">Tú</span>}</strong>
                      <span className="text-xs text-texto-suave">{usuario.correo} · {usuario.tipoDocumento} {usuario.numeroDocumento}</span>
                      {usuario.debeCambiarContrasena && <span className="block text-xs font-medium text-brillo">Aún debe cambiar su contraseña provisional</span>}
                    </td>
                    <td className="py-3">
                      <select
                        value={usuario.rol}
                        disabled={esYo}
                        aria-label={`Rol de ${usuario.nombre}`}
                        onChange={(evento) => ejecutar(() => solicitar(`/usuarios/${usuario.id}`, { method: "PUT", body: JSON.stringify({ rol: evento.target.value }) }), "Rol actualizado; sus sesiones abiertas se cerraron.")}
                        className={`${CAMPO} !w-auto !py-1.5`}
                      >
                        {ROLES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                      </select>
                    </td>
                    <td className="py-3"><span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${usuario.activo ? "bg-primario/8 text-primario" : "bg-arena text-texto-suave"}`}>{usuario.activo ? "Activo" : "Inactivo"}</span></td>
                    <td className="py-3 text-xs text-texto-suave">{usuario.creadoEn ? fecha(usuario.creadoEn.slice(0, 10), { day: "numeric", month: "short", year: "numeric" }) : "—"}</td>
                    <td className="py-3">
                      <div className="flex flex-wrap justify-end gap-2">
                        {!esYo && <button type="button" onClick={() => ejecutar(() => solicitar(`/usuarios/${usuario.id}/estado`, { method: "PATCH", body: JSON.stringify({ activo: !usuario.activo }) }), usuario.activo ? "Cuenta desactivada." : "Cuenta activada.")} className={BOTON_VIDRIO}>{usuario.activo ? "Desactivar" : "Activar"}</button>}
                        {!esYo && confirmando !== usuario.id && <button type="button" onClick={() => setConfirmando(usuario.id)} className="px-3 py-2 text-sm font-medium text-red-700 underline">Eliminar</button>}
                        {confirmando === usuario.id && (
                          <span className="flex items-center gap-2 text-sm text-red-700">¿Eliminar?
                            <button type="button" onClick={() => ejecutar(() => solicitar(`/usuarios/${usuario.id}`, { method: "DELETE" }), "Usuario eliminado.")} className="font-semibold underline">Sí</button>
                            <button type="button" onClick={() => setConfirmando(null)} className="font-semibold">No</button>
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {usuarios.datos === null && usuarios.cargando && <p className="py-4 text-sm text-texto-suave">Cargando usuarios…</p>}
          {usuarios.datos !== null && filtrados.length === 0 && <p className="py-4 text-sm text-texto-suave">No hay usuarios que coincidan.</p>}
        </div>
        <Paginacion pagina={pagina} total={filtrados.length} alCambiar={setPagina} />
      </section>

      <div className="mt-8 max-w-3xl">
        <FormularioDeUsuario alCrear={() => { avisar("Usuario creado. Deberá cambiar su contraseña al entrar."); usuarios.recargar(); }} />
      </div>
    </div>
  );
}

export default UsuariosPanel;
