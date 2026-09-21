# Aurora Viajes

Agencia de viajes en línea. El cliente reserva un **paquete cerrado** o arma su viaje **a la carta** (vuelo de ida y regreso + hotel + excursiones) con un asistente que le muestra el precio exacto en cada paso, paga con Stripe y sigue sus reservas desde su cuenta. El personal atiende también en el **mostrador**: reserva a nombre de un cliente, cobra en el momento y gestiona vuelos, catálogo, usuarios, facturas y reportes.

| Pieza | Tecnología | Dónde corre |
|---|---|---|
| `frontend/` | React 19, Vite, Tailwind 4, React Router | Cloudflare |
| `backend/` | FastAPI, SQLAlchemy async, Pydantic | Railway (Docker) |
| Base de datos | MySQL | Aiven (plan gratuito) |

Guías: **[DESPLIEGUE.md](DESPLIEGUE.md)** (producción, variables, Stripe, costes) y **[INTEGRACION_FULL_STACK.md](INTEGRACION_FULL_STACK.md)** (cómo se conectan las piezas).

## Páginas

| Ruta | Quién | Para qué |
|---|---|---|
| `/`, `/quienes-somos`, `/contacto` | todos | Portada, la agencia y formulario de contacto |
| `/registro`, `/login` | invitados | Crear cuenta e iniciar sesión (clientes) |
| `/acceso-personal` | invitados | Entrada del equipo; rechaza las cuentas de cliente |
| `/recuperar`, `/restablecer` | todos | Recuperar la contraseña por correo; el enlace sirve una sola vez |
| `/cambiar-contrasena` | con sesión | Cambio voluntario, u obligatorio si la clave es provisional |
| `/reservas` | con sesión | Asistente de reserva y las reservas del cliente |
| `/reservas/pago/:id`, `/reservas/pago-exitoso` | con sesión | Pago con Stripe y retorno |
| `/recomendaciones` | con sesión | Sugerencias de destinos con IA |
| `/panel` | con sesión | Cliente: sus reservas. Personal: `?vista=` reservas, nueva, vuelos; administrador además catálogo, usuarios y mensajes |
| `/panel/avance-cinco` | personal | Resumen comercial, ventas, facturas, PQR y chatbot |

## Estructura

```
backend/
├── app/
│   ├── main.py          # ensambla la app: ciclo de vida, formato de errores, middlewares, routers
│   ├── core/            # configuración, base de datos, JWT y hash, política de contraseñas, limitador
│   ├── models/          # dominio.py: tablas y restricciones
│   ├── schemas/         # validación de las entradas (Pydantic)
│   ├── routers/         # auth, usuarios, clientes, catalogo, viajes, reservas, pagos,
│   │                    # comercial (ventas, reportes, PQR, chatbot), contacto, recomendaciones
│   └── services/        # reservas, precios, disponibilidad (plazas), pagos (Stripe), catálogos,
│                        # siembra y migraciones, correos, documentos PDF/XLSX, IA
├── tests/               # pytest sobre una SQLite temporal (nunca lee .env)
├── scripts/             # exportar_esquema.py, probar_smtp.py
├── sql/schema.sql       # esquema MySQL, generado desde los modelos
└── postman/             # colección del quinto avance
frontend/src/
├── pages/               # una por ruta; pages/panel/ tiene cada vista del panel
├── components/          # reserva/ (asistente, tarjetas, detalle), auth/, Header, Footer, Sidebar...
├── layouts/  context/  utils/  data/
```

## Arranque local

Necesitas Python 3.12+, Node 22+ y, para desarrollar contra MySQL, XAMPP (o cualquier MySQL).

```powershell
# Backend  ->  http://127.0.0.1:8001
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }   # edita SECRET_KEY y, si usas MySQL, sus datos
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload

# Frontend  ->  http://localhost:5173  (Vite reenvía /api al backend)
cd frontend
npm install
npm run dev
```

