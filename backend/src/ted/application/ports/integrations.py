from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from ted.domain.models import (
    Delivery,
    Webhook,
)


class IntegrationsQueries(Protocol):
    async def webhooks(self) -> Sequence[Webhook]: ...

    async def deliveries(self) -> Sequence[Delivery]: ...


class IntegrationsRepository(IntegrationsQueries, Protocol):
    async def webhook(self, id: UUID, lock: bool = False) -> Webhook: ...

    async def save(self, *entities: Webhook | Delivery) -> None: ...
