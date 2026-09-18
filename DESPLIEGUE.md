# Despliegue de Aurora Viajes en Railway

Tres servicios en un mismo proyecto: `MySQL`, el backend y el frontend.
Orden: **MySQL → backend → frontend**, y al final se vuelve al backend para cerrar el CORS.

Cada carpeta trae su `Dockerfile` y su `railway.json`. En Railway se crea un servicio por carpeta y se fija el **Root Directory** de cada uno: `backend` y `frontend`.

---

## 1. Base de datos

**New → Database → Add MySQL**. No hay que configurar nada mas.

El backend crea las tablas y carga los datos iniciales al arrancar: paises, destinos, vuelos, hoteles, excursiones, roles y el usuario administrador. No hay que importar ningun `.sql`.

---

## 2. Backend

**New → GitHub Repo →** `davidabb2000/aurora-viajes`. En **Settings**: Root Directory `backend`, y **Networking → Generate Domain**.

Variables:

```
DATABASE_URL=${{MySQL.MYSQL_URL}}
MOTOR_BD=mysql
SECRET_KEY=<clave-larga-y-aleatoria>
ADMIN_EMAIL=admin@auroraviajes.com
ADMIN_PASSWORD=<contrasena-fuerte>
ENTORNO=produccion
DEPURACION=false
ORIGENES_PERMITIDOS=https://TU-FRONTEND.up.railway.app
FRONTEND_URL=https://TU-FRONTEND.up.railway.app
```

`DATABASE_URL=${{MySQL.MYSQL_URL}}` es una referencia de variable de Railway: se escribe tal cual, con las llaves dobles. Apunta al dominio **privado** (`mysql.railway.internal`), que no genera cargos de egreso; la URL publica si los generaria.

Para generar `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Opcionales, segun se usen: `PROVEEDOR_IA_API_KEY`, `PROVEEDOR_IA_URL`, `PROVEEDOR_IA_MODELO`, `STRIPE_SECRET_KEY` y `SMTP_*`. Sin la clave de IA las recomendaciones siguen funcionando con el respaldo local por palabras clave.

Verificacion: `https://TU-BACKEND.up.railway.app/api/health` debe devolver `{"estado":"ok"}`. Con `DEPURACION=false` el `/docs` queda deshabilitado a proposito.

---

## 3. Frontend

Segundo servicio desde el mismo repositorio. Root Directory `frontend`, y genera dominio.

```
VITE_API_URL=https://TU-BACKEND.up.railway.app/api
```

Con `/api` al final. Vite **incrusta este valor en el bundle durante el build**, asi que cambiarlo exige redesplegar; no basta con guardar la variable.

---

## 4. Cerrar el CORS

Con el dominio del frontend ya generado, corrige en el backend `ORIGENES_PERMITIDOS` y `FRONTEND_URL` con esa URL, sin barra final, y redespliega. Se acepta JSON o lista separada por comas.

---

## Gastar menos creditos

Railway cobra por consumo, no por servicio: **$10 por GB de RAM al mes**, **$20 por vCPU al mes**, **$0.05 por GB de egreso** y **$0.15 por GB de volumen al mes**. El plan Trial da **$5 una sola vez, sin renovacion**; Hobby son $5/mes con $5 de uso incluido.

Lo que mas gasta en este proyecto es tener tres contenedores encendidos las 24 horas. Ordenado por impacto:

### 1. Pon un limite de gasto duro

Es lo primero. En **Settings → Usage** del workspace se fijan limites blando y duro; al llegar al duro Railway apaga las cargas. Evita que un bucle de reinicios se coma el credito de un dia para otro.

### 2. El frontend ya no esta en Railway

Se sirve desde Cloudflare, gratis, en `https://aurora-viajes.carousel-app.workers.dev`. Los detalles estan mas abajo, en "Frontend en Cloudflare".

### 3. Activa Serverless en el backend

En **Settings → Deploy** del servicio. Railway duerme el servicio tras unos 5 minutos sin trafico y lo despierta con la primera peticion, que puede tardar o devolver un 502.

**Ojo:** un servicio con conexiones abiertas a la base **nunca se duerme**, porque sigue emitiendo trafico. Por eso el backend acepta:

```
BD_SIN_POOL=true
```

Con esa variable no se mantienen conexiones ociosas: cada peticion abre y cierra la suya. Cuesta unos milisegundos por peticion y es lo que permite que el servicio llegue a dormirse de verdad. Sin ella, activar Serverless no sirve de nada en esta aplicacion.

### 4. La base de datos ya no esta en Railway

