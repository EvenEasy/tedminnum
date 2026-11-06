Build the self-hosted productivity, project, time-tracking and billing platform described in `docs/PRODUCT_SPEC.md`.

Read `AGENTS.md` and the product specification first. Work as an autonomous software engineer with full-stack responsibility. Make sensible, documented decisions; prioritize simple, secure, maintainable solutions for a resource-constrained local server.

Implement an actual working application, not a UI mockup or architecture proposal. Start with the smallest usable vertical slice (authentication + scoped client/project/task management + persistent timer + invoice creation/payment status + real dashboard), then extend it toward the complete specification. For each slice, include schema/migrations, backend/API, frontend, and appropriate tests.

Before coding, briefly outline the modules, key data invariants, implementation order and major tradeoffs. Then proceed with implementation in the same task; do not stop after planning. Use the repository's existing conventions if it is not empty. If a requirement is underspecified, choose a conservative default, document the assumption and continue; ask only where incorrect assumptions could cause unsafe or irreversible financial/security behavior.

Use the billing-integrity-review and security-review skills for relevant final reviews. Execute checks and demonstrate the acceptance scenarios you can verify. Fix failures introduced by your work. Never present placeholders, mock data or unverified behavior as complete.

At the end, briefly report what actually works, how to run it, commands/tests actually executed, what remains incomplete, and any security limitations.
