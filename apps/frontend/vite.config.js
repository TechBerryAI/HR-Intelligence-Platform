import path from 'path'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const host = env.VITE_DEV_HOST || '0.0.0.0'
  const port = Number(env.VITE_DEV_PORT || 5173)

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    build: {
      sourcemap: false,
      target: 'es2018',
    },
    server: {
      host,
      port,
      strictPort: true,
      proxy: {
        // Same-origin API: browser calls /api and /health; Vite forwards to Flask.
        // Works from phones/other devices on the LAN without setting VITE_API_URL
        // (leave VITE_API_URL empty in .env — required for VM/LAN with backend FRONTEND_URL).
        '/api': {
          target: 'http://127.0.0.1:3000',
          changeOrigin: true,
          secure: false,
        },
        '/health': {
          target: 'http://127.0.0.1:3000',
          changeOrigin: true,
          secure: false,
        },
      },
    },
  }
})
