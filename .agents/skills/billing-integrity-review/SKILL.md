---
name: billing-integrity-review
description: Audit implementations and changes involving billable time, fixed-price tasks, invoices, payments, rates, or finance reports for monetary correctness and accounting invariants.
---
# Billing integrity review
When relevant, inspect the affected domain logic, database schema/constraints, application workflows, APIs, and tests. Trace a normal user journey end-to-end. Verify:
- Exact Decimal money calculations, currency consistency, rounding at defined boundaries, and rate precedence.
- Fixed-price and hourly task logic cannot unintentionally charge both.
- A billable item can appear on at most one active issued invoice, with cancellation/void semantics documented.
- Issued invoice lines have immutable historical price snapshots, unaffected by subsequent task/rate edits.
- Payments are idempotent and enforce valid state/amount transitions including partial payments.
- Report aggregates avoid double counting between earned, invoiced, outstanding, and paid.
- Permission checks and audit records cover monetary mutations.
- Race-condition and retry tests cover invoice creation, payment marking, and time-entry editing.
Report concrete defects with file paths, severity, and reproduction cases. Fix defects requested by the task and rerun relevant tests. Do not claim verified behavior without executing checks.
