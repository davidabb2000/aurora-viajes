import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { obtenerSesion, solicitar } from "../utils/api";

function Panel() {
  const sesion = obtenerSesion();
  const [reservas, setReservas] = useState([]);
  const [usuarios, setUsuarios] = useState([]);
  const [vista, setVista] = useState("reservas");
  const [mensaje, setMensaje] = useState("");
  const [cargando, setCargando] = useState(true);
  const [nuevoUsuario, setNuevoUsuario] = useState({ nombre: "", apellido: "", tipoDocumento: "CC", numeroDocumento: "", direccion: "", telefono: "", correo: "", contrasena: "", rol: "cliente" });
  const token = sesion?.token;
  const rol = sesion?.usuario.rol;

  useEffect(() => {
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}` };
    const cargar = async () => {
      try {
        const datos = await solicitar(rol === "cliente" ? "/reservas/mias" : "/reservas", { headers });
        setReservas(datos);
        if (rol === "administrador") setUsuarios(await solicitar("/usuarios", { headers }));
      } catch (error) { setMensaje(error.message); } finally { setCargando(false); }
    };
    cargar();
  }, [token, rol]);

  if (!sesion) return <Navigate to="/login" replace />;
  const headers = { Authorization: `Bearer ${sesion.token}` };
  const esAdmin = sesion.usuario.rol === "administrador";
  const esPersonal = esAdmin || sesion.usuario.rol === "empleado";

  const actualizarEstado = async (id, estado) => {
    try {
      await solicitar(`/reservas/${id}/estado`, { method: "PATCH", headers, body: JSON.stringify({ estado }) });
      setReservas(reservas.map((reserva) => reserva.id === id ? { ...reserva, estado } : reserva));
    } catch (error) { setMensaje(error.message); }
  };
  const cambiarEstadoUsuario = async (usuario) => {
    try {
      await solicitar(`/usuarios/${usuario.id}/estado`, { method: "PATCH", headers, body: JSON.stringify({ activo: !usuario.activo }) });
      setUsuarios(usuarios.map((item) => item.id === usuario.id ? { ...item, activo: !item.activo } : item));
    } catch (error) { setMensaje(error.message); }
  };
  const eliminarUsuario = async (id) => {
    if (!window.confirm("¿Eliminar este usuario?")) return;
    try { await solicitar(`/usuarios/${id}`, { method: "DELETE", headers }); setUsuarios(usuarios.filter((usuario) => usuario.id !== id)); } catch (error) { setMensaje(error.message); }
  };
  const crearUsuario = async (evento) => {
    evento.preventDefault();
    try {
      await solicitar("/usuarios", { method: "POST", headers, body: JSON.stringify(nuevoUsuario) });
      setMensaje("Usuario creado correctamente.");
      setNuevoUsuario({ ...nuevoUsuario, nombre: "", apellido: "", numeroDocumento: "", direccion: "", telefono: "", correo: "", contrasena: "" });
      setUsuarios(await solicitar("/usuarios", { headers }));
    } catch (error) { setMensaje(error.message); }
  };

  return <main className="mx-auto w-[92%] max-w-275 flex-1 py-12 sm:py-16">
    <span className="text-xs font-semibold uppercase tracking-widest text-primario-suave">Panel de {sesion.usuario.rol}</span>
    <h1 className="mt-2 font-display text-4xl font-bold text-primario">Hola, {sesion.usuario.nombre}</h1>
    <p className="mt-3 text-texto-suave">{esAdmin ? "Administra usuarios y supervisa las reservas de Aurora." : sesion.usuario.rol === "empleado" ? "Gestiona las solicitudes de viaje de nuestros clientes." : "Consulta tus reservas y mantén tus datos al día."}</p>
    <div className="mt-8 flex flex-wrap gap-3"><button type="button" onClick={() => setVista("reservas")} className="rounded-md bg-primario px-4 py-2 text-sm font-semibold text-white">Reservas</button>{esAdmin && <button type="button" onClick={() => setVista("usuarios")} className="rounded-md border border-borde px-4 py-2 text-sm font-semibold text-primario">Usuarios</button>}{esAdmin && <button type="button" onClick={() => setVista("crear")} className="rounded-md border border-borde px-4 py-2 text-sm font-semibold text-primario">Agregar usuario</button>}</div>
    {cargando ? <p className="mt-8 text-sm text-texto-suave">Cargando información...</p> : vista === "usuarios" ? <section className="mt-8 overflow-x-auto rounded-lg border border-borde bg-superficie p-6"><h2 className="font-display text-2xl font-bold text-primario">Usuarios registrados</h2><table className="mt-5 w-full min-w-[700px] text-left text-sm"><thead><tr className="border-b border-borde text-texto-suave"><th className="pb-3">Nombre</th><th className="pb-3">Correo</th><th className="pb-3">Rol</th><th className="pb-3">Estado</th><th /></tr></thead><tbody>{usuarios.map((usuario) => <tr key={usuario.id} className="border-b border-borde"><td className="py-3">{usuario.nombre} {usuario.apellido}</td><td>{usuario.correo}</td><td>{usuario.rol}</td><td>{usuario.activo ? "Activo" : "Inactivo"}</td><td className="flex gap-3 py-3 text-right"><button type="button" onClick={() => cambiarEstadoUsuario(usuario)} className="font-semibold text-primario-suave">Cambiar estado</button><button type="button" onClick={() => eliminarUsuario(usuario.id)} className="font-semibold text-red-700">Eliminar</button></td></tr>)}</tbody></table></section> : vista === "crear" ? <form onSubmit={crearUsuario} className="mt-8 max-w-2xl rounded-lg border border-borde bg-superficie p-6"><h2 className="font-display text-2xl font-bold text-primario">Agregar usuario</h2><div className="mt-5 grid gap-4 sm:grid-cols-2">{[["nombre","Nombre"],["apellido","Apellido"],["numeroDocumento","Documento"],["direccion","Dirección"],["telefono","Teléfono"],["correo","Correo"],["contrasena","Contraseña"]].map(([campo, etiqueta]) => <label key={campo} className="text-sm font-semibold text-texto">{etiqueta}<input required type={campo === "contrasena" ? "password" : campo === "correo" ? "email" : "text"} value={nuevoUsuario[campo]} onChange={(evento) => setNuevoUsuario({ ...nuevoUsuario, [campo]: evento.target.value })} className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-2 font-normal outline-none focus:border-primario" /></label>)}<label className="text-sm font-semibold text-texto">Rol<select value={nuevoUsuario.rol} onChange={(evento) => setNuevoUsuario({ ...nuevoUsuario, rol: evento.target.value })} className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-2 font-normal"><option>cliente</option><option>empleado</option><option>administrador</option></select></label></div><button type="submit" className="mt-5 rounded-md bg-primario px-5 py-2.5 font-semibold text-white">Crear usuario</button></form> : <section className="mt-8 rounded-lg border border-borde bg-superficie p-6"><h2 className="font-display text-2xl font-bold text-primario">{esPersonal ? "Solicitudes de viaje" : "Mis reservas"}</h2>{reservas.length === 0 ? <p className="mt-4 text-sm text-texto-suave">Aún no hay reservas para mostrar.</p> : <div className="mt-5 overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead><tr className="border-b border-borde text-texto-suave"><th className="pb-3">{esPersonal ? "Cliente" : "Destino"}</th><th className="pb-3">Salida</th><th className="pb-3">Regreso</th><th className="pb-3">Pasajeros</th><th className="pb-3">Estado</th>{esPersonal && <th />}</tr></thead><tbody>{reservas.map((reserva) => <tr key={reserva.id} className="border-b border-borde"><td className="py-3">{esPersonal ? reserva.cliente : reserva.destino}</td><td>{reserva.fechaSalida}</td><td>{reserva.fechaRegreso}</td><td>{reserva.pasajeros}</td><td className="capitalize">{reserva.estado}</td>{esPersonal && <td><select value={reserva.estado} onChange={(evento) => actualizarEstado(reserva.id, evento.target.value)} className="rounded border border-borde bg-fondo px-2 py-1"><option>pendiente</option><option>confirmada</option><option>cancelada</option></select></td>}</tr>)}</tbody></table></div>}</section>}
    {mensaje && <p className="mt-4 text-sm text-primario">{mensaje}</p>}
  </main>;
}

export default Panel;
