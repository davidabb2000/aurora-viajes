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
- convierte los errores del backend en un mensaje legible y cierra la sesión si el token caducó.

### Sesión

`guardarSesion()` guarda el token y el usuario en `localStorage` (si el usuario marca «Recordarme») o en `sessionStorage`. [AuthContext](frontend/src/context/AuthContext.jsx) los comparte con toda la app y se mantiene sincronizado entre pestañas. Las páginas protegidas (`Reservas`, `Panel`, pagos) redirigen a `/login` guardando en `state.desde` a dónde volver, y el Login devuelve al usuario allí tras entrar.

### Estructura de `frontend/src`

| Carpeta | Contenido |
|---|---|
| `pages/` | Una por ruta: `Index`, `Login`, `Reservas`, `Panel`, `AvanceCinco` (dashboard comercial), `Recomendaciones`, `PagoReserva`, `PagoExitoso`, `Contacto`, `QuienesSomos` |
| `components/` | Piezas reutilizables: `Header`, `Footer`, `Sidebar`, formularios (`Input`, `Select`, `Button`, `Modal`), `DestinosGrid`, `Sponsors` y las decoraciones de la portada |
| `layouts/` | `ClientLayout` (cabecera, pie y WhatsApp) y `AdminLayout` (barra lateral del panel) |
| `context/` | `AuthContext` |
| `utils/` | `api.js` y `validaciones.js` (las mismas reglas que valida el backend) |
| `data/` | `destinos.js`: nombre, texto e ilustración de cada destino |

El enrutado está en [App.jsx](frontend/src/App.jsx): las rutas `/panel*` usan `AdminLayout` cuando hay sesión; el resto, `ClientLayout`.

## Backend

Rutas JSON bajo `/api`, en capas que no se saltan:

1. **`routers/`** reciben la petición, aplican la autorización y devuelven JSON. No contienen reglas de negocio.
2. **`schemas/`** validan la entrada con Pydantic. Los errores salen con un formato único: `{codigo, mensaje, ruta, detalles}`.
3. **`services/`** guardan las reglas: qué vuelo, hotel y excursiones son válidos, cuánto cuesta, cómo se factura, cómo se cobra.
4. **`models/dominio.py`** define las tablas con SQLAlchemy async. La sesión de base de datos se abre y cierra por petición ([core/base_datos.py](backend/app/core/base_datos.py)).

### Seguridad

- Las contraseñas se guardan con **argon2** y nunca en texto plano ([core/seguridad.py](backend/app/core/seguridad.py)).
- La sesión es un **JWT** con un campo `purpose`: el token del correo de recuperación solo sirve para restablecer la contraseña y no abre sesión.
- El rol se lee de la base en cada petición, no del token.
- Login, registro, recuperación, contacto y chatbot tienen **límite de peticiones**; el chatbot además exige sesión y arma su contexto con mensajes que guardó el propio servidor.
- Las respuestas llevan cabeceras de seguridad y CORS solo admite `ORIGENES_PERMITIDOS`.

### Una reserva de principio a fin

```
POST /reservas ─▶ preparar_reserva()   valida vuelo, hotel y excursiones contra el catálogo y calcula el precio
              ─▶ crea Reserva + Venta (enlazada) + Factura, en una sola transacción
POST /reservas/{id}/pago/checkout ─▶ un único enlace de Stripe abierto por reserva
Stripe cobra ─▶ POST /pagos/stripe/webhook   (firmado)   ─▶ reserva "confirmada / pagada" y venta "completada"
             └▶ el navegador vuelve a /reservas/pago-exitoso y llama a .../pago/confirmar (respaldo)
```

Ambas vías de confirmación son idempotentes: da igual cuál llegue primero o si llegan las dos. Antes de aceptar un pago se comprueba que la sesión de Stripe pertenezca a esa reserva y que el importe y la moneda coincidan con su total. El estado de la venta y de su factura se deriva siempre del estado de la reserva (`services/reservas.py::sincronizar_venta`).

### Base de datos

Las tablas nacen de los modelos (`create_all`). Los cambios de esquema en bases ya existentes los aplica `services/siembra.py` al arrancar, de forma idempotente y solo en MySQL; hoy incluyen la columna `ventas.reserva_id` y el emparejamiento de las ventas anteriores con su reserva. Para bases nuevas y para documentar, `sql/schema.sql` se genera desde los modelos con `python -m scripts.exportar_esquema`.
