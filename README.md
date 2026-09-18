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

El backend corre en **Render** como contenedor Docker y el frontend en **Cloudflare Pages** como build estatico de Vite. La base de datos es un MySQL gestionado externo, porque Render solo ofrece PostgreSQL y este backend usa DDL y tipos propios de MySQL.

El procedimiento completo, con las variables de cada servicio, esta en **[DESPLIEGUE.md](DESPLIEGUE.md)**.

Resumen:

- Backend: blueprint [`render.yaml`](render.yaml), escucha el puerto de `PORT` y expone `/api/health`. Crea el esquema y carga los datos iniciales al arrancar. En el plan gratuito se apaga tras 15 minutos sin trafico.
- Frontend: raiz `frontend`, build `npm run build`, salida `dist`. `VITE_API_URL` se incrusta en tiempo de build, asi que cambiarla exige redesplegar.
- Base de datos: MySQL externo (Aiven, Clever Cloud u otro). El backend normaliza la URL y activa TLS solo si el proveedor lo pide.

No incluyas claves reales en el repositorio: van en las variables de cada servicio.

En el flujo comercial de Aurora Viajes, la venta corresponde a una reserva de viaje: cada reserva nueva crea automáticamente una venta, un detalle con el destino y los pasajeros, y una factura. Los campos de producto y servicio se conservan en el modelo para compatibilidad con el requerimiento general, pero no son necesarios para operar este proyecto.
