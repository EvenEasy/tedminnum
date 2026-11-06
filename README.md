# Tedminnum

A self-hosted project, focus-time and billing application. FastAPI + async SQLAlchemy + PostgreSQL, React + TypeScript + Vite. One workspace, a few users, no Redis or external payment service.

## Run with Docker Compose

1. Copy `.env.example` to `.env`. Generate **three different** passwords with `openssl rand -hex 32` and fill `POSTGRES_PASSWORD`, `APP_DB_PASSWORD`, and `MIGRATION_DB_PASSWORD`. Hex passwords avoid URL-escaping mistakes. Keep `.env` private (`chmod 600 .env`).
2. Set `APP_ORIGIN` to the exact browser origin. For local HTTP at `http://localhost:8000`, explicitly set `SECURE_COOKIES=false`. For HTTPS, leave it `true`. Bind to loopback by default; put your own TLS reverse proxy in front for other devices.
3. Run:

   ```sh
   docker compose up --build -d
   docker compose exec app python -m ted.cli admin@example.com --name "Administrator"
   ```

   The CLI prompts for the first administrator's password (at least 12 characters). It refuses to run after users exist. There are no shipped application credentials or automatic demo data.
4. Open `http://localhost:8000`. Create members under Settings, then a client, project with memberships, and tasks with assignees. Members sign in with their administrator-created credentials and can change their own passwords.

Compose uses separate database owner/migration and runtime roles. PostgreSQL is not published on a host port. Application containers run as a non-root user, with a read-only filesystem and dropped capabilities. The worker is the same monolith image running a small database-backed delivery loop; it does not require a message broker. Initial database role creation runs only on a fresh volume. Changing environment passwords on an existing volume does not rotate database roles: use PostgreSQL `ALTER ROLE` through a secure operator session and update `.env` together.

API documentation: `/api/docs`; OpenAPI: `/api/openapi.json`; health: `/api/health`. Browser and API use the same origin. API callers first log in, retain the HttpOnly session cookie, and send the returned `csrf` value in `X-CSRF-Token` for mutations. Monetary inputs and responses use decimal strings. Collections accept `limit` (1–200) and `offset`.

## Local development

Use Python 3.12+, uv, Node 22+ and a disposable or development PostgreSQL database with permission to install the trusted `btree_gist` extension. Configure backend environment variables in the shell or `backend/.env`:

```sh
export DATABASE_URL='postgresql+asyncpg://user:password@127.0.0.1:5432/ted_dev'
export APP_ORIGIN='http://localhost:5173'
export SECURE_COOKIES=false
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run python -m ted.cli admin@example.com
uv run uvicorn ted.presentation.api:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to FastAPI. To use the same-origin production build and local documentation assets instead, run `npm run build` in `frontend`, restart FastAPI, and set `APP_ORIGIN=http://localhost:8000`. Run `python -m ted.infrastructure.webhooks` in the backend environment for webhook delivery. Development via Vite does not serve the built documentation assets; use the production build to view `/api/docs`.

## Verification

Backend tests **truncate the configured test database** and refuse names that do not end in `_test`. Create it and migrate it first. For example, with a local PostgreSQL instance:

```sh
cd backend
export DATABASE_URL='postgresql+asyncpg://user:password@127.0.0.1:5432/ted_test'
uv run alembic upgrade head
uv run pytest -q
uv run ruff check src tests migrations
uv run ruff format --check src tests migrations
uv run mypy src
cd ../frontend
npm run typecheck
npm run build
npm run format:check
```

Browser tests require a **separate**, empty database named `ted_e2e_test`; setup migrates and explicitly seeds test-only credentials. They start and stop their own server on port 8000, which must be free:

```sh
cd frontend
export E2E_DATABASE_URL='postgresql+asyncpg://user:password@127.0.0.1:5432/ted_e2e_test'
npx playwright install chromium
npm run build
npm run test:e2e
```

See [implementation decisions](docs/DECISIONS.md), [acceptance evidence and limitations](docs/ACCEPTANCE.md), and [backup/restore and webhook operations](docs/OPERATIONS.md).
