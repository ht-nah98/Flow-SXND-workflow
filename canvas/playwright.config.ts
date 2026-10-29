import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: 'e2e',
  timeout: 90_000,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:5181', trace: 'retain-on-failure' },
  webServer: [
    { command: 'bash e2e/start-backend.sh', url: 'http://127.0.0.1:8120/health', timeout: 60_000, reuseExistingServer: false },
    { command: 'npx vite', url: 'http://127.0.0.1:5181', timeout: 60_000, reuseExistingServer: false,
      env: { CANVAS_PORT: '5181', VITE_FLOWKIT_URL: 'http://127.0.0.1:8120' } },
  ],
})
