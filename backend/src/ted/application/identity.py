from datetime import timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID

from ted.application.ports import Passwords, Store
from ted.application.services import Work, admin
from ted.domain.models import LoginSession, User, now
from ted.domain.rules import require


class Identity:
    def __init__(self, store: Store, passwords: Passwords):
        self.s, self.passwords = store, passwords

    async def login(
        self, email: str, password: str, hours: int
    ) -> tuple[User, str, LoginSession] | None:
        user = await self.s.user_by_email(email)
        # Dummy verify keeps unknown-account password work comparable to a known account.
        valid = self.passwords.verify(
            password, user.password_hash if user else self.passwords.dummy_hash
        )
        if user is None:
            return None
        if not user.active or (user.locked_until is not None and user.locked_until > now()):
            return None
        if not valid:
            user.failed_logins += 1
            if user.failed_logins >= 5:
                user.locked_until = now() + timedelta(minutes=5)
            await self.s.save(user)
            return None
        user.failed_logins, user.locked_until = 0, None
        token = token_urlsafe(48)
        session = LoginSession(
            user_id=user.id,
            token_hash=sha256(token.encode()).hexdigest(),
            csrf=token_urlsafe(32),
            expires_at=now() + timedelta(hours=hours),
        )
        await self.s.save(user, session)
        return user, token, session

    async def create_user(
        self, actor: User, email: str, name: str, password: str, role: str
    ) -> User:
        admin(actor)
        require(await self.s.user_by_email(email) is None, "Email is already registered", 409)
        user = User(email=email, name=name, password_hash=self.passwords.hash(password), role=role)
        await self.s.save(user)
        await Work(self.s, actor).audit("user.created", user.id, role)
        return user

    async def update_user(
        self, actor: User, id: UUID, role: str, active: bool, password: str | None
    ) -> User:
        admin(actor)
        await self.s.workspace(lock=True)
        user = await self.s.user(id, lock=True)
        if user.role == "admin" and user.active and (role != "admin" or not active):
            require(
                sum(u.role == "admin" and u.active for u in await self.s.users()) > 1,
                "Cannot disable the last active administrator",
                409,
            )
        user.role, user.active = role, active
        if password is not None:
            user.password_hash = self.passwords.hash(password)
        user.failed_logins, user.locked_until = 0, None
        await self.s.delete_sessions(id)
        await self.s.save(user)
        await Work(self.s, actor).audit(
            "user.access_changed",
            id,
            f"role={role}; active={active}; password_reset={password is not None}",
        )
        return user
