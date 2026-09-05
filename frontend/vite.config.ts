import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
// Port pinned to 5173 (Vite's default) because ashlar/api/server.py's CORS
// allowlist is hardcoded to http://localhost:5173 — see specs/00_ARCHITECTURE.md
// and the FRONTEND_ORIGIN constant in that file. strictPort so a silent
// fallback to 5174+ never quietly breaks the API connection.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
})
