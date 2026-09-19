/**
 * Componente de mapa de Google.
 * Integra Google Maps para mostrar la ubicación de la empresa.
 */
function GoogleMap() {
  // Coordenadas de ejemplo (Medellín, Colombia)
  const latitud = 6.2442;
  const longitud = -75.5898;
  const direccion = "Medellín, Colombia";

  // API Key - Asegúrate de configurar esto en tus variables de entorno
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || "";

  // URL de Google Maps
  const googleMapsUrl = `https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3965.7503215!2d${longitud}!3d${latitud}!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x8e4428c0e3dd09f7%3A0x1234567890abcdef!2s${encodeURIComponent(direccion)}!5e0!3m2!1ses!2sco!4v1234567890123`;

  return (
    <div className="vidrio-noche h-80 w-full overflow-hidden rounded-3xl p-1.5">
      <iframe
        width="100%"
        height="100%"
        style={{ border: 0, borderRadius: "1.25rem" }}
        allowFullScreen=""
        loading="lazy"
        referrerPolicy="no-referrer-when-downgrade"
        src={googleMapsUrl}
        title="Ubicación de Aurora Viajes"
      />
    </div>
  );
}

export default GoogleMap;
