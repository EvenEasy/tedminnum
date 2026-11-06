from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ted.domain import models as m

from . import records as r
from .mapping import listing, to_domain
from .mapping import save as persist
from .schema import entries


class SqlTrackingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def entry(self, id: UUID, lock: bool = False) -> m.TimeEntry | None:
        row = await self.db.get(r.TimeEntryRow, id, with_for_update=lock, populate_existing=lock)
        return to_domain(row, m.TimeEntry) if row is not None else None

    async def entries(self, actor: m.User) -> Sequence[m.TimeEntry]:
        return await listing(
            self.db,
            r.TimeEntryRow,
            m.TimeEntry,
            *([] if actor.role == "admin" else [entries.c.user_id == actor.id]),
        )

    async def active_entry(self, user_id: UUID) -> m.TimeEntry | None:
        row = await self.db.scalar(
            select(r.TimeEntryRow).where(entries.c.user_id == user_id, entries.c.ended_at.is_(None))
        )
        return to_domain(row, m.TimeEntry) if row is not None else None

    async def overlaps(self, user_id: UUID, start: datetime, end: datetime, exclude: UUID) -> bool:
        return bool(
            await self.db.scalar(
                select(entries.c.id)
                .where(
                    entries.c.user_id == user_id,
                    entries.c.id != exclude,
                    entries.c.started_at < end,
                    or_(entries.c.ended_at.is_(None), entries.c.ended_at > start),
                )
                .limit(1)
            )
        )

    async def save(self, *entities: m.TimeEntry) -> None:
        for entity in entities:
            if isinstance(entity, m.TimeEntry):
                await persist(self.db, r.TimeEntryRow, entity)
