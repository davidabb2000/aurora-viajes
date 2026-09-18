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

### 2. Saca el frontend de Railway

El frontend son archivos estaticos: no necesita un contenedor encendido. **Cloudflare Pages lo sirve gratis y sin limite practico**. Elimina un tercio del gasto sin perder nada. Root directory `frontend`, build `npm run build`, salida `dist`, y la variable `VITE_API_URL`. El enrutado del SPA funciona solo porque el build no genera `404.html`.

### 3. Activa Serverless en el backend

En **Settings → Deploy** del servicio. Railway duerme el servicio tras unos 5 minutos sin trafico y lo despierta con la primera peticion, que puede tardar o devolver un 502.

**Ojo:** un servicio con conexiones abiertas a la base **nunca se duerme**, porque sigue emitiendo trafico. Por eso el backend acepta:

```
BD_SIN_POOL=true
```

Con esa variable no se mantienen conexiones ociosas: cada peticion abre y cierra la suya. Cuesta unos milisegundos por peticion y es lo que permite que el servicio llegue a dormirse de verdad. Sin ella, activar Serverless no sirve de nada en esta aplicacion.

### 4. La base de datos no duerme

Un servicio MySQL corre siempre, y ademas paga volumen. Si el gasto aprieta, un MySQL gestionado gratuito fuera de Railway (Aiven, Clever Cloud) quita ese coste por completo: basta poner su URL en `DATABASE_URL`. El backend la normaliza sola y activa TLS si el proveedor lo pide.

### 5. Limita los recursos por replica

En **Settings → Resources** se topan CPU y memoria. El backend consume unos 100 MB en ejecucion, asi que un tope de 512 MB va sobrado y protege de picos inesperados.

### 6. Despliega menos veces

Cada build consume computo. Agrupa los cambios en un commit en vez de empujar seis seguidos, sobre todo en el backend, cuyo build compila dependencias pesadas.

### 7. Borra lo que no uses

Servicios viejos, entornos de prueba y despliegues parados siguen ocupando. Un proyecto duplicado gasta el doble.

---

## Problemas frecuentes

**El backend reinicia en bucle.** Casi siempre es `SECRET_KEY` sin definir: la aplicacion no arranca sin ella.

**El frontend carga pero ninguna llamada funciona.** `VITE_API_URL` quedo en su valor por defecto `/api`, que apunta al propio nginx. Corrigela y **redespliega** para reconstruir el bundle.

**Errores de CORS.** El origen del frontend no coincide exactamente con `ORIGENES_PERMITIDOS`: compara esquema, subdominio y ausencia de barra final.

**`'cryptography' package is required for ... caching_sha2_password`.** MySQL 8 usa ese metodo y PyMySQL necesita `cryptography`, que ya esta en `requirements.txt`.

**Tildes y enies mal.** El backend fuerza `charset=utf8mb4` cuando la URL no lo trae.
