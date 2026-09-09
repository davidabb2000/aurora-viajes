# Integración Full Stack

## Panorama general

Este proyecto conecta un frontend en React + Vite con un backend en FastAPI que expone endpoints JSON y persiste la información en una base de datos relacional SQL mediante SQLAlchemy.

La integración está pensada para trabajar así:

1. El frontend captura datos en formularios y los valida en la interfaz.
2. Las peticiones se envían al backend con `fetch` desde una capa única de acceso HTTP.
3. FastAPI recibe y valida el JSON con Pydantic.
4. SQLAlchemy traduce las operaciones a SQL contra la base de datos relacional.
5. El backend responde nuevamente en JSON para que React actualice la interfaz.

## Frontend React + Vite

La aplicación frontend vive en `frontend/` y usa Vite como servidor de desarrollo y empaquetador.

El punto central de comunicación con la API está en [frontend/src/utils/api.js](frontend/src/utils/api.js). Esa capa:

- Define una URL base con `VITE_API_URL` o, si no existe, usa `/api`.
- Envía el encabezado `Content-Type: application/json`.
- Serializa el cuerpo de la petición con `JSON.stringify(...)`.
- Convierte las respuestas a JSON.
- Normaliza los mensajes de error que devuelve el backend.

Los formularios principales ya consumen esa capa:

- Inicio de sesión en [frontend/src/pages/Login.jsx](frontend/src/pages/Login.jsx)
- Registro de usuarios en [frontend/src/components/RegisterModal.jsx](frontend/src/components/RegisterModal.jsx)
- Recuperación de contraseña en [frontend/src/components/RecoverPassword.jsx](frontend/src/components/RecoverPassword.jsx)
- Contacto en [frontend/src/pages/Contacto.jsx](frontend/src/pages/Contacto.jsx)
- Panel administrativo y de reservas en [frontend/src/pages/Panel.jsx](frontend/src/pages/Panel.jsx)

La sesión autenticada se guarda en `localStorage` o `sessionStorage` desde [frontend/src/utils/api.js](frontend/src/utils/api.js) y se comparte por contexto en [frontend/src/context/AuthContext.jsx](frontend/src/context/AuthContext.jsx).

## Conexión con FastAPI

El backend está en `backend/app/` y expone rutas JSON bajo el prefijo `/api`.

FastAPI recibe las solicitudes, valida el contenido con Pydantic y devuelve respuestas en JSON. Algunas rutas importantes son:

- `POST /api/auth/login`
- `POST /api/usuarios/registro`
- `POST /api/auth/recuperar`
- `POST /api/auth/restablecer`
- `GET /api/usuarios`
- `GET /api/reservas`
- `POST /api/contacto`

La configuración de CORS está habilitada para el frontend local en `http://localhost:5173` y `http://127.0.0.1:5173`, lo que permite consumir la API desde Vite durante desarrollo.

Además, el frontend ya tiene proxy configurado en [frontend/vite.config.js](frontend/vite.config.js), por lo que cualquier llamada a `/api` se redirige a `http://127.0.0.1:8001` en local.

## Validación JSON

El formato de intercambio entre frontend y backend es JSON.

Ejemplo de envío de login:

```json
{
  "correo": "admin@auroraviajes.com",
  "contrasena": "Admin123!"
}
```

Ejemplo de respuesta exitosa:

```json
{
  "token": "jwt-aqui",
  "usuario": {
    "id": 1,
    "nombre": "Administrador",
    "apellido": "Aurora",
    "correo": "admin@auroraviajes.com",
    "rol": "administrador",
    "activo": true
  }
}
```

## Backend con base de datos relacional SQL

La persistencia está implementada con SQLAlchemy en [backend/app/database.py](backend/app/database.py) y la configuración de conexión en [backend/app/config.py](backend/app/config.py).

### Flujo de conexión

1. `DATABASE_URL` define el motor y credenciales de la base de datos.
2. SQLAlchemy crea el `engine`.
3. `SessionLocal` administra sesiones por petición.
4. `Base.metadata.create_all(bind=engine)` crea las tablas a partir de los modelos.
5. Las rutas usan `get_db()` para abrir y cerrar sesiones de forma segura.

### Base relacional

El esquema relacional soporta entidades como:

- usuarios
- roles
- permisos
- reservas
- productos
- servicios
- mensajes de contacto

La contraseña nunca se guarda en texto plano. Se hashea con bcrypt desde [backend/app/security.py](backend/app/security.py).

## Ejecución local

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Backend:

```bash
cd backend
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --reload --port 8001
```

## Resumen técnico

La arquitectura final queda así:

React + Vite -> fetch -> FastAPI -> Pydantic -> SQLAlchemy -> Base de datos SQL

Ese flujo mantiene separada la interfaz del almacenamiento, centraliza la comunicación HTTP en una sola utilidad y deja el backend como fuente única de validación y persistencia.