import { useEffect, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { solicitar } from "../utils/api";
import { useAuth } from "../context/AuthContext";
import destinosBase from "../data/destinos";

const formatearUbicacion = (destino, pais) => {
  if (!pais) return destino;
  const destinoNormalizado = destino.trim().normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const paisNormalizado = pais.trim().normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  return destinoNormalizado.endsWith(`, ${paisNormalizado}`) ? destino : `${destino}, ${pais}`;
};

const AEROPUERTOS_POR_CIUDAD = {
  Bogotá: { terminales: ["T1"], puertas: ["A01", "A02", "A03", "B01", "B02", "B03", "C01", "C02"] },
  Medellín: { terminales: ["Terminal única"], puertas: ["M01", "M02", "M03", "M04", "M05", "M06"] },
  Cali: { terminales: ["Terminal única"], puertas: ["C01", "C02", "C03", "C04", "C05"] },
  Cartagena: { terminales: ["Terminal única"], puertas: ["K01", "K02", "K03", "K04"] },
  Barranquilla: { terminales: ["Terminal única"], puertas: ["B01", "B02", "B03", "B04"] },
  Lima: { terminales: ["Terminal única"], puertas: ["A01", "B01", "B02", "C01", "C02"] },
  Madrid: { terminales: ["T1", "T2", "T3", "T4", "T4S"], puertas: ["H01", "H02", "J01", "K01", "S01"] },
};

const opcionesAeropuerto = (ciudad) => AEROPUERTOS_POR_CIUDAD[ciudad] || { terminales: ["Terminal única"], puertas: ["G01", "G02", "G03"] };

const vueloInicial = {
  numeroVuelo: "",
  aerolinea: "",
  avion: "",
  origen: "",
  destino: "",
  fechaSalida: "",
  fechaLlegada: "",
  capacidadMaxima: 1,
  puerta: "",
  terminal: "",
  estado: "programado",
  activo: true,
};

const fechaLocal = (fecha) => (fecha ? fecha.slice(0, 16) : "");

function VuelosPanel({ vuelos }) {
  return (
    <main className="mx-auto w-[92%] max-w-275 flex-1 py-12 sm:py-16">
      <span className="text-xs font-semibold uppercase tracking-widest text-primario-suave">
        Panel de vuelos
      </span>
      <h1 className="mt-2 font-display text-4xl font-bold text-primario">
        Vuelos programados
      </h1>
      <section className="mt-8 overflow-x-auto rounded-lg border border-borde bg-superficie p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-2xl font-bold text-primario">Información de vuelos</h2>
          {esAdmin && <span className="text-sm text-texto-suave">Gestión exclusiva de administración</span>}
        </div>
        {vuelos.length === 0 ? (
          <p className="mt-4 text-sm text-texto-suave">No hay vuelos registrados.</p>
        ) : (
          <div className="mt-5 space-y-4">
            {vuelos.map((vuelo) => (
              <article key={vuelo.id} className="rounded-md border border-borde p-5">
                <div className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
                  <div><p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Vuelo</p><p className="mt-1 font-semibold text-texto">{vuelo.numeroVuelo} · {vuelo.aerolinea}</p></div>
                  <div><p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Ruta</p><p className="mt-1 text-texto">{vuelo.origen} → {vuelo.destino}</p></div>
                  <div><p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Salida</p><p className="mt-1 text-texto">{new Date(vuelo.fechaSalida).toLocaleString("es-CO")}</p></div>
                  <div><p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Llegada</p><p className="mt-1 text-texto">{new Date(vuelo.fechaLlegada).toLocaleString("es-CO")}</p></div>
                  <div><p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Avión</p><p className="mt-1 text-texto">{vuelo.avion}</p></div>
                  <div><p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Capacidad máxima</p><p className="mt-1 text-texto">{vuelo.capacidadMaxima} pasajeros</p></div>
                  <div><p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Puerta / terminal</p><p className="mt-1 text-texto">{vuelo.puerta || "-"} / {vuelo.terminal || "-"}</p></div>
                  <div><p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Estado</p><p className="mt-1 capitalize text-texto">{vuelo.estado}</p></div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
      {esAdmin && (
        <form onSubmit={guardar} className="mt-8 rounded-lg border border-borde bg-superficie p-6">
          <h2 className="font-display text-2xl font-bold text-primario">{editando ? "Modificar vuelo" : "Agregar vuelo"}</h2>
          <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[["numeroVuelo", "Número de vuelo"], ["aerolinea", "Aerolínea"], ["avion", "Avión"], ["origen", "Origen"], ["destino", "Destino"], ["puerta", "Puerta"], ["terminal", "Terminal"]].map(([campo, etiqueta]) => (
              <label key={campo} className="text-sm font-semibold text-texto">{etiqueta}<input required={!["puerta", "terminal"].includes(campo)} name={campo} value={(editando || nuevo)[campo]} onChange={(evento) => actualizarCampo(evento, editando ? setEditando : setNuevo)} className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-2 font-normal" /></label>
            ))}
            <label className="text-sm font-semibold text-texto">Salida<input required type="datetime-local" name="fechaSalida" value={(editando || nuevo).fechaSalida} onChange={(evento) => actualizarCampo(evento, editando ? setEditando : setNuevo)} className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-2 font-normal" /></label>
            <label className="text-sm font-semibold text-texto">Llegada<input required type="datetime-local" name="fechaLlegada" value={(editando || nuevo).fechaLlegada} onChange={(evento) => actualizarCampo(evento, editando ? setEditando : setNuevo)} className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-2 font-normal" /></label>
            <label className="text-sm font-semibold text-texto">Capacidad máxima<input required type="number" min="1" max="1000" name="capacidadMaxima" value={(editando || nuevo).capacidadMaxima} onChange={(evento) => actualizarCampo(evento, editando ? setEditando : setNuevo)} className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-2 font-normal" /></label>
            <label className="text-sm font-semibold text-texto">Estado<select name="estado" value={(editando || nuevo).estado} onChange={(evento) => actualizarCampo(evento, editando ? setEditando : setNuevo)} className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-2 font-normal"><option value="programado">Programado</option><option value="abordando">Abordando</option><option value="en_vuelo">En vuelo</option><option value="aterrizado">Aterrizado</option><option value="cancelado">Cancelado</option></select></label>
          </div>
          <label className="mt-4 flex items-center gap-2 text-sm font-semibold text-texto"><input type="checkbox" name="activo" checked={(editando || nuevo).activo} onChange={(evento) => actualizarCampo(evento, editando ? setEditando : setNuevo)} /> Vuelo activo</label>
          <div className="mt-5 flex gap-3"><button type="submit" className="rounded-md bg-primario px-5 py-2.5 font-semibold text-white">{editando ? "Guardar cambios" : "Crear vuelo"}</button>{editando && <button type="button" onClick={() => setEditando(null)} className="rounded-md border border-borde px-5 py-2.5 font-semibold text-primario">Cancelar</button>}</div>
        </form>
      )}
    </main>
  );
}

function PaquetesPanel({ paquetes, destinos, vuelos, hoteles, excursiones, onCrearHotel, onCrearExcursion, onCrearPaquete, onEliminarPaquete }) {
  const [hotel, setHotel] = useState({ nombre: "", ubicacion: "", estrellas: "", precioNoche: "", descripcion: "" });
  const [excursion, setExcursion] = useState({ nombre: "", ubicacion: "", duracionHoras: "", precio: "", descripcion: "" });
  const [paquete, setPaquete] = useState({ nombre: "", destinoId: "", hotelId: "", excursionIds: [], fechaSalida: "", fechaRegreso: "", precioBase: "", vuelo: { aerolinea: "Aurora Airlines", avion: "Airbus A320", origen: "", destino: "", fechaSalida: "", fechaLlegada: "", capacidadMaxima: 180, puerta: "", terminal: "", estado: "programado", activo: true } });
  const ubicaciones = destinos.length
    ? destinos
    : destinosBase.map((destino) => ({ id: destino.id, nombre: destino.titulo, pais: "" }));

  const actualizarRuta = (campo, valor) => {
    const siguiente = { ...paquete.vuelo, [campo]: valor };
    const codigo = `${siguiente.origen.slice(0, 3)}${siguiente.destino.slice(0, 3)}`.toUpperCase();
    const puerta = codigo.length >= 6 ? `${String.fromCharCode(65 + (codigo.charCodeAt(0) % 2))}${((codigo.charCodeAt(0) + codigo.charCodeAt(5)) % 20 + 1).toString().padStart(2, "0")}` : "";
    const terminal = puerta ? puerta.charAt(0) : "";
    setPaquete({ ...paquete, vuelo: { ...siguiente, puerta, terminal } });
  };

  const coincideConDestino = (item) => {
    const destino = ubicaciones.find((actual) => actual.id === Number(paquete.destinoId));
    if (!destino) return false;
    const partes = destino.nombre.split(",").map((parte) => parte.trim().toLowerCase());
    return partes.includes(item.ciudad.trim().toLowerCase()) && partes.includes(item.pais.trim().toLowerCase());
  };

  const datosUbicacion = (ubicacion) => {
    const partes = ubicacion.split(",").map((parte) => parte.trim());
    return { ciudad: partes.shift() || "", pais: partes.join(", ") };
  };

  const enviar = async (evento, tipo) => {
    evento.preventDefault();
    if (tipo === "hotel") { await onCrearHotel({ ...hotel, ...datosUbicacion(hotel.ubicacion), estrellas: Number(hotel.estrellas), precioNoche: Number(hotel.precioNoche) }); setHotel({ nombre: "", ubicacion: "", estrellas: "", precioNoche: "", descripcion: "" }); }
    if (tipo === "excursion") { await onCrearExcursion({ ...excursion, ...datosUbicacion(excursion.ubicacion), duracionHoras: Number(excursion.duracionHoras), precio: Number(excursion.precio) }); setExcursion({ nombre: "", ubicacion: "", duracionHoras: "", precio: "", descripcion: "" }); }
    if (tipo === "paquete") { await onCrearPaquete({ ...paquete, destinoId: Number(paquete.destinoId), hotelId: Number(paquete.hotelId), excursionIds: paquete.excursionIds.map(Number), precioBase: Number(paquete.precioBase), vuelo: { ...paquete.vuelo, capacidadMaxima: Number(paquete.vuelo.capacidadMaxima) } }); }
  };

  return (
    <main className="mx-auto w-[92%] max-w-275 flex-1 py-12 sm:py-16">
      <span className="text-xs font-semibold uppercase tracking-widest text-primario-suave">Catálogo administrable</span>
      <h1 className="mt-2 font-display text-4xl font-bold text-primario">Reservas y experiencias</h1>
      <section className="mt-8 rounded-lg border border-borde bg-superficie p-6">
        <h2 className="font-display text-2xl font-bold text-primario">Crear reserva publicada</h2>
        <p className="mt-2 text-sm text-texto-suave">Conecta un vuelo, hotel y excursiones en una sola opción para el usuario.</p>
        <form onSubmit={(evento) => enviar(evento, "paquete")} className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <input required placeholder="Nombre de la reserva" value={paquete.nombre} onChange={(evento) => setPaquete({ ...paquete, nombre: evento.target.value })} className="rounded-md border border-borde bg-fondo px-3 py-2" />
          <select required value={paquete.destinoId} onChange={(evento) => { const destino = ubicaciones.find((item) => item.id === Number(evento.target.value)); setPaquete({ ...paquete, destinoId: evento.target.value, vuelo: { ...paquete.vuelo, destino: destino?.nombre || "" } }); }} className="rounded-md border border-borde bg-fondo px-3 py-2"><option value="">Destino</option>{ubicaciones.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select>
          <div className="rounded-md border border-borde bg-fondo p-3 sm:col-span-2 lg:col-span-3"><p className="text-sm font-semibold text-texto">Configurar vuelo de esta reserva</p><p className="mt-1 text-xs text-texto-suave">El número, la puerta, la terminal y la capacidad se asignan automáticamente.</p><div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><select required value={paquete.vuelo.aerolinea} onChange={(evento) => setPaquete({ ...paquete, vuelo: { ...paquete.vuelo, aerolinea: evento.target.value } })} className="rounded-md border border-borde bg-white px-3 py-2"><option>Aurora Airlines</option><option>Avianca</option><option>LATAM</option><option>Copa Airlines</option><option>Iberia</option></select><select required value={paquete.vuelo.avion} onChange={(evento) => { const capacidades = { "Airbus A320": 180, "Airbus A330": 300, "Boeing 737": 189, "Boeing 787": 330, "Embraer E195": 132 }; setPaquete({ ...paquete, vuelo: { ...paquete.vuelo, avion: evento.target.value, capacidadMaxima: capacidades[evento.target.value] } }); }} className="rounded-md border border-borde bg-white px-3 py-2"><option>Airbus A320</option><option>Airbus A330</option><option>Boeing 737</option><option>Boeing 787</option><option>Embraer E195</option></select><select required value={paquete.vuelo.origen} onChange={(evento) => actualizarRuta("origen", evento.target.value)} className="rounded-md border border-borde bg-white px-3 py-2"><option value="">Origen</option><option>Bogotá</option><option>Medellín</option><option>Cali</option><option>Cartagena</option><option>Barranquilla</option><option>Lima</option><option>Madrid</option></select><input readOnly placeholder="Destino seleccionado" value={paquete.vuelo.destino} className="rounded-md border border-borde bg-white px-3 py-2" /><select required value={paquete.vuelo.terminal} onChange={(evento) => setPaquete({ ...paquete, vuelo: { ...paquete.vuelo, terminal: evento.target.value } })} className="rounded-md border border-borde bg-white px-3 py-2"><option value="">Terminal</option>{opcionesAeropuerto(paquete.vuelo.origen).terminales.map((item) => <option key={item}>{item}</option>)}</select><select required value={paquete.vuelo.puerta} onChange={(evento) => setPaquete({ ...paquete, vuelo: { ...paquete.vuelo, puerta: evento.target.value } })} className="rounded-md border border-borde bg-white px-3 py-2"><option value="">Puerta</option>{opcionesAeropuerto(paquete.vuelo.origen).puertas.map((item) => <option key={item}>{item}</option>)}</select><input readOnly placeholder="Capacidad automática" value={`${paquete.vuelo.capacidadMaxima} pasajeros`} className="rounded-md border border-borde bg-white px-3 py-2" /><input required type="datetime-local" value={paquete.vuelo.fechaSalida} onChange={(evento) => setPaquete({ ...paquete, fechaSalida: evento.target.value.slice(0, 10), vuelo: { ...paquete.vuelo, fechaSalida: evento.target.value } })} className="rounded-md border border-borde bg-white px-3 py-2" /><input required type="datetime-local" value={paquete.vuelo.fechaLlegada} onChange={(evento) => setPaquete({ ...paquete, vuelo: { ...paquete.vuelo, fechaLlegada: evento.target.value } })} className="rounded-md border border-borde bg-white px-3 py-2" /></div></div>
          <div className="grid gap-3 rounded-md border border-borde bg-fondo p-3 sm:col-span-2"><select required value={paquete.hotelId} onChange={(evento) => setPaquete({ ...paquete, hotelId: evento.target.value })} className="rounded-md border border-borde bg-white px-3 py-2"><option value="">Hotel según destino</option>{hoteles.filter((item) => item.activo && coincideConDestino(item)).map((item) => <option key={item.id} value={item.id}>{item.nombre} · {item.ciudad}, {item.pais}</option>)}</select><div className="grid gap-3 sm:grid-cols-2"><input readOnly value={paquete.fechaSalida} placeholder="Entrada del hotel: fecha de ida" className="rounded-md border border-borde bg-white px-3 py-2" /><input readOnly value={paquete.fechaRegreso} placeholder="Salida del hotel: fecha de regreso" className="rounded-md border border-borde bg-white px-3 py-2" /></div></div>
          <input required type="date" value={paquete.fechaSalida} onChange={(evento) => setPaquete({ ...paquete, fechaSalida: evento.target.value })} className="rounded-md border border-borde bg-fondo px-3 py-2" />
          <input required type="date" value={paquete.fechaRegreso} onChange={(evento) => setPaquete({ ...paquete, fechaRegreso: evento.target.value })} className="rounded-md border border-borde bg-fondo px-3 py-2" />
          <input required type="number" min="0" value={paquete.precioBase} onChange={(evento) => setPaquete({ ...paquete, precioBase: evento.target.value })} placeholder="Precio por pasajero" className="rounded-md border border-borde bg-fondo px-3 py-2" />
          <select multiple value={paquete.excursionIds} onChange={(evento) => setPaquete({ ...paquete, excursionIds: [...evento.target.selectedOptions].map((option) => option.value) })} className="min-h-24 rounded-md border border-borde bg-fondo px-3 py-2"><option disabled>Excursiones según destino</option>{excursiones.filter((item) => item.activo && coincideConDestino(item)).map((item) => <option key={item.id} value={item.id}>{item.nombre} · {item.ciudad}, {item.pais}</option>)}</select>
          <button type="submit" className="rounded-md bg-primario px-4 py-2 font-semibold text-white">Publicar reserva</button>
        </form>
      </section>
      <div className="mt-8 grid gap-8 lg:grid-cols-2">
        <form onSubmit={(evento) => enviar(evento, "hotel")} className="rounded-lg border border-borde bg-superficie p-6"><h2 className="font-display text-2xl font-bold text-primario">Agregar hotel</h2><div className="mt-4 grid gap-3"><input required placeholder="Nombre" value={hotel.nombre} onChange={(evento) => setHotel({ ...hotel, nombre: evento.target.value })} className="rounded-md border border-borde bg-fondo px-3 py-2" /><select required value={hotel.ubicacion} onChange={(evento) => setHotel({ ...hotel, ubicacion: evento.target.value })} className="rounded-md border border-borde bg-fondo px-3 py-2"><option value="">Ubicación de la reserva</option>{ubicaciones.map((destino) => <option key={destino.id} value={destino.nombre}>{destino.nombre}</option>)}</select><input required type="number" min="1" max="5" placeholder="Estrellas (1 a 5)" value={hotel.estrellas} onChange={(evento) => setHotel({ ...hotel, estrellas: evento.target.value })} className="rounded-md border border-borde bg-fondo px-3 py-2" /><input required type="number" min="0" placeholder="Precio por noche" value={hotel.precioNoche} onChange={(evento) => setHotel({ ...hotel, precioNoche: evento.target.value })} className="rounded-md border border-borde bg-fondo px-3 py-2" /></div><button className="mt-4 rounded-md bg-primario px-4 py-2 font-semibold text-white">Guardar hotel</button></form>
        <form onSubmit={(evento) => enviar(evento, "excursion")} className="rounded-lg border border-borde bg-superficie p-6"><h2 className="font-display text-2xl font-bold text-primario">Agregar excursión</h2><div className="mt-4 grid gap-3"><input required placeholder="Nombre" value={excursion.nombre} onChange={(evento) => setExcursion({ ...excursion, nombre: evento.target.value })} className="rounded-md border border-borde bg-fondo px-3 py-2" /><select required value={excursion.ubicacion} onChange={(evento) => setExcursion({ ...excursion, ubicacion: evento.target.value })} className="rounded-md border border-borde bg-fondo px-3 py-2"><option value="">Ubicación de la reserva</option>{ubicaciones.map((destino) => <option key={destino.id} value={destino.nombre}>{destino.nombre}</option>)}</select><input required type="number" min="1" max="48" placeholder="Duración en horas (1 a 48)" value={excursion.duracionHoras} onChange={(evento) => setExcursion({ ...excursion, duracionHoras: evento.target.value })} className="rounded-md border border-borde bg-fondo px-3 py-2" /><input required type="number" min="0" placeholder="Precio" value={excursion.precio} onChange={(evento) => setExcursion({ ...excursion, precio: evento.target.value })} className="rounded-md border border-borde bg-fondo px-3 py-2" /></div><button className="mt-4 rounded-md bg-primario px-4 py-2 font-semibold text-white">Guardar excursión</button></form>
      </div>
      <section className="mt-8 rounded-lg border border-borde bg-superficie p-6"><h2 className="font-display text-2xl font-bold text-primario">Reservas publicadas</h2><div className="mt-5 space-y-3">{paquetes.map((item) => <article key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-borde p-4"><div><p className="font-semibold text-texto">{item.nombre}</p><p className="text-sm text-texto-suave">{item.destino} · {item.vuelo?.numeroVuelo} · {item.hotel?.nombre}</p><p className="text-sm text-texto-suave">{item.excursiones.length} excursión(es) · ${Number(item.precioBase).toLocaleString("es-CO")} por pasajero</p></div><button type="button" onClick={() => onEliminarPaquete(item.id)} className="text-sm font-semibold text-red-700">Desactivar</button></article>)}</div></section>
    </main>
  );
}

function Panel() {
  const { sesion } = useAuth();
  const [parametros] = useSearchParams();
  const [reservas, setReservas] = useState([]);
  const [usuarios, setUsuarios] = useState([]);
  const [mensajesContacto, setMensajesContacto] = useState([]);
  const [vuelos, setVuelos] = useState([]);
  const [hoteles, setHoteles] = useState([]);
  const [excursiones, setExcursiones] = useState([]);
  const [paquetes, setPaquetes] = useState([]);
  const [destinos, setDestinos] = useState([]);
  const [reservaEditando, setReservaEditando] = useState(null);
  const [reservaDetalle, setReservaDetalle] = useState(null);
  const [vista, setVista] = useState(parametros.get("vista") || "reservas");
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
        setVuelos(await solicitar("/vuelos", { headers }));
        if (rol === "administrador") {
          setHoteles(await solicitar("/hoteles", { headers }));
          setExcursiones(await solicitar("/excursiones", { headers }));
          setPaquetes(await solicitar("/paquetes", { headers }));
          setDestinos(await solicitar("/catalogos/destinos"));
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

  useEffect(() => {
    const vistaSolicitada = parametros.get("vista");
    if (vistaSolicitada) setVista(vistaSolicitada);
  }, [parametros]);

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
  const crearVuelo = async (vuelo) => {
    try {
      const creado = await solicitar("/vuelos", { method: "POST", headers, body: JSON.stringify({ ...vuelo, capacidadMaxima: Number(vuelo.capacidadMaxima) }) });
      setVuelos((actuales) => [...actuales, creado].sort((a, b) => a.fechaSalida.localeCompare(b.fechaSalida)));
      setMensaje("Vuelo creado correctamente.");
    } catch (error) { setMensaje(error.message); }
  };
  const actualizarVuelo = async (id, vuelo) => {
    try {
      const actualizado = await solicitar(`/vuelos/${id}`, { method: "PUT", headers, body: JSON.stringify({ ...vuelo, capacidadMaxima: Number(vuelo.capacidadMaxima) }) });
      setVuelos((actuales) => actuales.map((item) => item.id === id ? actualizado : item));
      setMensaje("Vuelo actualizado correctamente.");
    } catch (error) { setMensaje(error.message); }
  };
  const eliminarVuelo = async (id) => {
    if (!window.confirm("¿Eliminar este vuelo?")) return;
    try {
      await solicitar(`/vuelos/${id}`, { method: "DELETE", headers });
      setVuelos((actuales) => actuales.filter((vuelo) => vuelo.id !== id));
    } catch (error) { setMensaje(error.message); }
  };
  const crearHotel = async (hotel) => {
    try { const creado = await solicitar("/hoteles", { method: "POST", headers, body: JSON.stringify(hotel) }); setHoteles((actuales) => [...actuales, creado]); setMensaje("Hotel guardado correctamente."); } catch (error) { setMensaje(error.message); }
  };
  const crearExcursion = async (excursion) => {
    try { const creada = await solicitar("/excursiones", { method: "POST", headers, body: JSON.stringify(excursion) }); setExcursiones((actuales) => [...actuales, creada]); setMensaje("Excursión guardada correctamente."); } catch (error) { setMensaje(error.message); }
  };
  const crearPaquete = async (paquete) => {
    try { const creado = await solicitar("/paquetes", { method: "POST", headers, body: JSON.stringify(paquete) }); setPaquetes((actuales) => [...actuales, creado]); setMensaje("Reserva publicada correctamente."); } catch (error) { setMensaje(error.message); }
  };
  const eliminarPaquete = async (id) => {
    try { await solicitar(`/paquetes/${id}`, { method: "DELETE", headers }); setPaquetes((actuales) => actuales.filter((item) => item.id !== id)); } catch (error) { setMensaje(error.message); }
  };

  if (vista === "vuelos") return <VuelosPanel vuelos={vuelos} esAdmin={esAdmin} onCrear={crearVuelo} onActualizar={actualizarVuelo} onEliminar={eliminarVuelo} />;
  if (vista === "paquetes" && esAdmin) return <PaquetesPanel paquetes={paquetes} destinos={destinos} vuelos={vuelos} hoteles={hoteles} excursiones={excursiones} onCrearHotel={crearHotel} onCrearExcursion={crearExcursion} onCrearPaquete={crearPaquete} onEliminarPaquete={eliminarPaquete} />;

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
                          Vuelo
                        </p>
                        <p className="mt-1 text-texto">
                          {reserva.vuelo ? `${reserva.vuelo.numeroVuelo} · ${reserva.vuelo.aerolinea}` : "Sin vuelo asignado"}
                        </p>
                      </div>
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
                    <details className="mt-5 rounded-md bg-fondo p-4">
                      <summary className="cursor-pointer font-semibold text-primario">
                        Ver información detallada del viaje
                      </summary>
                      <div className="mt-4 grid gap-5 text-sm lg:grid-cols-2">
                        <div>
                          <h3 className="font-semibold text-primario">Paquete y ubicación</h3>
                          <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                            <div><dt className="text-texto-suave">Paquete</dt><dd className="font-semibold text-texto">{reserva.paquete?.nombre || "Sin paquete"}</dd></div>
                            <div><dt className="text-texto-suave">Destino</dt><dd className="font-semibold text-texto">{formatearUbicacion(reserva.destino, reserva.pais)}</dd></div>
                            <div><dt className="text-texto-suave">Fecha de salida</dt><dd className="font-semibold text-texto">{reserva.fechaSalida}</dd></div>
                            <div><dt className="text-texto-suave">Fecha de regreso</dt><dd className="font-semibold text-texto">{reserva.fechaRegreso}</dd></div>
                          </dl>
                        </div>
                        <div>
                          <h3 className="font-semibold text-primario">Vuelo completo</h3>
                          {reserva.vuelo ? (
                            <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                              <div><dt className="text-texto-suave">Número</dt><dd className="font-semibold text-texto">{reserva.vuelo.numeroVuelo}</dd></div>
                              <div><dt className="text-texto-suave">Aerolínea</dt><dd className="font-semibold text-texto">{reserva.vuelo.aerolinea}</dd></div>
                              <div><dt className="text-texto-suave">Avión</dt><dd className="font-semibold text-texto">{reserva.vuelo.avion}</dd></div>
                              <div><dt className="text-texto-suave">Ruta</dt><dd className="font-semibold text-texto">{reserva.vuelo.origen} → {reserva.vuelo.destino}</dd></div>
                              <div><dt className="text-texto-suave">Salida</dt><dd className="font-semibold text-texto">{new Date(reserva.vuelo.fechaSalida).toLocaleString("es-CO")}</dd></div>
                              <div><dt className="text-texto-suave">Llegada</dt><dd className="font-semibold text-texto">{new Date(reserva.vuelo.fechaLlegada).toLocaleString("es-CO")}</dd></div>
                              <div><dt className="text-texto-suave">Terminal / puerta</dt><dd className="font-semibold text-texto">{reserva.vuelo.terminal || "Sin definir"} / {reserva.vuelo.puerta || "Sin definir"}</dd></div>
                              <div><dt className="text-texto-suave">Estado del vuelo</dt><dd className="font-semibold capitalize text-texto">{reserva.vuelo.estado || "Sin definir"}</dd></div>
                            </dl>
                          ) : <p className="mt-3 text-texto-suave">Sin vuelo asignado.</p>}
                        </div>
                        <div>
                          <h3 className="font-semibold text-primario">Hotel</h3>
                          {reserva.paquete?.hotel ? (
                            <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                              <div><dt className="text-texto-suave">Nombre</dt><dd className="font-semibold text-texto">{reserva.paquete.hotel.nombre}</dd></div>
                              <div><dt className="text-texto-suave">Ubicación</dt><dd className="font-semibold text-texto">{reserva.paquete.hotel.ciudad}, {reserva.paquete.hotel.pais}</dd></div>
                              <div><dt className="text-texto-suave">Categoría</dt><dd className="font-semibold text-texto">{reserva.paquete.hotel.estrellas} estrellas</dd></div>
                              <div><dt className="text-texto-suave">Precio por noche</dt><dd className="font-semibold text-texto">${Number(reserva.paquete.hotel.precioNoche || 0).toLocaleString("es-CO")}</dd></div>
                            </dl>
                          ) : <p className="mt-3 text-texto-suave">Sin hotel asociado.</p>}
                        </div>
                        <div>
                          <h3 className="font-semibold text-primario">Excursiones</h3>
                          {reserva.paquete?.excursiones?.length ? (
                            <ul className="mt-3 divide-y divide-borde">
                              {reserva.paquete.excursiones.map((excursion) => (
                                <li key={excursion.id} className="py-2 first:pt-0 last:pb-0">
                                  <strong className="text-texto">{excursion.nombre}</strong>
                                  <span className="block text-texto-suave">{excursion.ciudad}, {excursion.pais} · {excursion.duracionHoras} horas · ${Number(excursion.precio || 0).toLocaleString("es-CO")}</span>
                                </li>
                              ))}
                            </ul>
                          ) : <p className="mt-3 text-texto-suave">Sin excursiones asociadas.</p>}
                        </div>
                        <div className="border-t border-borde pt-4 lg:col-span-2">
                          <div className="grid gap-3 sm:grid-cols-3">
                            <p><span className="block text-texto-suave">Estado de reserva</span><strong className="capitalize text-texto">{reserva.estado || "pendiente"}</strong></p>
                            <p><span className="block text-texto-suave">Estado del pago</span><strong className="capitalize text-texto">{reserva.estadoPago || "pendiente"}</strong></p>
                            <p><span className="block text-texto-suave">Método de pago</span><strong className="capitalize text-texto">{reserva.metodoPago || "Pendiente"}</strong></p>
                          </div>
                        </div>
                      </div>
                    </details>
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
                        <label className="text-sm font-semibold text-texto sm:col-span-2">Vuelo<select required name="vueloId" value={reservaEditando.vueloId || ""} onChange={(evento) => { const vuelo = vuelos.find((item) => item.id === Number(evento.target.value)); setReservaEditando({ ...reservaEditando, vueloId: Number(evento.target.value), origen: vuelo?.origen || "" }); }} className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-2 font-normal"><option value="">Selecciona un vuelo</option>{vuelos.map((vuelo) => <option key={vuelo.id} value={vuelo.id}>{vuelo.numeroVuelo} · {vuelo.origen} → {vuelo.destino} · {new Date(vuelo.fechaSalida).toLocaleString("es-CO")}</option>)}</select></label>
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
        Consulta tus reservas y la información de tus viajes.
      </p>
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
                    <th className="pb-3">Vuelo</th>
                    <th className="pb-3">Regreso</th>
                    <th className="pb-3">Pasajeros</th>
                    <th className="pb-3">Estado</th>
                    <th className="pb-3">Pago</th>
                    <th className="pb-3">Total</th>
                    <th className="pb-3">Información</th>
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
                      <td>{reserva.vuelo?.numeroVuelo || "Sin asignar"}</td>
                      <td>{reserva.fechaRegreso}</td>
                      <td>{reserva.pasajeros}</td>
                      <td className="capitalize">{reserva.estado}</td>
                      <td className="capitalize">{reserva.estadoPago || "pendiente"}</td>
                      <td>${Number(reserva.montoTotal || 0).toLocaleString("es-CO")}</td>
                      <td>
                        <button
                          type="button"
                          onClick={() => setReservaDetalle(reserva)}
                          className="whitespace-nowrap font-semibold text-primario-suave"
                        >
                          Más información
                        </button>
                        {rol === "cliente" && reserva.estadoPago !== "pagado" && (
                          <button
                            type="button"
                            onClick={() => window.location.assign(`/reservas/pago/${reserva.id}`)}
                            className="ml-3 font-semibold text-primario-suave"
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
      {reservaDetalle && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-primario-oscuro/70 p-4" role="presentation" onClick={() => setReservaDetalle(null)}>
          <section className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-lg bg-superficie p-6 shadow-xl sm:p-8" role="dialog" aria-modal="true" aria-labelledby="detalle-reserva-titulo" onClick={(evento) => evento.stopPropagation()}>
            <div className="flex items-start justify-between gap-4 border-b border-borde pb-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-primario-suave">Reserva #{reservaDetalle.id}</p>
                <h2 id="detalle-reserva-titulo" className="mt-1 font-display text-3xl font-bold text-primario">{reservaDetalle.paquete?.nombre || reservaDetalle.destino}</h2>
                <p className="mt-1 text-sm text-texto-suave">{formatearUbicacion(reservaDetalle.destino, reservaDetalle.pais)}</p>
              </div>
              <button type="button" onClick={() => setReservaDetalle(null)} aria-label="Cerrar detalle" className="rounded-md border border-borde px-3 py-1 text-xl text-primario">×</button>
            </div>
            <div className="mt-5 grid gap-5 text-sm sm:grid-cols-2">
              <div className="rounded-md bg-fondo p-4">
                <h3 className="font-semibold text-primario">Viaje</h3>
                <dl className="mt-3 grid gap-2">
                  <div><dt className="text-texto-suave">Fechas</dt><dd className="font-semibold text-texto">{reservaDetalle.fechaSalida} al {reservaDetalle.fechaRegreso}</dd></div>
                  <div><dt className="text-texto-suave">Pasajeros</dt><dd className="font-semibold text-texto">{reservaDetalle.pasajeros}</dd></div>
                  <div><dt className="text-texto-suave">Estado</dt><dd className="capitalize font-semibold text-texto">{reservaDetalle.estado}</dd></div>
                  <div><dt className="text-texto-suave">Total</dt><dd className="font-semibold text-texto">${Number(reservaDetalle.montoTotal || 0).toLocaleString("es-CO")}</dd></div>
                </dl>
              </div>
              <div className="rounded-md bg-fondo p-4">
                <h3 className="font-semibold text-primario">Vuelo</h3>
                {reservaDetalle.vuelo ? <dl className="mt-3 grid gap-2"><div><dt className="text-texto-suave">Ruta</dt><dd className="font-semibold text-texto">{reservaDetalle.vuelo.origen} → {reservaDetalle.vuelo.destino}</dd></div><div><dt className="text-texto-suave">Vuelo y aerolínea</dt><dd className="font-semibold text-texto">{reservaDetalle.vuelo.numeroVuelo} · {reservaDetalle.vuelo.aerolinea}</dd></div><div><dt className="text-texto-suave">Horario</dt><dd className="font-semibold text-texto">{new Date(reservaDetalle.vuelo.fechaSalida).toLocaleString("es-CO")} a {new Date(reservaDetalle.vuelo.fechaLlegada).toLocaleString("es-CO")}</dd></div><div><dt className="text-texto-suave">Terminal / puerta</dt><dd className="font-semibold text-texto">{reservaDetalle.vuelo.terminal || "Sin definir"} / {reservaDetalle.vuelo.puerta || "Sin definir"}</dd></div></dl> : <p className="mt-3 text-texto-suave">Sin vuelo asignado.</p>}
              </div>
              <div className="rounded-md border border-borde p-4">
                <h3 className="font-semibold text-primario">Hotel</h3>
                {reservaDetalle.paquete?.hotel ? <dl className="mt-3 grid gap-2"><div><dt className="text-texto-suave">Nombre</dt><dd className="font-semibold text-texto">{reservaDetalle.paquete.hotel.nombre}</dd></div><div><dt className="text-texto-suave">Ubicación</dt><dd className="font-semibold text-texto">{reservaDetalle.paquete.hotel.ciudad}, {reservaDetalle.paquete.hotel.pais}</dd></div><div><dt className="text-texto-suave">Categoría</dt><dd className="font-semibold text-texto">{reservaDetalle.paquete.hotel.estrellas} estrellas</dd></div></dl> : <p className="mt-3 text-texto-suave">Sin hotel asociado.</p>}
              </div>
              <div className="rounded-md border border-borde p-4">
                <h3 className="font-semibold text-primario">Excursiones</h3>
                {reservaDetalle.paquete?.excursiones?.length ? <ul className="mt-3 divide-y divide-borde">{reservaDetalle.paquete.excursiones.map((excursion) => <li key={excursion.id} className="py-2 first:pt-0 last:pb-0"><strong className="text-texto">{excursion.nombre}</strong><span className="block text-texto-suave">{excursion.ciudad}, {excursion.pais} · {excursion.duracionHoras} horas</span></li>)}</ul> : <p className="mt-3 text-texto-suave">Sin excursiones asociadas.</p>}
              </div>
            </div>
            <div className="mt-5 border-t border-borde pt-4 text-sm"><p><span className="text-texto-suave">Contacto: </span><strong>{reservaDetalle.telefonoContacto || "No registrado"}</strong></p><p className="mt-2"><span className="text-texto-suave">Pago: </span><strong className="capitalize">{reservaDetalle.estadoPago || "pendiente"}</strong>{reservaDetalle.metodoPago && ` · ${reservaDetalle.metodoPago}`}</p>{reservaDetalle.notas && <p className="mt-3 rounded-md bg-fondo p-3"><strong>Notas:</strong> {reservaDetalle.notas}</p>}</div>
          </section>
        </div>
      )}
      {mensaje && <p className="mt-4 text-sm text-primario">{mensaje}</p>}
    </main>
  );
}

export default Panel;
