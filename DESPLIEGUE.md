# Despliegue de Aurora Viajes

Cada pieza vive en su plataforma:

| Pieza | Plataforma | Notas |
|---|---|---|
| Base de datos | **Aiven** (MySQL, plan gratuito) | 1 GB, sin caducidad ni tarjeta. Se apaga tras una inactividad prolongada y avisa antes. |
| Backend | **Railway** (Docker, Root Directory `backend`) | Escucha el puerto de `PORT` y expone `/api/health`. |
| Frontend | **Cloudflare** (assets estáticos, `frontend/wrangler.jsonc`) | Gratis. `VITE_API_URL` se incrusta al compilar. |

Orden: **base → backend → frontend**, y al final se vuelve al backend para cerrar el CORS y configurar el webhook de Stripe.

---

## 1. Base de datos (Aiven)

Crea un servicio MySQL gratuito y copia su URI (`mysql://usuario:clave@host:puerto/base?ssl-mode=REQUIRED`). Es lo único que necesitas: el backend crea las tablas y carga los datos iniciales (destinos, vuelos, hoteles, excursiones, paquetes, roles y el administrador) al arrancar. No hay que importar ningún `.sql`.

`DATABASE_URL` puede llevar la URI tal cual: el backend cambia el esquema a `mysql+aiomysql://`, fuerza `charset=utf8mb4` y activa TLS al ver `ssl-mode`. Sin certificado de CA propio la conexión va cifrada pero **no se verifica el certificado**; para verificarlo, descarga el CA de Aiven y apunta `MYSQL_SSL_CA` a él.

**Migraciones.** Las tablas ya existentes no las modifica `create_all`, así que el backend, al arrancar, detecta el esquema anterior y lo migra al normalizado (3FN) con `services/migraciones.py`:

1. Crea copias de seguridad `respaldo_v2_*` de cada tabla que va a tocar (dentro de la misma base).
2. Crea las tablas nuevas (`paises`, `ciudades`, `aerolineas`, `modelos_avion`, `reserva_excursiones`...) y las columnas nuevas.
3. Copia los datos: los países y ciudades se deducen sin duplicados de los textos antiguos, los hoteles y excursiones se enlazan a su ciudad, las reservas conservan su número, total y estado, y cada excursión de una reserva queda con su cantidad y el precio con el que se vendió.
4. Elimina las columnas que ya no se usan.

Es idempotente (un segundo arranque no hace nada) y reanudable (si se corta a la mitad, el siguiente arranque continúa). Aun así, **antes del primer despliegue con datos que te importen, haz tu propia copia**:

```bash
mysqldump --ssl-mode=REQUIRED -h HOST -P PUERTO -u USUARIO -p BASE > respaldo.sql
```

Cuando compruebes que todo funciona, las tablas `respaldo_v2_*` se pueden borrar para liberar espacio.

---

## 2. Backend (Railway)

**New → GitHub Repo →** `davidabb2000/aurora-viajes`. En **Settings**: Root Directory `backend`, y **Networking → Generate Domain**.

Variables:

```
DATABASE_URL=<URI de Aiven>
MOTOR_BD=mysql
SECRET_KEY=<clave-larga-y-aleatoria>
ADMIN_EMAIL=admin@auroraviajes.com
ADMIN_PASSWORD=<contrasena-fuerte>
ENTORNO=produccion
DEPURACION=false
PROXIES_DE_CONFIANZA=1
ORIGENES_PERMITIDOS=https://TU-FRONTEND
FRONTEND_URL=https://TU-FRONTEND
```

`ADMIN_PASSWORD` solo se usa **la primera vez**, cuando se crea el administrador (los arranques siguientes no la tocan). Si dejas la clave de ejemplo `Admin123!`, la cuenta obliga a cambiarla en el primer acceso, así que aun con esa clave no queda una puerta abierta. Si algún día pierdes el acceso, pon `ADMIN_RESTABLECER_CONTRASENA=true`, redespliega, entra y vuelve a ponerla en `false`.

