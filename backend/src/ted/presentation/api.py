import hmac
from collections.abc import AsyncIterator
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Header, Query, Request, Response, Security
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import APIKeyCookie
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ted.application.identity import Identity
from ted.application.services import Billing, Work, admin
from ted.domain.models import (
    Client,
    LoginSession,
    Project,
    Task,
    TimeEntry,
    User,
    Webhook,
    Workspace,
    now,
)
from ted.domain.rules import Problem, require
from ted.infrastructure.config import settings
from ted.infrastructure.database import SqlStore, sessions
from ted.infrastructure.passwords import ArgonPasswords
from ted.infrastructure.pdf import invoice_pdf
from ted.infrastructure.webhooks import validate_url
from ted.presentation import schemas as s

app = FastAPI(
    title="Tedminnum API",
    version="1.0.0",
    docs_url=None,
    openapi_url="/api/openapi.json",
    redoc_url=None,
)
passwords = ArgonPasswords()
cookie = APIKeyCookie(name="ted_session", auto_error=False)


def encode(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, list | tuple):
        return [encode(v) for v in value]
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    return value


def public(entity: Any, actor: User | None = None) -> dict[str, Any]:
    data = asdict(entity)
    if isinstance(entity, User):
        data = {
            k: v
            for k, v in data.items()
            if k
            in {
                "id",
                "name",
                "email",
                "role",
                "active",
                "work_minutes",
                "short_break",
                "long_break",
                "notifications",
            }
        }
    if isinstance(entity, Workspace):
        data = {"name": entity.name, "currency": entity.currency}
    if isinstance(entity, Webhook):
        data.pop("secret")
    if actor is not None and actor.role != "admin" and isinstance(entity, Client | Project | Task):
        for k in ("rate", "fixed_price"):
            data.pop(k, None)
    if isinstance(entity, TimeEntry):
        data["seconds"] = entity.seconds()
    return encode(data)  # type: ignore[no-any-return]


@app.exception_handler(Problem)
async def problem_handler(request: Request, error: Problem) -> JSONResponse:
    return JSONResponse({"detail": error.message}, status_code=error.status)


@app.exception_handler(IntegrityError)
async def conflict_handler(request: Request, error: IntegrityError) -> JSONResponse:
    return JSONResponse({"detail": "Conflicting change; refresh and try again"}, status_code=409)


@app.middleware("http")
async def headers_and_origin(request: Request, call_next: Any) -> Response:
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin is not None and origin != settings.app_origin:
            return JSONResponse({"detail": "Origin rejected"}, status_code=403)
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


async def store_dependency() -> AsyncIterator[SqlStore]:
    async with sessions() as session:
        async with session.begin():
            yield SqlStore(session)


StoreDep = Annotated[SqlStore, Depends(store_dependency, scope="function")]


async def session_dependency(
    store: StoreDep, token: Annotated[str | None, Security(cookie)]
) -> LoginSession:
    session = await store.session(sha256((token or "").encode()).hexdigest())
    require(session is not None and session.expires_at > now(), "Sign in required", 401)
    assert session is not None
    return session


SessionDep = Annotated[LoginSession, Depends(session_dependency)]


