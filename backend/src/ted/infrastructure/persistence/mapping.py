"""Small internal row conversion helpers, not a repository API."""

from dataclasses import asdict, fields
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ted.domain.rules import Problem


def to_domain[T](row: Any, entity: type[T]) -> T:
    return entity(**{field.name: getattr(row, field.name) for field in fields(entity)})  # type: ignore[arg-type]


async def get[T](
    db: AsyncSession, row_type: type[Any], entity: type[T], id: Any, lock: bool = False
) -> T:
    row = await db.get(row_type, id, with_for_update=lock, populate_existing=lock)
    if row is None:
        raise Problem("Not found", 404)
    return to_domain(row, entity)


async def listing[T](
    db: AsyncSession, row_type: type[Any], entity: type[T], *filters: Any
) -> list[T]:
    return [
        to_domain(row, entity) for row in (await db.scalars(select(row_type).where(*filters))).all()
    ]


async def save(db: AsyncSession, row_type: type[Any], entity: Any) -> None:
    values = asdict(entity)
    row = await db.get(row_type, entity.id)
    if row is None:
        db.add(row_type(**values))
    else:
        for name, value in values.items():
            setattr(row, name, value)
    await db.flush()