`PROXIES_DE_CONFIANZA=1` (Railway pone un proxy delante) hace que los límites de intentos identifiquen al cliente por su IP real. `DEPURACION` debe estar en `false`: encendida publica `/docs` y vuelca en el log cada consulta SQL con sus datos.

Para generar `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Opcionales, según se usen: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `PROVEEDOR_IA_API_KEY`, `PROVEEDOR_IA_URL`, `PROVEEDOR_IA_MODELO` y `SMTP_*`. Sin clave de IA las recomendaciones funcionan con el respaldo local por palabras clave y el chatbot responde con un texto fijo.

Verificación: `https://TU-BACKEND.up.railway.app/api/health` debe devolver `{"estado":"ok"}`. Con `DEPURACION=false` el `/docs` queda deshabilitado a propósito.

La imagen instala solo `requirements.txt`. Lo que solo necesitan las pruebas (`pytest`, cobertura) está en `requirements-dev.txt` y no se despliega.

---

## 3. Frontend (Cloudflare)

Son archivos estáticos: no necesitan un contenedor encendido. `frontend/wrangler.jsonc` sirve `dist/` como un Worker con assets, y `not_found_handling: "single-page-application"` hace que cualquier ruta desconocida devuelva `index.html` y la resuelva React Router.

```bash
cd frontend
VITE_API_URL=https://TU-BACKEND.up.railway.app/api npm run build
wrangler deploy
```

**La variable es obligatoria en el build.** Vite la incrusta en el bundle; si se compila sin ella, el valor cae al `/api` por defecto, que apunta al propio Worker, y ninguna llamada funciona. Merece la pena comprobarlo antes de subir:

```bash
grep -o "TU-BACKEND" dist/assets/*.js
```

Si el proyecto está conectado a GitHub en el panel de Cloudflare, define `VITE_API_URL` en las variables de **build** (no en las de ejecución) y usa como comando de compilación `npm run build`.

**Cabeceras de seguridad.** Cada compilación genera `dist/_headers`, que Cloudflare aplica a todas las respuestas: una política de contenido estricta (solo scripts y estilos propios, el mapa de Google y las llamadas a la API), `X-Frame-Options: DENY`, `X-Content-Type-Options`, `Referrer-Policy: no-referrer` y `Permissions-Policy`. El origen de la API que permite la política sale de `VITE_API_URL`, así que si el backend cambia de dirección basta con recompilar. Para comprobarlo: `curl -I https://TU-FRONTEND/` debe mostrar `content-security-policy`.

---

## 4. Cerrar el CORS y primer acceso

Con el dominio del frontend ya generado, corrige en el backend `ORIGENES_PERMITIDOS` y `FRONTEND_URL` con esa URL, sin barra final, y redespliega. Se acepta JSON o una lista separada por comas.

Después, entra por `/acceso-personal` con `ADMIN_EMAIL` y `ADMIN_PASSWORD` (si usaste la de ejemplo, la web te pedirá crear una propia). Desde el panel puedes crear las cuentas del equipo: nacen con una clave provisional que la persona debe cambiar al entrar. Los clientes se registran solos en `/registro`, y el personal puede dar de alta a un cliente desde el mostrador.

---

## 5. Stripe: el webhook de pagos

Sin webhook, una reserva solo se confirma si el cliente vuelve a la web después de pagar. Con él, Stripe avisa al backend de cada pago aunque el cliente cierre el navegador.

1. En Stripe: **Developers → Webhooks → Add endpoint**.
2. URL: `https://TU-BACKEND.up.railway.app/api/pagos/stripe/webhook`.
3. Evento: `checkout.session.completed`.
4. Copia el **Signing secret** (`whsec_...`) a la variable `STRIPE_WEBHOOK_SECRET` del backend y redespliega.

Sin esa variable el endpoint responde `503` y no acepta nada, a propósito: nadie puede fingir un pago sin el secreto. Cada aviso se valida por firma y por marca de tiempo, y solo se aplica si la sesión pertenece a la reserva y su importe y moneda coinciden con el total.