async def actor_dependency(
    request: Request,
    store: StoreDep,
    session: SessionDep,
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> User:
    user = await store.user(session.user_id)
    require(user.active, "Sign in required", 401)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require(
            hmac.compare_digest(csrf or "", session.csrf),
            "CSRF token required",
            403,
        )
    return user


Actor = Annotated[User, Depends(actor_dependency)]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


def page(items: list[Any], limit: int, offset: int) -> dict[str, Any]:
    return {
        "items": items[offset : offset + limit],
        "total": len(items),
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/health")
async def health(store: StoreDep) -> dict[str, str]:
    await store.db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/api/v1/auth/login")
async def login(body: s.Login, store: StoreDep, response: Response) -> Any:
    result = await Identity(store, passwords).login(
        body.email.lower(), body.password, settings.session_hours
    )
    if result is None:
        return JSONResponse(
            {"detail": "Invalid credentials or account temporarily locked"}, status_code=401
        )
    user, token, session = result
    response.set_cookie(
        "ted_session",
        token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        max_age=settings.session_hours * 3600,
        path="/",
    )
    return {"user": public(user), "csrf": session.csrf}


@app.get("/api/v1/auth/me")
async def me(actor: Actor, session: SessionDep) -> dict[str, Any]:
    return {"user": public(actor), "csrf": session.csrf, "server_time": now().isoformat()}


@app.post("/api/v1/auth/logout")
async def logout(
    actor: Actor, session: SessionDep, store: StoreDep, response: Response
) -> dict[str, bool]:
    await store.db.delete(session)
    response.delete_cookie("ted_session", path="/")
    return {"ok": True}


@app.post("/api/v1/auth/password")
async def change_password(
    body: s.PasswordChange, actor: Actor, store: StoreDep, response: Response
) -> dict[str, bool]:
    require(
        passwords.verify(body.current_password, actor.password_hash),
        "Current password is incorrect",
        403,
    )
    actor.password_hash = passwords.hash(body.new_password)
    await store.delete_sessions(actor.id)
    await store.save(actor)
    await Work(store, actor).audit("user.password_changed", actor.id)
    response.delete_cookie("ted_session", path="/")
    return {"ok": True}


@app.get("/api/v1/users")
async def users(
    actor: Actor, store: StoreDep, limit: Limit = 50, offset: Offset = 0
) -> dict[str, Any]:
    admin(actor)
    return page([public(u) for u in await store.users()], limit, offset)


@app.post("/api/v1/users", status_code=201)
async def create_user(body: s.UserCreate, actor: Actor, store: StoreDep) -> dict[str, Any]:
    data = body.model_dump()
    data["email"] = data["email"].lower()
    return public(await Identity(store, passwords).create_user(actor, **data))


@app.patch("/api/v1/users/{id}")
async def update_user(
    id: UUID, body: s.UserUpdate, actor: Actor, store: StoreDep
) -> dict[str, Any]:
    return public(await Identity(store, passwords).update_user(actor, id, **body.model_dump()))


@app.get("/api/v1/clients")
async def clients(
    actor: Actor, store: StoreDep, limit: Limit = 50, offset: Offset = 0
) -> dict[str, Any]:
    return page([public(c, actor) for c in await store.clients(actor)], limit, offset)


@app.get("/api/v1/clients/{id}")
async def client(id: UUID, actor: Actor, store: StoreDep) -> dict[str, Any]:
    return public(await Work(store, actor).client(id), actor)


@app.post("/api/v1/clients", status_code=201)
async def create_client(body: s.ClientInput, actor: Actor, store: StoreDep) -> dict[str, Any]:
    return public(await Work(store, actor).create_client(**body.model_dump()))


@app.patch("/api/v1/clients/{id}")
async def update_client(
    id: UUID, body: s.ClientInput, actor: Actor, store: StoreDep
) -> dict[str, Any]:
    return public(await Work(store, actor).update_client(id, **body.model_dump()))


async def project_data(project: Project, actor: User, store: SqlStore) -> dict[str, Any]:
    result = public(project, actor)
    if actor.role == "admin":
        result["member_ids"] = encode(await store.members(project.id))
    return result


@app.get("/api/v1/projects")
async def projects(
    actor: Actor,
    store: StoreDep,
    limit: Limit = 50,
    offset: Offset = 0,
    client_id: UUID | None = None,
) -> dict[str, Any]:
    return page(
        [
            await project_data(p, actor, store)
            for p in await store.projects(actor)
            if client_id is None or p.client_id == client_id
        ],
        limit,
        offset,
    )


@app.get("/api/v1/projects/{id}")
async def project(id: UUID, actor: Actor, store: StoreDep) -> dict[str, Any]:
    return await project_data(await Work(store, actor).project(id), actor, store)


@app.post("/api/v1/projects", status_code=201)
async def create_project(body: s.ProjectCreate, actor: Actor, store: StoreDep) -> dict[str, Any]:
    return await project_data(
        await Work(store, actor).create_project(**body.model_dump()), actor, store
    )


@app.patch("/api/v1/projects/{id}")
async def update_project(
    id: UUID, body: s.ProjectInput, actor: Actor, store: StoreDep
) -> dict[str, Any]:
    return await project_data(
        await Work(store, actor).update_project(id, **body.model_dump()), actor, store
    )


async def task_data(task: Task, actor: User, store: SqlStore) -> dict[str, Any]:
    return public(task, actor) | {"assignee_ids": encode(await store.assignees(task.id))}


@app.get("/api/v1/tasks")
async def tasks(
    actor: Actor,
    store: StoreDep,
    limit: Limit = 50,
    offset: Offset = 0,
    project_id: UUID | None = None,
    status: str | None = None,
    q: str = "",
) -> dict[str, Any]:
    result = [
        t
        for t in await store.tasks(actor)
        if (project_id is None or t.project_id == project_id)
        and (status is None or t.status == status)
        and q.lower() in t.title.lower()
    ]
    result.sort(key=lambda t: (t.position, str(t.id)))
    return page([await task_data(t, actor, store) for t in result], limit, offset)


@app.get("/api/v1/tasks/{id}")
async def task(id: UUID, actor: Actor, store: StoreDep) -> dict[str, Any]:
    return await task_data(await Work(store, actor).task(id), actor, store)


@app.post("/api/v1/tasks", status_code=201)
async def create_task(body: s.TaskCreate, actor: Actor, store: StoreDep) -> dict[str, Any]:
    return await task_data(await Work(store, actor).create_task(**body.model_dump()), actor, store)


@app.patch("/api/v1/tasks/{id}")
async def update_task(
    id: UUID, body: s.TaskUpdate, actor: Actor, store: StoreDep
) -> dict[str, Any]:
    return await task_data(
        await Work(store, actor).update_task(
            id, body.version, body.model_dump(exclude_unset=True, exclude={"version"})
        ),
        actor,
        store,
    )


@app.post("/api/v1/tasks/{id}/move")
async def move_task(id: UUID, body: s.TaskMove, actor: Actor, store: StoreDep) -> dict[str, Any]:
    return await task_data(
        await Work(store, actor).move_task(id, body.version, body.direction), actor, store
    )


@app.get("/api/docs", include_in_schema=False)
async def api_docs() -> HTMLResponse:
    return HTMLResponse(
        """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Tedminnum API</title><link rel="stylesheet" href="/docs-assets/swagger-ui.css"></head><body><div id="swagger-ui"></div><script src="/docs-assets/swagger-ui-bundle.js"></script><script src="/docs-assets/init.js"></script></body></html>"""
    )


@app.get("/api/v1/timer")
async def active_timer(actor: Actor, store: StoreDep) -> dict[str, Any]:
    entry = await store.active_entry(actor.id)
    return {"entry": public(entry) if entry else None, "server_time": now().isoformat()}


@app.post("/api/v1/timer", status_code=201)
async def start_timer(body: s.TimerStart, actor: Actor, store: StoreDep) -> dict[str, Any]:
    return public(
        await Work(store, actor).start_timer(
            body.request_key, body.task_id, body.kind, body.billable, body.long_break
        )
    )


@app.post("/api/v1/timer/{id}/{command}")
async def timer_command(id: UUID, command: str, actor: Actor, store: StoreDep) -> dict[str, Any]:
    require(command in {"pause", "resume", "stop"}, "Not found", 404)
    return public(await Work(store, actor).timer_command(id, command))


@app.get("/api/v1/time")
async def time_entries(
    actor: Actor,
    store: StoreDep,
    limit: Limit = 50,
    offset: Offset = 0,
    since: datetime | None = None,
    until: datetime | None = None,
    task_id: UUID | None = None,
) -> dict[str, Any]:
    for bound in (since, until):
        require(bound is None or bound.tzinfo is not None, "Use timezone-aware timestamps")
    entries = [
        e
        for e in await store.entries(actor)
        if (since is None or e.started_at >= since)
        and (until is None or e.started_at < until)
        and (task_id is None or e.task_id == task_id)
    ]
    entries.sort(key=lambda e: e.started_at, reverse=True)
    result = [public(e) for e in entries]
    if actor.role == "admin":
        reserved = {line.source_entry_id for line in await store.lines() if line.reserved}
        for item, entry in zip(result, entries, strict=True):
            item["reserved"] = entry.id in reserved
    return page(result, limit, offset)


@app.get("/api/v1/time/{id}")
async def get_time(id: UUID, actor: Actor, store: StoreDep) -> dict[str, Any]:
    entry = await store.entry(id)
    require(
        entry is not None and (actor.role == "admin" or entry.user_id == actor.id), "Not found", 404
    )
    return public(entry)


@app.patch("/api/v1/time/{id}")
async def edit_time(id: UUID, body: s.EntryUpdate, actor: Actor, store: StoreDep) -> dict[str, Any]:
    return public(await Work(store, actor).edit_entry(id, **body.model_dump()))


@app.get("/api/v1/invoices")
async def invoices(
    actor: Actor, store: StoreDep, limit: Limit = 50, offset: Offset = 0, status: str | None = None
) -> dict[str, Any]:
    admin(actor)
    return page(
        [public(i) for i in await store.invoices() if status is None or i.status == status],
        limit,
        offset,
    )


@app.post("/api/v1/invoices", status_code=201)
async def draft_invoice(body: s.Draft, actor: Actor, store: StoreDep) -> dict[str, Any]:
    return public(
        await Billing(store, actor).draft(
            body.client_id, body.request_key, body.entry_ids, body.task_ids
        )
    )


@app.get("/api/v1/invoices/{id}")
async def invoice(id: UUID, actor: Actor, store: StoreDep) -> dict[str, Any]:
    admin(actor)
    i = await store.invoice(id)
    return public(i) | {
        "lines": [public(line) for line in await store.lines(id)],
        "payments": [public(p) for p in await store.payments(id)],
    }


@app.post("/api/v1/invoices/{id}/{command}")
async def invoice_command(id: UUID, command: str, actor: Actor, store: StoreDep) -> dict[str, Any]:
    require(command in {"issue", "void"}, "Not found", 404)
    return public(await Billing(store, actor).transition(id, command))


@app.patch("/api/v1/invoices/{id}/lines/{line_id}")
async def describe_line(
    id: UUID, line_id: UUID, body: s.Description, actor: Actor, store: StoreDep
) -> dict[str, bool]:
    await Billing(store, actor).describe_line(id, line_id, body.description)
    return {"ok": True}


@app.get("/api/v1/invoices/{id}/pdf")
async def pdf(id: UUID, actor: Actor, store: StoreDep) -> Response:
    admin(actor)
    invoice = await store.invoice(id)
    content = invoice_pdf(invoice, await store.lines(id), await store.payments(id))
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.number}.pdf"'},
    )


