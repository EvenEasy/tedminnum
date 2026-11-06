from collections.abc import Sequence
from typing import Protocol

from ted.domain.models import (
    Audit,
)


class AuditQueries(Protocol):
    async def audits(self) -> Sequence[Audit]: ...


class AuditRepository(AuditQueries, Protocol):
    async def save(self, *entities: Audit) -> None: ...
