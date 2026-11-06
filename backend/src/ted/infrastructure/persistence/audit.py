from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ted.domain import models as m

from . import records as r
from .mapping import save as persist
from .mapping import to_domain
from .schema import tables


class SqlAuditRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def audits(self) -> Sequence[m.Audit]:
        rows = (
            await self.db.scalars(
                select(r.AuditRow).order_by(tables[r.AuditRow].c.created_at.desc()).limit(1000)
            )
        ).all()
        return [to_domain(row, m.Audit) for row in rows]

    async def save(self, *entities: m.Audit) -> None:
        for entity in entities:
            if isinstance(entity, m.Audit):
                await persist(self.db, r.AuditRow, entity)
