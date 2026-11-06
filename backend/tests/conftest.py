# ruff: noqa: E402
import os
from urllib.parse import urlsplit

# Refuse accidental execution against an operator's real data.
TEST_URL = os.environ.get("TEST_DATABASE_URL", "")
os.environ["DATABASE_URL"] = TEST_URL or "postgresql+asyncpg://test@db.invalid/disposable_test"
os.environ["APP_ENV"] = "development"
os.environ["DEV_ORIGINS"] = ""
os.environ["SECURE_COOKIES"] = "false"
os.environ["APP_ORIGIN"] = "http://test"

import httpx
import pytest
from sqlalchemy import text

from ted.domain.models import User
from ted.infrastructure.database import sessions
from ted.infrastructure.passwords import ArgonPasswords
from ted.infrastructure.persistence.identity import SqlIdentityRepository
from ted.infrastructure.runtime import settings
from ted.presentation.api import app

HASH = ArgonPasswords().hash("test-password-123")


@pytest.fixture
async def clean_database():
    if not TEST_URL or os.environ.get("ALLOW_DESTRUCTIVE_TESTS") != "1":
        pytest.skip(
            "Set TEST_DATABASE_URL and ALLOW_DESTRUCTIVE_TESTS=1 for a confirmed disposable database"
        )
    assert urlsplit(settings.database_url).path.rsplit("/", 1)[-1].endswith("_test"), (
        "Use a disposable database ending _test"
    )
    async with sessions() as session, session.begin():
        await session.execute(
            text(
                "TRUNCATE users, clients, projects, memberships, tasks, assignments, time_entries, invoices, invoice_lines, payments, audit, webhooks, deliveries, sessions RESTART IDENTITY CASCADE"
            )
        )
        await session.execute(
            text("UPDATE workspace SET currency='USD', name='Test studio', next_invoice=1")
        )
        await SqlIdentityRepository(session).save(
            User(email="admin@example.test", name="Admin", role="admin", password_hash=HASH)
        )
        await SqlIdentityRepository(session).save(
            User(email="member@example.test", name="Member", password_hash=HASH)
        )
        await SqlIdentityRepository(session).save(
            User(email="other@example.test", name="Other", password_hash=HASH)
        )
    yield


async def client_for(email: str) -> httpx.AsyncClient:
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "test-password-123"}
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf"]
    return client


@pytest.fixture
async def admin(clean_database):
    client = await client_for("admin@example.test")
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
async def member(clean_database):
    client = await client_for("member@example.test")
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
async def other(clean_database):
    client = await client_for("other@example.test")
    try:
        yield client
    finally:
        await client.aclose()


async def post(client: httpx.AsyncClient, path: str, body=None, status=201):
    result = await client.post("/api/v1" + path, json=body)
    assert result.status_code == status, result.text
    return result.json()


@pytest.fixture
async def work(admin):
    users = (await admin.get("/api/v1/users")).json()["items"]
    member = next(u for u in users if u["role"] == "member" and u["name"] == "Member")
    client = await post(admin, "/clients", {"name": "Acme", "rate": "120.00"})
    project = await post(
        admin,
        "/projects",
        {
            "name": "Website",
            "client_id": client["id"],
            "rate": "90.00",
            "member_ids": [member["id"]],
        },
    )
    task = await post(
        admin,
        "/tasks",
        {
            "project_id": project["id"],
            "title": "Build",
            "rate": "60.00",
            "assignee_ids": [member["id"]],
        },
    )
    return {"client": client, "project": project, "task": task, "member": member}
