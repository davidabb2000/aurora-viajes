import { useEffect, useRef, useState } from "react";
import Input from "../Input";
import Select from "../Select";
import { solicitar } from "../../utils/api";
import { validarCorreo, validarDocumento, validarNombre, validarTelefono } from "../../utils/validaciones";
import { BOTON_VIDRIO, CAJA_ERROR, CAMPO, ETIQUETA_MONO } from "./estilos";

const TIPOS_DOCUMENTO = [
  { value: "CC", label: "Cédula de ciudadanía" },
  { value: "TI", label: "Tarjeta de identidad" },
  { value: "CE", label: "Cédula de extranjería" },
  { value: "PA", label: "Pasaporte" },
];

const VACIO = { nombre: "", apellido: "", tipoDocumento: "CC", numeroDocumento: "", telefono: "", correo: "" };

const VALIDADORES = {
  nombre: (valor) => validarNombre(valor, "El nombre"),
  apellido: (valor) => validarNombre(valor, "El apellido"),
  numeroDocumento: validarDocumento,
  telefono: validarTelefono,
  correo: validarCorreo,
};

/**
 * Paso «Cliente» del personal: busca a quien ya tiene cuenta (por nombre, correo o documento) o lo da de alta
 * en el momento, sin salir de la reserva.
 */
