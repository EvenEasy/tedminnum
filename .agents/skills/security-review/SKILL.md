---
name: security-review
description: Review backend or frontend changes that affect authentication, authorization, user data isolation, APIs, webhooks, secrets, or deployment hardening.
---
# Security review
Review changed paths and their callers, storage and transport boundaries. Prioritize actual attack paths and trust boundaries, particularly:
- Server-side role plus object-level authorization for every request and export, with negative IDOR tests.
- Auth session/token lifecycle, password hashing, CSRF/CORS and browser cookie flags as applicable.
- Input validation, injection, XSS, unsafe file handling and error data leakage.
- Secure defaults and separation of development credentials from deploy configuration.
- Webhook HMAC signatures, timestamps, secret rotation, retry/duplicate handling, and outbound destination risks.
- Logs/audit trail that exclude secrets and personally sensitive payloads.
- Access to timers, money and invoices through alternate endpoints and report queries.
Produce concise, actionable findings with severity and evidence. Where asked to implement fixes, add regression tests and verify them. Do not assume VPN-only hosting makes application vulnerabilities acceptable.
