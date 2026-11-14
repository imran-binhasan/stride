"""Promote an existing trusted account; run only with operator database credentials."""

import argparse
import asyncio
from sqlalchemy import select
from src.core.database import async_session_factory
from src.models.auth import User


async def promote(email):
    async with async_session_factory() as db:
        user = await db.scalar(select(User).where(User.email == email.lower()))
        if not user:
            raise SystemExit("Register the account before promoting it")
        user.is_superadmin = True
        user.is_active = True
        await db.commit()
        print("Existing account promoted to platform administrator")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    asyncio.run(promote(parser.parse_args().email))
