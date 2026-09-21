import { Link, Navigate, useSearchParams } from "react-router-dom";
import MisReservas from "../components/reserva/MisReservas";
import { useAuth } from "../context/useAuth";
import { esPersonal } from "../utils/rutas";
import { useCarga } from "../utils/useCarga";
import CatalogoPanel from "./panel/CatalogoPanel";
import { Aviso, EncabezadoDePanel } from "./panel/Encabezado";
import MensajesPanel from "./panel/MensajesPanel";
import NuevaReserva from "./panel/NuevaReserva";
import ReservasPanel from "./panel/ReservasPanel";
import UsuariosPanel from "./panel/UsuariosPanel";
import VuelosPanel from "./panel/VuelosPanel";

/** Panel de un cliente: sus reservas, con el mismo detalle que en «Reservar». */
function PanelDeCliente({ usuario }) {
  const reservas = useCarga("/reservas/mias");
  return (
    <div className="mx-auto w-[96%] max-w-300 flex-1 py-8 sm:py-12">
      <EncabezadoDePanel etiqueta="Tu cuenta" titulo={`Hola, ${usuario.nombre}`} descripcion="Consulta el estado de tus reservas, págalas o cancela las que aún no has pagado.">
        <Link to="/reservas" className="boton-tinta px-6 py-3 text-sm font-semibold no-underline">Reservar un viaje</Link>
      </EncabezadoDePanel>
      <Aviso mensaje={reservas.error} tipo="error" />
      <div className="mt-8">
        <MisReservas reservas={reservas.datos} alCambiar={reservas.recargar} />
      </div>
    </div>
  );
}

/**
 * Enrutador de las vistas del panel según `?vista=`. Cada vista carga sus propios datos: antes esta página
 * pedía todo (reservas, usuarios, hoteles, paquetes, mensajes...) al abrirse, aunque solo se mirara una tabla.
 * Las vistas de administración redirigen a quien no lo es; el servidor lo vuelve a exigir en cada ruta.
 */
function Panel() {
  const { sesion } = useAuth();
  const [parametros] = useSearchParams();
  const vista = parametros.get("vista") || "reservas";
  const usuario = sesion.usuario;
  const esAdmin = usuario.rol === "administrador";

  if (!esPersonal(usuario)) return <PanelDeCliente usuario={usuario} />;

  switch (vista) {
    case "nueva":
      return <NuevaReserva />;
    case "vuelos":
      return <VuelosPanel esAdmin={esAdmin} />;
    case "catalogo":
    case "paquetes":
      return esAdmin ? <CatalogoPanel /> : <Navigate to="/panel" replace />;
    case "usuarios":
    case "crear":
      return esAdmin ? <UsuariosPanel /> : <Navigate to="/panel" replace />;
    case "mensajes":
      return esAdmin ? <MensajesPanel /> : <Navigate to="/panel" replace />;
    default:
      return <ReservasPanel />;
  }
}

export default Panel;
