# Guía de Configuración de Correos en Aurora Viajes

## 📧 Configuración de SMTP para Recuperación de Contraseña

El servicio de recuperación de contraseña requiere configurar un servidor SMTP para enviar correos.

## Opción 1: Gmail (Recomendado para desarrollo)

### Paso 1: Habilitar autenticación de 2 factores en Gmail
1. Ir a [https://myaccount.google.com/security](https://myaccount.google.com/security)
2. Buscar "Verificación en dos pasos" y habilitarlo

### Paso 2: Crear una contraseña de aplicación
1. En la misma sección de seguridad, buscar "Contraseñas de aplicación"
2. Seleccionar "Correo" y "Windows"
3. Google generará una contraseña de 16 caracteres

### Paso 3: Configurar en `.env`

```env
# CORREOS SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu_email@gmail.com
SMTP_PASSWORD=abcd efgh ijkl mnop  # (16 caracteres sin espacios)
SMTP_FROM=tu_email@gmail.com
SMTP_USE_TLS=True
```

⚠️ **Importante**: Usar la contraseña generada por Google, NO tu contraseña normal.

---

## Opción 2: Microsoft Outlook

```env
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=tu_email@outlook.com
SMTP_PASSWORD=tu_contraseña_outlook
SMTP_FROM=tu_email@outlook.com
SMTP_USE_TLS=True
```

---

## Opción 3: SendGrid

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.tu_clave_sendgrid_aqui
SMTP_FROM=noreply@auroraviajes.com
SMTP_USE_TLS=True
```

Registrarse en: https://sendgrid.com

---

## Opción 4: Servidor SMTP personalizado

```env
SMTP_HOST=mail.tudominio.com
SMTP_PORT=587  # o 465 para SSL
SMTP_USER=tu_usuario
SMTP_PASSWORD=tu_contraseña
SMTP_FROM=noreply@tudominio.com
SMTP_USE_TLS=True  # cambiar a False si usas puerto 465
```

---

## ✅ Cómo verificar que funciona

### 1. Prueba de conectividad SMTP

Ejecutar este script en Python:

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configuración
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "tu_email@gmail.com"
SMTP_PASSWORD = "tu_contraseña_app"
SMTP_FROM = "tu_email@gmail.com"

# Probar conexión
try:
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as servidor:
        servidor.starttls()
        servidor.login(SMTP_USER, SMTP_PASSWORD)
    print("✅ Conexión SMTP exitosa!")
except Exception as e:
    print(f"❌ Error: {e}")
```

### 2. Prueba de recuperación de contraseña desde la API

```bash
# Solicitar recuperación
curl -X POST http://localhost:8000/api/auth/recuperar \
  -H "Content-Type: application/json" \
  -d '{"correo":"usuario@example.com"}'

# Debería retornar:
# {"mensaje":"Se envió un enlace de recuperación a tu correo...","token":"..."}
```

### 3. Revisar logs

Los logs mostrarán:
```
INFO - Correo de recuperación enviado exitosamente a usuario@example.com
```

O si hay error:
```
ERROR - Error SMTP al enviar correo de recuperación a usuario@example.com: [ERRORMESSAGE]
```

---

## 🐛 Solución de problemas

### "SMTP no configurado"
**Solución**: Asegurar que `SMTP_HOST` y `SMTP_USER` están configurados en `.env`

### "Error de autenticación"
**Solución**: Verificar credenciales. Para Gmail, DEBE ser contraseña de aplicación, no la contraseña normal.

### "Connection timeout"
**Solución**: Verificar que `SMTP_HOST` y `SMTP_PORT` son correctos. Algunos ISP bloquean puerto 587.

### "TLS required"
**Solución**: Asegurar que `SMTP_USE_TLS=True`

### "Permiso denegado"
**Solución**: Para Gmail, habilitar "Acceso de aplicaciones menos seguras" o usar contraseña de aplicación.

---

## 📝 Flujo Completo de Recuperación

1. **Usuario solicita recuperación** en `/login`
   ```
   POST /api/auth/recuperar
   {"correo": "usuario@example.com"}
   ```

2. **Backend valida el correo** y genera token JWT de 1 hora

3. **Backend envía correo** con enlace:
   ```
   http://localhost:5173/login?token=JWT_AQUI&vista=recuperar
   ```

4. **Usuario recibe correo** con botón "Recuperar Contraseña"

5. **Usuario hace clic** y ve formulario de nueva contraseña

6. **Usuario envía nueva contraseña**:
   ```
   POST /api/auth/restablecer
   {"correo": "usuario@example.com", "token": "JWT_AQUI", "nuevaContrasena": "Nueva123!"}
   ```

7. **Backend valida token** y actualiza contraseña

8. **Usuario puede iniciar sesión** con nueva contraseña

---

## 🔒 Seguridad

- ✅ Tokens expiran en **1 hora**
- ✅ Token solo válido para el email específico
- ✅ Contraseña se envía solo por el cliente (HTTPS en producción)
- ✅ Se registran intentos fallidos en logs

---

## 🚀 Próximos pasos

1. Configurar variables en `.env` según tu proveedor SMTP
2. Instalar dependencias: `pip install aiosmtplib`
3. Reiniciar el servidor: `python -m uvicorn app.main:app --reload`
4. Probar recuperación de contraseña en el login

¡Listo! Los correos de recuperación ahora funcionarán automáticamente.
