import { execFileSync } from "node:child_process";
export default async function setup() {
  const env = {
    ...process.env,
    DATABASE_URL:
      process.env.E2E_DATABASE_URL ||
      "postgresql+asyncpg://mechanic@127.0.0.1:55432/ted_e2e_test",
  };
  execFileSync(".venv/bin/alembic", ["upgrade", "head"], {
    cwd: "../backend",
    env,
  });
  execFileSync(".venv/bin/python", ["tests/seed_e2e.py"], {
    cwd: "../backend",
    env,
  });
}
