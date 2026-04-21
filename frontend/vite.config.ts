import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      // Allow importing static assets (demo images) from the repo root
      allow: ['..'],
    },
  },
})
