import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  build: {
    sourcemap: false,
    target: 'es2018',
  },
  server: {
    port: 5173,
    proxy: {
      // Optional: Proxy API requests during development
      // Uncomment if you want to use proxy instead of CORS
      // '/api': {
      //   target: 'http://localhost:3000',
      //   changeOrigin: true,
      //   secure: false,
      // }
    }
  }
}))


