from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ted.domain import models as m
from ted.domain.rules import Problem

from . import records as r
from .mapping import listing, to_domain
from .mapping import save as persist
from .schema import tables


class SqlIntegrationsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def webhooks(self) -> Sequence[m.Webhook]:
        return await listing(
            self.db,
            r.WebhookRow,
            m.Webhook,
        )

    async def deliveries(self) -> Sequence[m.Delivery]:
        rows = (
            await self.db.scalars(
                select(r.DeliveryRow)
                .order_by(tables[r.DeliveryRow].c.next_attempt.desc())
                .limit(500)
            )
        ).all()
        return [to_domain(row, m.Delivery) for row in rows]

    async def save(self, *entities: m.Webhook | m.Delivery) -> None:
        for entity in entities:
            if isinstance(entity, m.Webhook):
                await persist(self.db, r.WebhookRow, entity)
            elif isinstance(entity, m.Delivery):
                await persist(self.db, r.DeliveryRow, entity)

    async def webhook(self, id: UUID, lock: bool = False) -> m.Webhook:
        # NO KEY UPDATE serializes edits but permits outbox foreign-key KEY SHARE locks.
        # A stronger UPDATE lock can deadlock against timer stop's user/audit locks.
        row = await self.db.get(
            r.WebhookRow,
            id,
            with_for_update={"key_share": True} if lock else None,
            populate_existing=lock,
        )
        if row is None:
            raise Problem("Not found", 404)
        return to_domain(row, m.Webhook)
