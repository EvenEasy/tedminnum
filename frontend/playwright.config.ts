import { defineConfig } from "@playwright/test";
import { testDatabase } from "./tests/database-safety";
const database = testDatabase();
const env = {
  ...process.env,
  DATABASE_URL: database,
  APP_ENV: "development",
  SECURE_COOKIES: "false",
  APP_ORIGIN: "http://127.0.0.1:8000",
  DEV_ORIGINS: "http://127.0.0.1:5173",
} as Record<string, string>;
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  fullyParallel: false,
  timeout: 60000,
  use: {
    baseURL: "http://127.0.0.1:5173",
    browserName: "chromium",
    trace: "retain-on-failure",
    actionTimeout: 10000,
  },
  globalSetup: "./tests/global-setup.ts",
  webServer: [
    {
      command: "../backend/.venv/bin/python -m ted.dev",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: false,
      env,
      timeout: 20000,
    },
    {
      command: "npm run dev -- --port 5173",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: false,
      timeout: 20000,
    },
  ],
});
