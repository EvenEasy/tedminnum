from decimal import Decimal
from typing import Any
from uuid import UUID

from ted.application.access import AccessPolicy, admin
from ted.application.activity import Activity
from ted.application.ports import (
    BillingQueries,
    IdentityRepository,
    TrackingQueries,
    WorkRepository,
    WorkspaceRepository,
)
from ted.domain.models import (
    Client,
    Project,
    Task,
    User,
)
from ted.domain.rules import require


class WorkManagement:
    def __init__(
        self,
        work: WorkRepository,
        identity: IdentityRepository,
        tracking: TrackingQueries,
        billing: BillingQueries,
        workspace: WorkspaceRepository,
        activity: Activity,
        access: AccessPolicy,
        actor: User,
    ):
        self.work, self.identity, self.tracking, self.billing = work, identity, tracking, billing
        self.workspace, self.activity, self.access, self.actor = workspace, activity, access, actor

    async def create_client(self, name: str, rate: Decimal) -> Client:
        admin(self.actor)
        c = Client(name=name, rate=rate)
        await self.work.save(c)
        return c

    async def update_client(self, id: UUID, name: str, rate: Decimal) -> Client:
        admin(self.actor)
        await self.workspace.workspace(lock=True)
        c = await self.work.client(id)
        c.name, c.rate = name, rate
        await self.work.save(c)
        await self.activity.audit(self.actor, "client.updated", id)
        return c

    async def create_project(
        self, client_id: UUID, name: str, rate: Decimal | None, member_ids: list[UUID]
    ) -> Project:
        admin(self.actor)
        await self.work.client(client_id)
        for id in member_ids:
            require((await self.identity.user(id)).active, "Inactive member")
        p = Project(client_id=client_id, name=name, rate=rate)
        await self.work.save(p)
        await self.work.set_members(p.id, member_ids)
        await self.activity.audit(self.actor, "project.created", p.id)
        return p

    async def update_project(
        self, id: UUID, name: str, rate: Decimal | None, member_ids: list[UUID]
    ) -> Project:
        admin(self.actor)
        await self.workspace.workspace(lock=True)
        p = await self.work.project(id)
        for user_id in member_ids:
            require((await self.identity.user(user_id)).active, "Inactive member")
        for task in await self.work.tasks(self.actor):
            if task.project_id == id:
                require(
                    set(await self.work.assignees(task.id)) <= set(member_ids),
                    "Remove task assignments before removing project membership",
                    409,
                )
        p.name, p.rate = name, rate
        await self.work.set_members(id, member_ids)
        await self.work.save(p)
        await self.activity.audit(self.actor, "project.updated", id)
        return p

    async def create_task(self, project_id: UUID, assignee_ids: list[UUID], **fields: Any) -> Task:
        admin(self.actor)
        await self.workspace.workspace(lock=True)
        await self.work.project(project_id)
        require(
            set(assignee_ids) <= set(await self.work.members(project_id)),
            "Assignees must be project members",
        )
        require(
            fields["billing"] != "fixed" or fields.get("fixed_price") is not None,
            "Fixed tasks need a price",
        )
        task = Task(project_id=project_id, **fields)
        await self.work.save(task)
        await self.work.set_assignees(task.id, assignee_ids)
        await self.activity.audit(self.actor, "task.created", task.id)
        return task

    async def update_task(self, id: UUID, version: int, fields: dict[str, Any]) -> Task:
        await self.workspace.workspace(lock=True)
        await self.access.task(id)
        task = await self.work.task(id, lock=True)
        require(task.version == version, "Task changed; refresh and try again", 409)
        if self.actor.role != "admin":
            require(
                set(fields) <= {"status", "position"},
                "Members may change task status and position only",
                403,
            )
        if "billing" in fields and fields["billing"] != task.billing:
            require(
                not any(e.task_id == id for e in await self.tracking.entries(self.actor)),
                "Billing mode cannot change after time is recorded",
                409,
            )
            require(
                not any(line.source_task_id == id for line in await self.billing.lines()),
                "Billing mode cannot change after invoicing",
                409,
            )
        assignees = fields.pop("assignee_ids", None)
        if assignees is not None:
            require(
                set(assignees) <= set(await self.work.members(task.project_id)),
                "Assignees must be project members",
            )
            await self.work.set_assignees(id, assignees)
        for key, value in fields.items():
            setattr(task, key, value)
        require(task.billing != "fixed" or task.fixed_price is not None, "Fixed tasks need a price")
        task.version += 1
        await self.work.save(task)
        await self.activity.audit(self.actor, "task.updated", id)
        await self.activity.event("task.updated", id)
        return task

    async def move_task(self, id: UUID, version: int, direction: str) -> Task:
        await self.workspace.workspace(lock=True)
        task = await self.access.task(id)
        require(task.version == version, "Task changed; refresh and try again", 409)
        peers = sorted(
            (
                t
                for t in await self.work.tasks(self.actor)
                if t.project_id == task.project_id and t.status == task.status
            ),
            key=lambda t: (t.position, str(t.id)),
        )
        index = next(i for i, t in enumerate(peers) if t.id == id)
        target = index + (-1 if direction == "up" else 1)
        if 0 <= target < len(peers):
            peers[index], peers[target] = peers[target], peers[index]
            for position, peer in enumerate(peers):
                peer.position = position
                peer.version += 1
                await self.work.save(peer)
            await self.activity.audit(self.actor, "task.moved", id)
            await self.activity.event("task.updated", id)
        return next(peer for peer in peers if peer.id == id)