Con `MOTOR_BD=sqlite` el backend funciona sin MySQL. Al arrancar crea las tablas, siembra ciudades, destinos, aerolíneas, aviones, hoteles, excursiones, paquetes y roles, programa vuelos y deja creado el administrador (`ADMIN_EMAIL` / `ADMIN_PASSWORD`). Si dejas la clave de ejemplo (`Admin123!`), la cuenta obliga a cambiarla en el primer acceso. No hace falta importar ningún `.sql`; `sql/schema.sql` existe solo para quien quiera crear la base a mano y se regenera con `python -m scripts.exportar_esquema`.

Los vuelos sembrados son una programación **rodante**: una salida semanal Bogotá ↔ cada destino, con regreso a las `noches` del paquete, siempre a partir de unos diez días y hasta unos setenta. Cada arranque repone lo que ya pasó y los paquetes de ejemplo saltan a la siguiente salida; lo que edite un administrador no se sobrescribe.

## Pruebas

```powershell
cd backend
pytest
```

La suite fija sus variables de entorno antes de importar la app y aborta si la configuración apuntara a algo que no sea SQLite, así que no toca la base, el correo, Stripe ni la IA aunque tengas un `.env` real. Cubre precios, plazas, cobro en mostrador, cuentas, inyección SQL, tokens manipulados, límites de intentos y una revisión estática que prohíbe construir SQL con texto (también en las migraciones).

En el frontend: `npm run lint` y `npm run build`.

## Modelo de datos (3FN)

Cada dato vive en un solo sitio y las piezas se enlazan por identificador, no por texto:

- **Lugares:** `paises` → `ciudades`. Destinos, hoteles, excursiones y vuelos (origen y destino) apuntan a una `ciudad_id`; nunca se comparan nombres.
- **Vuelos:** `aerolineas` y `modelos_avion` (con la capacidad física del avión). Cada vuelo vende `capacidad_maxima` plazas, sin pasar de las del modelo, y `(numero_vuelo, fecha_salida)` es único.
- **Paquetes:** guardan las `noches`; sus fechas salen de los vuelos. Sus excursiones van en una tabla de asociación.
- **Reservas:** un vuelo de ida (`vuelo_id`) y, si lo hay, uno de regreso (`vuelo_regreso_id`). Las excursiones están en `reserva_excursiones`, que guarda la `cantidad` de personas y el `precio_unitario` con que se vendió.
- **Catálogos de estado:** estado de la reserva, del pago y método de pago.
- **Copias intencionales:** el desglose de la reserva y sus fechas se guardan tal como se vendieron, para que un cambio de tarifas no altere lo emitido. La base lo vigila con restricciones `CHECK` (el total es la suma de sus partes, el regreso no precede a la salida, precios no negativos...).

Al arrancar contra una base MySQL con el esquema anterior, `services/migraciones.py` la migra sola: primero crea copias `respaldo_v2_*` de las tablas que va a tocar, luego expande, copia los datos y contrae, de forma idempotente y reanudable si se interrumpe. Un archivo SQLite con el esquema antiguo se rechaza con un mensaje claro (la SQLite es solo para desarrollo: bórrala y se vuelve a crear).

## Cómo se reserva

Cliente y personal usan el mismo asistente (`components/reserva/AsistenteDeReserva.jsx`): destino, pasajeros y tipo → vuelos (o paquete) → hotel y excursiones → confirmar. El personal añade un primer paso para elegir o dar de alta al cliente, y al final puede cobrar en el acto.

- **El precio lo calcula el servidor**, con `POST /reservas/cotizar`, que usa exactamente la misma función que la reserva real: lo que se ve es lo que se cobra. Al editar, la cotización recibe el `reservaId` y aplica las reglas de la edición.
  - *A la carta:* vuelo por pasajero (`precio_base` del destino) + hotel por noche y habitación (dos personas por habitación) + excursiones por persona.
  - *Paquete:* precio cerrado por pasajero; el hotel y las excursiones ya van incluidos y en la factura figuran a valor cero.
