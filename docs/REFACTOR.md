# Architecture refactor and local development verification

Implemented and verified on 2026-11-06. This is an incremental refactor of the existing application; domain calculations, public HTTP paths, persisted schema and migration revisions are preserved.

## Login diagnosis and fix

Read-only inspection of the existing root `.env` found `APP_ORIGIN=http://localhost:8000`, no `APP_ENV`/`DEV_ORIGINS`, and `SECURE_COOKIES=true`. Database credentials were omitted from inspection output; the file was not edited. Vite runs on port 5173 and preserves Origin when proxying `/api`. The existing middleware compared that browser origin with one different configured origin and returned `Origin rejected` before credential or CSRF evaluation.

Settings now validate exact canonical origins and a comma-separated `DEV_ORIGINS` allowlist. Development origins and non-Secure cookies require explicit `APP_ENV=development`. Production retains Secure/HttpOnly/SameSite=Strict cookies, exact-origin validation, CSRF and no permissive CORS. `.env` resolution is independent of working directory; environment variables override optional backend `.env` and root `.env`. Invalid configuration fails early without displaying database URL values.

`uv run python -m ted.dev --reload` explicitly supplies process-local development settings, binds only to `127.0.0.1:8000`, and retains the existing `DATABASE_URL`. It never rewrites `.env`, starts PostgreSQL, migrates, or seeds. Normal production invocation remains Uvicorn with validated production configuration. Repeated `--frontend-origin` arguments provide an explicit custom development allowlist. Vite now uses a strict port to avoid silent origin changes.

Browser evidence uses the actual native launcher and Vite proxy: Playwright's full header accessor observed `Origin: http://127.0.0.1:5173`; correct login worked, wrong credentials returned 401, cookies were HttpOnly/SameSite=Strict/non-Secure for local HTTP, reload restored the session, rejected Origin and invalid CSRF returned 403, and logout invalidated the session. HTTPS production cookie flags were verified with an in-process HTTPS test client, not a deployed TLS endpoint.

## Boundaries and transaction ownership

- `application/ports/{identity,work,tracking,billing,integrations,workspace,audit}.py`: focused consumer-owned query and repository protocols. No universal Store remains. Cross-capability read dependencies use query contracts.
- `application/access.py`, `activity.py`: shared authorization, audit and transactional-outbox collaborators. No business-service inheritance.
- `application/identity.py`: authentication/logout, user management, password changes and preference updates. Billing contains separate CreateInvoice, RecordPayment, InvoiceLifecycle and FinanceReport operations. Work management, tracking, workspace settings and integrations each own their workflows.
- `infrastructure/persistence/records.py` and `schema.py`: ORM records and the original schema. Domain entities are no longer instrumented by SQLAlchemy. Concrete capability repositories map records to/from plain domain dataclasses and only flush. Small internal mapping helpers do not expose a generic repository framework.
- `presentation/dependencies.py`: explicit manual constructor wiring. The existing outer `async with session.begin()` remains the single request transaction owner and ends before a successful response is sent. Repositories and nested operations never commit. Every request/job receives its own session. API, worker and CLI dispose the shared engine at process shutdown.
- `presentation/routers`: feature-specific transport adapters, with serialization separate from application assembly. No business handler accesses `store.db` or a concrete persistence repository. Health checking alone uses the database operationally.
- Alembic imports schema metadata and database-only configuration; migration tooling does not require development-origin/cookie settings. All existing migration revisions and domain files remain unchanged. `alembic check` reports no new upgrade operations.

## Frontend ownership

`main.tsx` only mounts App and styles. `app` owns composition, editor coordination and account-scoped data loading. Feature folders contain auth, dashboard, clients, projects, tasks, time/tracking, billing, reports and settings pages/components/API operations/hooks. Shared code contains UI primitives, formatting, types, theme and the typed API error/session client. No state-management dependency was added; the existing CSS and layouts are preserved.

Authentication is centralized in AuthProvider. Account/session changes clear credentials and remount all private state. Request generations, loading generations and operation lifetimes reject delayed results, including errors, from old sessions. Profile updates also check the current session generation and subject. Authenticated responses add the backward-compatible `X-Ted-User-ID` header; the client checks it before reading results so another tab changing the shared cookie cannot inject a different user's data. Browser tests cover a held old invoice response and cross-tab cookie replacement.

The tracking hook owns persisted timer reads, polling, clock offsets, pause subtraction and reminders; rendering is separate. Commands retain stable retry keys. Server timestamps remain authoritative. Task filters/status operations, invoice selection/detail, settings/audit/integration loading and theme have their own hooks/providers.

## Security and billing review findings fixed

The repository security-review and billing-integrity-review skills were applied to the new boundaries and existing callers.

- Detached mapping no longer updates an old task copy after reordering; the response returns the actual reordered domain object.
- Preferences/password changes reload and lock the current user before saving, preventing stale actor records from overwriting newer role/password fields. A regression verifies that newer access data survives a preference update.
- Webhook updates reload under a row lock so a concurrent toggle cannot restore an older rotated secret. PostgreSQL NO KEY UPDATE locking serializes updates while allowing outbox foreign-key KEY SHARE locks; a forced-interleaving test covers the timer-stop/audit/webhook deadlock path.
- Client session generations prevent stale mutation continuations from changing global auth state after an account switch; stale errors cannot sign out the newer account. The authenticated-subject header also protects shared-cookie changes across tabs.
- Test entrypoints no longer fall back to the operator's DATABASE_URL. PostgreSQL tests require explicit TEST_DATABASE_URL plus ALLOW_DESTRUCTIVE_TESTS=1. Browser setup validates its separate exact database name and opt-in before migrations or seeding. Native startup has neither action.

Existing Decimal rounding/rate precedence, fixed-price exclusion, immutable issued totals, source reservations, void/rebill history, payment idempotency, audit behavior, overlap constraints and timer/invoice/payment locks were exercised against PostgreSQL. Public path/method compatibility is checked against a snapshot extracted from the previously committed API.

## Executed evidence

- Full backend run: **46 passed**, using explicit `TEST_DATABASE_URL` and opt-in against the disposable `ted_test` database on the isolated cluster created in the earlier implementation session. No homelab/application database was used.
- Default backend run with TEST_DATABASE_URL and ALLOW_DESTRUCTIVE_TESTS removed: **26 passed, 20 skipped**; no database connection or truncation required.
- `alembic check` on the disposable database: **No new upgrade operations detected**. No migrations were applied to operator data.
- Ruff check and formatting check, strict mypy, TypeScript typecheck, production frontend build and Prettier checks passed.
- Playwright through the actual `python -m ted.dev` launcher and Vite: **3 passed**. This includes direct auth/Origin/cookie/CSRF/logout regression, the existing hourly/fixed-price billing workflow with stale/cross-tab account-switch checks, and mobile/theme/reminder behavior.
- Tests run here used Python 3.14.3, PostgreSQL 18.6 and Chromium. The configured Python 3.12/PostgreSQL 17 CI workflow was updated but not run on GitHub here.

## Limits and untouched work

The actual homelab database, remote migration privileges, Docker image/Compose startup, production TLS/reverse proxy, backup restoration and real external webhook delivery were not tested. None was needed for native development. The original product limitations (manual break transitions, aggregate financial reports, no MFA/refunds/closed-browser push) remain unchanged. Some small-workspace queries still hydrate/filter collections in memory; no scalability or load-test claim is made. The API still uses an explicitly documented outer request transaction; this task deliberately did not introduce a new transaction framework or distributed infrastructure.
