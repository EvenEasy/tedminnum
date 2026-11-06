from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ted.domain import models as m

from . import records as r
from .mapping import get, listing
from .mapping import save as persist
from .schema import tables


class SqlWorkRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def client(self, id: UUID) -> m.Client:
        return await get(self.db, r.ClientRow, m.Client, id)

    async def clients(self, actor: m.User) -> Sequence[m.Client]:
        if actor.role == "admin":
            return await listing(
                self.db,
                r.ClientRow,
                m.Client,
            )
        projects = await self.projects(actor)
        return await listing(
            self.db,
            r.ClientRow,
            m.Client,
            tables[r.ClientRow].c.id.in_([p.client_id for p in projects]),
        )

    async def project(self, id: UUID) -> m.Project:
        return await get(self.db, r.ProjectRow, m.Project, id)

    async def projects(self, actor: m.User) -> Sequence[m.Project]:
        filters = (
            []
            if actor.role == "admin"
            else [
                tables[r.ProjectRow].c.id.in_(
                    select(tables[r.MembershipRow].c.project_id).where(
                        tables[r.MembershipRow].c.user_id == actor.id
                    )
                )
            ]
        )
        return await listing(self.db, r.ProjectRow, m.Project, *filters)

    async def members(self, project_id: UUID) -> list[UUID]:
        return list(
            (
                await self.db.scalars(
                    select(tables[r.MembershipRow].c.user_id).where(
                        tables[r.MembershipRow].c.project_id == project_id
                    )
                )
            ).all()
        )

    async def set_members(self, project_id: UUID, ids: list[UUID]) -> None:
        await self.db.execute(
            delete(r.MembershipRow).where(tables[r.MembershipRow].c.project_id == project_id)
        )
        await self._save_membership(project_id, ids)

    async def task(self, id: UUID, lock: bool = False) -> m.Task:
        return await get(self.db, r.TaskRow, m.Task, id, lock)

    async def tasks(self, actor: m.User) -> Sequence[m.Task]:
        filters = (
            []
            if actor.role == "admin"
            else [
                tables[r.TaskRow].c.id.in_(
                    select(tables[r.AssignmentRow].c.task_id).where(
                        tables[r.AssignmentRow].c.user_id == actor.id
                    )
                ),
                tables[r.TaskRow].c.project_id.in_([p.id for p in await self.projects(actor)]),
            ]
        )
        return await listing(self.db, r.TaskRow, m.Task, *filters)

    async def assignees(self, task_id: UUID) -> list[UUID]:
        return list(
            (
                await self.db.scalars(
                    select(tables[r.AssignmentRow].c.user_id).where(
                        tables[r.AssignmentRow].c.task_id == task_id
                    )
                )
            ).all()
        )

    async def set_assignees(self, task_id: UUID, ids: list[UUID]) -> None:
        await self.db.execute(
            delete(r.AssignmentRow).where(tables[r.AssignmentRow].c.task_id == task_id)
        )
        await self._save_assignment(task_id, ids)

    async def save(self, *entities: m.Client | m.Project | m.Task) -> None:
        for entity in entities:
            if isinstance(entity, m.Client):
                await persist(self.db, r.ClientRow, entity)
            elif isinstance(entity, m.Project):
                await persist(self.db, r.ProjectRow, entity)
            elif isinstance(entity, m.Task):
                await persist(self.db, r.TaskRow, entity)

    async def _save_membership(self, project_id: UUID, ids: list[UUID]) -> None:
        for id in set(ids):
            await persist(self.db, r.MembershipRow, m.Membership(project_id=project_id, user_id=id))

    async def _save_assignment(self, task_id: UUID, ids: list[UUID]) -> None:
        for id in set(ids):
            await persist(self.db, r.AssignmentRow, m.Assignment(task_id=task_id, user_id=id))