# Registered separately to avoid collision with the lifecycle command route.
@app.post("/api/v1/payments", status_code=201)
async def payment(
    body: s.PaymentInput, invoice_id: UUID, actor: Actor, store: StoreDep
) -> dict[str, Any]:
    return public(
        await Billing(store, actor).pay(
            invoice_id, body.request_key, body.amount, body.currency, body.paid_on, body.reference
        )
    )


@app.get("/api/v1/reports")
async def report(actor: Actor, store: StoreDep) -> dict[str, Any]:
    return encode(await Billing(store, actor).report())  # type: ignore[no-any-return]


@app.get("/api/v1/dashboard")
async def dashboard(
    actor: Actor, store: StoreDep, day_start: datetime | None = None
) -> dict[str, Any]:
    start = day_start or now().replace(hour=0, minute=0, second=0, microsecond=0)
    require(start.tzinfo is not None, "Use timezone-aware day_start")
    from datetime import timedelta

    mine = [e for e in await store.entries(actor) if e.user_id == actor.id]
    today = [e for e in mine if start <= e.started_at < start + timedelta(days=1)]
    tasks = [
        t
        for t in await store.tasks(actor)
        if actor.id in await store.assignees(t.id) and t.status != "done"
    ]
    active = await store.active_entry(actor.id)
    return {
        "work_seconds": sum(e.seconds() for e in today if e.kind == "work"),
        "break_seconds": sum(e.seconds() for e in today if e.kind == "break"),
        "open_tasks": len(tasks),
        "tasks": [await task_data(t, actor, store) for t in tasks[:10]],
        "recent": [public(e) for e in sorted(mine, key=lambda e: e.started_at, reverse=True)[:8]],
        "active": public(active) if active else None,
        "finance": encode(await Billing(store, actor).report()) if actor.role == "admin" else None,
    }


