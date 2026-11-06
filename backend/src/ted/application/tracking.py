from datetime import datetime, timedelta
from uuid import UUID

from ted.application.access import AccessPolicy
from ted.application.activity import Activity
from ted.application.ports import (
    BillingQueries,
    IdentityRepository,
    TrackingRepository,
    WorkQueries,
    WorkspaceRepository,
)
from ted.domain.models import (
    TimeEntry,
    User,
    now,
)
from ted.domain.rules import require


class Tracking:
    def __init__(
        self,
        tracking: TrackingRepository,
        identity: IdentityRepository,
        work: WorkQueries,
        billing: BillingQueries,
        workspace: WorkspaceRepository,
        activity: Activity,
        access: AccessPolicy,
        actor: User,
    ):
        self.tracking, self.identity, self.work, self.billing = tracking, identity, work, billing
        self.workspace, self.activity, self.access, self.actor = workspace, activity, access, actor

    async def start_timer(
        self, key: UUID, task_id: UUID | None, kind: str, billable: bool, long_break: bool = False
    ) -> TimeEntry:
        await self.identity.user(self.actor.id, lock=True)
        existing = await self.tracking.entry(key)
        if existing is not None:
            require(existing.user_id == self.actor.id, "Not found", 404)
            require(
                existing.task_id == task_id and existing.kind == kind,
                "Request key was used for another timer",
                409,
            )
            return existing
        if task_id is not None:
            task = await self.access.task(task_id)
            billable = billable and task.billing != "nonbillable"
        else:
            billable = False
        require(
            await self.tracking.active_entry(self.actor.id) is None,
            "Stop your active timer first",
            409,
        )
        entry = TimeEntry(
            id=key,
            user_id=self.actor.id,
            task_id=task_id,
            kind=kind,
            billable=billable and kind == "work",
            target_seconds=60
            * (
                self.actor.work_minutes
                if kind == "work"
                else self.actor.long_break
                if long_break
                else self.actor.short_break
            ),
        )
        await self.tracking.save(entry)
        return entry

    async def timer_command(self, id: UUID, command: str) -> TimeEntry:
        await self.identity.user(self.actor.id, lock=True)
        entry = await self.tracking.entry(id, lock=True)
        require(entry is not None and entry.user_id == self.actor.id, "Not found", 404)
        assert entry is not None
        if entry.ended_at is not None:
            require(command == "stop", "Timer is already stopped", 409)
            return entry
        at = now()
        if command == "pause" and entry.paused_at is None:
            entry.paused_at = at
        elif command == "resume" and entry.paused_at is not None:
            entry.paused_microseconds += (at - entry.paused_at) // timedelta(microseconds=1)
            entry.paused_at = None
        elif command == "stop":
            if entry.paused_at is not None:
                entry.paused_microseconds += (at - entry.paused_at) // timedelta(microseconds=1)
                entry.paused_at = None
            entry.ended_at = at
            await self.activity.audit(self.actor, "timer.stopped", id)
            await self.activity.event("timer.stopped", id)
        await self.tracking.save(entry)
        return entry

    async def edit_entry(
        self, id: UUID, started_at: datetime, ended_at: datetime, billable: bool, note: str
    ) -> TimeEntry:
        await self.workspace.workspace(lock=True)
        entry = await self.tracking.entry(id)
        require(
            entry is not None and (self.actor.role == "admin" or entry.user_id == self.actor.id),
            "Not found",
            404,
        )
        assert entry is not None
        await self.identity.user(entry.user_id, lock=True)
        entry = await self.tracking.entry(id, lock=True)
        assert entry is not None
        require(entry.ended_at is not None, "Stop the timer before editing", 409)
        require(
            not any(
                line.reserved and line.source_entry_id == id for line in await self.billing.lines()
            ),
            "Reserved or invoiced time cannot be edited",
            409,
        )
        require(started_at < ended_at <= now(), "Use a valid past UTC interval")
        require(
            not await self.tracking.overlaps(entry.user_id, started_at, ended_at, id),
            "Time entries cannot overlap",
            409,
        )
        assert entry.ended_at is not None
        before = f"{entry.started_at.isoformat()}/{entry.ended_at.isoformat()}; paused={entry.paused_microseconds}; billable={entry.billable}"
        if entry.task_id is not None:
            task = await self.work.task(entry.task_id)
            billable = billable and task.billing != "nonbillable"
        else:
            billable = False
        entry.started_at, entry.ended_at = started_at, ended_at
        entry.billable = billable and entry.kind == "work"
        entry.paused_microseconds = 0
        entry.note = note
        await self.tracking.save(entry)
        await self.activity.audit(
            self.actor,
            "time.adjusted",
            id,
            before
            + f" -> {started_at.isoformat()}/{ended_at.isoformat()}; billable={entry.billable}",
        )
        return entry
