import { fechaHora } from "../../utils/formato";
import { useCarga } from "../../utils/useCarga";
import { Aviso, EncabezadoDePanel } from "./Encabezado";

/** Mensajes del formulario de contacto. Se muestran como texto: React escapa cualquier HTML que traigan. */
function MensajesPanel() {
  const { datos, cargando, error } = useCarga("/contacto");
  return (
    <div className="mx-auto w-[96%] max-w-350 flex-1 py-8 sm:py-12">
      <EncabezadoDePanel etiqueta="Administración" titulo="Mensajes de contacto" />
      <Aviso mensaje={error} tipo="error" />
      <section className="vidrio mt-8 overflow-x-auto rounded-3xl p-6">
        {datos === null && cargando && <p className="text-sm text-texto-suave">Cargando mensajes…</p>}
        {datos !== null && datos.length === 0 && <p className="text-sm text-texto-suave">No hay mensajes de contacto.</p>}
        {datos && datos.length > 0 && (
          <table className="w-full min-w-175 text-left text-sm">
            <thead>
              <tr className="border-b border-primario/12 text-texto-suave">
                <th className="pb-3 font-medium">Fecha</th><th className="pb-3 font-medium">Nombre</th><th className="pb-3 font-medium">Correo</th><th className="pb-3 font-medium">Mensaje</th>
              </tr>
            </thead>
            <tbody>
              {datos.map((mensaje) => (
                <tr key={mensaje.id} className="border-b border-primario/8 align-top">
                  <td className="whitespace-nowrap py-3">{fechaHora(mensaje.creadoEn)}</td>
                  <td className="py-3">{mensaje.nombre}</td>
                  <td className="py-3"><a href={`mailto:${encodeURIComponent(mensaje.correo)}`} className="text-primario underline">{mensaje.correo}</a></td>
                  <td className="max-w-md whitespace-pre-wrap py-3">{mensaje.mensaje}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

export default MensajesPanel;
