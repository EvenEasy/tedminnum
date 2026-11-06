from sqlalchemy.ext.asyncio import AsyncSession

from ted.domain import models as m

from . import records as r
from .mapping import get
from .mapping import save as persist


class SqlWorkspaceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def workspace(self, lock: bool = False) -> m.Workspace:
        return await get(self.db, r.WorkspaceRow, m.Workspace, 1, lock)

    async def save(self, *entities: m.Workspace) -> None:
        for entity in entities:
            if isinstance(entity, m.Workspace):
                await persist(self.db, r.WorkspaceRow, entity)
