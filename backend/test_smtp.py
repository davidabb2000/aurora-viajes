#!/usr/bin/env python
"""
Script para probar la configuración SMTP de Aurora Viajes.

Uso:
    python test_smtp.py
"""

import asyncio
import sys
from pathlib import Path

# Agregar el backend al path
backend_path = Path(__file__).parent.absolute()
sys.path.insert(0, str(backend_path))

# Importar configuración
from app.core.configuracion import configuracion
from app.services.correos import enviar_correo_recuperacion, enviar_correo_bienvenida


async def test_smtp_connection():
    """Prueba la conexión SMTP."""
    print("=" * 60)
    print("🔍 PRUEBA DE CONEXIÓN SMTP")
    print("=" * 60)
    
    # Verificar que SMTP esté configurado
    if not configuracion.smtp_host:
        print("❌ SMTP_HOST no configurado en .env")
        return False
    
    if not configuracion.smtp_user:
        print("❌ SMTP_USER no configurado en .env")
        return False
    
    print(f"✓ SMTP_HOST: {configuracion.smtp_host}")
    print(f"✓ SMTP_PORT: {configuracion.smtp_port}")
    print(f"✓ SMTP_USER: {configuracion.smtp_user}")
    print(f"✓ SMTP_USE_TLS: {configuracion.smtp_use_tls}")
    print(f"✓ SMTP_FROM: {configuracion.smtp_from}")
    
    # Importar aiosmtplib
    try:
        import aiosmtplib
        print("✓ aiosmtplib instalado correctamente")
    except ImportError:
        print("❌ aiosmtplib no instalado. Ejecutar: pip install aiosmtplib")
        return False
    
    # Intentar conectar
    try:
        print("\n📡 Intentando conectar al servidor SMTP...")
        
        # Para puerto 465: SSL implícito (use_tls=True)
        # Para puerto 587: TLS implícito en SendGrid (SIN starttls)
        if configuracion.smtp_port == 465:
            # SSL implícito desde el inicio
            async with aiosmtplib.SMTP(
                hostname=configuracion.smtp_host,
                port=configuracion.smtp_port,
                use_tls=True,
                start_tls=False,
                timeout=10
            ) as cliente:
                print("✓ Conexión exitosa (SSL implícito - puerto 465)")
                
                # Intentar autenticarse
                if configuracion.smtp_user and configuracion.smtp_password:
                    print("🔑 Intentando autenticación...")
                    await cliente.login(configuracion.smtp_user, configuracion.smtp_password)
                    print("✓ Autenticación exitosa")
                else:
                    print("⚠️  Sin credenciales para autenticarse (no es error crítico)")
        else:
            # Puerto 587 usa STARTTLS explícito.
            async with aiosmtplib.SMTP(
                hostname=configuracion.smtp_host,
                port=configuracion.smtp_port,
                start_tls=False,
                timeout=10
            ) as cliente:
                print("✓ Conexión exitosa (puerto 587 - TLS implícito)")
                if configuracion.smtp_use_tls:
                    await cliente.starttls()
                
                # Intentar autenticarse
                if configuracion.smtp_user and configuracion.smtp_password:
                    print("🔑 Intentando autenticación...")
                    await cliente.login(configuracion.smtp_user, configuracion.smtp_password)
                    print("✓ Autenticación exitosa")
                else:
                    print("⚠️  Sin credenciales para autenticarse (no es error crítico)")
        
        print("\n✅ Configuración SMTP válida")
        return True
        
    except asyncio.TimeoutError:
        print(f"❌ Timeout conectando a {configuracion.smtp_host}:{configuracion.smtp_port}")
        print("   Verificar firewall o que el puerto no esté bloqueado")
        return False
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False


async def test_enviar_correo_recuperacion():
    """Prueba envío de correo de recuperación."""
    print("\n" + "=" * 60)
    print("📧 PRUEBA DE ENVÍO - CORREO DE RECUPERACIÓN")
    print("=" * 60)
    
    email = input("\n¿A qué email enviar la prueba? >>> ").strip()
    if not email:
        print("❌ Email vacío")
        return False
    
    if "@" not in email:
        print("❌ Email inválido")
        return False
    
    nombre = "Usuario Prueba"
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.prueba.signature"
    
    print(f"\n📤 Enviando correo de recuperación a: {email}")
    resultado = await enviar_correo_recuperacion(email, nombre, token)
    
    if resultado:
        print("✅ Correo de recuperación enviado exitosamente")
        print(f"⏱️  Verifica tu bandeja de entrada en: {email}")
        return True
    else:
        print("❌ No se pudo enviar el correo")
        print("   Revisar logs y configuración SMTP")
        return False


async def test_enviar_correo_bienvenida():
    """Prueba envío de correo de bienvenida."""
    print("\n" + "=" * 60)
    print("🎉 PRUEBA DE ENVÍO - CORREO DE BIENVENIDA")
    print("=" * 60)
    
    email = input("\n¿A qué email enviar la prueba? >>> ").strip()
    if not email:
        print("❌ Email vacío")
        return False
    
    if "@" not in email:
        print("❌ Email inválido")
        return False
    
    nombre = "Usuario Bienvenido"
    
    print(f"\n📤 Enviando correo de bienvenida a: {email}")
    resultado = await enviar_correo_bienvenida(email, nombre)
    
    if resultado:
        print("✅ Correo de bienvenida enviado exitosamente")
        print(f"⏱️  Verifica tu bandeja de entrada en: {email}")
        return True
    else:
        print("❌ No se pudo enviar el correo")
        return False


async def main():
    """Menú principal."""
    print("\n")
    print("🚀 PRUEBA DE CONFIGURACIÓN SMTP - AURORA VIAJES")
    print("=" * 60)
    
    while True:
        print("\n¿Qué deseas probar?")
        print("1. Conexión SMTP")
        print("2. Enviar correo de recuperación de contraseña")
        print("3. Enviar correo de bienvenida")
        print("4. Probar todo")
        print("0. Salir")
        
        opcion = input("\nSelecciona una opción: >>> ").strip()
        
        if opcion == "1":
            await test_smtp_connection()
        elif opcion == "2":
            await test_enviar_correo_recuperacion()
        elif opcion == "3":
            await test_enviar_correo_bienvenida()
        elif opcion == "4":
            conexion_ok = await test_smtp_connection()
            if conexion_ok:
                await test_enviar_correo_recuperacion()
                await test_enviar_correo_bienvenida()
        elif opcion == "0":
            print("\n✋ ¡Hasta luego!")
            break
        else:
            print("❌ Opción no válida")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Programa interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
