# Operations

## Back up and restore

Back up the database and keep an encrypted copy of `.env` separately. Dumps contain password hashes and webhook secrets. Use restrictive permissions, encrypt backups, and move a copy off the server. With Compose running:

```sh
umask 077
docker compose exec -T db pg_dump -U postgres -d ted -Fc > ted-backup.dump
```

Before restore, stop mutations and delivery:

```sh
docker compose stop app worker
```

Restore first into a separate installation/database and verify before replacing the active data. To replace the database **on a new or deliberately disposable initialized Compose volume**, create roles with the Compose initialization script, then:

```sh
cat ted-backup.dump | docker compose exec -T db pg_restore -U postgres -d ted --clean --if-exists --exit-on-error
docker compose run --rm migrate
docker compose up -d app worker
```

`--clean` replaces the current database objects/data. Never run it against a live installation unintentionally. Restoring an existing volume retains its database-role passwords; restore the corresponding `.env` or rotate roles explicitly. Validate login, project scope, a historical invoice PDF and report balances, then make a fresh backup. Do not delete the only known good backup. Database role initialization was exercised on local PostgreSQL; the Compose image and volume initialization have not been executed in Docker in this development environment; perform a restore rehearsal on the target server.

For upgrades, back up first, then `docker compose up --build -d`. The one-shot migration service must complete before the API/worker start. Do not downgrade a financial database casually; retain audit and invoice history. Check `docker compose logs --tail=100 app worker migrate` and `/api/health` after an upgrade. `pgdata` is the persistent named volume; `docker compose down` preserves it, while `down -v` destroys it.

## TLS and sessions

Terminate TLS at an operator-managed reverse proxy, keep the app bound to loopback unless deliberately exposing it on a trusted network interface, set exact `APP_ORIGIN`, and retain `SECURE_COOKIES=true`. The server does not trust forwarded headers. For explicit local HTTP only, use the native development launcher or set `APP_ENV=development` and `SECURE_COOKIES=false`; production rejects insecure cookies and development-only origins. No CORS wildcard is configured. Changing an administrator's role/password revokes all their sessions too; sign in again. The bootstrap CLI works only before any users exist. Operator recovery after losing all admin credentials is a manual, audited database maintenance procedure, not an exposed API.

## Webhooks

Set `WEBHOOK_HOSTS=events.example.com,another.example.com` and restart the app/worker. Hosts must use HTTPS port 443 and resolve exclusively to globally routable IPs; private/LAN receivers are deliberately unsupported. Add the endpoint in Settings, copy its secret once, and configure the receiver. Payloads contain `id`, `event`, `object_id`, and UTC `occurred_at`, without task descriptions or invoice/customer details. An authorized integration can fetch details using the API session/CSRF workflow; there are no permanent integration tokens in this release.

Requests carry:

- `X-Ted-Timestamp`: Unix seconds, regenerated for each attempt.
- `X-Ted-Signature`: `v1=` followed by hex HMAC-SHA256 using the endpoint secret over **timestamp + "." + raw request body bytes**.

Verify the signature using a constant-time comparison **before parsing/acting**, require the timestamp within five minutes of your clock, and persist the payload event ID to reject duplicates. Apply the business operation and deduplication record in the same receiver transaction. Return 2xx only after accepting. A crash between delivery and local commit can resend an event, so duplicates must be harmless. Do not deduplicate by signature: retry timestamps and signatures change while the payload event ID remains stable.

The worker attempts each delivery up to six times, with delays of 5, 10, 20, 40 and 80 seconds between failures; polling adds up to two seconds. Redirects are failures. Logs in Settings show attempt counts/status codes. `-1` means validation/network failure, `-2` means an endpoint was disabled before delivery. Exhausted deliveries are retained; there is no manual replay button or dead-letter alerting. Rotation immediately changes the signing secret for subsequent attempts, including queued deliveries. Update the receiver accordingly; disable the endpoint during coordination if necessary.

The API and worker require protected database access. Webhook secrets are stored in that database. Log parameters are hidden, and delivery errors do not include secret URLs or payloads. Expired sessions, audit records and delivery history are not automatically pruned; monitor database size and establish an operator retention policy before long-term use.
