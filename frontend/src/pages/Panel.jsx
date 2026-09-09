import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { solicitar } from "../utils/api";
import { useAuth } from "../context/AuthContext";

function Panel() {
  const { sesion } = useAuth();
  const [reservas, setReservas] = useState([]);
  const [usuarios, setUsuarios] = useState([]);
  const [mensajesContacto, setMensajesContacto] = useState([]);
  const [reservaEditando, setReservaEditando] = useState(null);
  const [vista, setVista] = useState("reservas");
  const [mensaje, setMensaje] = useState("");
  const [cargando, setCargando] = useState(true);
  const [nuevoUsuario, setNuevoUsuario] = useState({
    nombre: "",
    apellido: "",
    tipoDocumento: "CC",
    numeroDocumento: "",
    direccion: "",
    telefono: "",
    correo: "",
    contrasena: "",
    rol: "cliente",
  });
  const token = sesion?.token;
  const rol = sesion?.usuario.rol;

  useEffect(() => {
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}` };
    const cargar = async () => {
      try {
        const datos = await solicitar(
          rol === "cliente" ? "/reservas/mias" : "/reservas",
          { headers },
        );
        setReservas(datos);
        if (rol === "administrador") {
          setUsuarios(await solicitar("/usuarios", { headers }));
          setMensajesContacto(await solicitar("/contacto", { headers }));
        }
      } catch (error) {
        setMensaje(error.message);
      } finally {
        setCargando(false);
      }
    };
    cargar();
  }, [token, rol]);

  if (!sesion) return <Navigate to="/login" replace />;
  const headers = { Authorization: `Bearer ${sesion.token}` };
  const esAdmin = sesion.usuario.rol === "administrador";
  const esPersonal = esAdmin || sesion.usuario.rol === "empleado";

  const actualizarEstado = async (id, estado) => {
    try {
      await solicitar(`/reservas/${id}/estado`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ estado }),
      });
      setReservas(
        reservas.map((reserva) =>
          reserva.id === id ? { ...reserva, estado } : reserva,
        ),
      );
    } catch (error) {
      setMensaje(error.message);
    }
  };
  const eliminarReserva = async (id) => {
    if (!window.confirm("¿Eliminar esta solicitud de viaje?")) return;
    try {
      await solicitar(`/reservas/${id}`, { method: "DELETE", headers });
      setReservas(reservas.filter((reserva) => reserva.id !== id));
    } catch (error) {
      setMensaje(error.message);
    }
  };
  const modificarReserva = async (evento) => {
    evento.preventDefault();
    try {
      await solicitar(`/reservas/${reservaEditando.id}`, {
        method: "PUT",
        headers,
        body: JSON.stringify({ ...reservaEditando, pasajeros: Number(reservaEditando.pasajeros) }),
      });
      setReservas(reservas.map((reserva) => reserva.id === reservaEditando.id ? reservaEditando : reserva));
      setReservaEditando(null);
      setMensaje("Solicitud actualizada correctamente.");
    } catch (error) { setMensaje(error.message); }
  };
  const cambiarEstadoUsuario = async (usuario) => {
    try {
      await solicitar(`/usuarios/${usuario.id}/estado`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ activo: !usuario.activo }),
      });
      setUsuarios(
        usuarios.map((item) =>
          item.id === usuario.id ? { ...item, activo: !item.activo } : item,
        ),
      );
    } catch (error) {
      setMensaje(error.message);
    }
  };
  const eliminarUsuario = async (id) => {
    if (!window.confirm("¿Eliminar este usuario?")) return;
    try {
      await solicitar(`/usuarios/${id}`, { method: "DELETE", headers });
      setUsuarios(usuarios.filter((usuario) => usuario.id !== id));
    } catch (error) {
      setMensaje(error.message);
    }
  };
  const crearUsuario = async (evento) => {
    evento.preventDefault();
    try {
      await solicitar("/usuarios", {
        method: "POST",
        headers,
        body: JSON.stringify(nuevoUsuario),
      });
      setMensaje("Usuario creado correctamente.");
      setNuevoUsuario({
        ...nuevoUsuario,
        nombre: "",
        apellido: "",
        numeroDocumento: "",
        direccion: "",
        telefono: "",
        correo: "",
        contrasena: "",
      });
      setUsuarios(await solicitar("/usuarios", { headers }));
    } catch (error) {
      setMensaje(error.message);
    }
  };

  if (vista === "mensajes" && esAdmin)
    return (
      <main className="mx-auto w-[92%] max-w-275 flex-1 py-12 sm:py-16 [&_button]:cursor-pointer">
        <span className="text-xs font-semibold uppercase tracking-widest text-primario-suave">
          Panel de {sesion.usuario.rol}
        </span>
        <h1 className="mt-2 font-display text-4xl font-bold text-primario">
          Mensajes de contacto
        </h1>
        <button
          type="button"
          onClick={() => setVista("reservas")}
          className="mt-6 cursor-pointer rounded-md bg-primario px-4 py-2 text-sm font-semibold text-white"
        >
          Volver al panel
        </button>
        <section className="mt-8 overflow-x-auto rounded-lg border border-borde bg-superficie p-6">
          {mensajesContacto.length ? (
            <table className="w-full min-w-175 text-left text-sm">
              <thead>
                <tr className="border-b border-borde text-texto-suave">
                  <th className="pb-3">Fecha</th>
                  <th className="pb-3">Nombre</th>
                  <th className="pb-3">Correo</th>
                  <th className="pb-3">Mensaje</th>
                </tr>
              </thead>
              <tbody>
                {mensajesContacto.map((item) => (
                  <tr key={item.id} className="border-b border-borde align-top">
                    <td className="whitespace-nowrap py-3">
                      {new Date(item.creadoEn).toLocaleString("es-CO")}
                    </td>
                    <td className="py-3">{item.nombre}</td>
                    <td className="py-3">{item.correo}</td>
                    <td className="max-w-md whitespace-pre-wrap py-3">
                      {item.mensaje}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-texto-suave">
              No hay mensajes de contacto.
            </p>
          )}
        </section>
      </main>
    );

  if (vista === "reservas" && esPersonal)
    return (
      <main className="mx-auto w-[92%] max-w-275 flex-1 py-12 sm:py-16 [&_button]:cursor-pointer">
        <span className="text-xs font-semibold uppercase tracking-widest text-primario-suave">
          Panel de {sesion.usuario.rol}
        </span>
        <h1 className="mt-2 font-display text-4xl font-bold text-primario">
          Hola, {sesion.usuario.nombre}
        </h1>
        <p className="mt-3 text-texto-suave">
          {esPersonal
            ? "Gestiona toda la información de las solicitudes de viaje."
            : "Consulta toda la información de tus reservas."}
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => setVista("reservas")}
            className="cursor-pointer rounded-md bg-primario px-4 py-2 text-sm font-semibold text-white"
          >
            Solicitudes
          </button>
          {esAdmin && (
            <button
              type="button"
              onClick={() => setVista("usuarios")}
              className="cursor-pointer rounded-md border border-borde px-4 py-2 text-sm font-semibold text-primario"
            >
              Usuarios
            </button>
          )}
          {esAdmin && (
            <button
              type="button"
              onClick={() => setVista("mensajes")}
              className="cursor-pointer rounded-md border border-borde px-4 py-2 text-sm font-semibold text-primario"
            >
              Mensajes
            </button>
          )}
          {esAdmin && (
            <button
              type="button"
              onClick={() => setVista("crear")}
              className="cursor-pointer rounded-md border border-borde px-4 py-2 text-sm font-semibold text-primario"
            >
              Agregar usuario
            </button>
          )}
        </div>
        {cargando ? (
          <p className="mt-8 text-sm text-texto-suave">
            Cargando información...
          </p>
        ) : (
          <section className="mt-8 rounded-lg border border-borde bg-superficie p-6">
            <h2 className="font-display text-2xl font-bold text-primario">
              {esPersonal ? "Solicitudes de viaje" : "Mis reservas"}
            </h2>
            {reservas.length === 0 ? (
              <p className="mt-4 text-sm text-texto-suave">
                Aún no hay solicitudes para mostrar.
              </p>
            ) : (
              <div className="mt-5 space-y-4">
                {reservas.map((reserva) => (
                  <article
                    key={reserva.id}
                    className="rounded-md border border-borde p-5"
                  >
                    <div className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">
                          {esPersonal ? "Cliente" : "Destino"}
                        </p>
                        <p className="mt-1 font-semibold text-texto">
                          {esPersonal ? reserva.cliente : reserva.destino}
                        </p>
                      </div>
                      {esPersonal && (
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">
                            Destino
                          </p>
                          <p className="mt-1 text-texto">{reserva.destino}</p>
                        </div>
                      )}
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">
                          Salida
                        </p>
                        <p className="mt-1 text-texto">{reserva.fechaSalida}</p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">
                          Regreso
                        </p>
                        <p className="mt-1 text-texto">
                          {reserva.fechaRegreso}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">
                          Pasajeros
                        </p>
                        <p className="mt-1 text-texto">{reserva.pasajeros}</p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">
                          Pago
                        </p>
                        <p className="mt-1 text-texto">
                          {reserva.estadoPago || "pendiente"}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">
                          Total
                        </p>
                        <p className="mt-1 text-texto">
                          ${Number(reserva.montoTotal || 0).toLocaleString("es-CO")}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">
                          Teléfono de contacto
                        </p>
                        <p className="mt-1 text-texto">
                          {reserva.telefonoContacto || "No registrado"}
                        </p>
                      </div>
                      <div className="sm:col-span-2 lg:col-span-3">
                        <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">
                          Notas
                        </p>
                        <p className="mt-1 whitespace-pre-wrap text-texto">
                          {reserva.notas || "Sin notas"}
                        </p>
                      </div>
                    </div>
                    <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-borde pt-4">
                      <label className="text-sm font-semibold text-texto">
                        Estado
                        <select
                          value={reserva.estado}
                          onChange={(evento) =>
                            actualizarEstado(reserva.id, evento.target.value)
                          }
                          className="ml-2 cursor-pointer rounded border border-borde bg-fondo px-2 py-1 font-normal"
                        >
                          <option value="pendiente">Pendiente</option>
                          <option value="confirmada">Confirmada</option>
                          <option value="cancelada">Cancelada</option>
                        </select>
                      </label>
                      {(esAdmin || rol === "cliente") && (
                        <button
                          type="button"
                          onClick={() => eliminarReserva(reserva.id)}
                          className="cursor-pointer rounded-md border border-red-200 px-3 py-2 text-sm font-semibold text-red-700"
                        >
                          Eliminar solicitud
                        </button>
                      )}
                      {rol === "cliente" && reserva.estadoPago !== "pagado" && (
                        <button
                          type="button"
                          onClick={() => window.location.assign(`/reservas/pago/${reserva.id}`)}
                          className="cursor-pointer rounded-md bg-primario px-3 py-2 text-sm font-semibold text-white"
                        >
                          Ir al pago
                        </button>
                      )}
                      {esPersonal && (
                        <button
                          type="button"
                          onClick={() => setReservaEditando({ ...reserva })}
                          className="cursor-pointer rounded-md border border-borde px-3 py-2 text-sm font-semibold text-primario-suave"
                        >
                          Modificar solicitud
                        </button>
                      )}
                    </div>
                    {reservaEditando?.id === reserva.id && (
                      <form onSubmit={modificarReserva} className="mt-5 grid gap-4 border-t border-borde pt-5 sm:grid-cols-2">
                        <label className="text-sm font-semibold text-texto sm:col-span-2">Destino<input required name="destino" value={reservaEditando.destino} onChange={(evento) => setReservaEditando({ ...reservaEditando, destino: evento.target.value })} className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-2 font-normal" /></label>
                        <label className="text-sm font-semibold text-texto">Fecha de salida<input required type="date" name="fechaSalida" value={reservaEditando.fechaSalida} onChange={(evento) => setReservaEditando({ ...reservaEditando, fechaSalida: evento.target.value })} className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-2 font-normal" /></label>
                        <label className="text-sm font-semibold text-texto">Fecha de regreso<input required type="date" name="fechaRegreso" value={reservaEditando.fechaRegreso} onChange={(evento) => setReservaEditando({ ...reservaEditando, fechaRegreso: evento.target.value })} className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-2 font-normal" /></label>
                        <label className="text-sm font-semibold text-texto">Pasajeros<input required type="number" min="1" max="9" name="pasajeros" value={reservaEditando.pasajeros} onChange={(evento) => setReservaEditando({ ...reservaEditando, pasajeros: evento.target.value })} className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-2 font-normal" /></label>
                        <label className="text-sm font-semibold text-texto">Teléfono de contacto<input required pattern="[0-9]{7,10}" maxLength="10" name="telefonoContacto" value={reservaEditando.telefonoContacto} onChange={(evento) => setReservaEditando({ ...reservaEditando, telefonoContacto: evento.target.value })} className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-2 font-normal" /></label>
                        <label className="text-sm font-semibold text-texto sm:col-span-2">Notas<textarea maxLength="300" name="notas" value={reservaEditando.notas || ""} onChange={(evento) => setReservaEditando({ ...reservaEditando, notas: evento.target.value })} rows="3" className="mt-2 w-full resize-y rounded-md border border-borde bg-fondo px-3 py-2 font-normal" /></label>
                        <div className="flex gap-3 sm:col-span-2"><button type="submit" className="cursor-pointer rounded-md bg-primario px-4 py-2 text-sm font-semibold text-white">Guardar cambios</button><button type="button" onClick={() => setReservaEditando(null)} className="cursor-pointer rounded-md border border-borde px-4 py-2 text-sm font-semibold text-primario">Cancelar</button></div>
                      </form>
                    )}
                  </article>
                ))}
              </div>
            )}
          </section>
        )}
        {mensaje && <p className="mt-4 text-sm text-primario">{mensaje}</p>}
      </main>
    );

  return (
    <main className="mx-auto w-[92%] max-w-275 flex-1 py-12 sm:py-16 [&_button]:cursor-pointer">
      <span className="text-xs font-semibold uppercase tracking-widest text-primario-suave">
        Panel de {sesion.usuario.rol}
      </span>
      <h1 className="mt-2 font-display text-4xl font-bold text-primario">
        Hola, {sesion.usuario.nombre}
      </h1>
      <p className="mt-3 text-texto-suave">
        {esAdmin
          ? "Administra usuarios y supervisa las reservas de Aurora."
          : sesion.usuario.rol === "empleado"
            ? "Gestiona las solicitudes de viaje de nuestros clientes."
            : "Consulta tus reservas y mantén tus datos al día."}
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => setVista("reservas")}
          className="cursor-pointer rounded-md bg-primario px-4 py-2 text-sm font-semibold text-white"
        >
          Reservas
        </button>
        {esAdmin && (
          <button
            type="button"
            onClick={() => setVista("usuarios")}
            className="cursor-pointer rounded-md border border-borde px-4 py-2 text-sm font-semibold text-primario"
          >
            Usuarios
          </button>
        )}
        {esAdmin && (
          <button
            type="button"
            onClick={() => setVista("mensajes")}
            className="cursor-pointer rounded-md border border-borde px-4 py-2 text-sm font-semibold text-primario"
          >
            Mensajes
          </button>
        )}
        {esAdmin && (
          <button
            type="button"
            onClick={() => setVista("crear")}
            className="cursor-pointer rounded-md border border-borde px-4 py-2 text-sm font-semibold text-primario"
          >
            Agregar usuario
          </button>
        )}
      </div>
      {cargando ? (
        <p className="mt-8 text-sm text-texto-suave">Cargando información...</p>
      ) : vista === "usuarios" ? (
        <section className="mt-8 overflow-x-auto rounded-lg border border-borde bg-superficie p-6">
          <h2 className="font-display text-2xl font-bold text-primario">
            Usuarios registrados
          </h2>
          <table className="mt-5 w-full min-w-175 text-left text-sm">
            <thead>
              <tr className="border-b border-borde text-texto-suave">
                <th className="pb-3">Nombre</th>
                <th className="pb-3">Correo</th>
                <th className="pb-3">Rol</th>
                <th className="pb-3">Estado</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {usuarios.map((usuario) => (
                <tr key={usuario.id} className="border-b border-borde">
                  <td className="py-3">
                    {usuario.nombre} {usuario.apellido}
                  </td>
                  <td>{usuario.correo}</td>
                  <td>{usuario.rol}</td>
                  <td>{usuario.activo ? "Activo" : "Inactivo"}</td>
                  <td className="flex gap-3 py-3 text-right">
                    <button
                      type="button"
                      onClick={() => cambiarEstadoUsuario(usuario)}
                      className="font-semibold text-primario-suave"
                    >
                      Cambiar estado
                    </button>
                    <button
                      type="button"
                      onClick={() => eliminarUsuario(usuario.id)}
                      className="font-semibold text-red-700"
                    >
                      Eliminar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : vista === "crear" ? (
        <form
          onSubmit={crearUsuario}
          className="mt-8 max-w-2xl rounded-lg border border-borde bg-superficie p-6"
        >
          <h2 className="font-display text-2xl font-bold text-primario">
            Agregar usuario
          </h2>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            {[
              ["nombre", "Nombre"],
              ["apellido", "Apellido"],
              ["numeroDocumento", "Documento"],
              ["direccion", "Dirección"],
              ["telefono", "Teléfono"],
              ["correo", "Correo"],
              ["contrasena", "Contraseña"],
            ].map(([campo, etiqueta]) => (
              <label key={campo} className="text-sm font-semibold text-texto">
                {etiqueta}
                <input
                  required
                  type={
                    campo === "contrasena"
                      ? "password"
                      : campo === "correo"
                        ? "email"
                        : "text"
                  }
                  value={nuevoUsuario[campo]}
                  onChange={(evento) =>
                    setNuevoUsuario({
                      ...nuevoUsuario,
                      [campo]: evento.target.value,
                    })
                  }
                  className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-2 font-normal outline-none focus:border-primario"
                />
              </label>
            ))}
            <label className="text-sm font-semibold text-texto">
              Rol
              <select
                value={nuevoUsuario.rol}
                onChange={(evento) =>
                  setNuevoUsuario({ ...nuevoUsuario, rol: evento.target.value })
                }
                className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-2 font-normal"
              >
                <option>cliente</option>
                <option>empleado</option>
                <option>administrador</option>
              </select>
            </label>
          </div>
          <button
            type="submit"
            className="mt-5 rounded-md bg-primario px-5 py-2.5 font-semibold text-white"
          >
            Crear usuario
          </button>
        </form>
      ) : (
        <section className="mt-8 rounded-lg border border-borde bg-superficie p-6">
          <h2 className="font-display text-2xl font-bold text-primario">
            {esPersonal ? "Solicitudes de viaje" : "Mis reservas"}
          </h2>
          {reservas.length === 0 ? (
            <p className="mt-4 text-sm text-texto-suave">
              Aún no hay reservas para mostrar.
            </p>
          ) : (
            <div className="mt-5 overflow-x-auto">
              <table className="w-full min-w-175 text-left text-sm">
                <thead>
                  <tr className="border-b border-borde text-texto-suave">
                    <th className="pb-3">
                      {esPersonal ? "Cliente" : "Destino"}
                    </th>
                    <th className="pb-3">Salida</th>
                    <th className="pb-3">Regreso</th>
                    <th className="pb-3">Pasajeros</th>
                    <th className="pb-3">Estado</th>
                    <th className="pb-3">Pago</th>
                    <th className="pb-3">Total</th>
                    <th className="pb-3" />
                    {esPersonal && <th />}
                  </tr>
                </thead>
                <tbody>
                  {reservas.map((reserva) => (
                    <tr key={reserva.id} className="border-b border-borde">
                      <td className="py-3">
                        {esPersonal ? reserva.cliente : reserva.destino}
                      </td>
                      <td>{reserva.fechaSalida}</td>
                      <td>{reserva.fechaRegreso}</td>
                      <td>{reserva.pasajeros}</td>
                      <td className="capitalize">{reserva.estado}</td>
                      <td className="capitalize">{reserva.estadoPago || "pendiente"}</td>
                      <td>${Number(reserva.montoTotal || 0).toLocaleString("es-CO")}</td>
                      <td>
                        {rol === "cliente" && reserva.estadoPago !== "pagado" && (
                          <button
                            type="button"
                            onClick={() => window.location.assign(`/reservas/pago/${reserva.id}`)}
                            className="font-semibold text-primario-suave"
                          >
                            Pagar
                          </button>
                        )}
                      </td>
                      {esPersonal && (
                        <td>
                          <select
                            value={reserva.estado}
                            onChange={(evento) =>
                              actualizarEstado(reserva.id, evento.target.value)
                            }
                            className="rounded border border-borde bg-fondo px-2 py-1"
                          >
                            <option>pendiente</option>
                            <option>confirmada</option>
                            <option>cancelada</option>
                          </select>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
      {mensaje && <p className="mt-4 text-sm text-primario">{mensaje}</p>}
    </main>
  );
}

export default Panel;
