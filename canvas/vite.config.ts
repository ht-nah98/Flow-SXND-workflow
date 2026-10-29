/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { host: '127.0.0.1', port: Number(process.env.CANVAS_PORT ?? 5180), strictPort: true },
  // The everyday canvas is the production build (./start.sh canvas): React dev mode re-validates every element and
  // made the 55-shot canvas several times slower (perf 19/10). `./start.sh canvas-dev` keeps hot reload for coding.
  preview: { host: '127.0.0.1', port: Number(process.env.CANVAS_PORT ?? 5180), strictPort: true },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
