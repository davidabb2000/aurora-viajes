# Despliegue de Aurora Viajes

| Pieza      | Plataforma        | Origen                                  |
|------------|-------------------|-----------------------------------------|
| Backend    | Render            | Docker, `backend/Dockerfile`            |
| Frontend   | Cloudflare Pages  | Build estatico de Vite, carpeta `frontend` |
| Base datos | MySQL gestionado externo | Aiven, Clever Cloud u otro       |

Orden: **base de datos → backend → frontend**, y al final se vuelve al backend para cerrar el CORS.

> **Por que la base va fuera.** Render solo ofrece PostgreSQL. Este backend esta atado a MySQL: unas 160 lineas de DDL crudo (`INSERT IGNORE`, `SHOW COLUMNS`, `ALTER ... AFTER`) y 12 columnas `INTEGER UNSIGNED`, que PostgreSQL no tiene. Portarlo seria un trabajo aparte, asi que la base se contrata en un proveedor de MySQL.

---

## 1. Base de datos MySQL

Crea una instancia MySQL gratuita en [Aiven](https://aiven.io) o [Clever Cloud](https://clever-cloud.com) y copia la **URL de conexion completa**. Suele verse asi:

```
mysql://usuario:contrasena@mysql-xxxx.aivencloud.com:12345/defaultdb?ssl-mode=REQUIRED
```

El backend la normaliza solo: convierte el esquema a `mysql+aiomysql://`, fuerza `charset=utf8mb4` y, si detecta `ssl-mode`, activa TLS y retira el parametro (que `aiomysql` no entiende). No hace falta tocar la URL.

No hay que importar ningun `.sql`: el backend crea las tablas y carga paises, destinos, vuelos, hoteles, excursiones, roles y el usuario administrador al arrancar.

---

## 2. Backend en Render

El repositorio trae [`render.yaml`](render.yaml), asi que se despliega como **Blueprint**:

1. En Render: **New → Blueprint**.
2. Conecta el repositorio `davidabb2000/aurora-viajes`.
3. Render lee `render.yaml` y pide un valor para cada variable marcada `sync: false`.

Valores a introducir:

| Variable | Valor |
|---|---|
| `DATABASE_URL` | la URL del paso 1, tal cual |
| `ADMIN_EMAIL` | correo del administrador |
| `ADMIN_PASSWORD` | contrasena fuerte |
| `ORIGENES_PERMITIDOS` | URL del frontend (paso 3), sin barra final |
| `FRONTEND_URL` | la misma URL del frontend |

`SECRET_KEY` la genera Render automaticamente. Las variables de IA, Stripe y SMTP son opcionales: si se dejan vacias, esas funciones quedan inactivas y las recomendaciones caen al respaldo local por palabras clave.

`ORIGENES_PERMITIDOS` y `FRONTEND_URL` todavia no se conocen en este paso; se ponen provisionalmente y se corrigen en el paso 4.

### Verificacion

```
https://TU-BACKEND.onrender.com/api/health          -> {"estado":"ok"}
https://TU-BACKEND.onrender.com/api/catalogos/destinos  -> 10 destinos
```

Con `DEPURACION=false` el `/docs` queda deshabilitado a proposito.

### Plan gratuito: lo que hay que saber

- El servicio **se apaga tras 15 minutos sin trafico** y tarda cerca de un minuto en despertar. La primera visita despues de un rato sera lenta.
- El disco es **efimero**: por eso la base va fuera y no se puede usar SQLite.
- 750 horas de instancia gratuitas al mes por workspace.

---

## 3. Frontend en Cloudflare Pages

**Workers & Pages → Create → Pages → Connect to Git**, y elige el repositorio.

Configuracion de build:

| Campo | Valor |
|---|---|
| Root directory | `frontend` |
| Build command | `npm run build` |
| Build output directory | `dist` |

Variable de entorno (de build):

```
VITE_API_URL = https://TU-BACKEND.onrender.com/api
```

Con `/api` al final. Vite **incrusta este valor en el bundle durante el build**, asi que cambiarlo exige volver a desplegar; no basta con guardar la variable.

El enrutado del SPA funciona solo: Cloudflare Pages sirve `index.html` para cualquier ruta no encontrada mientras el build no contenga un `404.html` en la raiz, y este no lo genera.

> `frontend/Dockerfile` y `frontend/nginx.conf.template` no se usan en Pages, que sirve archivos estaticos sin contenedor. Se conservan por si el frontend se mueve a un host con Docker.

---

## 4. Cerrar el CORS

Con el dominio de Pages ya generado, vuelve al servicio de Render y corrige:

```
ORIGENES_PERMITIDOS=https://tu-proyecto.pages.dev
FRONTEND_URL=https://tu-proyecto.pages.dev
```

Sin barra final. Para varios origenes se acepta JSON o separados por comas:

```
ORIGENES_PERMITIDOS=["https://a.pages.dev","https://b.pages.dev"]
ORIGENES_PERMITIDOS=https://a.pages.dev,https://b.pages.dev
```

`FRONTEND_URL` es la base de los enlaces de los correos y de las URLs de retorno de Stripe. Redespliega el backend para aplicarlo.

---

## 5. Comprobacion final

1. Abre la URL de Pages.
2. Entra con `ADMIN_EMAIL` / `ADMIN_PASSWORD`.
3. Crea una reserva y verifica que aparece en el panel.
4. Abre el dashboard comercial en `/panel/avance-cinco`.

La coleccion de Postman en `backend/postman/collections/` sirve para levantar evidencias apuntando al dominio de produccion.

---

## Problemas frecuentes

**El backend reinicia en bucle.** Casi siempre es `DATABASE_URL` mal copiada. `SECRET_KEY` la genera Render, pero si falta, la aplicacion no arranca.

**`'cryptography' package is required for ... caching_sha2_password`.** MySQL 8 usa ese metodo de autenticacion y PyMySQL necesita `cryptography`, que ya esta en `requirements.txt`. Si aparece, el build no se rehizo.

**Errores de TLS al conectar.** El backend cifra sin verificar el certificado cuando no se le da una CA, porque los hosts gestionados usan CA privadas. Para verificarla, descarga el certificado del proveedor y define `MYSQL_SSL_CA` con su ruta dentro de la imagen.

**El frontend carga pero ninguna llamada funciona.** `VITE_API_URL` quedo con el valor por defecto `/api`, que apunta al propio Pages. Corrigela y **vuelve a desplegar** para reconstruir el bundle.

**Errores de CORS en la consola.** El origen del frontend no coincide exactamente con `ORIGENES_PERMITIDOS`: compara esquema, subdominio y ausencia de barra final.

**La primera peticion del dia tarda un minuto.** Es el apagado por inactividad del plan gratuito de Render, no un fallo.
