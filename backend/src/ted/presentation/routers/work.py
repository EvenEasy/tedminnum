from typing import Any
from uuid import UUID

from fastapi import APIRouter

from ted.application.ports import WorkRepository
from ted.domain.models import Project, Task, User
from ted.presentation import schemas as s
from ted.presentation.dependencies import (
    Access,
    Actor,
    Limit,
    Offset,
    WorkRepo,
    WorkService,
)
from ted.presentation.serialization import encode, page, public

router = APIRouter()


@router.get("/api/v1/clients")
async def clients(
    actor: Actor, work: WorkRepo, limit: Limit = 50, offset: Offset = 0
) -> dict[str, Any]:
    return page([public(c, actor) for c in await work.clients(actor)], limit, offset)


@router.get("/api/v1/clients/{id}")
async def client(id: UUID, actor: Actor, access: Access) -> dict[str, Any]:
    return public(await access.client(id), actor)


@router.post("/api/v1/clients", status_code=201)
async def create_client(
    body: s.ClientInput, actor: Actor, work_service: WorkService
) -> dict[str, Any]:
    return public(await work_service.create_client(**body.model_dump()))


@router.patch("/api/v1/clients/{id}")
async def update_client(
    id: UUID, body: s.ClientInput, actor: Actor, work_service: WorkService
) -> dict[str, Any]:
    return public(await work_service.update_client(id, **body.model_dump()))


async def project_data(project: Project, actor: User, work: WorkRepository) -> dict[str, Any]:
    result = public(project, actor)
    if actor.role == "admin":
        result["member_ids"] = encode(await work.members(project.id))
    return result


@router.get("/api/v1/projects")
async def projects(
    actor: Actor,
    work: WorkRepo,
    limit: Limit = 50,
    offset: Offset = 0,
    client_id: UUID | None = None,
) -> dict[str, Any]:
    return page(
        [
            await project_data(p, actor, work)
            for p in await work.projects(actor)
            if client_id is None or p.client_id == client_id
        ],
        limit,
        offset,
    )


@router.get("/api/v1/projects/{id}")
async def project(work: WorkRepo, id: UUID, actor: Actor, access: Access) -> dict[str, Any]:
    return await project_data(await access.project(id), actor, work)


@router.post("/api/v1/projects", status_code=201)
async def create_project(
    work: WorkRepo, body: s.ProjectCreate, actor: Actor, work_service: WorkService
) -> dict[str, Any]:
    return await project_data(await work_service.create_project(**body.model_dump()), actor, work)


@router.patch("/api/v1/projects/{id}")
async def update_project(
    work: WorkRepo, id: UUID, body: s.ProjectInput, actor: Actor, work_service: WorkService
) -> dict[str, Any]:
    return await project_data(
        await work_service.update_project(id, **body.model_dump()), actor, work
    )


async def task_data(task: Task, actor: User, work: WorkRepository) -> dict[str, Any]:
    return public(task, actor) | {"assignee_ids": encode(await work.assignees(task.id))}


@router.get("/api/v1/tasks")
async def tasks(
    actor: Actor,
    work: WorkRepo,
    limit: Limit = 50,
    offset: Offset = 0,
    project_id: UUID | None = None,
    status: str | None = None,
    q: str = "",
) -> dict[str, Any]:
    result = [
        t
        for t in await work.tasks(actor)
        if (project_id is None or t.project_id == project_id)
        and (status is None or t.status == status)
        and q.lower() in t.title.lower()
    ]
    result.sort(key=lambda t: (t.position, str(t.id)))
    return page([await task_data(t, actor, work) for t in result], limit, offset)


@router.get("/api/v1/tasks/{id}")
async def task(work: WorkRepo, id: UUID, actor: Actor, access: Access) -> dict[str, Any]:
    return await task_data(await access.task(id), actor, work)


@router.post("/api/v1/tasks", status_code=201)
async def create_task(
    work: WorkRepo, body: s.TaskCreate, actor: Actor, work_service: WorkService
) -> dict[str, Any]:
    return await task_data(await work_service.create_task(**body.model_dump()), actor, work)


@router.patch("/api/v1/tasks/{id}")
async def update_task(
    work: WorkRepo, id: UUID, body: s.TaskUpdate, actor: Actor, work_service: WorkService
) -> dict[str, Any]:
    return await task_data(
        await work_service.update_task(
            id, body.version, body.model_dump(exclude_unset=True, exclude={"version"})
        ),
        actor,
        work,
    )


@router.post("/api/v1/tasks/{id}/move")
async def move_task(
    work: WorkRepo, id: UUID, body: s.TaskMove, actor: Actor, work_service: WorkService
) -> dict[str, Any]:
    return await task_data(
        await work_service.move_task(id, body.version, body.direction), actor, work
    )
