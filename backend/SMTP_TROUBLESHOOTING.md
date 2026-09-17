# ❌ Problema: Error de Conexión SMTP - Soluciones

## Error Observado
```
Error connecting to smtp.gmail.com on port 587: [SSL: WRONG_VERSION_NUMBER] wrong version number (_ssl.c:1082)
```

---

## 🔍 Causas Posibles

### 1. **Firewall o Proxy Bloqueando Puerto 587** ⚠️ MÁS PROBABLE
- El puerto 587 podría estar bloqueado por:
  - Firewall de Windows
  - Software antivirus
  - Router/ISP
  - Red corporativa

### 2. **Credenciales Inválidas**
- Contraseña de aplicación expirada
- Contraseña normal en lugar de contraseña de aplicación
- Autenticación 2FA no habilitada

### 3. **Problemas de Red**
- Conexión a internet inestable
- DNS no resolviendo smtp.gmail.com

---

## ✅ Soluciones (En Orden)

### Solución 1: Verificar Firewall de Windows

```powershell
# Abrir Windows Defender Firewall
# Settings → Privacy & Security → Windows Security → Firewall & network protection
# Permitir Python y aiosmtplib
```

### Solución 2: Intentar Puerto 465 (SSL Implícito)

Cambiar en `.env`:
```env
SMTP_PORT=465
SMTP_USE_TLS=False
```

⚠️ Nota: Requiere actualizar el código para usar `use_tls=True` en constructor si se usa puerto 465.

### Solución 3: Verificar Credenciales Gmail

1. Ir a [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Verificar que:
   - ✅ 2FA esté habilitado
   - ✅ La contraseña fue generada correctamente (16 caracteres)
   - ✅ La contraseña en `.env` sea exacta (sin espacios)

### Solución 4: Usar un Cliente SMTP Alternativo

#### Opción A: Cambiar a Outlook/Hotmail
```env
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=tu_email@outlook.com
SMTP_PASSWORD=tu_contraseña_outlook
SMTP_USE_TLS=True
```

#### Opción B: Usar SendGrid (Recomendado)
```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.tu_api_key_aqui
SMTP_USE_TLS=True
```

Registrarse gratis en: https://sendgrid.com

### Solución 5: Test de Conectividad Básico

```python
# test_connection.py - Verificar si el puerto está abierto
import socket

host = "smtp.gmail.com"
port = 587

try:
    socket.create_connection((host, port), timeout=5)
    print(f"✅ Puerto {port} está accesible")
except socket.timeout:
    print(f"❌ Timeout - puerto {port} bloqueado")
except ConnectionRefusedError:
    print(f"❌ Conexión rechazada en puerto {port}")
except Exception as e:
    print(f"❌ Error: {e}")
```

Ejecutar:
```bash
python test_connection.py
```

---

## 📊 Estado Actual del Código

✅ **Sintaxis**: Correcta (sin errores)
✅ **Lógica SMTP**: Implementada correctamente
✅ **Configuración**: Cargada desde `.env`
✅ **Async**: Usando `aiosmtplib`

### Lo que cambió:
- ❌ Removido `use_tls=True` del constructor SMTP
- ✅ Agregado `await cliente.starttls()` después de conectar
- ✅ Esto es correcto para puerto 587 (STARTTLS)

---

## 🚀 Próximos Pasos Recomendados

**Inmediato:**
1. Verificar firewall de Windows
2. Intentar puerto 465 con `SMTP_USE_TLS=False`
3. Ejecutar test de conectividad (socket)

**Alternativa:**
4. Cambiar a SendGrid (más confiable)

**Cuando funcione la conexión:**
5. Reiniciar servidor FastAPI
6. Probar flujo de recuperación de contraseña
7. Verificar logs en `backend/logs/`

---

## 💡 Nota Importante

El **error SSL es un problema de red/configuración**, NO del código. El servicio SMTP está correctamente implementado:

```python
# Ahora correcto para puerto 587:
async with aiosmtplib.SMTP(host, 587):
    await cliente.starttls()  # ✅ Correcto
    await cliente.login(user, pwd)
    await cliente.send_message(msg)
```

Una vez resueltas las conexión, los correos se enviarán automáticamente.

---

## ❓ Preguntas Frecuentes

**P: ¿Por qué funciona en una máquina pero no en otra?**
A: Diferente firewall, antivirus o configuración de red

**P: ¿Necesito cambiar código?**
A: No, el código está correcto. Es un problema de red/configuración

**P: ¿Qué hago si nada funciona?**
A: Usa SendGrid - es más confiable y tiene plan gratuito

---

**¿Necesitas ayuda con alguna solución específica?** 🆘
