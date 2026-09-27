import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Pre-bundle the runtime deps when the dev server boots instead of on the
  // first browser request: otherwise the first page load stalls every module
  // request until the optimizer finishes (looks like an eternal white/loading
  // screen in the browser).
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-dom/client', 'axios', 'leaflet', 'react-leaflet', 'recharts'],
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // Pin IPv4: the backend binds 0.0.0.0, and 'localhost' can resolve to
        // ::1 (IPv6) where nothing listens -> proxy requests hang or fail.
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  }
})
