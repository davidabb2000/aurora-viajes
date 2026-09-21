import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

const precio = (valor) =>
  new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(valor);

const dos = (numero) => String(numero).padStart(2, "0");

const INTERVALO_MS = 5500;

const BOTON =
  "grid h-11 w-11 place-items-center rounded-full border border-primario/20 bg-white/70 text-lg text-primario backdrop-blur-sm transition hover:-translate-y-0.5 hover:bg-white disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:translate-y-0";

const prefiereMenosMovimiento = () =>
  typeof window !== "undefined" && Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
const comportamiento = () => (prefiereMenosMovimiento() ? "auto" : "smooth");

function Tarjeta({ destino, posicion }) {
  const [ciudad, ...resto] = destino.titulo.split(",");
  const pais = resto.join(",").trim();
  return (
    <Link
      to={`/reservas?destino=${destino.id}`}
      draggable={false}
      className="group relative block h-[27rem] overflow-hidden rounded-[2.5rem] bg-marino text-crema no-underline shadow-[0_18px_40px_-30px_rgba(23,21,15,0.5)] transition-shadow duration-350 ease-[cubic-bezier(0.25,0.46,0.45,0.94)] hover:shadow-[0_40px_70px_-32px_rgba(23,21,15,0.6)] sm:h-[32rem]"
    >
      <img
        src={destino.imagen}
        alt=""
        loading="lazy"
        draggable={false}
        className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-105"
      />
      <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/5 to-black/10" />

      <div className="relative flex h-full flex-col justify-between p-6 sm:p-7">
        <div className="flex items-start justify-between gap-3">
          <span className="rounded-full border border-white/40 bg-white/15 px-3.5 py-1.5 font-mono text-[0.68rem] uppercase tracking-[0.12em] backdrop-blur-sm">
            {dos(posicion)}
            {pais && ` · ${pais}`}
          </span>
          <span
            aria-hidden="true"
            className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-crema text-xl text-primario transition-transform duration-500 ease-resorte group-hover:rotate-45"
          >
            →
          </span>
        </div>

        <div>
          <h3 className="font-display text-[2.4rem] leading-[1.02] sm:text-[2.6rem]">{ciudad}</h3>
          <p className="mt-2 line-clamp-3 max-w-[36ch] text-sm leading-relaxed text-crema/85">{destino.descripcion}</p>
          {destino.precioBase > 0 && (
            <p className="mt-4 font-mono text-xs uppercase tracking-[0.12em] text-oro">Desde {precio(destino.precioBase)} por persona</p>
          )}
        </div>
      </div>
      <span className="sr-only">Reservar viaje a {destino.titulo}</span>
    </Link>
  );
}

/**
 * Carrusel de destinos: una fila que se desplaza con el dedo, el trackpad, el teclado (← →) o los botones y que se
 * ajusta sola a cada tarjeta (scroll-snap). Avanza por sí mismo cada pocos segundos, pero se detiene mientras el
 * ratón o el foco están encima, cuando no está a la vista, en cuanto la persona lo usa a mano, con el botón de pausa
 * y siempre que el sistema pida menos movimiento. Los puntos y el contador marcan todas las tarjetas que se ven.
 * `items` = { id, imagen, titulo ("Ciudad, País"), descripcion, precioBase? }.
 */
