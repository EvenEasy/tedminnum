from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from ted.domain.models import (
    TimeEntry,
    User,
)


class TrackingQueries(Protocol):
    async def entry(self, id: UUID, lock: bool = False) -> TimeEntry | None: ...

    async def entries(self, actor: User) -> Sequence[TimeEntry]: ...

    async def active_entry(self, user_id: UUID) -> TimeEntry | None: ...

    async def overlaps(
        self, user_id: UUID, start: datetime, end: datetime, exclude: UUID
    ) -> bool: ...


class TrackingRepository(TrackingQueries, Protocol):
    async def save(self, *entities: TimeEntry) -> None: ...
