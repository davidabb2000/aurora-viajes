import { useState } from "react";
import { solicitar } from "../../utils/api";
import { validarDocumentoDePasajero, validarNombre } from "../../utils/validaciones";
import { BOTON_VIDRIO, CAJA_ERROR, CAMPO, ETIQUETA_MONO } from "./estilos";

const TIPOS = [["CC", "Cédula de ciudadanía"], ["TI", "Tarjeta de identidad"], ["CE", "Cédula de extranjería"], ["PA", "Pasaporte"]];
const VACIO = { nombre: "", apellido: "", tipoDocumento: "CC", numeroDocumento: "" };

const estaVacia = (fila) => !fila.nombre.trim() && !fila.apellido.trim() && !fila.numeroDocumento.trim();

/** Una fila con algo escrito debe estar completa y bien escrita; las vacías se ignoran (los datos se pueden dejar para después). */
function erroresDeFila(fila) {
  if (estaVacia(fila)) return {};
  return {
    nombre: validarNombre(fila.nombre, "El nombre"),
    apellido: validarNombre(fila.apellido, "El apellido"),
    numeroDocumento: validarDocumentoDePasajero(fila.numeroDocumento),
  };
}

function Campo({ etiqueta, error, children }) {
  return (
    <label className="text-xs font-medium text-texto">
      {etiqueta}
      {children}
      {error && <span className="mt-1 block font-medium text-red-600">{error}</span>}
    </label>
  );
}

function Formulario({ reserva, alGuardar, alCancelar }) {
  const [filas, setFilas] = useState(() =>
    Array.from({ length: reserva.pasajeros }, (_, indice) => {
      const existente = reserva.datosDePasajeros?.[indice];
      return existente
        ? { nombre: existente.nombre, apellido: existente.apellido, tipoDocumento: existente.tipoDocumento, numeroDocumento: existente.numeroDocumento }
        : VACIO;
    }),
  );
  const [errores, setErrores] = useState([]);
  const [errorGeneral, setErrorGeneral] = useState("");
  const [guardando, setGuardando] = useState(false);

  const cambiar = (indice, campo, valor) => {
    setFilas((actuales) => actuales.map((fila, posicion) => (posicion === indice ? { ...fila, [campo]: valor } : fila)));
    setErrores((actuales) => actuales.map((error, posicion) => (posicion === indice ? { ...error, [campo]: "" } : error)));
  };

  const guardar = async (evento) => {
    evento.preventDefault();
    const nuevos = filas.map(erroresDeFila);
    setErrores(nuevos);
    setErrorGeneral("");
    if (nuevos.some((error) => Object.values(error).some(Boolean))) return;
    setGuardando(true);
    try {
      const pasajeros = filas
        .filter((fila) => !estaVacia(fila))
        .map((fila) => ({ ...fila, nombre: fila.nombre.trim(), apellido: fila.apellido.trim(), numeroDocumento: fila.numeroDocumento.trim() }));
      await solicitar(`/reservas/${reserva.id}/pasajeros`, { method: "PUT", body: JSON.stringify({ pasajeros }) });
      await alGuardar();
    } catch (error) {
      setErrorGeneral(error.message);
      setGuardando(false);
    }
  };

  return (
    <form onSubmit={guardar} noValidate className="mt-4 space-y-4">
      <p className="text-xs text-texto-suave">Como aparecen en el documento con el que van a viajar. Puedes dejar filas vacías y completarlas después.</p>
      {filas.map((fila, indice) => (
        <fieldset key={indice} className="rounded-2xl border border-primario/12 bg-white/60 p-4">
          <legend className="px-1 text-xs font-semibold text-primario">Pasajero {indice + 1}</legend>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Campo etiqueta="Nombre" error={errores[indice]?.nombre}>
              <input value={fila.nombre} onChange={(evento) => cambiar(indice, "nombre", evento.target.value)} maxLength={40} autoComplete="off" className={`${CAMPO} mt-1`} />
            </Campo>
            <Campo etiqueta="Apellido" error={errores[indice]?.apellido}>
              <input value={fila.apellido} onChange={(evento) => cambiar(indice, "apellido", evento.target.value)} maxLength={40} autoComplete="off" className={`${CAMPO} mt-1`} />
            </Campo>
            <Campo etiqueta="Tipo de documento">
              <select value={fila.tipoDocumento} onChange={(evento) => cambiar(indice, "tipoDocumento", evento.target.value)} className={`${CAMPO} mt-1`}>
                {TIPOS.map(([valor, texto]) => <option key={valor} value={valor}>{texto}</option>)}
              </select>
            </Campo>
            <Campo etiqueta="Número" error={errores[indice]?.numeroDocumento}>
              <input value={fila.numeroDocumento} onChange={(evento) => cambiar(indice, "numeroDocumento", evento.target.value)} maxLength={20} autoComplete="off" className={`${CAMPO} mt-1`} />
            </Campo>
          </div>
        </fieldset>
      ))}
      {errorGeneral && <p role="alert" className={CAJA_ERROR}>{errorGeneral}</p>}
      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={guardando} className="boton-tinta px-5 py-2.5 text-sm font-semibold">{guardando ? "Guardando…" : "Guardar datos"}</button>
        <button type="button" onClick={alCancelar} disabled={guardando} className={BOTON_VIDRIO}>Cancelar</button>
      </div>
    </form>
  );
}

/**
 * Quiénes viajan en una reserva: la lista con sus documentos y, si se puede, el formulario para completarla.
 * `alCambiar` (recargar la reserva) activa la edición; sin él solo se muestra.
 */
function PasajerosDeLaReserva({ reserva, alCambiar }) {
  const [editando, setEditando] = useState(false);
  const registrados = reserva.datosDePasajeros ?? [];
  const faltan = reserva.pasajeros - registrados.length;
  const editable = Boolean(alCambiar) && reserva.estado !== "cancelada";

  return (
    <section className="vidrio-sutil rounded-2xl p-4 lg:col-span-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h4 className={ETIQUETA_MONO}>Pasajeros</h4>
          <p className="mt-1 text-sm text-texto">
            {registrados.length} de {reserva.pasajeros} con datos
            {faltan > 0 && <span className="ml-2 rounded-full bg-oro/70 px-2.5 py-0.5 text-xs font-semibold text-primario">Faltan {faltan}</span>}
          </p>
        </div>
        {editable && !editando && (
          <button type="button" onClick={() => setEditando(true)} className={BOTON_VIDRIO}>
            {registrados.length ? "Editar datos" : "Completar datos"}
          </button>
        )}
      </div>

      {!editando && registrados.length > 0 && (
        <ul className="mt-3 divide-y divide-primario/10 text-sm">
          {registrados.map((pasajero) => (
            <li key={pasajero.id} className="flex flex-wrap items-baseline justify-between gap-2 py-2 first:pt-0 last:pb-0">
              <strong className="text-texto">{pasajero.nombre} {pasajero.apellido}</strong>
              <span className="text-xs text-texto-suave">{pasajero.tipoDocumento} {pasajero.numeroDocumento}</span>
            </li>
          ))}
        </ul>
      )}
      {!editando && registrados.length === 0 && !editable && <p className="mt-3 text-sm text-texto-suave">Todavía no hay datos de los pasajeros.</p>}

      {editando && (
        <Formulario
          reserva={reserva}
          alCancelar={() => setEditando(false)}
          alGuardar={async () => {
            await alCambiar();
            setEditando(false);
          }}
        />
      )}
    </section>
  );
}

export default PasajerosDeLaReserva;
