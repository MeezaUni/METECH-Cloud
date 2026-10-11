import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, Vite proxies /api to the backend so the browser only ever talks to one origin.
// Cloud edition: API on :8010, UI on :5173.
const API_PORT = process.env.KMRL_API_PORT ?? '8010'

export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.KMRL_UI_PORT ?? 5173),
    proxy: { '/api': `http://127.0.0.1:${API_PORT}` },
  },
})
