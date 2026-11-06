from datetime import timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID

from ted.application.access import admin
from ted.application.activity import Activity
from ted.application.ports import IdentityRepository, Passwords, WorkspaceRepository
from ted.domain.models import LoginSession, User, now
from ted.domain.rules import require


class Identity:
    def __init__(
        self,
        identity: IdentityRepository,
        passwords: Passwords,
        workspace: WorkspaceRepository,
        activity: Activity,
    ):
        self.identity, self.passwords, self.workspace, self.activity = (
            identity,
            passwords,
            workspace,
            activity,
        )

    async def create_user(
        self, actor: User, email: str, name: str, password: str, role: str
    ) -> User:
        admin(actor)
        require(
            await self.identity.user_by_email(email) is None, "Email is already registered", 409
        )
        user = User(email=email, name=name, password_hash=self.passwords.hash(password), role=role)
        await self.identity.save(user)
        await self.activity.audit(actor, "user.created", user.id, role)
        return user

    async def update_user(
        self, actor: User, id: UUID, role: str, active: bool, password: str | None
    ) -> User:
        admin(actor)
        await self.workspace.workspace(lock=True)
        user = await self.identity.user(id, lock=True)
        if user.role == "admin" and user.active and (role != "admin" or not active):
            require(
                sum(u.role == "admin" and u.active for u in await self.identity.users()) > 1,
                "Cannot disable the last active administrator",
                409,
            )
        user.role, user.active = role, active
        if password is not None:
            user.password_hash = self.passwords.hash(password)
        user.failed_logins, user.locked_until = 0, None
        await self.identity.delete_sessions(id)
        await self.identity.save(user)
        await self.activity.audit(
            actor,
            "user.access_changed",
            id,
            f"role={role}; active={active}; password_reset={password is not None}",
        )
        return user


class Authenticate:
    def __init__(self, identity: IdentityRepository, passwords: Passwords):
        self.identity, self.passwords = identity, passwords

    async def execute(
        self, email: str, password: str, hours: int
    ) -> tuple[User, str, LoginSession] | None:
        user = await self.identity.user_by_email(email)
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
            await self.identity.save(user)
            return None
        user.failed_logins, user.locked_until = 0, None
        token = token_urlsafe(48)
        session = LoginSession(
            user_id=user.id,
            token_hash=sha256(token.encode()).hexdigest(),
            csrf=token_urlsafe(32),
            expires_at=now() + timedelta(hours=hours),
        )
        await self.identity.save(user, session)
        return user, token, session


class Logout:
    def __init__(self, identity: IdentityRepository):
        self.identity = identity

    async def execute(self, session_id: UUID) -> None:
        await self.identity.delete_session(session_id)


class ChangePassword:
    def __init__(self, identity: IdentityRepository, passwords: Passwords, activity: Activity):
        self.identity, self.passwords, self.activity = identity, passwords, activity

    async def execute(self, actor: User, current: str, replacement: str) -> None:
        user = await self.identity.user(actor.id, lock=True)
        require(
            self.passwords.verify(current, user.password_hash),
            "Current password is incorrect",
            403,
        )
        user.password_hash = self.passwords.hash(replacement)
        await self.identity.delete_sessions(actor.id)
        await self.identity.save(user)
        await self.activity.audit(actor, "user.password_changed", actor.id)


class UpdatePreferences:
    def __init__(self, identity: IdentityRepository):
        self.identity = identity

    async def execute(
        self, actor: User, work_minutes: int, short_break: int, long_break: int, notifications: bool
    ) -> User:
        user = await self.identity.user(actor.id, lock=True)
        user.work_minutes, user.short_break, user.long_break, user.notifications = (
            work_minutes,
            short_break,
            long_break,
            notifications,
        )
        await self.identity.save(user)
        return user