@app.get("/api/v1/settings")
async def get_settings(actor: Actor, store: StoreDep) -> dict[str, Any]:
    return {"workspace": public(await store.workspace()), "preferences": public(actor)}


@app.patch("/api/v1/settings/preferences")
async def preferences(body: s.Preferences, actor: Actor, store: StoreDep) -> dict[str, Any]:
    for key, value in body.model_dump().items():
        setattr(actor, key, value)
    await store.save(actor)
    return public(actor)


@app.patch("/api/v1/settings/workspace")
async def workspace_settings(
    body: s.WorkspaceInput, actor: Actor, store: StoreDep
) -> dict[str, Any]:
    admin(actor)
    workspace = await store.workspace(lock=True)
    if body.currency != workspace.currency:
        require(
            not await store.invoices() and not await store.clients(actor),
            "Set currency before adding clients or invoices",
            409,
        )
    workspace.name, workspace.currency = body.name, body.currency
    await store.save(workspace)
    await Work(store, actor).audit("workspace.updated", workspace.id)
    return public(workspace)


@app.get("/api/v1/audit")
async def audit(
    actor: Actor, store: StoreDep, limit: Limit = 50, offset: Offset = 0
) -> dict[str, Any]:
    admin(actor)
    return page([public(a) for a in await store.audits()], limit, offset)


