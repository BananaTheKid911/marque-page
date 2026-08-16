import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      // Nouvelle version du SW activée dès qu'elle est prête, sans invite de
      // rechargement : adapté à une app mono-utilisateur self-hosted.
      registerType: 'autoUpdate',
      // Assets à inclure dans le pré-cache en plus de ceux de dist/.
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'Marque-page',
        short_name: 'Marque-page',
        lang: 'fr',
        display: 'standalone',
        start_url: '/',
        theme_color: '#f6efe3', // le papier — pas d'accent coloré
        background_color: '#f6efe3',
        icons: [
          // PLACEHOLDERS — icônes finales (PNG 192/512, papier/encre) à
          // produire par design-ui (Claude Code). Ne pas dessiner ici.
          {
            src: 'icons/pwa-192.svg',
            sizes: '192x192',
            type: 'image/svg+xml',
            purpose: 'any',
          },
          {
            src: 'icons/pwa-512.svg',
            sizes: '512x512',
            type: 'image/svg+xml',
            purpose: 'any',
          },
        ],
      },
      workbox: {
        // SPA : toute navigation (deep link, rechargement) sert index.html.
        navigateFallback: '/index.html',
        cleanupOutdatedCaches: true,
        // Pré-cache l'app + les polices auto-hébergées (jamais de CDN), mais
        // PAS covers/ : les couvertures sont des données utilisateur, servies
        // normalement (réseau) pour rester fraîches.
        globPatterns: ['**/*.{js,css,html,svg,ico,woff,woff2}'],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
})