Un servicio MySQL corre siempre y ademas paga volumen, asi que era el mayor gasto fijo. La base vive ahora en el plan gratuito de **Aiven** (1 GB, sin caducidad ni tarjeta). Solo hubo que poner su URL en `DATABASE_URL`: el backend la normaliza sola, convierte el esquema a `mysql+aiomysql://`, fuerza `charset=utf8mb4` y activa TLS al detectar `ssl-mode=REQUIRED`.

No hizo falta migrar datos: el catalogo, los roles y el usuario administrador se recrean en cada arranque.

Aiven apaga el servicio tras inactividad prolongada, avisando antes.

### 5. Limita los recursos por replica

En **Settings → Resources** se topan CPU y memoria. El backend consume unos 100 MB en ejecucion, asi que un tope de 512 MB va sobrado y protege de picos inesperados.

### 6. Despliega menos veces

Cada build consume computo. Agrupa los cambios en un commit en vez de empujar seis seguidos.

Las dependencias del modelo de riesgo (pandas, numpy, scikit-learn, scipy y sus transitivas) estan separadas en `backend/requirements-ml.txt` y **no** se instalan en la imagen: nada las carga en ejecucion, porque solo se importan dentro de `app/services/riesgo.py` y su router no esta registrado en `main.py`. Eso acorta bastante cada build. Para reactivar el modelo, instala ese fichero tambien desde el `Dockerfile`.

### 7. Borra lo que no uses

Servicios viejos, entornos de prueba y despliegues parados siguen ocupando. Un proyecto duplicado gasta el doble.

---

## Frontend en Cloudflare

El frontend **no se despliega en Railway**: son archivos estaticos y no necesitan un contenedor encendido.

Cloudflare fusiono Pages con Workers, asi que `wrangler pages deploy` crea en realidad un **Worker con assets estaticos**, no un proyecto de Pages clasico. Por eso la URL es `*.workers.dev` y no `*.pages.dev`, y `wrangler pages project list` aparece vacio. Funcionalmente es equivalente para una SPA.

La configuracion vive en `frontend/wrangler.jsonc`. `not_found_handling: "single-page-application"` es lo que hace que cualquier ruta desconocida devuelva `index.html` y la resuelva React Router.

Para desplegar:

```bash
cd frontend
VITE_API_URL=https://TU-BACKEND.up.railway.app/api npm run build
wrangler deploy
```

**La variable es obligatoria en el build.** Vite la incrusta en el bundle; si se compila sin ella, el valor cae al `/api` por defecto, que apunta al propio Worker, y ninguna llamada funciona. Merece la pena comprobarlo antes de subir:

```bash
grep -o "TU-BACKEND" dist/assets/*.js
```

Tras cambiar la URL del frontend hay que actualizar `ORIGENES_PERMITIDOS` y `FRONTEND_URL` en el backend y redesplegarlo.

> Al ejecutar `wrangler pages project create` por primera vez, wrangler modifica el proyecto sin preguntar: anade `@cloudflare/vite-plugin` y `wrangler` a las dependencias, mete `cloudflare()` en `vite.config.js`, reescribe los scripts de `package.json` y crea `wrangler.jsonc`. Ademas recompila el build, **descartando las variables de entorno** que se pasaron antes.

---

## Problemas frecuentes

**El backend reinicia en bucle.** Casi siempre es `SECRET_KEY` sin definir: la aplicacion no arranca sin ella.

**El frontend carga pero ninguna llamada funciona.** `VITE_API_URL` quedo en su valor por defecto `/api`, que apunta al propio nginx. Corrigela y **redespliega** para reconstruir el bundle.

**Errores de CORS.** El origen del frontend no coincide exactamente con `ORIGENES_PERMITIDOS`: compara esquema, subdominio y ausencia de barra final.

**`'cryptography' package is required for ... caching_sha2_password`.** MySQL 8 usa ese metodo y PyMySQL necesita `cryptography`, que ya esta en `requirements.txt`.

**Tildes y enies mal.** El backend fuerza `charset=utf8mb4` cuando la URL no lo trae.

**En Windows, conectar a la base con TLS falla con `[WinError 87] El parametro no es correcto`.** Es un problema del bucle Proactor de asyncio con SSL, no del servidor ni del codigo: en Linux, que es lo que corre el contenedor, no ocurre. Para reproducirlo en local contra una base gestionada, usa el bucle Selector antes de arrancar:

```python
import asyncio, sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

Para el desarrollo diario contra el MySQL local de XAMPP no aplica, porque ahi no se usa TLS.
