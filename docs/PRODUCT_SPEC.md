# Product specification: Local productivity and billing platform

## Goal and constraints
Build a polished, lightweight self-hosted web app combining the core workflows of Super Productivity (focus/break timer), Kimai (billable time, clients and invoices), and Vikunja (task and project management). References are conceptual, not instructions to copy code, licenses, or UIs. Multi-user, admin-managed, only a few concurrent sessions on a modest local server. Responsive desktop/mobile layout, dark theme as default with light-mode toggle. Local/VPN deployment is infrastructure context; application security must stand on its own.

## Users and permissions
- Admin: manage users, memberships/assignments, clients, projects, tasks, rates, invoices, and workspace settings; inspect authorized organization-wide data and audit history.
- Member: access only assigned projects/tasks and their own time entries and relevant details. Cannot grant own permissions, modify another user's time, view unrelated projects, or access administrator financial totals.
- All protected object accesses, filtering, reports, exports, and API/webhook management must enforce permissions server-side.

## Features

### Projects and tasks
- Manage clients -> projects -> tasks, with project membership and task assignees.
- Tasks have title, description, status (e.g. backlog/in progress/done), priority, due date, assignee(s), and optional estimates.
- Provide list and Kanban views with working status transitions and mobile-friendly interactions; allow manual sort/move.

### Time and focus sessions
- Start/pause/resume/stop work sessions for an optional task. Only one active work timer per user; correct persistence across refresh, reconnect, and browser/device changes.
- Work/break cycles have configurable work duration, short/long break duration, and notification preferences. Track work versus breaks distinctly; breaks are never automatically billable.
- Show a reliable live timer and historical sessions. Persist authoritative start/end UTC timestamps server-side; ensure duplicate stop/start requests are safe. Background notifications must be implemented honestly: browser notifications while the app is active are sufficient for an initial release, but do not claim reliable closed-browser mobile push unless actually delivered and tested.
- Time entries can be edited with appropriate permissions and audit trails. Provide daily/weekly/monthly views and filters.

### Billing
- Clients, projects and tasks may have hourly rates; task-level and project-level overrides use a documented precedence, and the client-level rate can be a fallback.
- Support fixed-price tasks AND hourly tasks. Logging time on a fixed-price task must not automatically add hourly charges unless explicitly configured.
- Every billable work entry has clear ownership, billable/non-billable status and invoiced/uninvoiced state. Prevent overlap, duplicates and double-invoicing where applicable.
- Create invoice drafts from explicitly selected uninvoiced billable time entries and/or finished fixed-price tasks; show breakdown and editable non-destructive descriptions. Avoid double billing through unique links/transactional checks.
- Invoice lifecycle: draft -> issued -> partially paid/paid, plus void/cancel with appropriate rules. PDF export/download for manual delivery; no external payment gateway or email-provider integration is required initially.
- Invoice line amounts, rates, currency and computed totals must be snapshotted at issuance; later changes to tasks, rates or time entries must not silently alter issued invoices.
- Record payments manually, including date, amount, currency and optional reference; idempotently prevent accidental duplication. Reject invalid payment totals and cross-currency arithmetic. No FX conversion required.
- Reports distinguish worked value (estimated earned), uninvoiced billable value, invoiced outstanding, and payments received. Avoid misleading double-counting; explain which numbers are estimates versus fixed invoice liabilities.

### APIs and integrations
- Versioned, documented REST API (OpenAPI), with auth/permissions, pagination, filtering, and stable IDs.
- Outgoing webhooks for key domain events (e.g. task updated, timer stopped, invoice issued/paid); per-endpoint secret, signed timestamped payloads, delivery logs, retries with bounded backoff, and replay handling guidance.
- Keep integration interfaces extensible without building unnecessary event infrastructure. Incoming integration APIs may be added as individually justified endpoints.

### UI/UX
- Dashboard: personal focus/time today, active timer, assigned tasks, recent work, and role-appropriate finance KPIs.
- Navigation: Dashboard, Tasks, Projects, Time, Clients, Invoices, Reports, Settings (role-filtered).
- Responsive layouts for desktop/mobile. Dark by default; accessible light toggle. Loading, empty, error, success, confirmation states. Keyboard and touch usability.
- Use real API data; no fake KPI numbers or decorative controls that do not function.

## Cross-cutting requirements
- PostgreSQL primary store via SQLAlchemy ORM and Alembic; avoid coupling domain/application layers to PostgreSQL-specific features.
- Proper unique constraints, foreign keys, indexes, transaction and optimistic/concurrency rules for timers, invoices, and payments.
- Audit high-risk actions (role changes, timer adjustments, invoice issuance/void/payment).
- Seed only explicit demo accounts/data for development; never ship default credentials enabled in production.
- Docker Compose, .env.example without real secrets, database migrations, local onboarding steps and backup/restore instructions.
- Tests: domain logic, authorization/IDOR, timer concurrency, invoice calculations and double billing, payments/idempotency, critical API paths, and at least one browser-level end-to-end flow.

## Explicitly out of scope for first release
Public internet hosting setup, VPN setup, Kubernetes, microservices, mobile native apps, external payment processing, real bank synchronization, FX conversion, full accounting/ledger compliance, advanced employee payroll, guaranteed mobile push while the browser is closed.

## Acceptance scenarios (must work end to end)
1. Admin creates member, client, project, assignment, hourly task. Member sees only assigned content, records time, and admin creates, exports, issues and marks invoice paid. Dashboard separates billable value, outstanding and paid.
2. Admin creates fixed-price task, member tracks time, and invoice charges fixed amount exactly once without doubling hourly time.
3. Member cannot access unrelated client/project/task/time/invoice data by guessing IDs or manipulating API requests.
4. Refreshing the browser or reconnecting another device does not duplicate or lose an active time entry. Concurrent commands do not create multiple active timers.
5. Changing a task or rate after invoice issuance does not change previously issued totals. Duplicate invoice/payment requests cannot create duplicate charges.
6. Work/break reminders are visible as configured when the web app is active, and breaks don't count as billable time.
