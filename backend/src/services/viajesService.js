import api from './api';

export const obtenerPaquetes = async (destinoId = null, precioMax = null) => {
  const params = {};
  if (destinoId) params.destino_id = destinoId;
  if (precioMax) params.precio_max = precioMax;

  const respuesta = await api.get('/paquetes', { params });
  return respuesta.data;
};

export const solicitarRecomendacionIA = async (intereses) => {
  const respuesta = await api.post('/ia/recomendaciones', { intereses });
  return respuesta.data; // Retorna el origen ("modelo_externo" o "catalogo_local") y las 3 sugerencias
};

export const crearReservaYPago = async (salidaId) => {
  const respuesta = await api.post(`/reservas?salida_id=${salidaId}`);
  return respuesta.data; // Contiene la 'url_pago' de Stripe para redirigir al usuario
};