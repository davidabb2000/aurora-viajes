function Footer() {
  const anioActual = new Date().getFullYear();

  return (
    <footer className="mt-12 bg-primario text-[#e7e2d4]">
      <div className="mx-auto grid w-[92%] max-w-[1100px] grid-cols-1 gap-8 py-10 sm:grid-cols-3">
        <div>
          <p className="mb-2 font-display text-lg font-bold text-white">Aurora Viajes</p>
          <p className="text-sm text-[#cfc9b8]">Diseñando itinerarios memorables desde 2015.</p>
        </div>

        <div>
          <p className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-acento">Contacto</p>
          <p className="text-sm text-[#cfc9b8]">contacto@auroraviajes.com</p>
          <p className="text-sm text-[#cfc9b8]">+57 3503576793</p>
        </div>

        <div>
          <p className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-acento">Proyecto académico</p>
          <p className="text-sm text-[#cfc9b8]">Ficha 3406211 · SENA</p>
          <p className="text-sm text-[#cfc9b8]">Competencia: React</p>
        </div>
      </div>

      <div className="border-t border-white/10 py-4">
        <p className="mx-auto w-[92%] max-w-[1100px] text-xs text-[#a9a390]">
          © {anioActual} Aurora Viajes. Todos los derechos reservados.
        </p>
      </div>
    </footer>
  );
}

export default Footer;
