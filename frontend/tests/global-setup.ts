import { testDatabase } from "./database-safety";
import { execFileSync } from "node:child_process";
export default async function setup() {
  const env = {
    ...process.env,
    DATABASE_URL: testDatabase(),
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
