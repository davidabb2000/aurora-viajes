import { useState } from "react";
import { Link } from "react-router-dom";
import AsistenteDeReserva from "../../components/reserva/AsistenteDeReserva";
import { BOTON_VIDRIO } from "../../components/reserva/estilos";
import { moneda } from "../../utils/formato";
import { EncabezadoDePanel } from "./Encabezado";

/** Reserva a nombre de un cliente, hecha por el personal: mismo asistente que ve el cliente, más cliente y cobro. */
function NuevaReserva() {
  const [creada, setCreada] = useState(null);
  // Cambiar la clave reinicia el asistente para crear otra reserva desde cero.
  const [intento, setIntento] = useState(0);

  if (creada) {
    return (
      <div className="mx-auto w-[96%] max-w-3xl flex-1 py-12">
        <section className="vidrio rounded-3xl p-8 text-center sm:p-12" role="status">
          <span className="antetitulo mx-auto justify-center">Reserva registrada</span>
          <h1 className="mt-4 text-4xl text-primario">Reserva <em className="titulo-enfasis">#{creada.id}</em> creada</h1>
          <p className="mx-auto mt-4 max-w-[46ch] text-texto-suave">
            A nombre de <strong className="text-primario">{creada.cliente?.nombre} {creada.cliente?.apellido}</strong> por {moneda(creada.montoTotal)}.{" "}
            {creada.estadoPago === "pagado" ? "El pago quedó registrado y la reserva confirmada." : "Quedó pendiente de pago: el cliente puede pagarla en línea desde su cuenta, o puedes registrar el cobro en la lista de reservas."}
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link to="/panel?vista=reservas" className="boton-tinta px-6 py-3 text-sm font-semibold no-underline">Ver reservas</Link>
            <button type="button" onClick={() => { setCreada(null); setIntento((actual) => actual + 1); }} className={BOTON_VIDRIO}>Crear otra reserva</button>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="mx-auto w-[96%] max-w-350 flex-1 py-8 sm:py-12">
      <EncabezadoDePanel etiqueta="Mostrador" titulo="Nueva reserva" descripcion="Elige o crea al cliente, arma el viaje con vuelos de ida y regreso, hotel y excursiones, y cóbrala en el momento si paga en la agencia." />
      <div className="mt-8">
        <AsistenteDeReserva key={intento} modo="personal" alTerminar={setCreada} />
      </div>
    </div>
  );
}

export default NuevaReserva;
