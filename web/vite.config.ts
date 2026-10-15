import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    // Locally, /api goes to the FastAPI dev server, mirroring the Firebase Hosting rewrite.
    proxy: { '/api': 'http://localhost:8080' },
  },
})
