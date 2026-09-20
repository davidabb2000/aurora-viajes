/**
 * Mapa de Google con la ubicación de la empresa. Usa la vista embebida pública,
 * que no necesita clave de API.
 */
function GoogleMap() {
  const direccion = "Medellín, Colombia";
  const url = `https://www.google.com/maps?q=${encodeURIComponent(direccion)}&z=13&hl=es&output=embed`;

  return (
    <div className="vidrio h-80 w-full overflow-hidden rounded-3xl p-1.5">
      <iframe
        width="100%"
        height="100%"
        style={{ border: 0, borderRadius: "1.75rem" }}
        allowFullScreen
        loading="lazy"
        referrerPolicy="no-referrer-when-downgrade"
        src={url}
        title="Ubicación de Aurora Viajes"
      />
    </div>
  );
}

export default GoogleMap;
