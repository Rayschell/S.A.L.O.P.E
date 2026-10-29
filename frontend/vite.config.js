import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Robots d'aperçu de liens : même liste que la map $apercu_robot de nginx.conf
const ROBOT_APERCU = /discordbot|facebookexternalhit|facebot|whatsapp|telegrambot|slackbot|twitterbot|linkedinbot|skypeuripreview|applebot|iframely|embedly|redditbot|mastodon/i

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      // Formulaire public : page Open Graph pour les robots, SPA pour les humains
      '/dispo': {
        target: 'http://backend:8000',
        changeOrigin: true,
        bypass: (req) => {
          if (!ROBOT_APERCU.test(req.headers['user-agent'] || '')) return '/index.html'
        },
        rewrite: (path) => path.replace(/^\/dispo\/([^/?]+)\/?(\?.*)?$/, '/api/public/polls/$1/apercu'),
      },
      // Découverte OAuth du serveur MCP
      '/.well-known': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
})
