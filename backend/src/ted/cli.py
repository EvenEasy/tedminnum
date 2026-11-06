"""Explicit, interactive operator onboarding. No default credentials or demo seed."""

import argparse
import asyncio
from getpass import getpass

from sqlalchemy import select

from ted.domain.models import User, Workspace
from ted.infrastructure.database import sessions
from ted.infrastructure.passwords import ArgonPasswords
from ted.presentation.schemas import UserCreate


async def bootstrap(email: str, name: str) -> None:
    password = getpass("Administrator password (12+ characters): ")
    if password != getpass("Confirm password: "):
        raise SystemExit("Passwords differ")
    data = UserCreate(email=email.lower(), name=name, password=password, role="admin")
    async with sessions() as session, session.begin():
        await session.get(Workspace, 1, with_for_update=True)
        if await session.scalar(select(User).limit(1)):
            raise SystemExit("Users already exist; use an existing administrator account")
        session.add(
            User(
                email=data.email,
                name=data.name,
                password_hash=ArgonPasswords().hash(data.password),
                role="admin",
            )
        )
    print("Administrator created. Sign in through the web application.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first administrator interactively")
    parser.add_argument("email")
    parser.add_argument("--name", default="Administrator")
    args = parser.parse_args()
    asyncio.run(bootstrap(args.email, args.name))


if __name__ == "__main__":
    main()
