"""Framework-free entities. Persistence mapping lives in infrastructure."""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4


def now() -> datetime:
    return datetime.now(UTC)


@dataclass(kw_only=True)
class Entity:
    id: UUID = field(default_factory=uuid4)


@dataclass(kw_only=True)
class Workspace:
    id: int = 1
    currency: str = "USD"
    name: str = "Tedminnum"
    next_invoice: int = 1


@dataclass(kw_only=True)
class User(Entity):
    email: str
    name: str
    password_hash: str
    role: str = "member"
    active: bool = True
    work_minutes: int = 25
    short_break: int = 5
    long_break: int = 15
    notifications: bool = False
    failed_logins: int = 0
    locked_until: datetime | None = None


@dataclass(kw_only=True)
class LoginSession(Entity):
    user_id: UUID
    token_hash: str
    csrf: str
    expires_at: datetime


@dataclass(kw_only=True)
class Client(Entity):
    name: str
    rate: Decimal = Decimal("0")


@dataclass(kw_only=True)
class Project(Entity):
    client_id: UUID
    name: str
    rate: Decimal | None = None


@dataclass(kw_only=True)
class Membership(Entity):
    project_id: UUID
    user_id: UUID


@dataclass(kw_only=True)
class Task(Entity):
    project_id: UUID
    title: str
    description: str = ""
    status: str = "backlog"
    priority: str = "normal"
    due_date: date | None = None
    estimate_minutes: int | None = None
    position: int = 0
    billing: str = "hourly"
    rate: Decimal | None = None
    fixed_price: Decimal | None = None
    version: int = 1


@dataclass(kw_only=True)
class Assignment(Entity):
    task_id: UUID
    user_id: UUID


@dataclass(kw_only=True)
class TimeEntry(Entity):
    user_id: UUID
    task_id: UUID | None = None
    kind: str = "work"
    billable: bool = True
    started_at: datetime = field(default_factory=now)
    ended_at: datetime | None = None
    paused_at: datetime | None = None
    paused_microseconds: int = 0
    note: str = ""
    target_seconds: int = 1500

    def seconds(self, at: datetime | None = None) -> int:
        end = self.ended_at or self.paused_at or at or now()
        return max(
            0,
            ((end - self.started_at) // timedelta(microseconds=1) - self.paused_microseconds)
            // 1_000_000,
        )


@dataclass(kw_only=True)
class Invoice(Entity):
    client_id: UUID
    request_key: UUID
    request_fingerprint: str
    currency: str
    client_name: str
    issuer_name: str
    number: str
    status: str = "draft"
    created_at: datetime = field(default_factory=now)
    issued_at: datetime | None = None
    total: Decimal = Decimal("0.00")


@dataclass(kw_only=True)
class InvoiceLine(Entity):
    invoice_id: UUID
    description: str
    quantity: Decimal
    rate: Decimal
    amount: Decimal
    source_entry_id: UUID | None = None
    source_task_id: UUID | None = None
    reserved: bool = True


@dataclass(kw_only=True)
class Payment(Entity):
    invoice_id: UUID
    request_key: UUID
    amount: Decimal
    currency: str
    paid_on: date
    reference: str = ""
    created_at: datetime = field(default_factory=now)


@dataclass(kw_only=True)
class Audit(Entity):
    actor_id: UUID
    action: str
    object_id: str
    detail: str = ""
    created_at: datetime = field(default_factory=now)


@dataclass(kw_only=True)
class Webhook(Entity):
    url: str
    secret: str
    enabled: bool = True


@dataclass(kw_only=True)
class Delivery(Entity):
    webhook_id: UUID
    event: str
    payload: str
    attempts: int = 0
    next_attempt: datetime = field(default_factory=now)
    delivered_at: datetime | None = None
    status_code: int | None = None
