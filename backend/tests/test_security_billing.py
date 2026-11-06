import asyncio
import hmac
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256

import httpx
import pytest
from conftest import post
from sqlalchemy import text
from test_acceptance import draft, key, record

from ted.domain.models import Delivery, Webhook
from ted.domain.rules import Problem
from ted.infrastructure import webhooks
from ted.infrastructure.config import settings
from ted.infrastructure.database import sessions


async def test_session_revocation_login_lockout_and_cookie_flags(admin, member, work):
    response = await admin.patch(
        f"/api/v1/users/{work['member']['id']}", json={"role": "member", "active": False}
    )
    assert response.status_code == 200
    assert (await member.get("/api/v1/tasks")).status_code == 401
    async with httpx.AsyncClient(transport=member._transport, base_url="http://test") as client:
        for _ in range(5):
            result = await client.post(
                "/api/v1/auth/login", json={"email": "admin@example.test", "password": "wrong"}
            )
            assert result.status_code == 401
        result = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.test", "password": "test-password-123"},
        )
        assert result.status_code == 401
    cookie = next(iter(admin.cookies.jar))
    assert "HttpOnly" in cookie._rest and cookie._rest["SameSite"] == "strict"


async def test_rate_fallback_voided_issued_snapshots_and_db_immutability(admin, member, work):
    task = work["task"]
    result = await admin.patch(f"/api/v1/tasks/{task['id']}", json={"version": 1, "rate": None})
    assert result.status_code == 200
    entry = await record(member, task["id"])
    invoice = await draft(admin, work, [entry["id"]])
    assert invoice["total"] == "90.00"
    await post(admin, f"/invoices/{invoice['id']}/issue", status=200)
    async with sessions() as session:
        with pytest.raises(Exception, match="immutable"):
            async with session.begin():
                await session.execute(
                    text("UPDATE invoices SET total=1 WHERE id=:id"), {"id": invoice["id"]}
                )
    async with sessions() as session:
        with pytest.raises(Exception, match="Reserved time"):
            async with session.begin():
                await session.execute(
                    text("UPDATE time_entries SET note='changed' WHERE id=:id"), {"id": entry["id"]}
                )
    await post(admin, f"/invoices/{invoice['id']}/void", status=200)
    assert (await admin.get("/api/v1/reports")).json()["outstanding"] == "0.00"
    result = await admin.patch(
        f"/api/v1/projects/{work['project']['id']}",
        json={"name": "Website", "rate": None, "member_ids": [work["member"]["id"]]},
    )
    assert result.status_code == 200
    again = await draft(admin, work, [entry["id"]])
    assert again["total"] == "120.00"
    assert (await admin.get(f"/api/v1/invoices/{invoice['id']}")).json()["total"] == "90.00"


async def test_edit_and_invoice_race_has_consistent_snapshot(admin, member, work):
    entry = await record(member, work["task"]["id"])
    end = datetime.now(UTC) - timedelta(days=2)
    edit = {
        "started_at": (end - timedelta(hours=2)).isoformat(),
        "ended_at": end.isoformat(),
        "billable": True,
    }
    results = await asyncio.gather(
        member.patch(f"/api/v1/time/{entry['id']}", json=edit),
        admin.post(
            "/api/v1/invoices",
            json={
                "client_id": work["client"]["id"],
                "request_key": key(),
                "entry_ids": [entry["id"]],
            },
        ),
    )
    assert results[1].status_code == 201
    assert results[0].status_code in {200, 409}
    saved = (await member.get(f"/api/v1/time/{entry['id']}")).json()
    invoice = results[1].json()
    assert Decimal(invoice["total"]) == Decimal(saved["seconds"]) / 60


async def test_task_move_membership_invariants_and_cross_client_sources(admin, member, work):
    first = work["task"]
    second = await post(
        admin,
        "/tasks",
        {
            "project_id": work["project"]["id"],
            "title": "Second",
            "position": 1,
            "assignee_ids": [work["member"]["id"]],
        },
    )
    moved = await post(
        member, f"/tasks/{second['id']}/move", {"version": 1, "direction": "up"}, status=200
    )
    assert moved["position"] == 0
    assert [t["id"] for t in (await member.get("/api/v1/tasks")).json()["items"]] == [
        second["id"],
        first["id"],
    ]
    assert (
        await admin.patch(
            f"/api/v1/projects/{work['project']['id']}", json={"name": "Website", "member_ids": []}
        )
    ).status_code == 409
    entry = await record(member, first["id"])
    client = await post(admin, "/clients", {"name": "Different", "rate": "100.00"})
    await post(
        admin,
        "/invoices",
        {"client_id": client["id"], "request_key": key(), "entry_ids": [entry["id"]]},
        status=400,
    )
    await post(
        admin,
        "/invoices",
        {
            "client_id": work["client"]["id"],
            "request_key": key(),
            "entry_ids": [entry["id"], entry["id"]],
        },
        status=400,
    )


