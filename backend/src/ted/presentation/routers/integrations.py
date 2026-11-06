from typing import Any
from uuid import UUID

from fastapi import APIRouter

from ted.application.access import admin
from ted.presentation import schemas as s
from ted.presentation.dependencies import (
    Actor,
    IntegrationService,
    IntegrationsRepo,
)
from ted.presentation.serialization import public

router = APIRouter()


@router.get("/api/v1/webhooks")
async def webhooks(actor: Actor, integrations: IntegrationsRepo) -> dict[str, Any]:
    admin(actor)
    return {
        "items": [public(h) for h in await integrations.webhooks()],
        "deliveries": [public(d) for d in await integrations.deliveries()],
    }


@router.post("/api/v1/webhooks", status_code=201)
async def create_webhook(
    body: s.HookInput, actor: Actor, integration_service: IntegrationService
) -> dict[str, Any]:
    hook = await integration_service.create(actor, body.url)
    return public(hook) | {"secret": hook.secret}


@router.patch("/api/v1/webhooks/{id}")
async def update_webhook(
    id: UUID, body: s.HookUpdate, actor: Actor, integration_service: IntegrationService
) -> dict[str, Any]:
    hook = await integration_service.update(actor, id, body.enabled, body.rotate_secret)
    return public(hook) | ({"secret": hook.secret} if body.rotate_secret else {})
