# Despliegue de Aurora Viajes en Railway

Aurora Viajes se despliega como **tres servicios** dentro de un mismo proyecto de Railway:

| Servicio   | Origen                        | Rol                                  |
|------------|-------------------------------|--------------------------------------|
| `MySQL`    | Plantilla de Railway          | Base de datos                        |
| `backend`  | Este repo, raíz `backend`     | API FastAPI                          |
| `frontend` | Este repo, raíz `frontend`    | SPA de React servida por nginx       |

El orden importa: **MySQL → backend → frontend**, y al final se vuelve al backend para cerrar el CORS.

---

## 1. Base de datos

En el proyecto de Railway: **New → Database → Add MySQL**.

No hay que configurar nada más. Railway genera la variable `MYSQL_URL`, que el backend consumirá por referencia.

El backend crea las tablas y carga los datos iniciales (países, destinos, vuelos, hoteles, excursiones, roles y el usuario administrador) **automáticamente al arrancar**. No hay que importar `backend/sql/schema.sql` a mano.

---

## 2. Servicio backend

**New → GitHub Repo →** `davidabb2000/aurora-viajes`.

En **Settings** del servicio:

- **Root Directory**: `backend`
- **Builder**: Dockerfile (se detecta solo por `backend/railway.json`)
- **Networking → Generate Domain** para obtener la URL pública

### Variables

```
DATABASE_URL=${{MySQL.MYSQL_URL}}
MOTOR_BD=mysql
SECRET_KEY=<clave-larga-y-aleatoria>
ADMIN_EMAIL=admin@auroraviajes.com
ADMIN_PASSWORD=<contraseña-fuerte>
ENTORNO=produccion
DEPURACION=false
ORIGENES_PERMITIDOS=https://TU-FRONTEND.up.railway.app
FRONTEND_URL=https://TU-FRONTEND.up.railway.app
```

`DATABASE_URL=${{MySQL.MYSQL_URL}}` es una **referencia de variable** de Railway: se escribe tal cual, con las llaves dobles. Si el servicio de base de datos no se llama exactamente `MySQL`, hay que ajustar el nombre.

`ORIGENES_PERMITIDOS` y `FRONTEND_URL` todavía no se conocen en este paso: se ponen provisionalmente y se corrigen en el paso 4.

Para generar `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Variables opcionales

Solo si se usan esas funciones. Los valores reales están en el `backend/.env` local, que **no** está en el repo:

```
PROVEEDOR_IA_API_KEY=...        # chatbot y recomendaciones
PROVEEDOR_IA_URL=https://api.groq.com/openai/v1/chat/completions
PROVEEDOR_IA_MODELO=llama-3.1-8b-instant
STRIPE_SECRET_KEY=...           # checkout de pagos
SMTP_HOST=...                   # correos de bienvenida, reserva y recuperación
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=noreply@auroraviajes.com
SMTP_USE_TLS=true
```

Sin `PROVEEDOR_IA_API_KEY` las recomendaciones siguen funcionando con el fallback local por palabras clave.

### Verificación

```
https://TU-BACKEND.up.railway.app/api/health   → {"estado":"ok"}
https://TU-BACKEND.up.railway.app/api/catalogos/destinos   → 10 destinos
```

Con `DEPURACION=false` el `/docs` queda deshabilitado a propósito. Para habilitarlo temporalmente, poner `DEPURACION=true`.

---

## 3. Servicio frontend

**New → GitHub Repo →** el mismo repositorio, segundo servicio.

En **Settings**:

- **Root Directory**: `frontend`
- **Networking → Generate Domain**

### Variables

```
VITE_API_URL=https://TU-BACKEND.up.railway.app/api
```

Esta es la URL del backend del paso 2, **con `/api` al final**.

`VITE_API_URL` se consume en **tiempo de build**: Vite la incrusta en el bundle. Cambiarla exige un **redeploy**, no basta con guardar la variable.

---

## 4. Cerrar el CORS

Con el dominio del frontend ya generado, volver al servicio **backend** y corregir:

```
ORIGENES_PERMITIDOS=https://TU-FRONTEND.up.railway.app
FRONTEND_URL=https://TU-FRONTEND.up.railway.app
```

Sin dominio final `/`. Para varios orígenes se acepta JSON o separados por comas:

```
ORIGENES_PERMITIDOS=["https://a.up.railway.app","https://b.up.railway.app"]
ORIGENES_PERMITIDOS=https://a.up.railway.app,https://b.up.railway.app
```

`FRONTEND_URL` es la base de los enlaces en los correos y de las URLs de retorno de Stripe.

Redeploy del backend para aplicarlo.

---

## 5. Comprobación final

1. Abrir la URL del frontend.
2. Entrar con `ADMIN_EMAIL` / `ADMIN_PASSWORD`.
3. Crear una reserva y verificar que aparece en el panel.
4. Abrir el dashboard comercial en `/panel/avance-cinco`.

La colección de Postman en `backend/postman/collections/` sirve para levantar evidencias de los endpoints apuntando al dominio de producción.

---

## Problemas frecuentes

**El backend reinicia en bucle.** Revisar los logs de deploy. Casi siempre es `SECRET_KEY` sin definir (la aplicación no arranca sin ella) o `DATABASE_URL` mal referenciada.

**El frontend carga pero ninguna llamada funciona.** `VITE_API_URL` quedó con el valor por defecto `/api`, que apunta al propio nginx. Corregir la variable y **redesplegar** para reconstruir el bundle.

**Errores de CORS en la consola del navegador.** El origen del frontend no coincide exactamente con `ORIGENES_PERMITIDOS`: comparar esquema, subdominio y ausencia de `/` final.

**Build del frontend muy lento o que falla por tamaño.** Confirmar que `frontend/.dockerignore` está en el repo; sin él se sube `node_modules` al contexto de build.

**Tildes y eñes mal en la base de datos.** El backend fuerza `charset=utf8mb4` sobre `DATABASE_URL` cuando la URL no lo trae. Si aparecen mal, verificar que el servicio MySQL de Railway no esté configurado en `latin1`.
