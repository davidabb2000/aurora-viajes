# Aurora Viajes API

Backend en FastAPI para **Aurora Viajes**, con persistencia en **MySQL/XAMPP** en la base `aurora_viajes`.

El esquema está normalizado y mantiene el contrato que consume el frontend:

- `usuarios`
- `roles`
- `permisos`
- `rol_permisos`
- `tipos_documento`
- `paises`
- `destinos`
- `estados_reserva`
- `estados_pago`
- `metodos_pago`
- `productos`
- `servicios`
- `reservas`
- `mensajes_contacto`

## Ejecutar en local

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Si la base no existe, importa primero `sql\schema.sql` en phpMyAdmin.

## Variables importantes

| Variable | Uso |
|---|---|
| `MOTOR_BD` | `mysql` para XAMPP |
| `MYSQL_DATABASE` | Debe ser `aurora_viajes` |
| `MYSQL_HOST` / `MYSQL_PORT` | Conexión a phpMyAdmin/MySQL |
| `SECRET_KEY` | Clave JWT |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Usuario administrador inicial |
| `STRIPE_SECRET_KEY` | Clave privada de Stripe para Checkout |
| `FRONTEND_URL` | URL del frontend para retorno de Stripe |

## Endpoints principales

| Método | Ruta | Uso |
|---|---|---|
| GET | `/api/health` | Estado del servicio |
| POST | `/api/auth/login` | Inicio de sesión |
| POST | `/api/usuarios/registro` | Registro público |
| GET | `/api/usuarios` | Listado administrativo |
| GET/POST/PUT/DELETE | `/api/productos` | CRUD de productos |
| GET/POST/PUT/DELETE | `/api/servicios` | CRUD de servicios |
| GET | `/api/catalogos/destinos` | Catálogo de destinos normalizados |
| POST | `/api/reservas` | Crear reserva |
| GET | `/api/reservas` | Reservas administrativas |
| GET | `/api/reservas/mias` | Reservas del usuario autenticado |
| GET | `/api/reservas/{id}` | Detalle de reserva |
| PUT | `/api/reservas/{id}` | Actualizar reserva |
| POST | `/api/reservas/{id}/pago/checkout` | Checkout de pago |
| POST | `/api/reservas/{id}/pago/confirmar` | Confirmación de pago |
| PATCH | `/api/reservas/{id}/estado` | Cambio de estado |
| POST | `/api/contacto` | Enviar mensaje |

## Base de datos

Las reservas guardan:

- `destino_id`
- `fecha_salida`
- `fecha_regreso`
- `pasajeros`
- `telefono_contacto`
- `notas`
- `estado_id`
- `estado_pago_id`
- `metodo_pago_id`
- `monto_total`
- `stripe_session_id`

El total se calcula con:

- destino (`precio_base`)
- pasajeros
- duración del viaje en días

Stripe recibe el total convertido a su unidad mínima de cobro, mientras el proyecto muestra el valor en pesos.

El frontend sigue viendo los nombres de siempre (`destino`, `estadoPago`, `metodoPago`, etc.) porque el backend resuelve los catálogos y los serializa en ese formato.
