import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from conftest import post
from sqlalchemy import text

from ted.infrastructure.database import sessions
from ted.presentation.api import app


def key():
    return str(uuid4())


async def record(client, task, seconds=3600, days=1):
    entry = await post(client, "/timer", {"request_key": key(), "task_id": task, "billable": True})
    await post(client, f"/timer/{entry['id']}/stop", status=200)
    end = datetime.now(UTC) - timedelta(days=days)
    response = await client.patch(
        f"/api/v1/time/{entry['id']}",
        json={
            "started_at": (end - timedelta(seconds=seconds)).isoformat(),
            "ended_at": end.isoformat(),
            "billable": True,
            "note": "Verified work",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def draft(admin, work, entry_ids=None, task_ids=None, request_key=None):
    return await post(
        admin,
        "/invoices",
        {
            "client_id": work["client"]["id"],
            "request_key": request_key or key(),
            "entry_ids": entry_ids or [],
            "task_ids": task_ids or [],
        },
    )


async def pay(admin, invoice, amount, request_key=None, currency="USD"):
    return await post(
        admin,
        f"/payments?invoice_id={invoice['id']}",
        {
            "request_key": request_key or key(),
            "amount": amount,
            "currency": currency,
            "paid_on": datetime.now(UTC).date().isoformat(),
            "reference": "Bank transfer",
        },
    )


async def test_hourly_workflow_snapshot_partial_payment_pdf_dashboard(admin, member, work):
    entry = await record(member, work["task"]["id"])
    invoice = await draft(admin, work, [entry["id"]])
    assert invoice["total"] == "60.00"  # task overrides project and client
    pdf = await admin.get(f"/api/v1/invoices/{invoice['id']}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    await post(admin, f"/invoices/{invoice['id']}/issue", status=200)
    changed = await admin.patch(
        f"/api/v1/tasks/{work['task']['id']}",
        json={"version": 1, "rate": "150.00", "title": "Renamed"},
    )
    assert changed.status_code == 200, changed.text
    detail = (await admin.get(f"/api/v1/invoices/{invoice['id']}")).json()
    assert detail["lines"][0]["rate"] == "60.00" and detail["total"] == "60.00"
    await pay(admin, invoice, "20.00")
    report = (await admin.get("/api/v1/reports")).json()
    assert report["outstanding"] == "40.00" and report["payments_received"] == "20.00"
    assert report["uninvoiced_estimate"] == "0.00" and report["worked_estimate"] == "150.00"
    final_key = key()
    p1 = await pay(admin, invoice, "40.00", final_key)
    p2 = await pay(admin, invoice, "40.00", final_key)
    assert p1["id"] == p2["id"]
    detail = (await admin.get(f"/api/v1/invoices/{invoice['id']}")).json()
    assert detail["status"] == "paid" and len(detail["payments"]) == 2
    assert (await admin.get("/api/v1/dashboard")).json()["finance"]["outstanding"] == "0.00"
    assert (await member.get("/api/v1/dashboard")).json()["finance"] is None
    actions = {a["action"] for a in (await admin.get("/api/v1/audit")).json()["items"]}
    assert {"time.adjusted", "invoice.issue", "invoice.payment"} <= actions


async def test_fixed_price_time_is_never_hourly_and_charged_once(admin, member, work):
    task = await post(
        admin,
        "/tasks",
        {
            "project_id": work["project"]["id"],
            "title": "Fixed scope",
            "billing": "fixed",
            "fixed_price": "300.25",
            "status": "done",
            "assignee_ids": [work["member"]["id"]],
        },
    )
    entry = await record(member, task["id"])
    await post(
        admin,
        "/invoices",
        {"client_id": work["client"]["id"], "request_key": key(), "entry_ids": [entry["id"]]},
        status=400,
    )
    invoice = await draft(admin, work, task_ids=[task["id"]])
    assert invoice["total"] == "300.25"
    await post(admin, f"/invoices/{invoice['id']}/issue", status=200)
    await post(
        admin,
        "/invoices",
        {"client_id": work["client"]["id"], "request_key": key(), "task_ids": [task["id"]]},
        status=409,
    )
    report = (await admin.get("/api/v1/reports")).json()
    assert report["worked_estimate"] == "300.25" and report["uninvoiced_estimate"] == "0.00"


async def test_scope_and_idor_every_alternate_path(admin, member, other, work):
    entry = await record(member, work["task"]["id"])
    invoice = await draft(admin, work, [entry["id"]])
    for path in [
        f"/clients/{work['client']['id']}",
        f"/projects/{work['project']['id']}",
        f"/tasks/{work['task']['id']}",
        f"/time/{entry['id']}",
    ]:
        assert (await other.get("/api/v1" + path)).status_code == 404
    for path in ["/clients", "/projects", "/tasks", "/time"]:
        assert (await other.get("/api/v1" + path)).json()["items"] == []
    for path in [
        "/invoices",
        f"/invoices/{invoice['id']}",
        f"/invoices/{invoice['id']}/pdf",
        "/reports",
        "/users",
        "/audit",
        "/webhooks",
    ]:
        assert (await member.get("/api/v1" + path)).status_code == 403
    await post(other, "/timer", {"request_key": key(), "task_id": work["task"]["id"]}, status=404)
    assert (
        await other.patch(
            f"/api/v1/time/{entry['id']}",
            json={
                "started_at": entry["started_at"],
                "ended_at": entry["ended_at"],
                "billable": True,
            },
        )
    ).status_code == 404
    assert (
        await member.patch(
            f"/api/v1/tasks/{work['task']['id']}", json={"version": 1, "rate": "1.00"}
        )
    ).status_code == 403
    assert "rate" not in (await member.get(f"/api/v1/tasks/{work['task']['id']}")).json()
    assert "rate" not in (await member.get("/api/v1/clients")).json()["items"][0]
    assert (await member.get("/api/v1/time?task_id=" + key())).json()["items"] == []


async def test_timer_persists_and_concurrent_commands_are_safe(member, work):
    request_key = key()
    body = {"request_key": request_key, "task_id": work["task"]["id"]}
    results = await asyncio.gather(*[member.post("/api/v1/timer", json=body) for _ in range(5)])
    assert all(r.status_code == 201 for r in results), [r.text for r in results]
    assert {r.json()["id"] for r in results} == {request_key}
    other_key = await member.post("/api/v1/timer", json={**body, "request_key": key()})
    assert other_key.status_code == 409
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", cookies=member.cookies
    ) as device:
        assert (await device.get("/api/v1/timer")).json()["entry"]["id"] == request_key
    await post(member, f"/timer/{request_key}/pause", status=200)
    paused = (await member.get("/api/v1/timer")).json()["entry"]
    assert paused["paused_at"] is not None
    await post(member, f"/timer/{request_key}/resume", status=200)
    results = await asyncio.gather(
        *[member.post(f"/api/v1/timer/{request_key}/stop") for _ in range(3)]
    )
    assert all(r.status_code == 200 for r in results)
    assert (await member.get("/api/v1/timer")).json()["entry"] is None
    assert (await member.get("/api/v1/time")).json()["total"] == 1


async def test_concurrent_distinct_starts_have_one_winner(member, work):
    results = await asyncio.gather(
        *[
            member.post("/api/v1/timer", json={"request_key": key(), "task_id": work["task"]["id"]})
            for _ in range(5)
        ]
    )
    assert sorted(r.status_code for r in results) == [201, 409, 409, 409, 409]


async def test_concurrent_invoices_payment_retries_and_edit_reservation(admin, member, work):
    entry = await record(member, work["task"]["id"])
    invoice_key = key()
    body = {
        "client_id": work["client"]["id"],
        "entry_ids": [entry["id"]],
        "request_key": invoice_key,
    }
    results = await asyncio.gather(*[admin.post("/api/v1/invoices", json=body) for _ in range(3)])
    assert all(r.status_code == 201 for r in results), [r.text for r in results]
    assert len({r.json()["id"] for r in results}) == 1
    invoice = results[0].json()
    # Distinct invoice requests cannot reserve the same work.
    results = await asyncio.gather(
        *[admin.post("/api/v1/invoices", json={**body, "request_key": key()}) for _ in range(3)]
    )
    assert all(r.status_code == 409 for r in results)
    assert (
        await member.patch(
            f"/api/v1/time/{entry['id']}",
            json={
                "started_at": entry["started_at"],
                "ended_at": entry["ended_at"],
                "billable": False,
            },
        )
    ).status_code == 409
    await post(admin, f"/invoices/{invoice['id']}/issue", status=200)
    payment_body = {
        "request_key": key(),
        "amount": "40.00",
        "currency": "USD",
        "paid_on": datetime.now(UTC).date().isoformat(),
        "reference": "same",
    }
    results = await asyncio.gather(
        *[
            admin.post(f"/api/v1/payments?invoice_id={invoice['id']}", json=payment_body)
            for _ in range(3)
        ]
    )
    assert all(r.status_code == 201 for r in results), [r.text for r in results]
    assert len({r.json()["id"] for r in results}) == 1
    results = await asyncio.gather(
        *[
            admin.post(
                f"/api/v1/payments?invoice_id={invoice['id']}",
                json={**payment_body, "request_key": key(), "amount": "20.00"},
            )
            for _ in range(3)
        ]
    )
    assert sorted(r.status_code for r in results) == [201, 409, 409]
    assert (await admin.get("/api/v1/reports")).json()["payments_received"] == "60.00"


async def test_invalid_payments_void_and_rebill(admin, member, work):
    entry = await record(member, work["task"]["id"])
    invoice = await draft(admin, work, [entry["id"]])
    await post(admin, f"/invoices/{invoice['id']}/void", status=200)
    again = await draft(admin, work, [entry["id"]])
    assert again["id"] != invoice["id"]
    await post(admin, f"/invoices/{again['id']}/issue", status=200)
    body = {
        "request_key": key(),
        "amount": "61.00",
        "currency": "USD",
        "paid_on": datetime.now(UTC).date().isoformat(),
    }
    assert (
        await admin.post(f"/api/v1/payments?invoice_id={again['id']}", json=body)
    ).status_code == 400
    assert (
        await admin.post(
            f"/api/v1/payments?invoice_id={again['id']}",
            json={**body, "currency": "EUR", "amount": "10.00"},
        )
    ).status_code == 400
    await pay(admin, again, "10.00")
    await post(admin, f"/invoices/{again['id']}/void", status=409)


async def test_overlap_breaks_preferences_and_optimistic_updates(admin, member, work):
    entry = await record(member, work["task"]["id"])
    second = await post(member, "/timer", {"request_key": key(), "kind": "break", "billable": True})
    assert not second["billable"] and second["target_seconds"] == 300
    await post(member, f"/timer/{second['id']}/stop", status=200)
    r = await member.patch(
        f"/api/v1/time/{second['id']}",
        json={"started_at": entry["started_at"], "ended_at": entry["ended_at"], "billable": True},
    )
    assert r.status_code == 409
    r = await member.patch(
        "/api/v1/settings/preferences",
        json={"work_minutes": 1, "short_break": 2, "long_break": 3, "notifications": False},
    )
    assert r.status_code == 200
    long = await post(
        member,
        "/timer",
        {"request_key": key(), "kind": "break", "long_break": True, "billable": True},
    )
    assert long["target_seconds"] == 180 and not long["billable"]
    task = work["task"]
    assert (
        await member.patch(
            f"/api/v1/tasks/{task['id']}", json={"version": 1, "status": "in_progress"}
        )
    ).status_code == 200
    assert (
        await member.patch(f"/api/v1/tasks/{task['id']}", json={"version": 1, "status": "done"})
    ).status_code == 409


async def test_csrf_origin_auth_and_last_admin(admin, member, work):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as anonymous:
        assert (await anonymous.get("/api/v1/tasks")).status_code == 401
    assert (
        await member.post(
            "/api/v1/timer", json={"request_key": key()}, headers={"X-CSRF-Token": ""}
        )
    ).status_code == 403
    assert (
        await member.post(
            "/api/v1/timer", json={"request_key": key()}, headers={"Origin": "https://evil.example"}
        )
    ).status_code == 403
    me = (await admin.get("/api/v1/auth/me")).json()["user"]
    assert (
        await admin.patch(f"/api/v1/users/{me['id']}", json={"role": "member", "active": True})
    ).status_code == 409
    assert (await member.get("/api/v1/tasks?limit=100000")).status_code == 422
    assert (await member.get("/api/v1/time?since=2026-01-01T00:00:00")).status_code == 400


async def test_database_constraints_independent_of_api(member, work):
    entry = await record(member, work["task"]["id"])
    async with sessions() as session:
        with pytest.raises(Exception, match="no_overlapping_sessions"):
            async with session.begin():
                await session.execute(
                    text(
                        "INSERT INTO time_entries (id,user_id,task_id,kind,billable,started_at,ended_at,paused_at,paused_microseconds,note,target_seconds) SELECT :new_id, user_id, task_id, kind, billable, started_at, ended_at, paused_at, paused_microseconds, note, target_seconds FROM time_entries WHERE id=:old_id"
                    ),
                    {"new_id": uuid4(), "old_id": entry["id"]},
                )
