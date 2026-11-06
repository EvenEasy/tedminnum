"""Explicit disposable browser-test seed; never used by the app or Compose."""

import asyncio
import os

from sqlalchemy import text

from ted.domain.models import User
from ted.infrastructure.database import sessions
from ted.infrastructure.passwords import ArgonPasswords
from ted.infrastructure.persistence.identity import SqlIdentityRepository
from ted.infrastructure.runtime import settings


async def seed():
    assert os.environ.get("ALLOW_DESTRUCTIVE_TESTS") == "1", (
        "Explicit destructive-test opt-in required"
    )
    assert settings.database_url.endswith("/ted_e2e_test"), (
        "Browser tests require a disposable ted_e2e_test database"
    )
    async with sessions() as session, session.begin():
        await session.execute(
            text(
                "TRUNCATE users, clients, projects, memberships, tasks, assignments, time_entries, invoices, invoice_lines, payments, audit, webhooks, deliveries, sessions RESTART IDENTITY CASCADE"
            )
        )
        await session.execute(
            text("UPDATE workspace SET name='Browser test studio', currency='USD', next_invoice=1")
        )
        await SqlIdentityRepository(session).save(
            User(
                email="admin@e2e.test",
                name="Test Admin",
                role="admin",
                password_hash=ArgonPasswords().hash("browser-test-password-123"),
            )
        )


if __name__ == "__main__":
    asyncio.run(seed())
