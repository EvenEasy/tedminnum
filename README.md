# Tedminnum

A self-hosted project, focus-time and billing application. FastAPI, async SQLAlchemy, PostgreSQL, React, TypeScript and Vite; one modular monolith for a small workspace.

## Native local development with existing PostgreSQL

Requires Python 3.12+, uv and Node 22+. Use your existing PostgreSQL server through `DATABASE_URL`. No Docker, local PostgreSQL installation, new containers, or infrastructure services are required.

1. Preserve an existing `.env` and its `DATABASE_URL`. If none exists, copy `.env.example` to `.env` at the repository root and set the existing application database URL (URL-encode reserved password characters). The development launcher below supplies process-local development settings without changing your file. If you prefer launching Uvicorn directly, configure this explicit local profile instead:

   ```dotenv
   DATABASE_URL=postgresql+asyncpg://user:password@existing-host:5432/ted
   APP_ENV=development
   APP_ORIGIN=http://localhost:8000
   DEV_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
   SECURE_COOKIES=false
   ```

   Keep `.env` private (`chmod 600 .env`). Configuration loads root `.env`, then optional `backend/.env` overrides, then shell environment overrides. This is independent of the command's working directory. Do not put database credentials in frontend environment files. Unused Compose credentials can stay empty.
2. Start the backend:

   ```sh
   cd backend
   uv sync --frozen
   uv run python -m ted.dev --reload
   ```

`ted.dev` binds only to loopback, explicitly enables the listed local origins and non-Secure cookies for HTTP, and reuses the existing database URL. It never rewrites `.env`, changes production defaults, migrates, seeds, or starts PostgreSQL. Repeat `--frontend-origin http://host:port` to override its frontend allowlist. For ordinary production/native execution use `uv run uvicorn ted.presentation.api:app --host 127.0.0.1 --port 8000` with your validated environment.

3. Start the frontend in a second terminal:

   ```sh
   cd frontend
   npm ci
   npm run dev
   ```

4. Open **http://localhost:5173** or **http://127.0.0.1:5173**. Vite proxies `/api` to `http://127.0.0.1:8000` while preserving the browser's Origin. Port 5173 is strict: an occupied port causes an error instead of silently choosing an unconfigured origin.

Normal startup never creates schemas, migrates, seeds, or truncates a database. For an existing installation, keep its accounts and data. For a fresh **dedicated application database**, or a reviewed upgrade after a backup, explicitly inspect migration state and apply only the intended migrations:

```sh
cd backend
uv run alembic current
# Only after confirming DATABASE_URL and reviewing the upgrade:
uv run alembic upgrade head
```

The database must support the existing `btree_gist` extension/constraints. On a fresh dedicated database, its administrator must install the extension or give the migration role the necessary CREATE privilege; the runtime role does not need superuser or schema-creation privileges. This refactor adds no schema migration. If the database has no users, explicitly create the first administrator with `uv run python -m ted.cli admin@example.com`; it prompts for a password and refuses after users exist. Never use test seed scripts on this database.

For webhook delivery, optionally run `uv run python -m ted.infrastructure.webhooks` with the same environment. It uses the existing database; there is no Redis or broker dependency.

## Login troubleshooting and security

`403 {"detail":"Origin rejected"}` means the request was rejected **before credentials or CSRF were checked**. Compare the browser's Network → login request → `Origin` with `APP_ORIGIN` and `DEV_ORIGINS`. Restart the backend after changing configuration. `localhost`, `127.0.0.1`, schemes and ports are different origins; origins must have no path/trailing slash. Vite preserves Origin intentionally. Do not solve this by rewriting Origin, allowing `*`, trusting Host, disabling CSRF, or adding broad CORS.

Production defaults to `APP_ENV=production`, Secure cookies, and one exact `APP_ORIGIN`. Development-only origins and `SECURE_COOKIES=false` require explicit development mode. Non-loopback production origins must use HTTPS. Production deployments must set their actual HTTPS origin and leave `DEV_ORIGINS` empty.

