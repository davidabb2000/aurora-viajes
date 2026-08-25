# Backend Aurora Viajes

## Puesta en marcha

1. Configura las credenciales en `.env` (o conserva `src/.env`).
2. Ejecuta `npm install` y luego `npm run db:init` para crear la base y las tablas.
3. Ejecuta `npm run dev`.

El servidor queda disponible en `http://localhost:3000`. En XAMPP, inicia Apache y MySQL; phpMyAdmin estará disponible en `http://localhost/phpmyadmin`.

## Endpoints principales

- `GET /api/health`
- `POST /api/auth/registro`
- `POST /api/auth/login`
- `POST /api/auth/recuperar`
- `GET /api/usuarios` (administrador, JWT)
- `PUT /api/usuarios/:id` (administrador, JWT)
- `PATCH /api/usuarios/:id/estado` (administrador, JWT)
- `DELETE /api/usuarios/:id` (administrador, JWT)
- `GET /api/catalogo/productos`
- `GET /api/catalogo/servicios`
- `GET /api/reservas/mias` (cliente autenticado, JWT)
- `POST /api/reservas` (usuario autenticado, JWT)
- `GET /api/reservas` y `PATCH /api/reservas/:id/estado` (empleado o administrador, JWT)
- `DELETE /api/reservas/:id` (cliente propietario o administrador, JWT)
- `GET|PUT /api/perfil` (usuario autenticado, JWT)
- `POST|PUT|DELETE /api/catalogo/{productos|servicios}` (administrador, JWT)

En las rutas protegidas envía `Authorization: Bearer <token>`.

La base de datos incluye `roles`, `permisos`, `usuarios`, `productos`, `servicios` y `reservas`. Ejecuta `npm run db:init` sobre una base nueva para crear el esquema; las contraseñas se almacenan únicamente como hashes bcrypt.