function SelectorDeCliente({ cliente, alElegir }) {
  const [busqueda, setBusqueda] = useState("");
  const [resultados, setResultados] = useState([]);
  const [buscando, setBuscando] = useState(false);
  const [errorBusqueda, setErrorBusqueda] = useState("");
  const [nuevo, setNuevo] = useState(false);
  const [formulario, setFormulario] = useState(VACIO);
  const [errores, setErrores] = useState({});
  const [errorAlta, setErrorAlta] = useState("");
  const [guardando, setGuardando] = useState(false);
  const temporizador = useRef(null);

  useEffect(() => () => clearTimeout(temporizador.current), []);

  const buscar = (texto) => {
    setBusqueda(texto);
    clearTimeout(temporizador.current);
    if (texto.trim().length < 2) {
      setResultados([]);
      setBuscando(false);
      return;
    }
    setBuscando(true);
    // Espera a que se deje de escribir para no preguntar al servidor por cada letra.
    temporizador.current = setTimeout(async () => {
      try {
        const encontrados = await solicitar(`/clientes?q=${encodeURIComponent(texto.trim())}`);
        setResultados(encontrados);
        setErrorBusqueda("");
      } catch (error) {
        setErrorBusqueda(error.message);
      } finally {
        setBuscando(false);
      }
    }, 300);
  };

  const cambiarFormulario = (evento) => {
    const { name, value } = evento.target;
    setFormulario((actual) => ({ ...actual, [name]: value }));
    setErrores((actual) => ({ ...actual, [name]: "" }));
  };

  const crear = async (evento) => {
    evento.preventDefault();
    const nuevosErrores = Object.fromEntries(Object.entries(VALIDADORES).map(([campo, validar]) => [campo, validar(formulario[campo])]));
    setErrores(nuevosErrores);
    if (Object.values(nuevosErrores).some(Boolean)) return;
    setGuardando(true);
    setErrorAlta("");
    try {
      const creado = await solicitar("/clientes", { method: "POST", body: JSON.stringify({ ...formulario, nombre: formulario.nombre.trim(), apellido: formulario.apellido.trim(), correo: formulario.correo.trim() }) });
      alElegir(creado);
      setNuevo(false);
      setFormulario(VACIO);
    } catch (error) {
      setErrorAlta(error.message);
    } finally {
      setGuardando(false);
    }
  };

  if (cliente) {
    return (
      <div className="vidrio-sutil flex flex-wrap items-center justify-between gap-4 rounded-2xl p-5">
        <div>
          <p className={ETIQUETA_MONO}>Cliente de la reserva</p>
          <p className="mt-1 text-lg font-semibold text-primario">{cliente.nombre} {cliente.apellido}</p>
          <p className="text-sm text-texto-suave">
            {cliente.correo}
            {cliente.telefono ? ` · ${cliente.telefono}` : ""}
            {cliente.numeroDocumento ? ` · ${cliente.tipoDocumento} ${cliente.numeroDocumento}` : ""}
          </p>
        </div>
        <button type="button" onClick={() => alElegir(null)} className={BOTON_VIDRIO}>Cambiar cliente</button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-2" role="tablist" aria-label="Cliente">
        {[[false, "Buscar cliente"], [true, "Cliente nuevo"]].map(([valor, texto]) => (
          <button
            key={texto}
            type="button"
            role="tab"
            aria-selected={nuevo === valor}
            onClick={() => setNuevo(valor)}
            className={`flex-1 rounded-full px-4 py-2.5 text-sm font-semibold transition ${nuevo === valor ? "boton-tinta" : "vidrio text-texto-suave hover:text-primario"}`}
          >
            {texto}
          </button>
        ))}
      </div>

      {!nuevo ? (
        <div>
          <label className="block text-sm font-medium text-texto">
            Nombre, correo o documento
            <input
              type="search"
              value={busqueda}
              onChange={(evento) => buscar(evento.target.value)}
              placeholder="Ej.: María Gómez, maria@correo.com o 1098765432"
              className={`${CAMPO} mt-1.5`}
              autoFocus
            />
          </label>
          <div aria-live="polite" className="mt-3">
            {buscando && <p className="text-sm text-texto-suave">Buscando…</p>}
            {errorBusqueda && <p className={CAJA_ERROR}>{errorBusqueda}</p>}
            {!buscando && busqueda.trim().length >= 2 && resultados.length === 0 && !errorBusqueda && (
              <p className="vidrio-sutil rounded-xl px-4 py-3 text-sm text-texto-suave">
                No hay clientes con ese dato.{" "}
                <button type="button" onClick={() => setNuevo(true)} className="font-semibold text-primario underline">Crear un cliente nuevo</button>
              </p>
            )}
            {resultados.length > 0 && (
              <ul className="divide-y divide-primario/10 overflow-hidden rounded-2xl border border-primario/10 bg-white/60">
                {resultados.map((resultado) => (
                  <li key={resultado.id}>
                    <button type="button" onClick={() => alElegir(resultado)} className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition hover:bg-white/90">
                      <span>
                        <strong className="block text-sm text-primario">{resultado.nombre} {resultado.apellido}</strong>
                        <span className="text-xs text-texto-suave">{resultado.correo} · {resultado.tipoDocumento} {resultado.numeroDocumento}</span>
                      </span>
                      <span className="text-xs font-semibold text-primario-suave">Elegir →</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      ) : (
        <form onSubmit={crear} noValidate className="flex flex-col gap-4">
          <p className="text-sm text-texto-suave">
            Solo lo necesario para reservar. La cuenta se crea con una clave que nadie conoce; si el cliente quiere entrar a la web, usa «¿Olvidaste tu contraseña?».
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Nombre" name="nombre" value={formulario.nombre} onChange={cambiarFormulario} error={errores.nombre} required maxLength={40} />
            <Input label="Apellido" name="apellido" value={formulario.apellido} onChange={cambiarFormulario} error={errores.apellido} required maxLength={40} />
            <Select label="Tipo de documento" name="tipoDocumento" value={formulario.tipoDocumento} onChange={cambiarFormulario} options={TIPOS_DOCUMENTO} required />
            <Input label="Número de documento" name="numeroDocumento" value={formulario.numeroDocumento} onChange={cambiarFormulario} error={errores.numeroDocumento} required maxLength={12} inputMode="numeric" />
            <Input label="Teléfono" name="telefono" value={formulario.telefono} onChange={cambiarFormulario} error={errores.telefono} required maxLength={10} inputMode="tel" />
            <Input label="Correo electrónico" name="correo" type="email" value={formulario.correo} onChange={cambiarFormulario} error={errores.correo} required maxLength={60} />
          </div>
          {errorAlta && <p role="alert" className={CAJA_ERROR}>{errorAlta}</p>}
          <button type="submit" disabled={guardando} className="boton-tinta self-start px-6 py-2.5 text-sm font-semibold">
            {guardando ? "Guardando…" : "Crear y elegir cliente"}
          </button>
        </form>
      )}
    </div>
  );
}

export default SelectorDeCliente;
