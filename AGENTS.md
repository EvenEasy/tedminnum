# Repository instructions for Codex

## Engineering principles
- Build a production-quality, self-hosted modular monolith, not a distributed system.
- Apply Clean Architecture pragmatically: domain has no dependencies on FastAPI, SQLAlchemy, HTTP, or UI; application defines workflows and ports; infrastructure implements adapters; presentation handles transport.
- Dependencies point inward. Enforce clear module ownership and avoid circular module dependencies. Prefer explicit interfaces only at real boundaries; avoid generic repositories, premature abstractions, and unnecessary layers.
- Prefer small, cohesive modules, readable typed Python, consistent errors, and explicit transaction boundaries. Follow SOLID where it meaningfully improves maintainability.
- Preserve existing behavior unless the task requires a change. Prefer focused edits over large rewrites.

## Stack and operations
- Backend: Python 3.12+, FastAPI, Pydantic 2, SQLAlchemy 2 async, Alembic, uv, pytest, Ruff.
- Persistence: PostgreSQL by default. Keep database-specific SQL/types confined to infrastructure; avoid unnecessary database vendor coupling. Test database-sensitive/concurrent behavior against PostgreSQL, not just SQLite.
- Frontend: React, TypeScript, Vite, responsive UI, accessible components. Choose a restrained UI stack; avoid gratuitous dependencies.
- Deploy using a simple Docker Compose setup; optimize for a low-power local server and a few concurrent users. Do not introduce Kubernetes, microservices, Celery, or Redis without a demonstrated requirement.
- Store timestamps in timezone-aware UTC; convert at presentation boundaries. Store money using Decimal / exact database numeric types, never binary floating point.

## Security and correctness
- Treat the application as security-sensitive regardless of its VPN-only deployment.
- Authenticate every protected API; authorize each action and object server-side (role AND ownership/assignment). Do not trust frontend filtering or client-provided prices, ownership, roles, or durations.
- Use robust password hashing, safe session or token handling, restrictive CORS, appropriate CSRF protections, validation, parameterized queries, secrets outside source control, and least-privilege configuration.
- Sign outgoing webhook payloads with HMAC, timestamps, and replay-resistant verification guidance. Keep secrets masked in logs.
- Ensure billing calculations are deterministic and traceable. Never double-invoice work; persist price/rate snapshots at invoice creation; prevent subsequent task/rate edits from silently changing invoices. Support idempotent payment marking and audit sensitive state changes.
- Handle concurrency in timers and invoicing; enforce critical invariants in database constraints/transactions as well as application code.

## Delivery discipline
- Implement working vertical slices: schema, application behavior, API, UI, tests, and migration together.
- Do not present mock values, static demos, TODOs, or unimplemented buttons as finished functionality.
- Run focused tests, lint, and type checks when available; fix issues introduced by changes. Clearly identify anything unverified.
- Keep explanations concise. State files/features changed, tests actually executed, and known limitations; do not dump entire files in the final response.
- Read docs/PRODUCT_SPEC.md for product-level decisions or when planning a feature; don't reread unrelated documents for small edits.
