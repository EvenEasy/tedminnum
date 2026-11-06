from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from ted.application.access import admin
from ted.domain.models import now
from ted.infrastructure.runtime import settings
from ted.presentation import schemas as s
from ted.presentation.dependencies import (
    Actor,
    Authentication,
    IdentityRepo,
    IdentityService,
    Limit,
    LogoutOperation,
    Offset,
    PasswordOperation,
    SessionDep,
)
from ted.presentation.serialization import page, public

router = APIRouter()


@router.post("/api/v1/auth/login")
async def login(body: s.Login, response: Response, authentication: Authentication) -> Any:
    result = await authentication.execute(body.email.lower(), body.password, settings.session_hours)
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


@router.get("/api/v1/auth/me")
async def me(
    actor: Actor,
    session: SessionDep,
) -> dict[str, Any]:
    return {"user": public(actor), "csrf": session.csrf, "server_time": now().isoformat()}


@router.post("/api/v1/auth/logout")
async def logout(
    actor: Actor, session: SessionDep, response: Response, logout_operation: LogoutOperation
) -> dict[str, bool]:
    await logout_operation.execute(session.id)
    response.delete_cookie("ted_session", path="/")
    return {"ok": True}


@router.post("/api/v1/auth/password")
async def change_password(
    body: s.PasswordChange, actor: Actor, response: Response, password_operation: PasswordOperation
) -> dict[str, bool]:
    await password_operation.execute(actor, body.current_password, body.new_password)
    response.delete_cookie("ted_session", path="/")
    return {"ok": True}


@router.get("/api/v1/users")
async def users(
    actor: Actor, identity: IdentityRepo, limit: Limit = 50, offset: Offset = 0
) -> dict[str, Any]:
    admin(actor)
    return page([public(u) for u in await identity.users()], limit, offset)


@router.post("/api/v1/users", status_code=201)
async def create_user(
    body: s.UserCreate, actor: Actor, identity_service: IdentityService
) -> dict[str, Any]:
    data = body.model_dump()
    data["email"] = data["email"].lower()
    return public(await identity_service.create_user(actor, **data))


@router.patch("/api/v1/users/{id}")
async def update_user(
    id: UUID, body: s.UserUpdate, actor: Actor, identity_service: IdentityService
) -> dict[str, Any]:
    return public(await identity_service.update_user(actor, id, **body.model_dump()))
