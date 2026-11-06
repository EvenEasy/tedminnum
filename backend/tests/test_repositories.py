from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ted.domain.models import Audit, Client
from ted.infrastructure.database import sessions
from ted.infrastructure.persistence.audit import SqlAuditRepository
from ted.infrastructure.persistence.records import AuditRow, ClientRow, ProjectRow
from ted.infrastructure.persistence.work import SqlWorkRepository
from ted.presentation.api import app


async def test_repository_mapping_flush_and_multi_repository_rollback(clean_database):
    actor = uuid4()
    client = Client(name="Rollback client", rate=Decimal("12.34"))
    # The audit FK deliberately fails after the client flushed. The outer owner rolls both back.
    with pytest.raises(IntegrityError):
        async with sessions() as db, db.begin():
            work = SqlWorkRepository(db)
            await work.save(client)
            detached = await work.client(client.id)
            assert detached.rate == Decimal("12.34")
            detached.name = "Only in memory"
            assert (await work.client(client.id)).name == "Rollback client"
            await SqlAuditRepository(db).save(
                Audit(actor_id=actor, action="test", object_id=str(client.id))
            )
    async with sessions() as db:
        assert await db.get(ClientRow, client.id) is None
        assert not (
            await db.scalars(select(AuditRow).where(AuditRow.object_id == str(client.id)))
        ).all()


async def test_http_failure_rolls_back_already_flushed_project(admin, work, monkeypatch):
    async def fail(*args, **kwargs):
        raise RuntimeError("Injected audit failure")

    monkeypatch.setattr(SqlAuditRepository, "save", fail)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        cookies=admin.cookies,
        headers=dict(admin.headers),
    ) as client:
        response = await client.post(
            "/api/v1/projects",
            json={"name": "Must roll back", "client_id": work["client"]["id"], "member_ids": []},
        )
        assert response.status_code == 500
    async with sessions() as db:
        assert not (
            await db.scalars(select(ProjectRow).where(ProjectRow.name == "Must roll back"))
        ).all()
