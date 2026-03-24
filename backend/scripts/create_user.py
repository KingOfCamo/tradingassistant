"""Interactive script to create the admin user.

Usage: python -m backend.scripts.create_user
"""

import asyncio
import getpass
import re
import sys
import uuid

from passlib.hash import bcrypt
from sqlalchemy import insert, select

# Must set up path before imports
sys.path.insert(0, ".")

from backend.db.database import engine, async_session, Base
from backend.db.models import User


def validate_password(password: str) -> list[str]:
    errors = []
    if len(password) < 12:
        errors.append("at least 12 characters")
    if not re.search(r"[A-Z]", password):
        errors.append("one uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("one lowercase letter")
    if not re.search(r"\d", password):
        errors.append("one number")
    if not re.search(r"[!@#$%^&*()\-_+=\[\]{}|;:,.<>?]", password):
        errors.append("one symbol (!@#$%^&*...)")
    return errors


async def create_user():
    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    username = input("Username (default: admin): ").strip() or "admin"

    # Check if user exists
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.username == username)
        )
        if result.scalar_one_or_none():
            print(f"User '{username}' already exists.")
            sys.exit(1)

    while True:
        password = getpass.getpass("Password: ")
        errors = validate_password(password)
        if errors:
            print(f"Password must contain: {', '.join(errors)}")
            continue

        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.")
            continue
        break

    hashed = bcrypt.using(rounds=12).hash(password)

    async with async_session() as session:
        await session.execute(
            insert(User).values(
                id=uuid.uuid4(),
                username=username,
                hashed_password=hashed,
            )
        )
        await session.commit()

    print(f"User '{username}' created successfully.")


if __name__ == "__main__":
    asyncio.run(create_user())
