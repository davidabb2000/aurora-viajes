import { useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { solicitar } from "../utils/api";
import { useAuth } from "../context/useAuth";

function PagoReserva() {
  const { sesion } = useAuth();
  const token = sesion?.token;
  const { id } = useParams();
  const [reserva, setReserva] = useState(null);
  const [checkoutUrl, setCheckoutUrl] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    if (!token) return undefined;
    let activo = true;
    const cargar = async () => {
      try {
        const datos = await solicitar(`/reservas/${id}`);
        if (!activo) return;
        setReserva(datos);
        // Una reserva pagada o cancelada no se cobra: antes esta página abría un
        // cobro nuevo en cada visita, incluso con la reserva ya pagada.
        if (datos.estadoPago === "pagado" || datos.estado === "cancelada") return;
        const checkout = await solicitar(`/reservas/${id}/pago/checkout`, { method: "POST" });
        if (activo) setCheckoutUrl(checkout.checkoutUrl || "");
      } catch (requestError) {
        if (activo) setError(requestError.message);
      } finally {
        if (activo) setCargando(false);
      }
    };
    cargar();
    return () => {
      activo = false;
    };
  }, [id, token]);

  if (!sesion) return <Navigate to="/login" state={{ desde: `/reservas/pago/${id}` }} replace />;

  if (cargando) {
    return (
      <div className="mx-auto w-[92%] max-w-3xl flex-1 py-12 sm:py-16">
        <p className="vidrio rounded-2xl p-6 text-sm text-texto-suave">Preparando la pasarela de pago...</p>
      </div>
    );
  }

  if (!reserva) {
    return (
      <div className="mx-auto w-[92%] max-w-3xl flex-1 py-12 sm:py-16">
        <p className="vidrio rounded-2xl border-red-200 p-6 text-sm text-red-700">{error || "No se pudo cargar la reserva."}</p>
      </div>
    );
  }

  const yaPagada = reserva.estadoPago === "pagado";
  const cancelada = reserva.estado === "cancelada";

  return (
    <div className="mx-auto w-[92%] max-w-3xl flex-1 py-12 sm:py-16">
      <section className="vidrio rounded-3xl p-6 sm:p-9">
        <span className="antetitulo">{yaPagada ? "Pago registrado" : cancelada ? "Reserva cancelada" : "Checkout seguro"}</span>
        <h1 className="mt-3 text-4xl sm:text-5xl">
          <span className="titulo-aurora">
            {yaPagada ? "Esta reserva ya está pagada" : cancelada ? "Esta reserva fue cancelada" : "Completa el pago de tu reserva"}
          </span>
        </h1>
        <p className="mt-3 text-texto-suave">
          {yaPagada
            ? "No tienes nada más que pagar. Puedes ver el detalle y descargar tu factura desde tu panel."
            : cancelada
              ? "Una reserva cancelada no se puede pagar. Si fue un error, escríbenos y la revisamos."
              : "Tu reserva quedará confirmada cuando Stripe marque el pago como realizado."}
        </p>
        <div className="mt-6 grid gap-4 text-sm sm:grid-cols-2">
          <div className="vidrio-sutil rounded-2xl p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Destino</p>
            <p className="mt-1 font-semibold text-texto">{reserva.destino}</p>
          </div>
          <div className="vidrio-sutil rounded-2xl p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Total</p>
            <p className="mt-1 text-lg font-bold text-primario">${Number(reserva.montoTotal || 0).toLocaleString("es-CO")}</p>
          </div>
          <div className="vidrio-sutil rounded-2xl p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Estado pago</p>
            <p className="mt-1 font-semibold capitalize text-texto">{reserva.estadoPago || "pendiente"}</p>
          </div>
          <div className="vidrio-sutil rounded-2xl p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-texto-suave">Pasajeros</p>
            <p className="mt-1 font-semibold text-texto">{reserva.pasajeros}</p>
          </div>
        </div>
        <div className="mt-6 flex flex-wrap gap-3">
          {yaPagada || cancelada ? (
            <Link to="/panel" className="boton-tinta px-6 py-3 font-semibold no-underline">
              Ir a mi panel
            </Link>
          ) : (
            <>
              <button
                type="button"
                onClick={() => window.location.assign(checkoutUrl)}
                disabled={!checkoutUrl}
                className="boton-tinta px-6 py-3 font-semibold"
              >
                Ir a Stripe Checkout
              </button>
              <Link to="/panel" className="rounded-full border border-primario/25 px-6 py-3 font-semibold text-primario no-underline transition hover:bg-primario/5">
                Pagar más tarde
              </Link>
            </>
          )}
        </div>
        {error && <p className="mt-4 rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm font-medium text-red-700 backdrop-blur-sm">{error}</p>}
        {!yaPagada && !cancelada && <p className="mt-5 text-sm text-texto-suave">Al volver desde Stripe, la reserva se confirma automáticamente.</p>}
      </section>
    </div>
  );
}

export default PagoReserva;
