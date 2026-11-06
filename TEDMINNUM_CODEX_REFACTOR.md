# Codex task: Tedminnum stabilization and architecture refactor

Repository: `EvenEasy/tedminnum`, existing `main` workspace. Work in the CURRENT codebase; this is a refactor and bug-fix task, NOT a greenfield rewrite.

Read root `AGENTS.md`, `docs/DECISIONS.md`, `docs/PRODUCT_SPEC.md`, `docs/ACCEPTANCE.md`, and the relevant code/tests. Use `.agents/skills/python-backend-architecture/SKILL.md` with its `references/` for backend architecture. Apply the existing security and billing review skills when touching those areas.

## Goals, in priority order

### 1. Fix local login and make Docker-free development reliable

Current code checks every non-safe request's `Origin` against a single `APP_ORIGIN` in `backend/src/ted/presentation/api.py`. The default is `http://localhost:8000`, while Vite normally serves `http://localhost:5173` and proxies `/api` to `127.0.0.1:8000`. This can cause HTTP 403 `{"detail":"Origin rejected"}` before credential validation.

- Reproduce/verify the exact request flow (including the browser's `Origin`, Vite proxy, settings load, cookie and CSRF behavior), then fix its configuration and any implementation defect.
- Preserve a restrictive origin policy, CSRF protection, HttpOnly sessions, and safe cookie defaults. Never solve the issue by disabling origin checks, allowing every origin, using wildcard CORS, or broadly disabling CSRF.
- Support explicitly configured local development origins (including the intentional `localhost`/`127.0.0.1` distinction), with clear validation and sensible documented defaults. Production must remain strict.
- Add regression tests for accepted same-origin Vite login, rejected unknown origins, invalid credentials, valid credentials, login -> `/auth/me`, logout, CSRF failures, and cookie flags under HTTP-development versus HTTPS-production settings. Include a real-browser flow when feasible, not only HTTP tests without an Origin header.
- Enable direct native execution of the backend (Python/uv) and frontend (Node/Vite), connecting through `DATABASE_URL` to an already running PostgreSQL database, including a remote development database on a homelab. Do not require local Docker, a local PostgreSQL container, or a Docker Compose stack. Existing Compose deployment should keep working.
- Make `.env.example`, settings resolution, and a concise README runbook consistent. Clearly document `cd backend`, `uv sync --frozen`, explicit `uv run alembic upgrade head` on a **dedicated development database**, interactive administrator bootstrap, `uv run uvicorn ...`, then `cd frontend`, `npm ci`, `npm run dev`. Use an explicit configuration for the actual browser origin and HTTP-only local cookie setting; never ship real secrets or demo passwords.

### 2. Refactor the backend into a pragmatic modular monolith

Known hotspots: `application/ports.py` has an all-purpose `Store` protocol; `infrastructure/database.py` has a broad `SqlStore`, ORM mapping, engine and session initialization; `application/services.py` has multi-domain `Work` and `Billing`; `presentation/api.py` has most HTTP routes, serialization, auth and DB wiring in one module. The current infrastructure imperatively maps domain dataclasses to SQLAlchemy models.

- Identify meaningful bounded feature areas such as identity/access, clients/projects/tasks, time/focus tracking, billing/payments/reporting, and webhooks/audit. Use per-feature modules and inward dependencies, keeping the structure proportionate to a small self-hosted app. Do not just split files arbitrarily.
- Replace the universal `Store` with small consumer-owned repository/query ports (Protocol when useful), distinct SQLAlchemy repository implementations, and explicit transaction ownership. Repositories should not commit; a single top-level operation owns the success/rollback boundary. When migrating the existing request-scoped `session.begin()` design, preserve atomicity and observable API behavior at every step: no mixed or nested competing transaction owners.
- Separate persistence entities/mapping from pure domain objects where genuinely required to achieve framework independence; avoid ORM-controlled business entities leaking across boundaries. Keep PostgreSQL-specific constraints, triggers and SQL isolated in persistence/migrations. Preserve them rather than weakening guarantees for hypothetical portability.
- Move business operations into small named use cases/application services with constructor-injected dependencies; move HTTP routing, request validation, response mapping and identity extraction to presentation. No direct `store.db`/`AsyncSession` access inside business HTTP handlers. Use a composition root/DI only as complex as the resulting graph requires.
- Enforce server-side role AND object authorization, idempotency and transactional monetary invariants. Preserve existing persisted schema/data, API paths/shapes, financial snapshots, concurrency locks, audit history, webhook outbox semantics, and migration continuity unless a justified and tested change is necessary.
- Avoid generic CRUD superclasses, god services, blanket base repositories, CQRS/event buses, extra databases, Redis, Celery, microservices, or empty layers introduced for appearances.

### 3. Refactor the React/TypeScript frontend by feature and responsibility

`frontend/src/main.tsx` is approximately 1,692 lines and combines all pages, UI, requests, auth, timers, invoices, settings and event handling. `style.css` is approximately 1,318 lines. Existing `EditorDialog`, `work-forms`, `api.ts` and shared components are only partial separation.

- Make `main.tsx` a tiny bootstrapping entry point. Organize features (auth, dashboard, tasks/projects/clients, timer/time, billing/reports, settings) into cohesive pages, components, hooks and data/API modules, with a small shared API client and design-system primitives.
- Preserve current responsive light/dark UI and existing workflows. Improve clarity and maintainability rather than redesigning unnecessarily.
- Keep authentication/CSRF and account switching safe; avoid stale data from another user on logout/login. Centralize reusable remote loading/error/mutation behavior appropriately without adding a heavyweight state-management library without a demonstrated need.
- Separate timer business state/clock synchronization from rendering; keep server authoritative. Do not introduce duplicate mutations or optimistic billing behavior that breaks idempotency.
- Split CSS by meaningful feature/layout responsibility if helpful; maintain responsive/mobile styles and accessible labels.

### 4. Validate and document the result

- Preserve and expand focused domain, application, SQLAlchemy/PostgreSQL, authorization, Origin/CSRF/cookie, concurrency, billing/payment, API and Playwright tests. Ensure tests cover actual new boundaries, not only mocked route success.
- Maintain the existing schema/financial invariants: no overlapping active sessions, no duplicate invoice source, exact Decimal calculations, stable invoice snapshots, payment idempotency, no cross-user data leakage.
- Make non-destructive checks (`ruff`, `mypy`, `pytest` only with a dedicated disposable `_test` database, frontend `typecheck`, build, format checks, Playwright when safely available). Tests in this repository TRUNCATE data. NEVER use the homelab/operator database for test runs or implicit migrations; never run destructive scripts against real data. If a safe test DB is unavailable, report unexecuted checks rather than inventing a pass.
- Keep Alembic history intact. Inspect PostgreSQL extension privileges (`btree_gist`) and migration prerequisites before assuming the remote DB can be migrated.
- Update `docs/DECISIONS.md`, README and relevant operations docs to reflect the implemented architecture and exact local start steps. Do not claim Docker/E2E integration has been verified unless actually executed.

## Execution discipline

First map the current dependencies and write a short refactor sequence, then IMPLEMENT it incrementally, prioritizing working local authentication and a complete vertical slice. Avoid changing unrelated functionality. Run targeted checks after each meaningful change. If full migration cannot safely be completed in one session, leave the tree in a working, testable state, report precisely what is complete and what remains, and do not claim that architectural refactoring is finished.

Final reply: concise summary of root cause and solution, new module structure and dependency rules, files/API behavior changed, exact tests executed/results, unverified items and next remaining steps. Do not include secrets or dump full files.
