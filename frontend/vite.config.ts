import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: 1500 }, // MapLibre alone is over 1 MB minified.
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
