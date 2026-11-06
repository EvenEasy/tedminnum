from typing import Protocol

from ted.domain.models import (
    Workspace,
)


class WorkspaceQueries(Protocol):
    async def workspace(self, lock: bool = False) -> Workspace: ...


class WorkspaceRepository(WorkspaceQueries, Protocol):
    async def save(self, *entities: Workspace) -> None: ...
