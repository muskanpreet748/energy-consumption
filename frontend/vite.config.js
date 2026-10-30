import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development the backend runs separately on :8000, so /api is
// proxied. In production the app and the API share an origin, so no
// proxy or CORS configuration is needed.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
