import wspicon from '../assets/images/wsp-icon.png'

function WhatsAppButton({ telefono = "573503576793", mensaje = "Hola, quiero información sobre sus viajes." }) {
  const enlace = `https://wa.me/${telefono}?text=${encodeURIComponent(mensaje)}`;

  return (
    <a
      href={enlace}
      target="_blank"
      rel="noreferrer"
      aria-label="Contactar por WhatsApp"
      className="fixed bottom-5 right-5 z-30 flex h-14 w-14 items-center justify-center rounded-full border border-white/40 bg-[#25D366]/90 p-3 text-2xl text-white shadow-lg shadow-[#25D366]/40 backdrop-blur-sm transition hover:scale-110 hover:bg-[#1ebe5d]"
    >
      <span aria-hidden="true"><img src={wspicon} alt="" /></span>
    </a>
  );
}

export default WhatsAppButton;
