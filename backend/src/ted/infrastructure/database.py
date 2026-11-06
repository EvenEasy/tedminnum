from collections.abc import Sequence
from datetime import datetime
from typing import Any, TypeVar, cast
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    delete,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import registry

from ted.domain import models as m
from ted.domain.rules import Problem
from ted.infrastructure.config import settings

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
    }
)
mapper = registry(metadata=metadata)
tables: dict[type[Any], Table] = {}


def col(name: str, type_: Any, *, nullable: bool = False, **kw: Any) -> Column[Any]:
    return Column(name, type_, nullable=nullable, **kw)


def ref(name: str, target: str, nullable: bool = False) -> Column[Any]:
    return Column(name, Uuid, ForeignKey(target), nullable=nullable, index=True)


def table(cls: type[Any], name: str, *columns: Any) -> Table:
    t = Table(name, metadata, col("id", Uuid, primary_key=True), *columns)
    mapper.map_imperatively(cls, t)
    tables[cls] = t
    return t


workspace = Table(
    "workspace",
    metadata,
    col("id", Integer, primary_key=True),
    col("currency", String(3)),
    col("name", String(200)),
    col("next_invoice", Integer),
    CheckConstraint("id = 1", name="singleton"),
    CheckConstraint("next_invoice > 0", name="number"),
)
mapper.map_imperatively(m.Workspace, workspace)
users = table(
    m.User,
    "users",
    col("email", String(254), unique=True),
    col("name", String(200)),
    col("password_hash", Text),
    col("role", String(10)),
    col("active", Boolean),
    col("work_minutes", Integer),
    col("short_break", Integer),
    col("long_break", Integer),
    col("notifications", Boolean),
    col("failed_logins", Integer),
    col("locked_until", DateTime(timezone=True), nullable=True),
    CheckConstraint("role IN ('admin', 'member')", name="role"),
    CheckConstraint(
        "work_minutes BETWEEN 1 AND 180 AND short_break BETWEEN 1 AND 60 AND long_break BETWEEN 1 AND 120",
        name="focus",
    ),
)
table(
    m.LoginSession,
    "sessions",
    ref("user_id", "users.id"),
    col("token_hash", String(64), unique=True),
    col("csrf", String(100)),
    col("expires_at", DateTime(timezone=True)),
)
table(
    m.Client,
    "clients",
    col("name", String(200)),
    col("rate", Numeric(14, 2)),
    CheckConstraint("rate >= 0", name="rate"),
)
table(
    m.Project,
    "projects",
    ref("client_id", "clients.id"),
    col("name", String(200)),
    col("rate", Numeric(14, 2), nullable=True),
    CheckConstraint("rate >= 0", name="rate"),
)
table(
    m.Membership,
    "memberships",
    ref("project_id", "projects.id"),
    ref("user_id", "users.id"),
    UniqueConstraint("project_id", "user_id"),
)
table(
    m.Task,
    "tasks",
    ref("project_id", "projects.id"),
    col("title", String(200)),
    col("description", Text),
    col("status", String(20)),
    col("priority", String(20)),
    col("due_date", Date, nullable=True),
    col("estimate_minutes", Integer, nullable=True),
    col("position", Integer),
    col("billing", String(20)),
    col("rate", Numeric(14, 2), nullable=True),
    col("fixed_price", Numeric(14, 2), nullable=True),
    col("version", Integer),
    CheckConstraint("status IN ('backlog','in_progress','done')", name="status"),
    CheckConstraint("priority IN ('low','normal','high','urgent')", name="priority"),
    CheckConstraint("billing IN ('hourly','fixed','nonbillable')", name="billing"),
    CheckConstraint("rate >= 0 AND (fixed_price IS NULL OR fixed_price >= 0)", name="rate"),
    CheckConstraint("billing != 'fixed' OR fixed_price IS NOT NULL", name="fixed_price"),
)
table(
    m.Assignment,
    "assignments",
    ref("task_id", "tasks.id"),
    ref("user_id", "users.id"),
    UniqueConstraint("task_id", "user_id"),
)
entries = table(
    m.TimeEntry,
    "time_entries",
    ref("user_id", "users.id"),
    ref("task_id", "tasks.id", True),
    col("kind", String(10)),
    col("billable", Boolean),
    col("started_at", DateTime(timezone=True)),
    col("ended_at", DateTime(timezone=True), nullable=True),
    col("paused_at", DateTime(timezone=True), nullable=True),
    col("paused_microseconds", BigInteger),
    col("note", Text),
    col("target_seconds", Integer),
    CheckConstraint("kind IN ('work','break')", name="kind"),
    CheckConstraint("NOT billable OR (kind = 'work' AND task_id IS NOT NULL)", name="billable"),
    CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="end"),
    CheckConstraint("paused_microseconds >= 0", name="pause"),
)
Index(
    "one_active_timer_per_user",
    entries.c.user_id,
    unique=True,
    postgresql_where=entries.c.ended_at.is_(None),
)
table(
    m.Invoice,
    "invoices",
    ref("client_id", "clients.id"),
    col("request_key", Uuid, unique=True),
    col("request_fingerprint", String(64)),
    col("currency", String(3)),
    col("client_name", String(200)),
    col("issuer_name", String(200)),
    col("number", String(40), unique=True),
    col("status", String(20)),
    col("created_at", DateTime(timezone=True)),
    col("issued_at", DateTime(timezone=True), nullable=True),
    col("total", Numeric(16, 2)),
    CheckConstraint("total >= 0", name="total"),
    CheckConstraint("status IN ('draft','issued','partially_paid','paid','void')", name="status"),
)
lines = table(
    m.InvoiceLine,
    "invoice_lines",
    ref("invoice_id", "invoices.id"),
    col("description", Text),
    col("quantity", Numeric(18, 9)),
    col("rate", Numeric(14, 2)),
    col("amount", Numeric(16, 2)),
    ref("source_entry_id", "time_entries.id", True),
    ref("source_task_id", "tasks.id", True),
    col("reserved", Boolean),
    CheckConstraint("(source_entry_id IS NULL) != (source_task_id IS NULL)", name="one_source"),
    CheckConstraint("quantity >= 0 AND rate >= 0 AND amount >= 0", name="amount"),
)
Index(
    "one_invoice_per_entry",
    lines.c.source_entry_id,
    unique=True,
    postgresql_where=lines.c.reserved.is_(True),
)
Index(
    "one_invoice_per_fixed_task",
    lines.c.source_task_id,
    unique=True,
    postgresql_where=lines.c.reserved.is_(True),
)
table(
    m.Payment,
    "payments",
    ref("invoice_id", "invoices.id"),
    col("request_key", Uuid, unique=True),
    col("amount", Numeric(16, 2)),
    col("currency", String(3)),
    col("paid_on", Date),
    col("reference", String(200)),
    col("created_at", DateTime(timezone=True)),
    CheckConstraint("amount > 0", name="amount"),
)
table(
    m.Audit,
    "audit",
    ref("actor_id", "users.id"),
    col("action", String(60)),
    col("object_id", String(100)),
    col("detail", Text),
    col("created_at", DateTime(timezone=True)),
)
table(
    m.Webhook,
    "webhooks",
    col("url", String(2000)),
    col("secret", String(100)),
    col("enabled", Boolean),
)
table(
    m.Delivery,
    "deliveries",
    ref("webhook_id", "webhooks.id"),
    col("event", String(60)),
    col("payload", Text),
    col("attempts", Integer),
    col("next_attempt", DateTime(timezone=True)),
    col("delivered_at", DateTime(timezone=True), nullable=True),
    col("status_code", Integer, nullable=True),
)

