# Acceptance evidence and remaining work

This records the original implementation run. See [the refactor verification](REFACTOR.md) for the current architecture, safer test entrypoints and newer test results.

Verification performed on 2026-11-06 with local PostgreSQL 18.6, Python 3.14.3, Node 26.13 and Playwright Chromium. Deployment targets Python 3.12, Node 22 and PostgreSQL 17; the CI workflow declares that combination but has not run on GitHub here. Docker is unavailable in this workspace, so an image build/Compose startup is not claimed.

## Executed checks

- `backend/.venv/bin/pytest -q --tb=short`: **20 passed**. Real PostgreSQL; no SQLite substitution. Each test uses a disposable database. Concurrency tests issue simultaneous HTTP requests with separate database transactions.
- Alembic `downgrade base` followed by `upgrade head`: completed on the disposable PostgreSQL test database; then all 20 tests passed. Browser setup separately migrated its own database.
- `backend/.venv/bin/ruff check src tests migrations`: passed.
- `backend/.venv/bin/ruff format --check src tests migrations`: passed (28 files).
- `backend/.venv/bin/mypy src`: passed (18 source files, strict settings).
- `npm run typecheck`, `npm run build`, `npm run format:check`: passed. Production assets built and actually served in browser tests.
- `PLAYWRIGHT_BROWSERS_PATH=/tmp/ted-browsers npm run test:e2e`: **2 passed** (desktop workflow and mobile/reminder workflow). No mocked application API or mocked billing data.
- Shell syntax check on `scripts/init-db.sh`; Prettier parsed/checked Compose and CI YAML. A Python YAML parsing attempt was unavailable because PyYAML is not installed; Docker Compose's own configuration validator was unavailable with Docker.
- Separate PostgreSQL runtime-role smoke: executed the actual `scripts/init-db.sh` against an isolated database using generated ephemeral credentials, applied migrations as `ted_owner`, then created/issued/paid a fixed invoice as `ted_app` through the API. Receipts were correct and an attempted audit UPDATE was denied. The temporary driver lived in `/tmp/ted-role-smoke.py` and is not application source or a production bootstrap command.

## Product scenarios

| Scenario | Executed evidence |
| --- | --- |
| 1. Admin creates member/client/project/assignment/hourly task; member tracks time; admin drafts, exports, issues and pays; dashboard separates totals | Full desktop Playwright flow creates all these records through UI, refreshes/pauses/resumes/stops the member's timer, adjusts a past hour, downloads PDF, issues and records payment. API tests additionally check partial payments, actual PDF bytes, audit actions and member dashboard finance exclusion. |
| 2. Fixed-price task logs time and charges once without hourly doubling | Desktop browser flow creates an assigned fixed task, logs member time, marks it done and issues a one-line fixed invoice. API test rejects using its time as hourly sources and rejects a second invoice for the same fixed task. |
| 3. Members cannot guess unrelated IDs or mutate privileges | Negative API tests cover clients/projects/tasks/time detail and lists, timer start, another user's time edit, task rates, invoices/PDF, reports, users, audit and webhooks. Member monetary fields are removed. Browser test switches from admin to member in the same tab and checks that finance controls/data disappear. |
| 4. Timer survives refresh/device changes/concurrent commands | Browser refresh preserves active timer. API test uses a second client with the same session. Simultaneous equal-key starts collapse to one entry; distinct-key starts have one winner; repeated stops remain safe. Database exclusion constraint independently rejects overlapping sessions. |
| 5. Issued totals survive rate/task changes; retries do not double-charge | API tests change task names/rates after issue, verify saved line rates/totals, test concurrent invoice/payment retries, distinct concurrent payments with one remaining balance, and a race between time editing and draft reservation. Database triggers independently reject modifying issued totals and reserved time. Void/rebill retains old snapshots. |
| 6. Active-app reminders and non-billable breaks | Mobile Chromium test saves a one-minute work preference, advances the browser clock and sees the actual in-app reminder. API tests verify configured long/short break targets, non-billable breaks and overlap rejection. OS notification delivery and closed-browser behavior were not tested or claimed. |

## Reviews

The repository's billing-integrity-review and security-review skills were applied to domain calculations, transaction/locking paths, schema constraints/triggers, presentation routes, browser state and tests. Findings fixed during implementation:

- Fractional pauses previously rounded independently: exact microseconds now aggregate before final work-second rounding (`domain/models.py`, `application/services.py`).
- Concurrent billing/time mutations: workspace/user locks, reserved source uniqueness, overlap exclusion, immutable snapshots, append-only payments, database lifecycle and payment guards (`infrastructure/database.py`, migrations, services).
- Stale browser state across account switches: clear account data, reject outdated load results and explicitly gate finance rendering (`frontend/src/main.tsx`); covered by browser regression.
- Password whitespace and unknown-account timing: preserve password whitespace; use a precomputed dummy Argon2 hash for unknown accounts (`presentation/schemas.py`, `application/identity.py`, `infrastructure/passwords.py`).
- Member financial metadata exposure: strip rate/fixed price fields and invoice sequence metadata (`presentation/api.py`); covered by API tests.
- Webhook destination and response risks: operator allowlist, public-address validation, DNS pinning/TLS hostname preservation, bounded DNS/network timeouts, no redirects/proxies, streamed response status (`infrastructure/webhooks.py`). Mock transport tests verify the destination/signature and database tests verify outbox retries and locked claims.
- Shared form labels and navigation accessible names: explicit label associations and accessible navigation names (`frontend/src/components.tsx`, `main.tsx`); verified through role/label-based browser interactions.

No known unresolved critical defect was found in the exercised core workflows. This is not an independent penetration test, accounting certification, or deployment verification.

## Remaining work and limits

- Docker/Compose image build, startup, target-server memory use, reverse-proxy TLS configuration and backup restore rehearsal remain unverified. The database initialization script and restricted role were tested separately.
- External webhook delivery was tested through mock HTTP transport, not a real receiver/TLS server. The actual pinned-IP SNI path relies on HTTPX's transport extension and needs an operator integration test. Deliveries are at least once; receivers must enforce timestamp freshness and deduplicate IDs. Exhausted deliveries have logs but no alerting/manual replay UI.
- Full OS/browser notification compatibility is unverified. There is no guaranteed closed-browser notification, automatic four-cycle scheduler or background mobile push. Break transitions are manual. Time summaries attribute whole sessions to their start date; they do not split across midnight.
- No MFA, invitation/recovery email, public signup, permanent integration tokens, automatic retention cleanup or password-recovery endpoint. HTTPS/Secure cookie configuration is operator-owned. Webhook secrets are protected by database permissions rather than encrypted with a separate key.
- No destructive object deletion/archive workflow, payment reversal/refund, taxes, FX, full ledger, custom PDF branding, international font coverage, CSV export or detailed date/client financial report builder. The delivered report is an all-time workspace summary with distinct estimates, draft reservations, liabilities and receipts.
- Collection responses are paginated and scoped, but some application queries aggregate small-workspace data in memory. Large installations need database-side aggregate/report pagination work and load tests. Initial scope is a few users on a local server.
