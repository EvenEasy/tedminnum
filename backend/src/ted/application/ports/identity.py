from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from ted.domain.models import (
    LoginSession,
    User,
)


class IdentityQueries(Protocol):
    async def user(self, id: UUID, lock: bool = False) -> User: ...

    async def user_by_email(self, email: str) -> User | None: ...

    async def users(self) -> Sequence[User]: ...

    async def session(self, token_hash: str) -> LoginSession | None: ...


class IdentityRepository(IdentityQueries, Protocol):
    async def delete_sessions(self, user_id: UUID) -> None: ...

    async def save(self, *entities: User | LoginSession) -> None: ...

    async def delete_session(self, id: UUID) -> None: ...
