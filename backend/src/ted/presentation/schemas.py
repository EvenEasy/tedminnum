from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator

Name = Annotated[str, Field(min_length=1, max_length=200)]
Price = Annotated[Decimal, Field(ge=0, le=9999999999, max_digits=12, decimal_places=2)]
Password = Annotated[
    str, StringConstraints(strip_whitespace=False), Field(min_length=12, max_length=128)
]
RawPassword = Annotated[
    str, StringConstraints(strip_whitespace=False), Field(min_length=1, max_length=128)
]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Input):
    email: str = Field(max_length=254)
    password: RawPassword


class UserCreate(Input):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    name: Name
    password: Password
    role: Literal["admin", "member"] = "member"


class UserUpdate(Input):
    role: Literal["admin", "member"]
    active: bool
    password: Password | None = None


class PasswordChange(Input):
    current_password: RawPassword
    new_password: Password


class ClientInput(Input):
    name: Name
    rate: Price = Decimal(0)


class ProjectInput(Input):
    name: Name
    rate: Price | None = None
    member_ids: list[UUID] = Field(default_factory=list, max_length=100)


class ProjectCreate(ProjectInput):
    client_id: UUID


class TaskCreate(Input):
    project_id: UUID
    title: Name
    description: str = Field(default="", max_length=10000)
    status: Literal["backlog", "in_progress", "done"] = "backlog"
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    due_date: date | None = None
    estimate_minutes: int | None = Field(default=None, ge=0, le=1000000)
    position: int = Field(default=0, ge=0, le=1000000)
    billing: Literal["hourly", "fixed", "nonbillable"] = "hourly"
    rate: Price | None = None
    fixed_price: Price | None = None
    assignee_ids: list[UUID] = Field(default_factory=list, max_length=100)


class TaskUpdate(Input):
    version: int = Field(ge=1)
    title: Name | None = None
    description: str | None = Field(default=None, max_length=10000)
    status: Literal["backlog", "in_progress", "done"] | None = None
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    due_date: date | None = None
    estimate_minutes: int | None = Field(default=None, ge=0, le=1000000)
    position: int | None = Field(default=None, ge=0, le=1000000)
    billing: Literal["hourly", "fixed", "nonbillable"] | None = None
    rate: Price | None = None
    fixed_price: Price | None = None
    assignee_ids: list[UUID] | None = Field(default=None, max_length=100)

    @field_validator(
        "title", "description", "status", "priority", "position", "billing", "assignee_ids"
    )
    @classmethod
    def nonnull(cls, value: object) -> object:
        if value is None:
            raise ValueError("This field cannot be null")
        return value


class TimerStart(Input):
    long_break: bool = False
    request_key: UUID
    task_id: UUID | None = None
    kind: Literal["work", "break"] = "work"
    billable: bool = True


class EntryUpdate(Input):
    started_at: AwareDatetime
    ended_at: AwareDatetime
    billable: bool
    note: str = Field(default="", max_length=2000)


class Draft(Input):
    client_id: UUID
    request_key: UUID
    entry_ids: list[UUID] = Field(default_factory=list, max_length=500)
    task_ids: list[UUID] = Field(default_factory=list, max_length=500)


class Description(Input):
    description: str = Field(min_length=1, max_length=2000)


class PaymentInput(Input):
    request_key: UUID
    amount: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    paid_on: date
    reference: str = Field(default="", max_length=200)


class Preferences(Input):
    work_minutes: int = Field(ge=1, le=180)
    short_break: int = Field(ge=1, le=60)
    long_break: int = Field(ge=1, le=120)
    notifications: bool


class WorkspaceInput(Input):
    name: Name
    currency: Literal["USD", "EUR", "GBP", "UAH", "CAD", "PLN", "CHF", "AUD"]


class HookInput(Input):
    url: str = Field(max_length=2000)


class HookUpdate(Input):
    enabled: bool
    rotate_secret: bool = False


class TaskMove(Input):
    version: int = Field(ge=1)
    direction: Literal["up", "down"]
