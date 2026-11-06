from typing import Any

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
)
from sqlalchemy.orm import registry

from ted.infrastructure.persistence import records as m

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
mapper.map_imperatively(m.WorkspaceRow, workspace)
users = table(
    m.UserRow,
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
    m.LoginSessionRow,
    "sessions",
    ref("user_id", "users.id"),
    col("token_hash", String(64), unique=True),
    col("csrf", String(100)),
    col("expires_at", DateTime(timezone=True)),
)
table(
    m.ClientRow,
    "clients",
    col("name", String(200)),
    col("rate", Numeric(14, 2)),
    CheckConstraint("rate >= 0", name="rate"),
)
table(
    m.ProjectRow,
    "projects",
    ref("client_id", "clients.id"),
    col("name", String(200)),
    col("rate", Numeric(14, 2), nullable=True),
    CheckConstraint("rate >= 0", name="rate"),
)
table(
    m.MembershipRow,
    "memberships",
    ref("project_id", "projects.id"),
    ref("user_id", "users.id"),
    UniqueConstraint("project_id", "user_id"),
)
table(
    m.TaskRow,
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
    m.AssignmentRow,
    "assignments",
    ref("task_id", "tasks.id"),
    ref("user_id", "users.id"),
    UniqueConstraint("task_id", "user_id"),
)
entries = table(
    m.TimeEntryRow,
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
    m.InvoiceRow,
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
    m.InvoiceLineRow,
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
    m.PaymentRow,
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
    m.AuditRow,
    "audit",
    ref("actor_id", "users.id"),
    col("action", String(60)),
    col("object_id", String(100)),
    col("detail", Text),
    col("created_at", DateTime(timezone=True)),
)
table(
    m.WebhookRow,
    "webhooks",
    col("url", String(2000)),
    col("secret", String(100)),
    col("enabled", Boolean),
)
table(
    m.DeliveryRow,
    "deliveries",
    ref("webhook_id", "webhooks.id"),
    col("event", String(60)),
    col("payload", Text),
    col("attempts", Integer),
    col("next_attempt", DateTime(timezone=True)),
    col("delivered_at", DateTime(timezone=True), nullable=True),
    col("status_code", Integer, nullable=True),
)
