from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from ted.domain.models import Client, Project, Task, TimeEntry, User, Webhook, Workspace


def encode(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, list | tuple):
        return [encode(v) for v in value]
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    return value


def public(entity: Any, actor: User | None = None) -> dict[str, Any]:
    data = asdict(entity)
    if isinstance(entity, User):
        data = {
            k: v
            for k, v in data.items()
            if k
            in {
                "id",
                "name",
                "email",
                "role",
                "active",
                "work_minutes",
                "short_break",
                "long_break",
                "notifications",
            }
        }
    if isinstance(entity, Workspace):
        data = {"name": entity.name, "currency": entity.currency}
    if isinstance(entity, Webhook):
        data.pop("secret")
    if actor is not None and actor.role != "admin" and isinstance(entity, Client | Project | Task):
        for k in ("rate", "fixed_price"):
            data.pop(k, None)
    if isinstance(entity, TimeEntry):
        data["seconds"] = entity.seconds()
    return encode(data)  # type: ignore[no-any-return]


def page(items: list[Any], limit: int, offset: int) -> dict[str, Any]:
    return {
        "items": items[offset : offset + limit],
        "total": len(items),
        "limit": limit,
        "offset": offset,
    }
