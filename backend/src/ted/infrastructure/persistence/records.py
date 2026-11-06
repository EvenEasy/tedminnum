from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


class Record:
    def __init__(self, **values: Any):
        for name, value in values.items():
            setattr(self, name, value)


class WorkspaceRow(Record):
    id: int
    currency: str
    name: str
    next_invoice: int


class UserRow(Record):
    id: UUID
    email: str
    name: str
    password_hash: str
    role: str
    active: bool
    work_minutes: int
    short_break: int
    long_break: int
    notifications: bool
    failed_logins: int
    locked_until: datetime | None


class LoginSessionRow(Record):
    id: UUID
    user_id: UUID
    token_hash: str
    csrf: str
    expires_at: datetime


class ClientRow(Record):
    id: UUID
    name: str
    rate: Decimal


class ProjectRow(Record):
    id: UUID
    client_id: UUID
    name: str
    rate: Decimal | None


class MembershipRow(Record):
    id: UUID
    project_id: UUID
    user_id: UUID


class TaskRow(Record):
    id: UUID
    project_id: UUID
    title: str
    description: str
    status: str
    priority: str
    due_date: date | None
    estimate_minutes: int | None
    position: int
    billing: str
    rate: Decimal | None
    fixed_price: Decimal | None
    version: int


class AssignmentRow(Record):
    id: UUID
    task_id: UUID
    user_id: UUID


class TimeEntryRow(Record):
    id: UUID
    user_id: UUID
    task_id: UUID | None
    kind: str
    billable: bool
    started_at: datetime
    ended_at: datetime | None
    paused_at: datetime | None
    paused_microseconds: int
    note: str
    target_seconds: int


class InvoiceRow(Record):
    id: UUID
    client_id: UUID
    request_key: UUID
    request_fingerprint: str
    currency: str
    client_name: str
    issuer_name: str
    number: str
    status: str
    created_at: datetime
    issued_at: datetime | None
    total: Decimal


class InvoiceLineRow(Record):
    id: UUID
    invoice_id: UUID
    description: str
    quantity: Decimal
    rate: Decimal
    amount: Decimal
    source_entry_id: UUID | None
    source_task_id: UUID | None
    reserved: bool


class PaymentRow(Record):
    id: UUID
    invoice_id: UUID
    request_key: UUID
    amount: Decimal
    currency: str
    paid_on: date
    reference: str
    created_at: datetime


class AuditRow(Record):
    id: UUID
    actor_id: UUID
    action: str
    object_id: str
    detail: str
    created_at: datetime


class WebhookRow(Record):
    id: UUID
    url: str
    secret: str
    enabled: bool


class DeliveryRow(Record):
    id: UUID
    webhook_id: UUID
    event: str
    payload: str
    attempts: int
    next_attempt: datetime
    delivered_at: datetime | None
    status_code: int | None
