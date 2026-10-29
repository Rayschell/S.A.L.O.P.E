import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      // Découverte OAuth du serveur MCP
      '/.well-known': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
})