engine = create_async_engine(
    settings.database_url, pool_size=5, max_overflow=5, hide_parameters=True
)
sessions = async_sessionmaker(engine, expire_on_commit=False)
T = TypeVar("T")


class SqlStore:
    def __init__(self, session: AsyncSession):
        self.db = session

    async def _get(self, cls: type[T], id: Any, lock: bool = False) -> T:
        item = await self.db.get(cls, id, with_for_update=lock, populate_existing=lock)
        if item is None:
            raise Problem("Not found", 404)
        return item

    async def _list(self, cls: type[T], *filters: Any) -> Sequence[T]:
        return (await self.db.scalars(select(cls).where(*filters))).all()

    async def workspace(self, lock: bool = False) -> m.Workspace:
        return await self._get(m.Workspace, 1, lock)

    async def user(self, id: UUID, lock: bool = False) -> m.User:
        return await self._get(m.User, id, lock)

    async def user_by_email(self, email: str) -> m.User | None:
        return cast(
            m.User | None,
            await self.db.scalar(select(m.User).where(users.c.email == email).with_for_update()),
        )

    async def users(self) -> Sequence[m.User]:
        return await self._list(m.User)

    async def session(self, token_hash: str) -> m.LoginSession | None:
        return cast(
            m.LoginSession | None,
            await self.db.scalar(
                select(m.LoginSession).where(tables[m.LoginSession].c.token_hash == token_hash)
            ),
        )

    async def delete_sessions(self, user_id: UUID) -> None:
        await self.db.execute(
            delete(m.LoginSession).where(tables[m.LoginSession].c.user_id == user_id)
        )

    async def client(self, id: UUID) -> m.Client:
        return await self._get(m.Client, id)

    async def clients(self, actor: m.User) -> Sequence[m.Client]:
        if actor.role == "admin":
            return await self._list(m.Client)
        projects = await self.projects(actor)
        return await self._list(
            m.Client, tables[m.Client].c.id.in_([p.client_id for p in projects])
        )

    async def project(self, id: UUID) -> m.Project:
        return await self._get(m.Project, id)

    async def projects(self, actor: m.User) -> Sequence[m.Project]:
        filters = (
            []
            if actor.role == "admin"
            else [
                tables[m.Project].c.id.in_(
                    select(tables[m.Membership].c.project_id).where(
                        tables[m.Membership].c.user_id == actor.id
                    )
                )
            ]
        )
        return await self._list(m.Project, *filters)

    async def members(self, project_id: UUID) -> list[UUID]:
        return list(
            (
                await self.db.scalars(
                    select(tables[m.Membership].c.user_id).where(
                        tables[m.Membership].c.project_id == project_id
                    )
                )
            ).all()
        )

    async def set_members(self, project_id: UUID, ids: list[UUID]) -> None:
        await self.db.execute(
            delete(m.Membership).where(tables[m.Membership].c.project_id == project_id)
        )
        await self.save(*(m.Membership(project_id=project_id, user_id=id) for id in set(ids)))

    async def task(self, id: UUID, lock: bool = False) -> m.Task:
        return await self._get(m.Task, id, lock)

    async def tasks(self, actor: m.User) -> Sequence[m.Task]:
        filters = (
            []
            if actor.role == "admin"
            else [
                tables[m.Task].c.id.in_(
                    select(tables[m.Assignment].c.task_id).where(
                        tables[m.Assignment].c.user_id == actor.id
                    )
                ),
                tables[m.Task].c.project_id.in_([p.id for p in await self.projects(actor)]),
            ]
        )
        return await self._list(m.Task, *filters)

    async def assignees(self, task_id: UUID) -> list[UUID]:
        return list(
            (
                await self.db.scalars(
                    select(tables[m.Assignment].c.user_id).where(
                        tables[m.Assignment].c.task_id == task_id
                    )
                )
            ).all()
        )

    async def set_assignees(self, task_id: UUID, ids: list[UUID]) -> None:
        await self.db.execute(delete(m.Assignment).where(tables[m.Assignment].c.task_id == task_id))
        await self.save(*(m.Assignment(task_id=task_id, user_id=id) for id in set(ids)))

    async def entry(self, id: UUID, lock: bool = False) -> m.TimeEntry | None:
        return await self.db.get(m.TimeEntry, id, with_for_update=lock, populate_existing=lock)

    async def entries(self, actor: m.User) -> Sequence[m.TimeEntry]:
        return await self._list(
            m.TimeEntry, *([] if actor.role == "admin" else [entries.c.user_id == actor.id])
        )

    async def active_entry(self, user_id: UUID) -> m.TimeEntry | None:
        return cast(
            m.TimeEntry | None,
            await self.db.scalar(
                select(m.TimeEntry).where(
                    entries.c.user_id == user_id, entries.c.ended_at.is_(None)
                )
            ),
        )

    async def overlaps(self, user_id: UUID, start: datetime, end: datetime, exclude: UUID) -> bool:
        return bool(
            await self.db.scalar(
                select(entries.c.id)
                .where(
                    entries.c.user_id == user_id,
                    entries.c.id != exclude,
                    entries.c.started_at < end,
                    or_(entries.c.ended_at.is_(None), entries.c.ended_at > start),
                )
                .limit(1)
            )
        )

    async def invoice(self, id: UUID) -> m.Invoice:
        return await self._get(m.Invoice, id)

    async def invoice_by_key(self, key: UUID) -> m.Invoice | None:
        return cast(
            m.Invoice | None,
            await self.db.scalar(select(m.Invoice).where(tables[m.Invoice].c.request_key == key)),
        )

    async def invoices(self) -> Sequence[m.Invoice]:
        return await self._list(m.Invoice)

    async def lines(self, invoice_id: UUID | None = None) -> Sequence[m.InvoiceLine]:
        return await self._list(
            m.InvoiceLine, *([] if invoice_id is None else [lines.c.invoice_id == invoice_id])
        )

    async def payments(self, invoice_id: UUID | None = None) -> Sequence[m.Payment]:
        return await self._list(
            m.Payment,
            *([] if invoice_id is None else [tables[m.Payment].c.invoice_id == invoice_id]),
        )

    async def payment_by_key(self, key: UUID) -> m.Payment | None:
        return cast(
            m.Payment | None,
            await self.db.scalar(select(m.Payment).where(tables[m.Payment].c.request_key == key)),
        )

    async def audits(self) -> Sequence[m.Audit]:
        return (
            await self.db.scalars(
                select(m.Audit).order_by(tables[m.Audit].c.created_at.desc()).limit(1000)
            )
        ).all()

    async def webhooks(self) -> Sequence[m.Webhook]:
        return await self._list(m.Webhook)

    async def deliveries(self) -> Sequence[m.Delivery]:
        return (
            await self.db.scalars(
                select(m.Delivery).order_by(tables[m.Delivery].c.next_attempt.desc()).limit(500)
            )
        ).all()

    async def save(self, *entities: object) -> None:
        self.db.add_all(entities)
        await self.db.flush()