- **Plazas:** se cuentan las de ida y regreso de las reservas no canceladas. Al reservar, editar o reactivar se bloquean las filas de los vuelos (en orden, para no provocar interbloqueos): con 3 plazas libres y 12 reservas simultáneas se venden exactamente 3.
- **Precios ya vendidos:** al editar una reserva, lo que no se toca conserva su tarifa. Un hotel, excursión o paquete que el catálogo retiró después de la venta se conserva en esa reserva, pero no se ofrece a reservas nuevas.
- **Estados:** confirmar exige el pago; una reserva pagada no vuelve a pendiente ni cambia de precio (se cancela y se crea otra); reactivar una cancelada vuelve a comprobar las plazas. El cliente puede cancelar la que aún no pagó; el personal puede cancelar cualquiera. Una reserva ajena responde «no existe».
- **Mostrador:** el personal reserva a nombre de un cliente (`clienteId`) y puede registrar el cobro en efectivo, transferencia o datáfono, con referencia, quién lo cobró y cuándo. Cada reserva crea sola su **venta** y su **factura**, enlazadas: pagar completa la venta y cancelar (o eliminar, si no estaba pagada) la anula.

## Contrato principal de la API

Todas las rutas cuelgan de `/api`. Las marcadas con 🔒 exigen sesión (`Authorization: Bearer <token>`); *personal* es empleado o administrador.

- **Sesión:** `POST /usuarios/registro`, `POST /auth/login`, 🔒 `GET /auth/yo`, 🔒 `POST /auth/cambiar-contrasena`, 🔒 `POST /auth/cerrar-sesiones`, `POST /auth/recuperar`, `POST /auth/restablecer`
- **Catálogo público:** `GET /catalogos/destinos`, `GET /catalogos/destinos/{id}/opciones` (vuelos, hoteles, excursiones y paquetes con sus plazas libres)
- **Catálogo 🔒:** lectura para el personal y escritura para el administrador de `/vuelos`, `/hoteles`, `/excursiones`, `/paquetes` (`DELETE` los desactiva), `/ciudades`, `/aerolineas`, `/modelos-avion`
- **Clientes 🔒 personal:** `GET /clientes?q=`, `POST /clientes`
- **Usuarios 🔒 administrador:** `GET|POST /usuarios`, `GET|PUT|DELETE /usuarios/{id}`, `PATCH /usuarios/{id}/estado`
- **Reservas 🔒:** `POST /reservas/cotizar`, `POST /reservas`, `GET /reservas/mias`, `GET /reservas` (personal), `GET|PUT|DELETE /reservas/{id}`, `PATCH /reservas/{id}/estado`, `POST /reservas/{id}/cancelar`
- **Pagos 🔒:** `POST /reservas/{id}/pago/checkout`, `POST /reservas/{id}/pago/confirmar`, `POST /reservas/{id}/pago/manual` (personal); webhook de Stripe: `POST /pagos/stripe/webhook`
- **Comercial 🔒:** `GET /ventas`, `GET /facturas`, `GET /facturas/{id}/pdf`, `GET /reportes/ventas?formato=json|pdf|xlsx`, `GET /estadisticas`, `POST|GET|PATCH /pqr`, `POST /chatbot`, `POST /destinos/recomendaciones`
- **Contacto:** `POST /contacto` (público), `GET /contacto` (administrador)
- **Salud:** `GET /api/health`

Los errores tienen un formato único: `{codigo, mensaje, ruta, detalles}`, con los problemas por campo en `detalles`.

## Seguridad

