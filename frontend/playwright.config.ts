import { defineConfig, devices } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const backendDir = path.resolve(__dirname, '..', 'backend')

// Dedicated ports, distinct from any dev instance a human might already have
// running (5173/8000 and friends) — this config always starts its own pair.
const BACKEND_PORT = 8020
const FRONTEND_PORT = 5190
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`
const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  // Both specs share the same live Postgres claim-discovery/seeding logic
  // (e2e/claim-fixture.ts) — running them concurrently risks two workers
  // racing to claim the same eligible row. This suite is deliberately small
  // (one broad journey + one narrow regression test), so serial execution
  // costs nothing and removes that race entirely.
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [['list']],

  use: {
    baseURL: FRONTEND_URL,
    trace: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  webServer: [
    {
      command: `"${path.join(backendDir, '.venv', 'Scripts', 'python.exe')}" -m uvicorn main:app --host 127.0.0.1 --port ${BACKEND_PORT}`,
      cwd: backendDir,
      url: `${BACKEND_URL}/api/health`,
      reuseExistingServer: false,
      timeout: 30_000,
      env: {
        // Real Postgres, real Commander pipeline, real HTTP — only the
        // Claude API calls (02/03) are swapped for a deterministic fake.
        // See backend/app/testing/fake_anthropic.py.
        MOCK_ANTHROPIC: '1',
        CORS_ORIGINS: `${FRONTEND_URL},http://localhost:${FRONTEND_PORT}`,
      },
    },
    {
      command: `npx vite --host 127.0.0.1 --port ${FRONTEND_PORT}`,
      cwd: __dirname,
      url: FRONTEND_URL,
      reuseExistingServer: false,
      timeout: 30_000,
      env: {
        VITE_API_BASE: BACKEND_URL,
      },
    },
  ],
})
