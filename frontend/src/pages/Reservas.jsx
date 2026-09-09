import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import destinos from "../data/destinos";
import { solicitar } from "../utils/api";
import { useAuth } from "../context/AuthContext";

function Reservas() {
    const { sesion } = useAuth();
    const location = useLocation();
    const navigate = useNavigate();
    const [formulario, setFormulario] = useState({ destino: destinos[0].titulo, fechaSalida: "", fechaRegreso: "", pasajeros: 1, telefonoContacto: "", notas: "" });
    const [mensaje, setMensaje] = useState("");
    const [error, setError] = useState("");
    const [cargando, setCargando] = useState(false);

    if (!sesion) return <Navigate to="/login" state={{ desde: location.pathname }} replace />;

    const cambiar = (evento) => setFormulario({ ...formulario, [evento.target.name]: evento.target.value });
    const reservar = async (evento) => {
        evento.preventDefault();
        setMensaje("");
        setError("");
        if (new Date(formulario.fechaRegreso) < new Date(formulario.fechaSalida)) return setError("La fecha de regreso debe ser posterior a la fecha de salida.");
        setCargando(true);
        try {
            const reserva = await solicitar("/reservas", { method: "POST", headers: { Authorization: `Bearer ${sesion.token}` }, body: JSON.stringify({ ...formulario, pasajeros: Number(formulario.pasajeros) }) });
            setMensaje("Tu solicitud fue registrada. Ahora completa el pago para confirmar la reserva.");
            setFormulario({ ...formulario, fechaSalida: "", fechaRegreso: "", notas: "" });
            navigate(`/reservas/pago/${reserva.id}`);
        } catch (requestError) { setError(requestError.message); } finally { setCargando(false); }
    };

    return <main className="mx-auto w-[92%] max-w-275 flex-1 py-12 sm:py-16">
        <section className="max-w-2xl"><span className="text-xs font-semibold uppercase tracking-widest text-primario-suave">Planea con Aurora</span><h1 className="mt-2 font-display text-4xl font-bold text-primario sm:text-5xl">Reserva tu próxima historia</h1><p className="mt-4 text-lg leading-relaxed text-texto-suave">Elige un destino, cuéntanos cuándo viajas y nos encargamos de preparar el resto.</p></section>
        <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_0.85fr]">
            <form onSubmit={reservar} className="rounded-lg border border-borde bg-superficie p-6 shadow-sm sm:p-8"><h2 className="font-display text-2xl font-bold text-primario">Datos del viaje</h2><div className="mt-6 grid gap-5 sm:grid-cols-2">
                <label className="text-sm font-semibold text-texto sm:col-span-2">Destino<select name="destino" value={formulario.destino} onChange={cambiar} className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-3 font-normal outline-none focus:border-primario">{destinos.map((destino) => <option key={destino.id}>{destino.titulo}</option>)}</select></label>
                <label className="text-sm font-semibold text-texto">Fecha de salida<input required type="date" name="fechaSalida" value={formulario.fechaSalida} onChange={cambiar} min={new Date().toISOString().split("T")[0]} className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-3 font-normal outline-none focus:border-primario" /></label>
                <label className="text-sm font-semibold text-texto">Fecha de regreso<input required type="date" name="fechaRegreso" value={formulario.fechaRegreso} onChange={cambiar} min={formulario.fechaSalida || new Date().toISOString().split("T")[0]} className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-3 font-normal outline-none focus:border-primario" /></label>
                <label className="text-sm font-semibold text-texto">Pasajeros<select name="pasajeros" value={formulario.pasajeros} onChange={cambiar} className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-3 font-normal outline-none focus:border-primario">{Array.from({ length: 9 }, (_, indice) => <option key={indice + 1} value={indice + 1}>{indice + 1}</option>)}</select></label>
                <label className="text-sm font-semibold text-texto">Teléfono de contacto<input required pattern="[0-9]{7,10}" maxLength={10} name="telefonoContacto" value={formulario.telefonoContacto} onChange={cambiar} className="mt-2 w-full rounded-md border border-borde bg-fondo px-3 py-3 font-normal outline-none focus:border-primario" placeholder="3000000000" /></label>
                <label className="text-sm font-semibold text-texto sm:col-span-2">Notas para el equipo<textarea maxLength={300} name="notas" value={formulario.notas} onChange={cambiar} rows="3" className="mt-2 w-full resize-y rounded-md border border-borde bg-fondo px-3 py-3 font-normal outline-none focus:border-primario" placeholder="Cuéntanos alguna preferencia (opcional)" /></label>
            </div><button type="submit" disabled={cargando} className="mt-6 w-full rounded-md bg-primario px-5 py-3 font-semibold text-white transition hover:bg-primario-oscuro disabled:opacity-60">{cargando ? "Enviando solicitud..." : "Solicitar y continuar al pago"}</button>{mensaje && <p className="mt-4 text-sm font-medium text-primario">{mensaje}</p>}{error && <p className="mt-4 text-sm font-medium text-red-700">{error}</p>}</form>
            <aside className="rounded-lg bg-primario p-7 text-white sm:p-8"><span className="text-xs font-semibold uppercase tracking-widest text-acento-suave">Tu experiencia empieza aquí</span><h2 className="mt-4 font-display text-3xl font-bold">Viajar se siente distinto cuando todo está pensado para ti.</h2><p className="mt-5 leading-relaxed text-white/75">Recibiremos tu solicitud, verificaremos disponibilidad y actualizaremos el estado de tu reserva desde tu panel personal.</p><div className="mt-8 border-t border-white/20 pt-5 text-sm text-white/75">Sesión activa como <strong className="text-white">{sesion.usuario.nombre}</strong></div></aside>
        </div>
    </main>;
}

export default Reservas