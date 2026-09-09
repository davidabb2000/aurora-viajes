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
- reservas
- mensajes_contacto

### Arranque

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
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
- `POST /api/reservas`
- `GET /api/reservas/mias`
- `GET /api/reservas/{id}`
- `PUT /api/reservas/{id}`
- `POST /api/reservas/{id}/pago/checkout`
- `POST /api/reservas/{id}/pago/confirmar`
- `POST /api/contacto`

## Observación

El frontend sigue enviando el destino como texto; el backend lo guarda así para mantener compatibilidad con lo que ya existe en la interfaz y en el panel.
