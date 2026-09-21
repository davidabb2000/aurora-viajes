import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

import { cloudflare } from "@cloudflare/vite-plugin";

/**
 * Cabeceras de seguridad de la web, en el archivo `_headers` que Cloudflare lee junto a los assets.
 *
 * La política de contenido solo deja cargar lo propio, el mapa de Google y la API. El origen de la API sale
 * de VITE_API_URL en cada compilación, así que si el backend cambia de dirección no hay que tocar nada aquí.
 */
function cabecerasDeSeguridad(urlDeLaApi) {
  let origenDeLaApi = ''
  try {
    origenDeLaApi = new URL(urlDeLaApi).origin
  } catch {
    // Sin VITE_API_URL (o relativa, como /api) la API es del mismo origen y 'self' ya la cubre.
  }
  const politica = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `connect-src 'self'${origenDeLaApi ? ` ${origenDeLaApi}` : ''}`,
    "frame-src https://www.google.com",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
  ].join('; ')

  return {
    name: 'aurora-cabeceras-de-seguridad',
    apply: 'build',
    generateBundle() {
      // El plugin de Cloudflare compila también el worker: el archivo va solo con los assets del navegador.
      if (this.environment?.name && this.environment.name !== 'client') return
      this.emitFile({
        type: 'asset',
        fileName: '_headers',
        source: [
          '/*',
          `  Content-Security-Policy: ${politica}`,
          '  X-Content-Type-Options: nosniff',
          '  X-Frame-Options: DENY',
          '  Referrer-Policy: no-referrer',
          '  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()',
          '',
        ].join('\n'),
      })
    },
  }
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const entorno = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react(), tailwindcss(), cloudflare(), cabecerasDeSeguridad(entorno.VITE_API_URL)],
    server: {
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8001',
          changeOrigin: true,
        },
      },
    },
  }
})