Si alguna vez llega un pago para una reserva ya cancelada, el backend la deja cancelada y lo anota en el log como «requiere un reembolso manual»: el reembolso se hace desde el panel de Stripe.

---

## Gastar menos créditos

Railway cobra por consumo: **$10 por GB de RAM al mes**, **$20 por vCPU al mes**, **$0.05 por GB de egreso** y **$0.15 por GB de volumen al mes**. El plan Trial da **$5 una sola vez, sin renovación**; Hobby son $5/mes con $5 de uso incluido. Ordenado por impacto:

1. **Pon un límite de gasto duro.** En **Settings → Usage** del workspace se fijan límites blando y duro; al llegar al duro Railway apaga las cargas. Evita que un bucle de reinicios se coma el crédito en un día.
2. **Activa Serverless en el backend** (**Settings → Deploy**). Railway duerme el servicio tras unos 5 minutos sin tráfico y lo despierta con la primera petición, que puede tardar o devolver un 502. Un servicio con conexiones abiertas a la base **nunca se duerme**, por eso existe `BD_SIN_POOL=true`: sin pool, cada petición abre y cierra su conexión, cuesta unos milisegundos y es lo que permite que el servicio llegue a dormirse de verdad. Sin ella, Serverless no sirve de nada en esta aplicación.
3. **Limita los recursos por réplica** (**Settings → Resources**). El backend consume unos 100 MB en ejecución, así que un tope de 512 MB va sobrado.
4. **Despliega menos veces.** Cada build consume cómputo: agrupa los cambios en un commit en vez de empujar seis seguidos.
5. **Borra lo que no uses.** Servicios viejos, entornos de prueba y despliegues parados siguen ocupando.

La base en Aiven y el frontend en Cloudflare no consumen créditos de Railway.

---

## Problemas frecuentes

**El backend reinicia en bucle.** Casi siempre es `SECRET_KEY` sin definir: la aplicación no arranca sin ella.

**El frontend carga pero ninguna llamada funciona.** `VITE_API_URL` quedó en su valor por defecto `/api`. Corrígela y **vuelve a compilar y desplegar** para reconstruir el bundle.

**Errores de CORS.** El origen del frontend no coincide exactamente con `ORIGENES_PERMITIDOS`: compara esquema, subdominio y ausencia de barra final.

**`'cryptography' package is required for ... caching_sha2_password`.** MySQL 8 usa ese método y necesita `cryptography`, que ya está en `requirements.txt`.

**Los correos de recuperación no llegan.** Revisa las variables `SMTP_*` (y el log del backend: si faltan, avisa «SMTP no configurado»). Algunas plataformas bloquean los puertos SMTP salientes; en ese caso usa un proveedor con un puerto permitido (`python -m scripts.probar_smtp` prueba la conexión).

**No puedo entrar y me pide cambiar la contraseña.** Es a propósito: las cuentas con clave provisional (las que crea un administrador y el administrador con la clave de ejemplo) tienen que fijar una propia antes de usar el panel.

**Tildes y eñes mal.** El backend fuerza `charset=utf8mb4` cuando la URL no lo trae.

**Stripe cobra, pero la reserva sigue «pendiente».** Falta configurar el webhook (sección 5) o `STRIPE_WEBHOOK_SECRET` no coincide con el del endpoint. Mientras tanto, la reserva se confirma cuando el cliente vuelve a la web.

**En Windows, conectar a la base con TLS falla con `[WinError 87] El parámetro no es correcto`.** Es un problema del bucle Proactor de asyncio con SSL, no del servidor ni del código: en Linux, que es lo que corre el contenedor, no ocurre. Para reproducirlo en local contra una base gestionada, usa el bucle Selector antes de arrancar:

```python
import asyncio, sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

Para el desarrollo diario contra el MySQL local de XAMPP no aplica, porque ahí no se usa TLS.
