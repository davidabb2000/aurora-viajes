# Aurora Viajes

Agencia de viajes en línea. El cliente reserva un **paquete cerrado** o arma su viaje **a la carta** (vuelo + hotel + excursiones), paga con Stripe y sigue su reserva desde un panel. El personal gestiona vuelos, paquetes, reservas, facturas y reportes.

| Pieza | Tecnología | Dónde corre |
|---|---|---|
| `frontend/` | React 19, Vite, Tailwind 4, React Router | Cloudflare |
| `backend/` | FastAPI, SQLAlchemy async, Pydantic | Railway (Docker) |
| Base de datos | MySQL | Aiven (plan gratuito) |

Guías: **[DESPLIEGUE.md](DESPLIEGUE.md)** (producción, variables, Stripe, costes) y **[INTEGRACION_FULL_STACK.md](INTEGRACION_FULL_STACK.md)** (cómo se conectan las piezas).

## Estructura

```
backend/
├── app/
│   ├── main.py          # ensambla la app: ciclo de vida, formato de errores, routers
│   ├── core/            # configuración, base de datos, JWT y hash, limitador de peticiones
│   ├── models/          # dominio.py: tablas
│   ├── schemas/         # validación de las entradas (Pydantic)
│   ├── routers/         # un archivo por tema: auth, usuarios, catalogo, viajes, reservas,
│   │                    # pagos, comercial (ventas, reportes, PQR, chatbot), contacto, recomendaciones
│   └── services/        # reglas de negocio: reservas, precios, pagos (Stripe), siembra y
│                        # migraciones, correos, documentos PDF/XLSX, IA
├── tests/               # pytest sobre una SQLite temporal (nunca lee .env)
├── scripts/             # exportar_esquema.py, probar_smtp.py
├── sql/schema.sql       # esquema MySQL, generado desde los modelos
└── postman/             # colección del quinto avance
frontend/src/
├── pages/  components/  layouts/  context/  utils/  data/
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

Con `MOTOR_BD=sqlite` el backend funciona sin MySQL. Al arrancar crea las tablas, siembra destinos, vuelos, hoteles, excursiones, paquetes y roles, y deja creado el administrador (`ADMIN_EMAIL` / `ADMIN_PASSWORD`). No hace falta importar ningún `.sql`; `sql/schema.sql` existe solo para quien quiera crear la base a mano y se regenera con `python -m scripts.exportar_esquema`.

## Pruebas

```powershell
cd backend
pytest
```

La suite fija sus variables de entorno antes de importar la app y aborta si la configuración apuntara a algo que no sea SQLite, así que no toca la base, el correo, Stripe ni la IA aunque tengas un `.env` real.

## Contrato principal de la API

Todas las rutas cuelgan de `/api`. Las marcadas con 🔒 exigen sesión (`Authorization: Bearer <token>`).

- **Sesión:** `POST /auth/login`, `POST /usuarios/registro`, `POST /auth/recuperar`, `POST /auth/restablecer`
- **Catálogo:** `GET /catalogos/destinos`, `GET /catalogos/destinos/{id}/opciones`, 🔒 `GET /vuelos`, `/hoteles`, `/excursiones`, `/paquetes`
- **Reservas 🔒:** `POST /reservas`, `GET /reservas/mias`, `GET|PUT|DELETE /reservas/{id}`, `PATCH /reservas/{id}/estado`
- **Pagos 🔒:** `POST /reservas/{id}/pago/checkout`, `POST /reservas/{id}/pago/confirmar`; webhook de Stripe: `POST /pagos/stripe/webhook`
- **Comercial 🔒:** `GET /ventas`, `GET /facturas`, `GET /facturas/{id}/pdf`, `GET /reportes/ventas?formato=json|pdf|xlsx`, `GET /estadisticas`, `POST|GET|PATCH /pqr`, `POST /chatbot`, `POST /destinos/recomendaciones`
- **Contacto:** `POST /contacto`
- **Salud:** `GET /api/health`

Cada reserva crea sola su **venta** y su **factura**, enlazadas con ella: pagar la reserva completa la venta y cancelarla (o eliminarla, si no estaba pagada) la anula. `POST /ventas` es una venta de mostrador de productos y servicios y solo la registra el personal.

## Precios

El servidor calcula el precio; el cliente solo lo muestra.

- **A la carta:** vuelo por pasajero (`precio_base` del destino) + hotel por noche y habitación (dos personas por habitación) + excursiones por pasajero.
- **Paquete:** precio cerrado por pasajero; el hotel y las excursiones ya van incluidos y en la factura figuran a valor cero.

El desglose se guarda en la reserva, así que un cambio posterior de tarifas no altera lo ya emitido.

## Variables de entorno (backend)

Todas van en `backend/.env` en local y en las variables del servicio en Railway. Nunca se suben al repositorio; `backend/.env.example` lista las disponibles.

| Variable | Uso |
|---|---|
| `SECRET_KEY` | Firma de los JWT. **Obligatoria**: sin ella la app no arranca. |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Administrador inicial. La contraseña se vuelve a aplicar en cada arranque. |
| `DATABASE_URL` o `MYSQL_*` | Conexión a la base (una URL de Aiven activa TLS sola). `MOTOR_BD=sqlite` para desarrollo sin MySQL. |
| `ORIGENES_PERMITIDOS`, `FRONTEND_URL` | CORS y enlaces de retorno de Stripe. |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Cobro y confirmación de pagos (el webhook exige su secreto). |
| `PROVEEDOR_IA_API_KEY`, `_URL`, `_MODELO` | Recomendaciones y chatbot; sin clave hay respaldo local. |
| `SMTP_*` | Correos de bienvenida, recuperación y reserva. |
| `BD_SIN_POOL` | Sin conexiones ociosas, para que Railway Serverless pueda dormir el servicio. |

En el frontend solo existe `VITE_API_URL` (URL del backend terminada en `/api`), que Vite incrusta al compilar.

## Diseño del frontend

Paleta de papel crema con tinta casi negra, oro y coral; cielo azul solo en la portada. Tipografías autoalojadas: DM Serif Display (titulares), Space Grotesk (texto) y JetBrains Mono (etiquetas). Los colores, radios, sombras y botones viven como tokens en `frontend/src/index.css`: cambiarlos ahí reviste toda la aplicación. Las animaciones respetan `prefers-reduced-motion`.
