"""Full HTTP auth pipeline with an injected identity port; never opens a database."""

from copy import deepcopy
from uuid import UUID

import httpx
import pytest

from ted.domain.models import LoginSession, User
from ted.domain.rules import Problem
from ted.infrastructure.runtime import settings
from ted.presentation.api import app
from ted.presentation.dependencies import identity_repository, passwords


class MemoryIdentity:
    def __init__(self):
        self.person = User(
            email="browser@example.test",
            name="Browser",
            password_hash=passwords.hash("valid-password-123"),
        )
        self.sessions: dict[UUID, LoginSession] = {}

    async def user_by_email(self, email):
        return deepcopy(self.person) if email == self.person.email else None

    async def user(self, id, lock=False):
        if id != self.person.id:
            raise Problem("Not found", 404)
        return deepcopy(self.person)

    async def users(self):
        return [deepcopy(self.person)]

    async def session(self, token_hash):
        return next(
            (deepcopy(s) for s in self.sessions.values() if s.token_hash == token_hash), None
        )

    async def save(self, *entities):
        for e in entities:
            if isinstance(e, User):
                self.person = deepcopy(e)
            else:
                self.sessions[e.id] = deepcopy(e)

    async def delete_session(self, id):
        self.sessions.pop(id, None)

    async def delete_sessions(self, user_id):
        self.sessions.clear()


@pytest.fixture
async def browser_auth(monkeypatch):
    repo = MemoryIdentity()
    app.dependency_overrides[identity_repository] = lambda: repo
    monkeypatch.setattr(settings, "dev_origins", ("http://localhost:5173", "http://127.0.0.1:5173"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://localhost:5173",
        headers={"Origin": "http://localhost:5173"},
    ) as client:
        yield client, repo
    app.dependency_overrides.clear()


async def test_vite_origin_credentials_session_csrf_and_logout(browser_auth):
    client, repo = browser_auth
    invalid = await client.post(
        "/api/v1/auth/login", json={"email": repo.person.email, "password": "invalid"}
    )
    assert invalid.status_code == 401 and not client.cookies
    unknown = await client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.test", "password": "valid-password-123"},
    )
    assert unknown.status_code == 401
    login = await client.post(
        "/api/v1/auth/login", json={"email": repo.person.email, "password": "valid-password-123"}
    )
    assert login.status_code == 200
    assert (
        "HttpOnly" in login.headers["set-cookie"]
        and "SameSite=strict" in login.headers["set-cookie"]
    )
    assert "password_hash" not in login.json()["user"]
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["user"]["id"] == str(repo.person.id)
    # A second client represents reload/reconnect with only the cookie, then obtains CSRF again.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://localhost:5173",
        cookies=client.cookies,
    ) as reloaded:
        assert (await reloaded.get("/api/v1/auth/me")).json()["csrf"] == login.json()["csrf"]
    assert (await client.post("/api/v1/auth/logout")).status_code == 403
    assert (
        await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "wrong"})
    ).status_code == 403
    rejected = await client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "https://evil.example", "X-CSRF-Token": login.json()["csrf"]},
    )
    assert rejected.status_code == 403 and repo.sessions
    old_cookie = dict(client.cookies)
    assert (
        await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": login.json()["csrf"]})
    ).status_code == 200
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:5173", cookies=old_cookie
    ) as replay:
        assert (await replay.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.parametrize(
    "origin",
    ["http://localhost:5174", "https://evil.example", "null", "http://localhost:5173.evil.example"],
)
async def test_rejected_origin_never_creates_session(browser_auth, origin):
    client, repo = browser_auth
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": repo.person.email, "password": "valid-password-123"},
        headers={"Origin": origin},
    )
    assert r.status_code == 403 and r.json() == {"detail": "Origin rejected"}
    assert not repo.sessions


async def test_production_origin_and_secure_cookie(browser_auth, monkeypatch):
    client, repo = browser_auth
    monkeypatch.setattr(settings, "dev_origins", ())
    monkeypatch.setattr(settings, "app_origin", "https://work.example")
    monkeypatch.setattr(settings, "secure_cookies", True)
    body = {"email": repo.person.email, "password": "valid-password-123"}
    assert (await client.post("/api/v1/auth/login", json=body)).status_code == 403
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://work.example",
        headers={"Origin": "https://work.example"},
    ) as secure:
        r = await secure.post("/api/v1/auth/login", json=body)
        assert r.status_code == 200 and "Secure" in r.headers["set-cookie"]
        assert (await secure.get("/api/v1/auth/me")).status_code == 200


async def test_expired_and_unknown_sessions_are_rejected(browser_auth):
    from datetime import timedelta

    from ted.domain.models import now

    client, repo = browser_auth
    result = await client.post(
        "/api/v1/auth/login", json={"email": repo.person.email, "password": "valid-password-123"}
    )
    assert result.status_code == 200
    for session in repo.sessions.values():
        session.expires_at = now() - timedelta(seconds=1)
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    client.cookies.clear()
    client.cookies.set("ted_session", "unknown-token")
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_profile_update_reloads_locked_access_fields_instead_of_saving_stale_actor(
    browser_auth,
):
    from ted.application.identity import UpdatePreferences

    client, repo = browser_auth
    stale = deepcopy(repo.person)
    repo.person.role = "admin"
    repo.person.password_hash = "new-hash-from-another-session"
    operation = UpdatePreferences(repo)
    updated = await operation.execute(stale, 30, 5, 15, False)
    assert updated.role == repo.person.role == "admin"
    assert repo.person.password_hash == "new-hash-from-another-session"
    assert repo.person.work_minutes == 30
