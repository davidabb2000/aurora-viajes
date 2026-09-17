# Aurora Viajes

Proyecto full stack con **React + Vite** en `frontend/` y **FastAPI** en `backend/`.

## Backend

El backend usa MySQL/XAMPP con base `aurora_viajes`, con un esquema normalizado y el contrato que espera el frontend.

Los precios de reserva se calculan por destino, pasajeros y duración del viaje.

### Tablas principales

- usuarios
- roles
- permisos
- rol_permisos
- tipos_documento
- paises
- destinos
- estados_reserva
- estados_pago
- metodos_pago
- productos
- servicios
- vuelos
- hoteles
- excursiones
- paquetes
- paquete_excursiones
- reservas
- mensajes_contacto
- ventas
- detalle_ventas
- facturas
- detalle_facturas
- pqr
- conversaciones
- mensajes

### Arranque

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Si vas a recrear la base desde cero, importa antes `backend\sql\schema.sql` en phpMyAdmin.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

## Integración

El frontend llama a la API mediante `frontend/src/utils/api.js` y Vite redirige `/api` a `http://127.0.0.1:8001`.

## Contrato principal

- `POST /api/auth/login`
- `POST /api/usuarios/registro`
- `GET /api/productos`
- `GET /api/servicios`
- `GET /api/catalogos/destinos`
- `GET /api/vuelos`
- `GET /api/hoteles`
- `GET /api/excursiones`
- `GET /api/paquetes`
- `POST /api/paquetes`
- `POST /api/reservas`
- `GET /api/reservas/mias`
- `GET /api/reservas/{id}`
- `PUT /api/reservas/{id}`
- `POST /api/reservas/{id}/pago/checkout`
- `POST /api/reservas/{id}/pago/confirmar`
- `POST /api/contacto`
- `POST /api/ventas`
- `GET /api/ventas?desde=&hasta=&estado=&cliente_id=&producto_id=&servicio_id=`
- `GET /api/reportes/ventas?fecha=&formato=json|pdf|xlsx`
- `GET /api/facturas?numero=&cliente_id=&desde=&hasta=`
- `GET /api/facturas/{id}/pdf`
- `GET /api/estadisticas?periodo=dia|semana|mes&desde=&hasta=`
- `POST /api/pqr`
- `GET /api/pqr`
- `PATCH /api/pqr/{id}`
- `POST /api/chatbot`

## Observación

El frontend sigue enviando el destino como texto; el backend lo guarda así para mantener compatibilidad con lo que ya existe en la interfaz y en el panel.

### Quinto avance

El dashboard comercial está disponible en `/panel/avance-cinco` para usuarios autenticados. La colección importable de Postman está en `backend/postman/collections/aurora-quinto-avance.postman_collection.json`.

Para IA y despliegue, configura las variables `PROVEEDOR_IA_API_KEY`, `PROVEEDOR_IA_URL`, `PROVEEDOR_IA_MODELO`, `ORIGENES_PERMITIDOS` y `FRONTEND_URL` en el entorno de ejecución. No incluyas claves reales en GitHub.

### Despliegue

El backend y el frontend incluyen un `Dockerfile` independiente para desplegarlos como servicios separados en Railway. En el servicio backend configura `MOTOR_BD=mysql`, las variables `MYSQL_*`, `SECRET_KEY`, `ORIGENES_PERMITIDOS` y `PROVEEDOR_IA_*`. En el servicio frontend configura `VITE_API_URL` con la URL pública del backend más `/api` y reconstruye la imagen. Configura CORS en el backend con la URL pública del frontend.

Para Railway crea dos servicios desde este repositorio y define la carpeta raíz de cada uno: `backend` para la API y `frontend` para la aplicación web. Railway detectará el `Dockerfile` de cada carpeta. El backend escucha el puerto que Railway entrega mediante `PORT` y expone `/api/health`. El frontend debe construirse con `VITE_API_URL=https://tu-backend.up.railway.app/api`.

Variables mínimas del backend: `SECRET_KEY` (una clave larga y aleatoria), `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ORIGENES_PERMITIDOS=["https://tu-frontend.up.railway.app"]`, `MOTOR_BD=mysql` y las variables `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`. También puedes usar `DATABASE_URL` con una URL MySQL completa; esta variable tiene prioridad sobre `MYSQL_*`. Si usas IA, pagos o correo, agrega `PROVEEDOR_IA_*`, `STRIPE_SECRET_KEY` y `SMTP_*` según corresponda.

La URL pública y las evidencias de producción deben agregarse después de crear ambos servicios en Railway. La colección Postman incluida permite generar las evidencias de endpoints antes y después del despliegue.

En el flujo comercial de Aurora Viajes, la venta corresponde a una reserva de viaje: cada reserva nueva crea automáticamente una venta, un detalle con el destino y los pasajeros, y una factura. Los campos de producto y servicio se conservan en el modelo para compatibilidad con el requerimiento general, pero no son necesarios para operar este proyecto.
