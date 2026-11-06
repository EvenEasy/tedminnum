import { defineConfig } from "@playwright/test";
const database =
  process.env.E2E_DATABASE_URL ||
  "postgresql+asyncpg://mechanic@127.0.0.1:55432/ted_e2e_test";
const env = {
  ...process.env,
  DATABASE_URL: database,
  SECURE_COOKIES: "false",
  APP_ORIGIN: "http://127.0.0.1:8000",
} as Record<string, string>;
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  fullyParallel: false,
  timeout: 60000,
  use: {
    baseURL: "http://127.0.0.1:8000",
    browserName: "chromium",
    trace: "retain-on-failure",
    actionTimeout: 10000,
  },
  globalSetup: "./tests/global-setup.ts",
  webServer: {
    command:
      "../backend/.venv/bin/uvicorn ted.presentation.api:app --app-dir ../backend/src --host 127.0.0.1 --port 8000 --no-proxy-headers",
    url: "http://127.0.0.1:8000/api/health",
    reuseExistingServer: false,
    env,
    timeout: 20000,
  },
});