def test_hmac_signature_and_registration_allowlist(monkeypatch):
    payload = b'{"id":"stable-event-id"}'
    expected = hmac.new(b"secret", b"123." + payload, sha256).hexdigest()
    assert webhooks.signature("secret", "123", payload) == "v1=" + expected
    monkeypatch.setattr(settings, "webhook_hosts", "events.example.test")
    webhooks.validate_url("https://events.example.test/hook")
    for url in [
        "http://events.example.test/hook",
        "https://evil.test/hook",
        "https://name:pass@events.example.test/hook",
        "https://events.example.test:8443/hook",
        "https://events.example.test:invalid/hook",
    ]:
        with pytest.raises(Problem):
            webhooks.validate_url(url)


async def test_webhook_dns_pin_signature_and_private_address_rejection(monkeypatch):
    monkeypatch.setattr(settings, "webhook_hosts", "events.example.test")
    hook = Webhook(url="https://events.example.test/hook", secret="secret")
    delivery = Delivery(webhook_id=hook.id, event="task.updated", payload='{"id":"stable"}')
    monkeypatch.setattr(
        webhooks.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 443))]
    )
    with pytest.raises(Problem, match="Non-public"):
        await webhooks.deliver(hook, delivery)
    monkeypatch.setattr(
        webhooks.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))]
    )
    captured = []

    def handler(request):
        captured.append(request)
        assert request.url.host == "93.184.216.34"
        assert request.headers["Host"] == "events.example.test"
        assert request.extensions["sni_hostname"] == "events.example.test"
        assert request.headers["X-Ted-Signature"] == webhooks.signature(
            "secret", request.headers["X-Ted-Timestamp"], request.content
        )
        return httpx.Response(204)

    original = httpx.AsyncClient
    monkeypatch.setattr(
        webhooks.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    assert await webhooks.deliver(hook, delivery) == 204
    assert len(captured) == 1


async def test_transactional_webhook_outbox_retries_and_no_concurrent_double_send(
    admin, member, work, monkeypatch
):
    monkeypatch.setattr(settings, "webhook_hosts", "events.example.test")
    hook = await post(admin, "/webhooks", {"url": "https://events.example.test/hook"})
    assert "secret" in hook
    assert "secret" not in (await admin.get("/api/v1/webhooks")).json()["items"][0]
    task = work["task"]
    assert (
        await member.patch(f"/api/v1/tasks/{task['id']}", json={"version": 1, "status": "done"})
    ).status_code == 200
    calls = []
    entered = asyncio.Event()
    release = asyncio.Event()

    async def send(hook, delivery):
        calls.append(delivery.id)
        entered.set()
        await release.wait()
        return 503

    monkeypatch.setattr(webhooks, "deliver", send)
    first = asyncio.create_task(webhooks.tick())
    await entered.wait()
    assert not await webhooks.tick()  # row is locked by first worker
    release.set()
    assert await first
    assert len(calls) == 1
    log = (await admin.get("/api/v1/webhooks")).json()["deliveries"][0]
    assert log["attempts"] == 1 and log["status_code"] == 503 and log["delivered_at"] is None
    async with sessions() as session, session.begin():
        await session.execute(
            text("UPDATE deliveries SET next_attempt=CURRENT_TIMESTAMP-interval '1 second'")
        )

    async def success(hook, delivery):
        assert delivery.id == calls[0]
        return 200

    monkeypatch.setattr(webhooks, "deliver", success)
    assert await webhooks.tick()
    log = (await admin.get("/api/v1/webhooks")).json()["deliveries"][0]
    assert log["attempts"] == 2 and log["delivered_at"] is not None
    assert not await webhooks.tick()


async def test_password_whitespace_and_workspace_counter_privacy(admin, member):
    user = await post(
        admin,
        "/users",
        {
            "name": "Whitespace",
            "email": "spaces@example.test",
            "password": "  password-with-spaces  ",
        },
    )
    async with httpx.AsyncClient(transport=member._transport, base_url="http://test") as client:
        result = await client.post(
            "/api/v1/auth/login", json={"email": user["email"], "password": "password-with-spaces"}
        )
        assert result.status_code == 401
        result = await client.post(
            "/api/v1/auth/login",
            json={"email": user["email"], "password": "  password-with-spaces  "},
        )
        assert result.status_code == 200
    workspace = (await member.get("/api/v1/settings")).json()["workspace"]
    assert set(workspace) == {"name", "currency"}
