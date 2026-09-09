import api from './api';

export const iniciarSesion = async (documento, password) => {
  const datosFormulario = new URLSearchParams();
  datosFormulario.append('username', documento); // FastAPI espera 'username' aunque sea tu documento
  datosFormulario.append('password', password);

  const respuesta = await api.post('/auth/token', datosFormulario, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });
  
  if (respuesta.data.acceso) {
    localStorage.setItem('token_acceso', respuesta.data.acceso);
  }
  return respuesta.data;
};

export const obtenerPerfilActual = async () => {
  const respuesta = await api.get('/auth/yo');
  return respuesta.data;
};