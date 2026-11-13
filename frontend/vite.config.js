import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, /api calls go to the Flask backend. NEXT_PUBLIC_ is allowed so the Clerk publishable key the
// Vercel Marketplace provisions (NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) reaches the browser (spec 08).
export default defineConfig({
  plugins: [react()],
  envPrefix: ['VITE_', 'NEXT_PUBLIC_'],
  server: {
    port: 5173,
    proxy: { '/api': process.env.VITE_API_URL || 'http://localhost:5000' },
  },
})
