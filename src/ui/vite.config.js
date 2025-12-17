import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  esbuild: {
    // SECURITY: Strip console.log and debugger statements in production builds.
    // This prevents accidental exposure of sensitive data (user IDs, API endpoints,
    // configuration details) that may be logged during development.
    // The conditional ensures development debugging remains functional.
    
    drop: process.env.NODE_ENV === 'production' ? ['console', 'debugger'] : [],
  },
})