@app.get("/api/v1/webhooks")
async def webhooks(actor: Actor, store: StoreDep) -> dict[str, Any]:
    admin(actor)
    return {
        "items": [public(h) for h in await store.webhooks()],
        "deliveries": [public(d) for d in await store.deliveries()],
    }


@app.post("/api/v1/webhooks", status_code=201)
async def create_webhook(body: s.HookInput, actor: Actor, store: StoreDep) -> dict[str, Any]:
    admin(actor)
    validate_url(body.url)
    hook = Webhook(url=body.url, secret=token_urlsafe(32))
    await store.save(hook)
    await Work(store, actor).audit("webhook.created", hook.id)
    return public(hook) | {"secret": hook.secret}


@app.patch("/api/v1/webhooks/{id}")
async def update_webhook(
    id: UUID, body: s.HookUpdate, actor: Actor, store: StoreDep
) -> dict[str, Any]:
    admin(actor)
    hook = next((h for h in await store.webhooks() if h.id == id), None)
    require(hook is not None, "Not found", 404)
    assert hook is not None
    hook.enabled = body.enabled
    if body.rotate_secret:
        hook.secret = token_urlsafe(32)
    await store.save(hook)
    await Work(store, actor).audit("webhook.updated", id)
    return public(hook) | ({"secret": hook.secret} if body.rotate_secret else {})


# API routes are registered before the SPA fallback.
static = Path(__file__).resolve().parents[4] / "frontend" / "dist"
if static.is_dir():

    class SPA(StaticFiles):
        async def get_response(self, path: str, scope: Any) -> Response:
            if path.startswith("api/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            try:
                return await super().get_response(path, scope)
            except Exception as error:
                if getattr(error, "status_code", None) != 404:
                    raise
                return await super().get_response("index.html", scope)

    app.mount("/", SPA(directory=static, html=True), name="web")
