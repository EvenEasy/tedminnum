from uuid import UUID

from ted.application.ports import (
    WorkQueries,
)
from ted.domain.models import (
    Client,
    Project,
    Task,
    User,
)
from ted.domain.rules import require


def admin(actor: User) -> None:
    require(actor.role == "admin", "Administrator access required", 403)


class AccessPolicy:
    def __init__(self, work: WorkQueries, actor: User):
        self.work, self.actor = work, actor

    async def project(self, id: UUID) -> Project:
        p = await self.work.project(id)
        require(
            self.actor.role == "admin" or self.actor.id in await self.work.members(id),
            "Not found",
            404,
        )
        return p

    async def task(self, id: UUID) -> Task:
        task = await self.work.task(id)
        await self.project(task.project_id)
        require(
            self.actor.role == "admin" or self.actor.id in await self.work.assignees(id),
            "Not found",
            404,
        )
        return task

    async def client(self, id: UUID) -> Client:
        require(id in [c.id for c in await self.work.clients(self.actor)], "Not found", 404)
        return await self.work.client(id)
