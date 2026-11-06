from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter

from ted.domain.models import now
from ted.domain.rules import require
from ted.presentation import schemas as s
from ted.presentation.dependencies import (
    Actor,
    BillingRepo,
    Limit,
    Offset,
    TrackingRepo,
    TrackingService,
)
from ted.presentation.serialization import page, public

router = APIRouter()


@router.get("/api/v1/timer")
async def active_timer(actor: Actor, tracking: TrackingRepo) -> dict[str, Any]:
    entry = await tracking.active_entry(actor.id)
    return {"entry": public(entry) if entry else None, "server_time": now().isoformat()}


@router.post("/api/v1/timer", status_code=201)
async def start_timer(
    body: s.TimerStart, actor: Actor, tracking_service: TrackingService
) -> dict[str, Any]:
    return public(
        await tracking_service.start_timer(
            body.request_key, body.task_id, body.kind, body.billable, body.long_break
        )
    )


@router.post("/api/v1/timer/{id}/{command}")
async def timer_command(
    id: UUID, command: str, actor: Actor, tracking_service: TrackingService
) -> dict[str, Any]:
    require(command in {"pause", "resume", "stop"}, "Not found", 404)
    return public(await tracking_service.timer_command(id, command))


@router.get("/api/v1/time")
async def time_entries(
    actor: Actor,
    tracking: TrackingRepo,
    billing: BillingRepo,
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
        for e in await tracking.entries(actor)
        if (since is None or e.started_at >= since)
        and (until is None or e.started_at < until)
        and (task_id is None or e.task_id == task_id)
    ]
    entries.sort(key=lambda e: e.started_at, reverse=True)
    result = [public(e) for e in entries]
    if actor.role == "admin":
        reserved = {line.source_entry_id for line in await billing.lines() if line.reserved}
        for item, entry in zip(result, entries, strict=True):
            item["reserved"] = entry.id in reserved
    return page(result, limit, offset)


@router.get("/api/v1/time/{id}")
async def get_time(id: UUID, actor: Actor, tracking: TrackingRepo) -> dict[str, Any]:
    entry = await tracking.entry(id)
    require(
        entry is not None and (actor.role == "admin" or entry.user_id == actor.id), "Not found", 404
    )
    return public(entry)


@router.patch("/api/v1/time/{id}")
async def edit_time(
    id: UUID, body: s.EntryUpdate, actor: Actor, tracking_service: TrackingService
) -> dict[str, Any]:
    return public(await tracking_service.edit_entry(id, **body.model_dump()))
