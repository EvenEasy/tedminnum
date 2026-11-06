from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ted.domain import models as m

from . import records as r
from .mapping import get, listing, to_domain
from .mapping import save as persist
from .schema import lines, tables


class SqlBillingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def invoice(self, id: UUID) -> m.Invoice:
        return await get(self.db, r.InvoiceRow, m.Invoice, id)

    async def invoice_by_key(self, key: UUID) -> m.Invoice | None:
        row = await self.db.scalar(
            select(r.InvoiceRow).where(tables[r.InvoiceRow].c.request_key == key)
        )
        return to_domain(row, m.Invoice) if row is not None else None

    async def invoices(self) -> Sequence[m.Invoice]:
        return await listing(
            self.db,
            r.InvoiceRow,
            m.Invoice,
        )

    async def lines(self, invoice_id: UUID | None = None) -> Sequence[m.InvoiceLine]:
        return await listing(
            self.db,
            r.InvoiceLineRow,
            m.InvoiceLine,
            *([] if invoice_id is None else [lines.c.invoice_id == invoice_id]),
        )

    async def payments(self, invoice_id: UUID | None = None) -> Sequence[m.Payment]:
        return await listing(
            self.db,
            r.PaymentRow,
            m.Payment,
            *([] if invoice_id is None else [tables[r.PaymentRow].c.invoice_id == invoice_id]),
        )

    async def payment_by_key(self, key: UUID) -> m.Payment | None:
        row = await self.db.scalar(
            select(r.PaymentRow).where(tables[r.PaymentRow].c.request_key == key)
        )
        return to_domain(row, m.Payment) if row is not None else None

    async def save(self, *entities: m.Invoice | m.InvoiceLine | m.Payment) -> None:
        for entity in entities:
            if isinstance(entity, m.Invoice):
                await persist(self.db, r.InvoiceRow, entity)
            elif isinstance(entity, m.InvoiceLine):
                await persist(self.db, r.InvoiceLineRow, entity)
            elif isinstance(entity, m.Payment):
                await persist(self.db, r.PaymentRow, entity)
