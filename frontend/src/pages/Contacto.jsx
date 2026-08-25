import { useState } from "react";
import Input from "../components/Input";
import Button from "../components/Button";
import { validarRequerido, validarCorreo } from "../utils/validaciones";

function Contacto() {
  const [formulario, setFormulario] = useState({ nombre: "", correo: "", mensaje: "" });
  const [errores, setErrores] = useState({});
  const [enviado, setEnviado] = useState(false);

  const manejarCambio = (evento) => {
    const { name, value } = evento.target;
    setFormulario((prev) => ({ ...prev, [name]: value }));
  };

  const manejarEnvio = (evento) => {
    evento.preventDefault();
    const nuevosErrores = {
      nombre: validarRequerido(formulario.nombre),
      correo: validarCorreo(formulario.correo),
      mensaje: validarRequerido(formulario.mensaje),
    };
    setErrores(nuevosErrores);

    const hayErrores = Object.values(nuevosErrores).some(Boolean);
    if (!hayErrores) setEnviado(true);
  };

  return (
    <div className="flex-1 py-12 sm:py-16">
      <div className="mx-auto w-[92%] max-w-[560px]">
        <span className="mb-3.5 inline-block text-xs font-semibold uppercase tracking-widest text-primario-suave">
          Hablemos
        </span>
        <h1 className="mb-3.5 font-display text-3xl font-bold leading-tight text-primario sm:text-4xl">
          Cuéntanos a dónde quieres ir
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
              Mensaje<span className="text-acento"> *</span>
            </span>
            <textarea
              name="mensaje"
              value={formulario.mensaje}
              onChange={manejarCambio}
              rows={5}
              placeholder="Cuéntanos qué destino tienes en mente"
              className={`w-full resize-y rounded-md border bg-superficie px-3.5 py-2.5 text-[0.95rem] text-texto outline-none transition focus:ring-3 ${
                errores.mensaje
                  ? "border-red-400 focus:border-red-400 focus:ring-red-100"
                  : "border-borde focus:border-primario-suave focus:ring-primario-suave/15"
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
            <p role="status" className="text-sm font-medium text-primario-suave">
              ¡Gracias, {formulario.nombre || "viajero"}! Recibimos tu mensaje.
            </p>
          )}
        </form>
      </div>
    </div>
  );
}

export default Contacto;
