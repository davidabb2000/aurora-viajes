import { useState } from "react";
import Input from "../components/Input";
import Button from "../components/Button";
import GoogleMap from "../components/GoogleMap";
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
    <div className="flex-1 py-10 sm:py-16">
      <div className="mx-auto w-[92%] max-w-300">
        <div className="grid gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16">
          <div>
            <span className="antetitulo">Hablemos</span>
            <h1 className="mt-5 text-[clamp(2.9rem,6.4vw,5.2rem)] leading-[1.03] tracking-[-0.03em]">
              <span className="titulo-aurora">
                Cuéntanos a dónde quieres <em className="titulo-enfasis">ir</em>
              </span>
            </h1>
            <p className="mt-6 max-w-[46ch] text-lg leading-relaxed text-texto-suave">
              Escríbenos y uno de nuestros asesores de viaje te contactará en menos de 24 horas hábiles.
            </p>

            <div className="vidrio mt-10 rounded-3xl p-7 sm:p-9">
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
                    className={`w-full resize-y rounded-xl border bg-white/70 px-3.5 py-2.5 text-[0.95rem] text-texto backdrop-blur-sm outline-none transition focus:bg-white/90 focus:ring-3 ${
                      errores.mensaje
                        ? "border-red-400 focus:border-red-400 focus:ring-red-100"
                        : "border-primario/12 shadow-sm shadow-primario/5 focus:border-primario-suave focus:ring-primario-suave/20"
                    }`}
                  />
                  {errores.mensaje && <span className="text-xs font-medium text-red-600">{errores.mensaje}</span>}
                </label>

                <Button type="submit" className="self-start">
                  Enviar mensaje
                </Button>

                {enviado && (
                  <p role="status" className="vidrio-sutil rounded-xl px-4 py-3 text-sm font-medium text-primario">
                    ¡Gracias, {formulario.nombre || "viajero"}! Recibimos tu mensaje.
                  </p>
                )}
                {errorEnvio && (
                  <p role="alert" className="rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm font-medium text-red-700 backdrop-blur-sm">
                    {errorEnvio}
                  </p>
                )}
              </form>
            </div>
          </div>

          <aside className="flex flex-col gap-6 lg:pt-6" aria-label="Datos de contacto">
            <div className="rounded-[2.1rem] bg-arena p-7 sm:p-8">
              <p className="antetitulo">Escríbenos o llámanos</p>
              <ul className="mt-6 list-none space-y-4 p-0">
                <li>
                  <p className="font-mono text-[0.7rem] uppercase tracking-[0.12em] text-texto-suave">Correo</p>
                  <a href="mailto:contacto@auroraviajes.com" className="font-display text-2xl text-primario no-underline hover:text-acento">contacto@auroraviajes.com</a>
                </li>
                <li>
                  <p className="font-mono text-[0.7rem] uppercase tracking-[0.12em] text-texto-suave">Teléfono y WhatsApp</p>
                  <a href="https://wa.me/573503576793" target="_blank" rel="noreferrer" className="font-display text-2xl text-primario no-underline hover:text-acento">+57 350 357 6793</a>
                </li>
                <li>
                  <p className="font-mono text-[0.7rem] uppercase tracking-[0.12em] text-texto-suave">Oficina</p>
                  <p className="font-display text-2xl text-primario">Medellín, Colombia</p>
                </li>
              </ul>
            </div>
            <GoogleMap />
          </aside>
        </div>
      </div>
    </div>
  );
}

export default Contacto;