function CarruselDeDestinos({ items }) {
  const region = useRef(null);
  const pista = useRef(null);
  const [rango, setRango] = useState({ desde: 0, hasta: 0 });
  const [alInicio, setAlInicio] = useState(true);
  const [alFinal, setAlFinal] = useState(false);
  const [reproduciendo, setReproduciendo] = useState(() => !prefiereMenosMovimiento());
  const [pausado, setPausado] = useState(false);
  const [visible, setVisible] = useState(false);

  /** Distancia entre el inicio de una tarjeta y el de la siguiente. */
  const paso = useCallback(() => {
    const tarjetas = pista.current?.children;
    if (!tarjetas || tarjetas.length < 2) return pista.current?.clientWidth ?? 0;
    return tarjetas[1].offsetLeft - tarjetas[0].offsetLeft;
  }, []);

  /** Lee la posición de la pista: qué tarjetas se ven (al menos la mitad) y si está en un extremo. */
  const medir = useCallback(() => {
    const nodo = pista.current;
    if (!nodo || nodo.children.length === 0) return;
    const tarjetas = Array.from(nodo.children);
    const origen = tarjetas[0].offsetLeft;
    const { scrollLeft, clientWidth, scrollWidth } = nodo;
    let desde = -1;
    let hasta = -1;
    tarjetas.forEach((tarjeta, indice) => {
      const inicio = tarjeta.offsetLeft - origen - scrollLeft;
      const enPantalla = Math.min(inicio + tarjeta.offsetWidth, clientWidth) - Math.max(inicio, 0);
      if (enPantalla >= tarjeta.offsetWidth / 2) {
        if (desde < 0) desde = indice;
        hasta = indice;
      }
    });
    if (desde < 0) {
      desde = Math.min(tarjetas.length - 1, Math.round(scrollLeft / (paso() || 1)));
      hasta = desde;
    }
    setRango((previo) => (previo.desde === desde && previo.hasta === hasta ? previo : { desde, hasta }));
    setAlInicio(scrollLeft <= 2);
    setAlFinal(scrollLeft >= scrollWidth - clientWidth - 2);
  }, [paso]);

  // Las medidas cambian con el ancho de la ventana y con la cantidad de destinos.
  useEffect(() => {
    const nodo = pista.current;
    if (!nodo || typeof ResizeObserver === "undefined") return undefined;
    const observador = new ResizeObserver(medir);
    observador.observe(nodo);
    medir();
    return () => observador.disconnect();
  }, [medir, items.length]);

  // Solo avanza sola mientras está a la vista.
  useEffect(() => {
    const nodo = region.current;
    if (!nodo || typeof IntersectionObserver === "undefined") return undefined;
    const observador = new IntersectionObserver(([entrada]) => setVisible(entrada.isIntersecting), { threshold: 0.35 });
    observador.observe(nodo);
    return () => observador.disconnect();
  }, []);

  useEffect(() => {
    if (!reproduciendo || pausado || !visible) return undefined;
    const temporizador = setInterval(() => {
      const nodo = pista.current;
      if (!nodo || document.hidden) return;
      if (nodo.scrollLeft >= nodo.scrollWidth - nodo.clientWidth - 2) nodo.scrollTo({ left: 0, behavior: comportamiento() });
      else nodo.scrollBy({ left: paso(), behavior: comportamiento() });
    }, INTERVALO_MS);
    return () => clearInterval(temporizador);
  }, [reproduciendo, pausado, visible, paso]);

  const mover = (direccion) => {
    setReproduciendo(false);
    pista.current?.scrollBy({ left: direccion * paso(), behavior: comportamiento() });
  };

  const irA = (indice) => {
    const tarjetas = pista.current?.children;
    if (!tarjetas?.[indice]) return;
    setReproduciendo(false);
    pista.current.scrollTo({ left: tarjetas[indice].offsetLeft - tarjetas[0].offsetLeft, behavior: comportamiento() });
  };

  const alTeclear = (evento) => {
    if (evento.key !== "ArrowRight" && evento.key !== "ArrowLeft") return;
    evento.preventDefault();
    mover(evento.key === "ArrowRight" ? 1 : -1);
  };

  const total = items.length;
  if (total === 0) return null;
  const puedeReproducirse = !prefiereMenosMovimiento();
  const contador = rango.desde === rango.hasta ? dos(rango.desde + 1) : `${dos(rango.desde + 1)}–${dos(rango.hasta + 1)}`;

  return (
    <div
      ref={region}
      role="region"
      aria-roledescription="carrusel"
      aria-label="Destinos disponibles"
      onKeyDown={alTeclear}
      onMouseEnter={() => setPausado(true)}
      onMouseLeave={() => setPausado(false)}
      onFocus={() => setPausado(true)}
      onBlur={(evento) => {
        if (!evento.currentTarget.contains(evento.relatedTarget)) setPausado(false);
      }}
      onPointerDown={(evento) => {
        // Un dedo o un lápiz sobre la pista es una persona usándola: deja de avanzar sola.
        if (evento.pointerType !== "mouse") setReproduciendo(false);
      }}
      onWheel={(evento) => {
        if (Math.abs(evento.deltaX) > Math.abs(evento.deltaY)) setReproduciendo(false);
      }}
    >
      <div
        ref={pista}
        onScroll={medir}
        className="sin-barra flex snap-x snap-mandatory gap-5 overflow-x-auto overscroll-x-contain pb-10 pt-2 sm:gap-6"
      >
        {items.map((destino, indice) => (
          <div
            key={destino.id}
            role="group"
            aria-roledescription="diapositiva"
            aria-label={`${indice + 1} de ${total}`}
            className="w-[82%] shrink-0 snap-start sm:w-[24rem] lg:w-[22.5rem]"
          >
            <Tarjeta destino={destino} posicion={indice + 1} />
          </div>
        ))}
      </div>

      <div className="-mt-3 flex flex-wrap items-center justify-between gap-x-6 gap-y-4">
        <div className="flex items-center gap-2.5">
          <button type="button" onClick={() => mover(-1)} disabled={alInicio} aria-label="Destino anterior" className={BOTON}>
            ←
          </button>
          <button type="button" onClick={() => mover(1)} disabled={alFinal} aria-label="Destino siguiente" className={BOTON}>
            →
          </button>
          {puedeReproducirse && (
            <button
              type="button"
              onClick={() => setReproduciendo((actual) => !actual)}
              aria-label={reproduciendo ? "Pausar el avance automático" : "Reanudar el avance automático"}
              className={`${BOTON} text-sm`}
            >
              {reproduciendo ? "❚❚" : "▶"}
            </button>
          )}
        </div>

        <div className="flex flex-wrap items-center" role="group" aria-label="Elegir destino">
          {items.map((destino, indice) => {
            const enPantalla = indice >= rango.desde && indice <= rango.hasta;
            return (
              <button
                key={destino.id}
                type="button"
                onClick={() => irA(indice)}
                aria-label={`Ir a ${destino.titulo.split(",")[0]}`}
                aria-current={enPantalla ? "true" : undefined}
                className="group/punto grid h-6 place-items-center px-[3px]"
              >
                <span
                  aria-hidden="true"
                  className={`block h-2 rounded-full transition-all duration-300 ${enPantalla ? "w-5 bg-primario" : "w-2 bg-primario/25 group-hover/punto:bg-primario/50"}`}
                />
              </button>
            );
          })}
        </div>

        <p className="hidden font-mono text-xs uppercase tracking-[0.14em] text-texto-suave sm:block" aria-hidden="true">
          {contador} / {dos(total)}
        </p>
      </div>
    </div>
  );
}

export default CarruselDeDestinos;
