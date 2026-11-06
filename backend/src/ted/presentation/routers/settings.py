from typing import Any

from fastapi import APIRouter

from ted.application.access import admin
from ted.presentation import schemas as s
from ted.presentation.dependencies import (
    Actor,
    AuditRepo,
    Limit,
    Offset,
    PreferencesOperation,
    WorkspaceRepo,
    WorkspaceService,
)
from ted.presentation.serialization import page, public

router = APIRouter()


@router.get("/api/v1/settings")
async def get_settings(actor: Actor, workspace: WorkspaceRepo) -> dict[str, Any]:
    return {"workspace": public(await workspace.workspace()), "preferences": public(actor)}


@router.patch("/api/v1/settings/preferences")
async def preferences(
    body: s.Preferences, actor: Actor, preferences_operation: PreferencesOperation
) -> dict[str, Any]:
    return public(await preferences_operation.execute(actor, **body.model_dump()))


@router.patch("/api/v1/settings/workspace")
async def workspace_settings(
    body: s.WorkspaceInput, actor: Actor, workspace_service: WorkspaceService
) -> dict[str, Any]:
    return public(await workspace_service.update(actor, body.name, body.currency))


@router.get("/api/v1/audit")
async def audit(
    actor: Actor, audit: AuditRepo, limit: Limit = 50, offset: Offset = 0
) -> dict[str, Any]:
    admin(actor)
    return page([public(a) for a in await audit.audits()], limit, offset)
