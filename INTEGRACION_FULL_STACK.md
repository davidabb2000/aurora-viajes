# Integración full stack

Cómo se conectan las piezas de Aurora Viajes. Para arrancar el proyecto y ver el listado de rutas, ve al [README](README.md); para producción, a [DESPLIEGUE.md](DESPLIEGUE.md).

```
React + Vite ──fetch──▶ FastAPI ──Pydantic──▶ servicios ──SQLAlchemy──▶ MySQL
   (Cloudflare)          (Railway)                                       (Aiven)
```

## Frontend

### Una sola puerta hacia la API

Todo el tráfico pasa por `solicitar()` en [frontend/src/utils/api.js](frontend/src/utils/api.js). Esa función:

- toma la URL base de `VITE_API_URL` o, si no existe, usa `/api` (en desarrollo Vite lo reenvía a `http://127.0.0.1:8001`, ver [vite.config.js](frontend/vite.config.js));
- envía y recibe JSON;
- **adjunta sola el token de la sesión**, de modo que las páginas no repiten la cabecera `Authorization`;
- convierte los errores del backend en un `ErrorApi` con mensaje legible, código y los problemas por campo (`detalles`), para pintarlos junto a cada input; si el servidor está caído (502, 503, 504 o un fallo de red con internet disponible) el mensaje es «El servicio no está disponible en este momento», y solo se culpa a la conexión de quien navega si el navegador está sin internet;
- cierra la sesión si el token caducó o se revocó, y lleva a `/cambiar-contrasena` si la cuenta tiene una clave provisional (código `cambio_de_contrasena_requerido`).

### Sesión

`guardarSesion()` guarda el token y el usuario en `localStorage` (si el usuario marca «Recordarme») o en `sessionStorage`. [AuthContext](frontend/src/context/AuthContext.jsx) los comparte con toda la app, se mantiene sincronizado entre pestañas y ofrece `renovarSesion` (tras cambiar la contraseña, para tomar el token nuevo) y `cerrarTodasLasSesiones`.

Las rutas protegidas usan [RutaProtegida](frontend/src/components/RutaProtegida.jsx): sin sesión redirigen a `/login` guardando en `state.desde` a dónde volver, y con una clave provisional llevan a `/cambiar-contrasena`. `SoloInvitados` hace lo contrario con `/login`, `/registro` y `/acceso-personal`: quien ya tiene sesión no las necesita. El token va en la cabecera `Authorization`, no en cookies.

### Estructura de `frontend/src`

| Carpeta | Contenido |
|---|---|
| `pages/` | Una por ruta: `Index`, `Login`, `Registro`, `AccesoPersonal`, `RecuperarContrasena`, `RestablecerContrasena`, `CambiarContrasena`, `Reservas`, `Panel`, `AvanceCinco` (dashboard comercial), `Recomendaciones`, `PagoReserva`, `PagoExitoso`, `Contacto`, `QuienesSomos`, `NoEncontrada` |
| `pages/panel/` | Una vista del panel cada una, elegida por `?vista=`: `ReservasPanel`, `NuevaReserva`, `VuelosPanel` (con el manifiesto de cada vuelo, `ManifiestoDeVuelo`), `CatalogoPanel` (paquetes, hoteles, excursiones, destinos y lugares), `UsuariosPanel`, `MensajesPanel` |
| `components/reserva/` | `AsistenteDeReserva` (el mismo para clientes y personal), sus pasos, `TarjetaDeVuelo`, `ResumenDeViaje`, `SelectorDeCliente`, `DetalleDeReserva`, `PasajerosDeLaReserva` (datos de quienes viajan) y `MisReservas` |
| `components/` | `Header`, `Footer`, `Sidebar`, `RutaProtegida`, formularios (`Input`, `Select`, `Button`), `auth/` (marco de las pantallas de acceso e indicador de contraseña), `CarruselDeDestinos` (los destinos de la portada), `GoogleMap` (el mapa del pie), `Sponsors` y las decoraciones de la portada |
| `layouts/` | `ClientLayout` (cabecera, pie y WhatsApp) y `AdminLayout` (barra lateral del panel) |
| `context/` | `AuthContext` (el proveedor de la sesión) y `useAuth` (el hook, aparte para que el proveedor sea un archivo de un solo componente) |
| `utils/` | `api.js`, `validaciones.js` (las mismas reglas que valida el backend), `formato.js` (moneda, fechas), `rutas.js` y `useCarga.js` (carga de datos con estado de carga y error) |
| `data/` | `destinos.js`: nombre, texto e ilustración de cada destino |

El enrutado está en [App.jsx](frontend/src/App.jsx): las rutas `/panel*` usan `AdminLayout` cuando hay sesión (y la clave no es provisional); el resto, `ClientLayout`. Al cambiar de página se vuelve arriba, salvo si la dirección trae un ancla.

### El asistente de reserva

`AsistenteDeReserva` no repite ninguna fórmula: cada vez que cambia la selección pide `POST /reservas/cotizar` y muestra lo que devuelve el servidor (total, desglose, noches, plazas libres). Los vuelos, hoteles, excursiones y paquetes de un destino llegan en una sola llamada, `GET /catalogos/destinos/{id}/opciones`. Al editar una reserva se conservan las piezas que ya tenía aunque el catálogo las haya retirado, y la cotización lleva el `reservaId` para aplicar las reglas de la edición.

