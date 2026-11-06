from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ted.domain import models as m

from . import records as r
from .mapping import get, listing, to_domain
from .mapping import save as persist
from .schema import tables, users


class SqlIdentityRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def user(self, id: UUID, lock: bool = False) -> m.User:
        return await get(self.db, r.UserRow, m.User, id, lock)

    async def user_by_email(self, email: str) -> m.User | None:
        row = await self.db.scalar(
            select(r.UserRow).where(users.c.email == email).with_for_update()
        )
        return to_domain(row, m.User) if row is not None else None

    async def users(self) -> Sequence[m.User]:
        return await listing(
            self.db,
            r.UserRow,
            m.User,
        )

    async def session(self, token_hash: str) -> m.LoginSession | None:
        row = await self.db.scalar(
            select(r.LoginSessionRow).where(tables[r.LoginSessionRow].c.token_hash == token_hash)
        )
        return to_domain(row, m.LoginSession) if row is not None else None

    async def delete_sessions(self, user_id: UUID) -> None:
        await self.db.execute(
            delete(r.LoginSessionRow).where(tables[r.LoginSessionRow].c.user_id == user_id)
        )

    async def delete_session(self, id: UUID) -> None:
        await self.db.execute(delete(r.LoginSessionRow).where(tables[r.LoginSessionRow].c.id == id))

    async def save(self, *entities: m.User | m.LoginSession) -> None:
        for entity in entities:
            if isinstance(entity, m.User):
                await persist(self.db, r.UserRow, entity)
            elif isinstance(entity, m.LoginSession):
                await persist(self.db, r.LoginSessionRow, entity)
