from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from ted.domain.models import (
    Invoice,
    InvoiceLine,
    Payment,
)


class BillingQueries(Protocol):
    async def invoice(self, id: UUID) -> Invoice: ...

    async def invoice_by_key(self, key: UUID) -> Invoice | None: ...

    async def invoices(self) -> Sequence[Invoice]: ...

    async def lines(self, invoice_id: UUID | None = None) -> Sequence[InvoiceLine]: ...

    async def payments(self, invoice_id: UUID | None = None) -> Sequence[Payment]: ...

    async def payment_by_key(self, key: UUID) -> Payment | None: ...


class BillingRepository(BillingQueries, Protocol):
    async def save(self, *entities: Invoice | InvoiceLine | Payment) -> None: ...
