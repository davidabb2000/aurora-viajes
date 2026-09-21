import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import destinosBase, { ilustracionGenerica } from "../data/destinos";
import { solicitar } from "../utils/api";
import CarruselDeDestinos from "../components/CarruselDeDestinos";
import Sponsors from "../components/Sponsors";
import Revelar from "../components/Revelar";
import TextoRevelado from "../components/TextoRevelado";
import { BordeDeNubes, Nube, PaseDeAbordar, SenderoDeVuelo, SolRayado } from "../components/Decoraciones";

const HISTORIA = [
  { texto: "Empezamos en 2015 con tres destinos y un equipo de cuatro personas. Hoy armamos viajes completos: " },
  { texto: "el vuelo, el hotel y las excursiones en una sola reserva,", negrita: true },
  { texto: " con el precio claro desde el primer día y sin sorpresas a la hora de pagar." },
];

const CIERRE = [{ texto: "Un buen viaje se planea con calma, se paga con seguridad y se recuerda toda la vida.", negrita: true }];

// Los destinos salen del catálogo y el administrador puede sumar o retirar alguno: el título cuenta los que hay.
const CANTIDADES = ["Cero", "Un", "Dos", "Tres", "Cuatro", "Cinco", "Seis", "Siete", "Ocho", "Nueve", "Diez", "Once", "Doce"];
const lugaresPara = (cantidad) => `${CANTIDADES[cantidad] ?? cantidad} ${cantidad === 1 ? "lugar" : "lugares"} para`;

const PASOS = [
  {
    numero: "01",
    titulo: "Elige tu destino",
    texto: "Ciudades con vuelo asignado y tarifa por pasajero. Si dudas, pídele una recomendación a nuestro asistente.",
    etiqueta: "Vuelo incluido",
    giro: "md:-rotate-2",
  },
  {
    numero: "02",
    titulo: "Arma tu viaje",
    texto: "Un paquete cerrado o a la carta: tú eliges el hotel, las noches y las excursiones que quieres sumar.",
    etiqueta: "Hotel y excursiones",
    giro: "md:rotate-1",
  },
  {
    numero: "03",
    titulo: "Paga y sigue el viaje",
    texto: "Pago seguro con Stripe, factura en PDF y el estado de tu reserva siempre a la vista en tu panel.",
    etiqueta: "Pago seguro",
    giro: "md:rotate-2",
  },
];

