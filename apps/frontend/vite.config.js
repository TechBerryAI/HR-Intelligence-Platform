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
    test: {
      environment: 'jsdom',
      include: ['src/**/*.{test,spec}.{js,jsx}'],
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
          // Long parse SSE streams (resume/JD) must not be cut off by the default proxy timeout.
          timeout: 320000,
          proxyTimeout: 320000,
          configure(proxy) {
            proxy.on('proxyRes', (proxyRes, _req, res) => {
              const ct = String(proxyRes.headers['content-type'] || '')
              if (!ct.includes('text/event-stream')) return
              proxyRes.headers['cache-control'] = 'no-cache, no-transform'
              proxyRes.headers['x-accel-buffering'] = 'no'
              proxyRes.headers['connection'] = 'keep-alive'
              delete proxyRes.headers['content-length']
              delete proxyRes.headers['content-encoding']
              const origWrite = typeof res.write === 'function' ? res.write.bind(res) : null
              if (origWrite) {
                res.write = (...args) => {
                  const ok = origWrite(...args)
                  if (typeof res.flush === 'function') res.flush()
                  return ok
                }
              }
            })
          },
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