A successful login followed by `401` is a separate session/cookie issue: use one browser hostname consistently and check whether the cookie was accepted. Native HTTP development needs the explicit profile above. Cookies stay HttpOnly and SameSite=Strict. Protected mutations also require the per-session `X-CSRF-Token` returned by login or `/api/v1/auth/me`; a CSRF failure says `CSRF token required`. Invalid credentials return `401`. Logout revokes the server-side session.

The React client centralizes authentication, clears credentials/private state on account changes and session expiry, rejects delayed results from old sessions, and checks the authenticated subject response header to detect cookies changed by another tab. Timers render from authoritative server timestamps and a refreshed server clock offset.

## Architecture and API

- `backend/src/ted/domain`: framework-free domain entities and deterministic money rules.
- `application`: identity, work management, tracking, billing, integrations and shared access/audit policies. Consumer-owned query/repository ports and constructor injection; no FastAPI, SQLAlchemy or infrastructure imports.
- `infrastructure/persistence`: separate ORM records, existing schema metadata, row/domain conversion and focused concrete repositories. Repositories flush but never commit.
- `presentation/routers`: feature-specific HTTP routes. `presentation/dependencies.py` is the manual composition root. The existing explicit outer request transaction still commits before success is sent and rolls back on failure. Each request/job owns a separate session; process shutdown disposes the engine.
- `frontend/src/main.tsx`: bootstrap only. Feature pages/components/API operations/hooks live under `features`; application composition/loading under `app`; reusable UI, types, theme and API error handling under `shared`.

Public paths, payloads, decimal-string amounts, UUIDs, persisted data and the Alembic chain are preserved. PostgreSQL-specific constraints remain in infrastructure/migrations. See [decisions](docs/DECISIONS.md) and [refactor verification](docs/REFACTOR.md).

API: `/api/v1`; health: `/api/health`; OpenAPI: `/api/openapi.json`. Collections accept `limit` (1–200) and `offset`. For the self-hosted documentation UI, run `npm run build` in `frontend` and serve FastAPI on port 8000; `/api/docs` then uses the built local assets. Vite development alone does not serve those documentation assets.

## Safe verification

Without database configuration, `uv run pytest -q` runs pure/domain/HTTP-auth tests and skips PostgreSQL tests. It never falls back to `DATABASE_URL`. Full integration tests **truncate tables** and require both an explicit `TEST_DATABASE_URL` naming a confirmed disposable database ending `_test` and `ALLOW_DESTRUCTIVE_TESTS=1`. Prepare that disposable database separately; never use a homelab/application database, even if its name happens to end in `_test`.

```sh
cd backend
uv run ruff check src tests migrations
uv run ruff format --check src tests migrations
uv run mypy src
uv run pytest -q
# Only with a separately confirmed disposable, already migrated test database:
TEST_DATABASE_URL='postgresql+asyncpg://.../ted_test' ALLOW_DESTRUCTIVE_TESTS=1 uv run pytest -q
cd ../frontend
npm run typecheck
npm run build
npm run format:check
```

Browser tests also modify data and run migrations/seeding. They require a **separate disposable database named exactly `ted_e2e_test`**, validated before setup/migrations, and start their own native backend/Vite processes on ports 8000/5173:

```sh
cd frontend
npx playwright install chromium
E2E_DATABASE_URL='postgresql+asyncpg://.../ted_e2e_test' ALLOW_DESTRUCTIVE_TESTS=1 npm run test:e2e
```

## Optional Docker Compose deployment

Native development does not use Compose. For Compose, fill the three separate generated database passwords in `.env`, configure the correct `APP_ENV`, exact browser origin and cookie security, then run:

```sh
docker compose up --build -d
docker compose exec app python -m ted.cli admin@example.com
```

The Compose database is local to that deployment, with separate migration/runtime roles; its database service does not use native `DATABASE_URL`. App containers run without root, with dropped capabilities and read-only filesystems. Compose migrations are an explicit deployment workflow, not part of native startup. See [operations and backup/restore](docs/OPERATIONS.md) and [original acceptance evidence](docs/ACCEPTANCE.md).
