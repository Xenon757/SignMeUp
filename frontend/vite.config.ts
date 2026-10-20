/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development, API and static requests go to the Flask app (port 5001 by default;
// macOS uses 5000 for AirPlay). In production Flask serves the built files itself.
const backend = process.env.SIGNMEUP_BACKEND ?? 'http://localhost:5001'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': backend, '/poses': backend, '/static': backend, '/upload': backend },
  },
  test: { environment: 'node' },
})
