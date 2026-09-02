# Backend Aurora Viajes — FastAPI

El backend oficial de la evaluación es la API **FastAPI** ubicada en `app/`
(SQLAlchemy + Pydantic + JWT + bcrypt sobre MySQL). La carpeta `src/` contiene
una versión previa en Node/Express + MySQL de un avance anterior del
proyecto; se conserva como referencia pero **no** se usa para esta entrega.

## Puesta en marcha (FastAPI)

1. Crea y activa un entorno virtual (PowerShell, desde `backend/`):
   ```powershell
   python -m venv venv
   venv\Scripts\Activate.ps1
   ```
2. Instala las dependencias:
   ```powershell
   pip install -r requirements.txt
   ```
3. Configura `backend/.env` (ya incluido con valores de desarrollo):
   ```env
   DATABASE_URL=mysql+pymysql://root:@localhost:3306/aurora_viajes?charset=utf8mb4
   JWT_SECRET=cambia-esta-clave-en-produccion
   JWT_EXPIRES_IN=8h
   FRONTEND_URL=http://localhost:5173
   ADMIN_EMAIL=admin@auroraviajes.com
   ADMIN_PASSWORD=Admin123!
   ```
   Crea antes la base de datos vacía en MySQL/XAMPP (`CREATE DATABASE aurora_viajes;`);
   SQLAlchemy crea las tablas automáticamente al iniciar la app.
4. Ejecuta el servidor:
   ```powershell
   uvicorn app.main:app --host 127.0.0.1 --reload --port 8001
   ```

Al iniciar, la aplicación crea automáticamente los roles `administrador`,
`empleado` y `cliente`, sus permisos mínimos, y **un usuario administrador
inicial** con las credenciales de `ADMIN_EMAIL`/`ADMIN_PASSWORD` (solo si aún
no existe ningún administrador). Úsalas para el primer login y para crear
el resto de usuarios desde el panel.

El servidor queda disponible en `http://127.0.0.1:8001`.

## Documentación interactiva (Swagger)

Con el servidor corriendo, visita `http://127.0.0.1:8001/docs` (Swagger UI)
o `http://127.0.0.1:8001/redoc` (ReDoc) para probar cada endpoint.

## Pruebas con Postman

Importa [`postman_collection.json`](./postman_collection.json) en Postman.
Incluye carpetas para Salud, Autenticación, Usuarios, Productos, Servicios,
Reservas y Contacto, cubriendo los métodos `GET`, `POST`, `PUT`, `PATCH` y
`DELETE`. Ejecuta primero **Autenticación → Login administrador**: un script
de test guarda el token JWT en la variable de colección `{{token}}` para que
el resto de solicitudes autenticadas funcionen automáticamente.

## Pruebas automatizadas

```powershell
pytest
```

## Endpoints principales

- `GET /api/health`
- `POST /api/usuarios/registro` — registro público de clientes
- `POST /api/auth/login` — genera el JWT
- `POST /api/auth/recuperar` / `POST /api/auth/restablecer` — recuperación de contraseña
- `GET /api/usuarios` / `GET /api/usuarios/{id}` (administrador, JWT)
- `POST /api/usuarios` (administrador, JWT) — crea usuarios con cualquier rol
- `PUT /api/usuarios/{id}` (administrador, JWT)
- `PATCH /api/usuarios/{id}/estado` (administrador, JWT)
- `DELETE /api/usuarios/{id}` (administrador, JWT)
- `GET|POST|PUT|DELETE /api/productos` (lectura pública, escritura admin)
- `GET|POST|PUT|DELETE /api/servicios` (lectura pública, escritura admin)
- `POST /api/reservas` (usuario autenticado, JWT)
- `GET /api/reservas/mias` (cliente autenticado, JWT)
- `GET /api/reservas` y `PATCH /api/reservas/{id}/estado` (empleado o administrador, JWT)
- `DELETE /api/reservas/{id}` (propietario o administrador, JWT)
- `POST /api/contacto` (público) / `GET /api/contacto` (administrador, JWT)

En las rutas protegidas envía `Authorization: Bearer <token>`.

La base de datos incluye `roles`, `permisos`, `rol_permisos`, `usuarios`,
`productos`, `servicios`, `reservas` y `mensajes_contacto`. Las contraseñas
se almacenan únicamente como hashes bcrypt; nunca en texto plano.