## Backend

Rutas JSON bajo `/api`, en capas que no se saltan:

1. **`routers/`** reciben la petición, aplican la autorización y devuelven JSON. No contienen reglas de negocio.
2. **`schemas/`** validan la entrada con Pydantic. Los errores salen con un formato único: `{codigo, mensaje, ruta, detalles}`.
3. **`services/`** guardan las reglas: qué vuelo, hotel y excursiones son válidos, cuánto cuesta, cómo se factura, cómo se cobra.
4. **`models/dominio.py`** define las tablas con SQLAlchemy async. La sesión de base de datos se abre y cierra por petición ([core/base_datos.py](backend/app/core/base_datos.py)).

### Seguridad

- Las contraseñas se guardan con **argon2** y nunca en texto plano ([core/seguridad.py](backend/app/core/seguridad.py)); la política (longitud, composición, lista de claves comunes, sin el correo ni el nombre) está en [core/politica_contrasena.py](backend/app/core/politica_contrasena.py) y el frontend la repite para avisar antes de enviar.
- La sesión es un **JWT** con algoritmo fijo, campos obligatorios y un campo `purpose`: el token del correo de recuperación solo sirve para restablecer la contraseña y no abre sesión. Lleva además la versión de sesión del usuario (`sv`): cambiar la contraseña o el rol, desactivar la cuenta o «cerrar todas las sesiones» la incrementa y los tokens anteriores dejan de valer. El enlace de recuperación lleva una huella de la contraseña vigente, así que sirve una sola vez.
- El rol y el estado de la cuenta se leen de la base en cada petición, no del token.
- Las cuentas con **clave provisional** (las que crea un administrador, o el administrador con la clave de ejemplo) solo pueden cambiarla: el resto de la API responde `cambio_de_contrasena_requerido`.
- Login, registro, recuperación, cotización, contacto y chatbot tienen **límite de peticiones**, por IP real (`X-Forwarded-For` contado desde la derecha) y, en el login, también por correo. El chatbot además exige sesión y arma su contexto con mensajes que guardó el propio servidor.
- El login y la recuperación responden igual exista o no el correo.
- Todo el SQL pasa por el ORM con parámetros, y una prueba estática impide construirlo con texto.
- Las respuestas llevan cabeceras de seguridad, el cuerpo de la petición está limitado a 1 MB y CORS solo admite `ORIGENES_PERMITIDOS`.

### Una reserva de principio a fin

```
POST /reservas/cotizar ─▶ preparar_reserva(bloquear=False)   el precio que verá el cliente, sin guardar nada
POST /reservas ─▶ preparar_reserva()   valida vuelos, hotel y excursiones contra el catálogo, bloquea las filas de
                                       los vuelos, comprueba las plazas de ida y regreso y calcula el precio
              ─▶ crea Reserva + Venta (enlazada) + Factura, en una sola transacción
              ─▶ si la crea el personal, puede cobrarla en el mismo paso (efectivo, transferencia o datáfono)
PUT /reservas/{id}/pasajeros ─▶ los datos de quienes viajan (opcionales; nunca más que las plazas ni una persona dos veces en el mismo vuelo)
GET /vuelos/{id}/manifiesto ─▶ quién viaja en un vuelo, con lo que falta por completar (personal)
POST /reservas/{id}/pago/checkout ─▶ un único enlace de Stripe abierto por reserva
Stripe cobra ─▶ POST /pagos/stripe/webhook   (firmado)   ─▶ reserva "confirmada / pagada" y venta "completada"
             └▶ el navegador vuelve a /reservas/pago-exitoso y llama a .../pago/confirmar (respaldo)
```

Ambas vías de confirmación son idempotentes: da igual cuál llegue primero o si llegan las dos. Antes de aceptar un pago se comprueba que la sesión de Stripe pertenezca a esa reserva y que el importe y la moneda coincidan con su total. El estado de la venta y de su factura se deriva siempre del estado de la reserva (`services/reservas.py::sincronizar_venta`).

### Base de datos

Las tablas nacen de los modelos (`create_all`), normalizadas a 3FN: los lugares (`paises` → `ciudades`), las aerolíneas y los modelos de avión son tablas propias, y vuelos, hoteles, excursiones y destinos las referencian por identificador. El detalle está en el [README](README.md#modelo-de-datos-3fn).

Al arrancar sobre una base MySQL con el esquema anterior, `services/migraciones.py` la migra (con copias `respaldo_v2_*`, de forma idempotente y reanudable) y después `services/siembra.py` completa los datos iniciales y repone la programación de vuelos. Cuando la migración termina sin nada pendiente deja una marca en `esquema_version` y los reinicios siguientes se la saltan; la siembra lee los catálogos enteros y compara en memoria, así que un arranque sin cambios son unas treinta consultas y no cuatrocientas (cada una es una ida y vuelta por la red con una base remota).

Si la base no responde al arrancar, `main.py` no se cae: levanta la API en modo degradado (todo responde 503, salvo `/api/health`) y reintenta en segundo plano hasta que la base vuelve; el estado se guarda en `core/estado_arranque.py` y lo ve la puerta `exigir_base_lista` de `middlewares.py`. Para bases nuevas y para documentar, `sql/schema.sql` se genera desde los modelos con `python -m scripts.exportar_esquema`.