- **Inyección SQL:** todo el acceso es por el ORM con parámetros; una prueba estática recorre el código y falla si alguna consulta se construye con texto. Los comodines de las búsquedas se escapan. Los identificadores del SQL de las migraciones se validan.
- **Contraseñas:** argon2; mínimo 8 caracteres (máximo 128) con mayúscula, minúscula, número y símbolo, sin contraseñas comunes ni el correo o el nombre dentro. Las cuentas que crea un administrador nacen con clave provisional y obligan a cambiarla antes de hacer nada más.
- **Sesión:** JWT con algoritmo fijo y campos obligatorios. Cambiar la contraseña, cambiar el rol, desactivar la cuenta o «cerrar sesión en todos los dispositivos» invalida los tokens anteriores; el enlace de recuperación es de un solo uso y solo sirve para restablecer.
- **Intentos:** límites por IP, por correo y por correo+IP en login, registro, recuperación y cotización, sin que un atacante pueda bloquear a otra persona. La IP sale de `X-Forwarded-For` contando desde la derecha (`PROXIES_DE_CONFIANZA`).
- **Cuentas:** el login y la recuperación responden igual exista o no el correo; el correo de recuperación se envía después de responder; no se puede dejar sin administradores ni borrar a quien tiene historial.
- **Servidor:** cuerpo máximo de 1 MB, `/docs` y `openapi.json` ocultos salvo con `DEPURACION`, `IntegrityError` como 409, cabeceras de seguridad y CORS solo con `ORIGENES_PERMITIDOS`. El webhook de Stripe valida firma, sesión, importe y moneda.
- **Web:** el build genera `_headers` con una política de contenido estricta (solo lo propio, el mapa de Google y la API), `X-Frame-Options`, `Referrer-Policy: no-referrer` y `Permissions-Policy`. React escapa todo lo que se muestra; el token va en la cabecera `Authorization` (sin cookies), así que no hay CSRF.

## Variables de entorno (backend)

Todas van en `backend/.env` en local y en las variables del servicio en Railway. Nunca se suben al repositorio; `backend/.env.example` lista las disponibles.

| Variable | Uso |
|---|---|
| `SECRET_KEY` | Firma de los JWT. **Obligatoria**: sin ella la app no arranca. |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Administrador inicial, que se crea una sola vez. Con la clave de ejemplo (`Admin123!`) obliga a cambiarla al entrar. |
| `ADMIN_RESTABLECER_CONTRASENA` | En `true`, el siguiente arranque vuelve a fijar la clave del administrador a `ADMIN_PASSWORD` (para recuperar el acceso). |
| `DATABASE_URL` o `MYSQL_*` | Conexión a la base (una URL de Aiven activa TLS sola). `MOTOR_BD=sqlite` para desarrollo sin MySQL. |
| `ORIGENES_PERMITIDOS`, `FRONTEND_URL` | CORS y enlaces de retorno de Stripe y de los correos. |
| `PROXIES_DE_CONFIANZA` | Proxies delante de la app (Railway = 1; con 0 se ignora `X-Forwarded-For`). |
| `DEPURACION` | `true` publica `/docs` y registra cada consulta SQL. Solo para desarrollo. |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Cobro y confirmación de pagos (el webhook exige su secreto). |
| `PROVEEDOR_IA_API_KEY`, `_URL`, `_MODELO` | Recomendaciones y chatbot; sin clave hay respaldo local. |
| `SMTP_*` | Correos de bienvenida, recuperación y reserva. |
| `BD_SIN_POOL` | Sin conexiones ociosas, para que Railway Serverless pueda dormir el servicio. |

En el frontend solo existe `VITE_API_URL` (URL del backend terminada en `/api`), que Vite incrusta al compilar y de la que sale también el origen permitido en la política de contenido.

## Diseño del frontend

Paleta de papel crema con tinta casi negra, oro y coral; cielo azul solo en la portada. Tipografías autoalojadas: DM Serif Display (titulares), Space Grotesk (texto) y JetBrains Mono (etiquetas). Los colores, radios, sombras y botones viven como tokens en `frontend/src/index.css`: cambiarlos ahí reviste toda la aplicación. Las animaciones respetan `prefers-reduced-motion`.
