import { Link } from "react-router-dom";

function NoEncontrada() {
  return (
    <div className="flex flex-1 items-center justify-center px-4 py-24">
      <div className="max-w-xl text-center">
        <p className="font-mono text-sm uppercase tracking-[0.2em] text-texto-suave">Error 404</p>
        <h1 className="mt-4 text-[clamp(3rem,9vw,6rem)] leading-none">
          Esta ruta <em className="titulo-enfasis">no existe</em>
        </h1>
        <p className="mx-auto mt-6 max-w-[42ch] text-lg leading-relaxed text-texto-suave">
          Puede que el enlace esté roto o que la página se haya movido. Vuelve al inicio y sigue explorando destinos.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link to="/" className="boton-tinta px-7 py-3.5 text-sm font-semibold no-underline">
            Ir al inicio
          </Link>
          <Link to="/reservas" className="rounded-full border border-primario/25 px-7 py-3.5 text-sm font-medium text-primario no-underline transition hover:bg-primario/5">
            Reservar un viaje
          </Link>
        </div>
      </div>
    </div>
  );
}

export default NoEncontrada;
