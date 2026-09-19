import { useState } from "react";
import Input from "../components/Input";
import Button from "../components/Button";
import { validarRequerido, validarCorreo } from "../utils/validaciones";
import { solicitar } from "../utils/api";

function Contacto() {
  const [formulario, setFormulario] = useState({ nombre: "", correo: "", mensaje: "" });
  const [errores, setErrores] = useState({});
  const [enviado, setEnviado] = useState(false);
  const [errorEnvio, setErrorEnvio] = useState("");

  const manejarCambio = (evento) => {
    const { name, value } = evento.target;
    setFormulario((prev) => ({ ...prev, [name]: value }));
  };

  const manejarEnvio = async (evento) => {
    evento.preventDefault();
    setErrorEnvio("");
    const nuevosErrores = {
      nombre: validarRequerido(formulario.nombre),
      correo: validarCorreo(formulario.correo),
      mensaje: validarRequerido(formulario.mensaje),
    };
    setErrores(nuevosErrores);

    const hayErrores = Object.values(nuevosErrores).some(Boolean);
    if (hayErrores) return;
    try {
      await solicitar("/contacto", { method: "POST", body: JSON.stringify(formulario) });
      setEnviado(true);
    } catch (error) {
      setErrorEnvio(error.message);
    }
  };

  return (
    <div className="flex-1 py-10 sm:py-14">
      <div className="mx-auto w-[92%] max-w-[560px]">
        <div className="vidrio filo-aurora rounded-3xl p-7 sm:p-9">
        <span className="inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/60 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-primario-suave backdrop-blur-sm">
          <span className="h-1.5 w-1.5 rounded-full bg-acento" aria-hidden="true" />
          Hablemos
        </span>
        <h1 className="mb-3.5 mt-3.5 font-display text-3xl font-bold leading-tight sm:text-4xl">
          <span className="titulo-aurora">Cuéntanos a dónde quieres ir</span>
        </h1>
        <p className="mb-8 text-texto-suave">
          Escríbenos y uno de nuestros asesores de viaje te contactará en menos
          de 24 horas hábiles.
        </p>

        <form className="flex flex-col gap-4.5" onSubmit={manejarEnvio} noValidate>
          <Input
            label="Nombre"
            name="nombre"
            value={formulario.nombre}
            onChange={manejarCambio}
            error={errores.nombre}
            required
            placeholder="Tu nombre completo"
          />

          <Input
            label="Correo electrónico"
            name="correo"
            type="email"
            value={formulario.correo}
            onChange={manejarCambio}
            error={errores.correo}
            required
            placeholder="tucorreo@ejemplo.com"
          />

          <label className="flex flex-col gap-1.5 text-sm font-medium text-texto">
            <span>
              Mensaje<span className="text-brillo"> *</span>
            </span>
            <textarea
              name="mensaje"
              value={formulario.mensaje}
              onChange={manejarCambio}
              rows={5}
              placeholder="Cuéntanos qué destino tienes en mente"
              className={`w-full resize-y rounded-xl border bg-white/70 px-3.5 py-2.5 text-[0.95rem] text-texto backdrop-blur-sm outline-none transition focus:bg-white/90 focus:ring-3 ${
                errores.mensaje
                  ? "border-red-400 focus:border-red-400 focus:ring-red-100"
                  : "border-white/70 shadow-sm shadow-primario/5 focus:border-primario-suave focus:ring-primario-suave/20"
              }`}
            />
            {errores.mensaje && (
              <span className="text-xs font-medium text-red-600">{errores.mensaje}</span>
            )}
          </label>

          <Button type="submit" className="self-start">
            Enviar mensaje
          </Button>

          {enviado && (
            <p role="status" className="vidrio-sutil rounded-xl px-4 py-3 text-sm font-medium text-primario">
              ¡Gracias, {formulario.nombre || "viajero"}! Recibimos tu mensaje.
            </p>
          )}
          {errorEnvio && <p role="alert" className="rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm font-medium text-red-700 backdrop-blur-sm">{errorEnvio}</p>}
        </form>
        </div>
      </div>
    </div>
  );
}

export default Contacto;
