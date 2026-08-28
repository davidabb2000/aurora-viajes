import wspicon from '../assets/images/wsp-icon.png'

function WhatsAppButton({ telefono = "573503576793", mensaje = "Hola, quiero información sobre sus viajes." }) {
  const enlace = `https://wa.me/${telefono}?text=${encodeURIComponent(mensaje)}`;

  return (
    <a
      href={enlace}
      target="_blank"
      rel="noreferrer"
      aria-label="Contactar por WhatsApp"
      className="fixed bottom-5 right-5 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-[#25D366] text-2xl text-white shadow-lg transition hover:scale-105 hover:bg-[#1ebe5d]"
    >
      <span aria-hidden="true"><img src={wspicon} alt="" /></span>
    </a>
  );
}

export default WhatsAppButton;
