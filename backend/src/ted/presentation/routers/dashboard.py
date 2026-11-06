from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter

from ted.domain.models import now
from ted.domain.rules import require
from ted.presentation.dependencies import (
    Actor,
    FinanceReportOperation,
    TrackingRepo,
    WorkRepo,
)
from ted.presentation.serialization import encode, public

from .work import task_data

router = APIRouter()


@router.get("/api/v1/dashboard")
async def dashboard(
    actor: Actor,
    work: WorkRepo,
    tracking: TrackingRepo,
    finance_report: FinanceReportOperation,
    day_start: datetime | None = None,
) -> dict[str, Any]:
    start = day_start or now().replace(hour=0, minute=0, second=0, microsecond=0)
    require(start.tzinfo is not None, "Use timezone-aware day_start")

    mine = [e for e in await tracking.entries(actor) if e.user_id == actor.id]
    today = [e for e in mine if start <= e.started_at < start + timedelta(days=1)]
    tasks = [
        t
        for t in await work.tasks(actor)
        if actor.id in await work.assignees(t.id) and t.status != "done"
    ]
    active = await tracking.active_entry(actor.id)
    return {
        "work_seconds": sum(e.seconds() for e in today if e.kind == "work"),
        "break_seconds": sum(e.seconds() for e in today if e.kind == "break"),
        "open_tasks": len(tasks),
        "tasks": [await task_data(t, actor, work) for t in tasks[:10]],
        "recent": [public(e) for e in sorted(mine, key=lambda e: e.started_at, reverse=True)[:8]],
        "active": public(active) if active else None,
        "finance": encode(await finance_report.execute()) if actor.role == "admin" else None,
    }