function Index() {
  const { hash } = useLocation();
  const [catalogo, setCatalogo] = useState([]);

  // Los precios salen del catálogo real; si la API no responde, las tarjetas se muestran sin precio.
  useEffect(() => {
    let activo = true;
    solicitar("/catalogos/destinos")
      .then((datos) => {
        if (activo && Array.isArray(datos)) setCatalogo(datos);
      })
      .catch(() => {});
    return () => {
      activo = false;
    };
  }, []);

  // Con el catálogo a la vista se muestran los destinos que hay hoy (los de la portada, en su orden, y los que el
  // administrador haya agregado, con una ilustración genérica). Sin catálogo (la API no responde) quedan los de siempre, sin precio.
  const destinos = useMemo(() => {
    if (catalogo.length === 0) return destinosBase.map((destino) => ({ ...destino, precioBase: 0 }));
    const conIlustracion = new Map(destinosBase.map((destino) => [destino.titulo, destino]));
    const propios = catalogo.filter((vivo) => conIlustracion.has(vivo.nombre)).map((vivo) => ({ ...conIlustracion.get(vivo.nombre), id: vivo.id, precioBase: vivo.precioBase }));
    const orden = new Map(destinosBase.map((destino, posicion) => [destino.titulo, posicion]));
    propios.sort((a, b) => orden.get(a.titulo) - orden.get(b.titulo));
    const agregados = catalogo
      .filter((vivo) => !conIlustracion.has(vivo.nombre))
      .map((vivo) => ({ id: vivo.id, imagen: ilustracionGenerica, titulo: vivo.nombre, descripcion: vivo.descripcion || "", precioBase: vivo.precioBase }));
    return [...propios, ...agregados];
  }, [catalogo]);

  useEffect(() => {
    if (hash) document.querySelector(hash)?.scrollIntoView({ behavior: "smooth" });
  }, [hash]);

  return (
    <div className="flex-1">
      <section className="cielo relative -mt-20 flex min-h-[max(41rem,100svh)] flex-col justify-center overflow-hidden pb-44 pt-32 text-crema">
        <SolRayado className="absolute right-[9%] top-28 h-28 w-28 sm:h-40 sm:w-40 lg:h-52 lg:w-52" />
        <Nube className="animate-flotar absolute left-[4%] top-[26%] w-40 text-white/70 sm:w-60" />
        <Nube className="animate-flotar absolute right-[30%] top-[13%] w-48 text-white/55 [animation-delay:-7s] sm:w-72" />
        <Nube className="animate-flotar absolute -right-6 top-[54%] w-56 text-white/60 [animation-delay:-3s] sm:w-80" />
        <SenderoDeVuelo className="absolute -left-6 bottom-16 hidden w-[44rem] max-w-[62%] lg:block" />

        <p
          aria-hidden="true"
          className="absolute left-8 top-1/2 hidden -translate-y-1/2 rotate-180 font-mono text-[0.7rem] uppercase tracking-[0.22em] text-white/90 [writing-mode:vertical-rl] 2xl:block"
        >
          Vuelos / Hoteles / Excursiones
        </p>

        <div className="relative mx-auto w-[92%] max-w-300">
          <p className="antetitulo text-white">Hola, somos Aurora Viajes. Una agencia —</p>

          <h1 className="mt-6 text-[clamp(3.5rem,10.5vw,8.6rem)] leading-[1.05] tracking-[-0.02em] text-crema">
            <span className="block">El mundo,</span>
            <span className="mt-4 flex flex-wrap items-center gap-x-8 gap-y-5">
              <PaseDeAbordar className="w-[19.5rem] shrink-0 -rotate-2 sm:w-[23.5rem]" />
              <span>
                a tu <em className="italic">ritmo</em>.
              </span>
            </span>
          </h1>

          <p className="mt-9 max-w-[46ch] text-lg leading-relaxed text-white/95 sm:text-xl">
            Paquetes cerrados o viajes a la carta: vuelo, hotel y excursiones en una sola reserva.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/reservas" className="boton-claro px-7 py-4 text-sm font-semibold no-underline">
              Reservar ahora
            </Link>
            <Link to={{ pathname: "/", hash: "#destinos" }} className="boton-vidrio px-7 py-4 text-sm font-semibold no-underline">
              Ver destinos
            </Link>
          </div>
        </div>

        <BordeDeNubes className="absolute inset-x-0 -bottom-px h-24 w-full text-fondo sm:h-36" />
      </section>

      <section className="bg-fondo py-20 sm:py-32" aria-label="Quiénes somos en breve">
        <div className="mx-auto w-[92%] max-w-245">
          <TextoRevelado partes={HISTORIA} className="text-[clamp(1.6rem,3.3vw,2.6rem)] leading-[1.28] tracking-[-0.035em] text-primario" />
          <TextoRevelado partes={CIERRE} className="mt-10 text-[clamp(1.6rem,3.3vw,2.6rem)] leading-[1.28] tracking-[-0.035em] text-primario" />
        </div>
      </section>

      <section id="destinos" className="scroll-mt-4 bg-fondo pb-24 sm:pb-36" aria-labelledby="destinos-titulo">
        <div className="mx-auto w-[92%] max-w-300">
          <Revelar className="mb-12 flex flex-wrap items-end justify-between gap-6 sm:mb-16">
            <div>
              <p className="antetitulo">Destinos</p>
              <h2 id="destinos-titulo" className="mt-4 max-w-[14ch] text-[clamp(2.6rem,6vw,4.6rem)] leading-[1.03] tracking-[-0.03em]">
                {lugaresPara(destinos.length)} <em className="titulo-enfasis">empezar</em>
              </h2>
            </div>
            <p className="max-w-[38ch] leading-relaxed text-texto-suave">
              Elige uno y arma tu viaje: un paquete listo o a la carta, con precio por pasajero desde el primer paso.
            </p>
          </Revelar>
          <Revelar>
            <CarruselDeDestinos items={destinos} />
          </Revelar>
        </div>
      </section>

      <section className="bg-arena py-24 sm:py-36" aria-labelledby="pasos-titulo">
        <div className="mx-auto w-[92%] max-w-300">
          <Revelar>
            <p className="antetitulo">Cómo funciona</p>
            <h2 id="pasos-titulo" className="mt-4 text-[clamp(2.6rem,6vw,4.6rem)] leading-[1.03] tracking-[-0.03em]">
              Tres pasos y a volar
            </h2>
          </Revelar>

          <ol className="mt-14 grid list-none gap-6 p-0 md:mt-20 md:grid-cols-3">
            {PASOS.map((paso, indice) => (
              <Revelar as="li" key={paso.numero} retraso={indice * 120} className={indice === 1 ? "md:mt-12" : ""}>
                <article
                  className={`h-full rounded-[2.1rem] bg-fondo p-8 shadow-[0_1px_0_rgba(255,255,255,0.9)_inset,0_30px_50px_-34px_rgba(23,21,15,0.45)] transition-transform duration-500 ease-resorte hover:rotate-0 sm:p-9 ${paso.giro}`}
                >
                  <span className="font-display text-7xl leading-none text-acento-suave">{paso.numero}</span>
                  <h3 className="mt-7 font-display text-[2rem] leading-tight">{paso.titulo}</h3>
                  <p className="mt-3 leading-relaxed text-texto-suave">{paso.texto}</p>
                  <p className="antetitulo mt-8">{paso.etiqueta}</p>
                </article>
              </Revelar>
            ))}
          </ol>
        </div>
      </section>

      <Sponsors />
    </div>
  );
}

export default Index;
