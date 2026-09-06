"""Development seed data.

Creates two unrelated test businesses (not one) on purpose: with a single
tenant in the dev database, a query missing a `business_id` filter still
"works" by accident. With two, that same bug returns the wrong data
immediately and is caught while developing, not in production.

Run with:  python -m app.db.seed
"""

import asyncio

from app.core.db import AsyncSessionLocal
from app.schemas.auth import RegisterRequest
from app.services import auth_service
from app.services.exceptions import EmailAlreadyExistsError

SEED_ACCOUNTS = [
    RegisterRequest(
        email="ana@peluqueriabella-demo.com",
        password="test1234",
        full_name="Ana Gómez",
        business_name="Peluquería Bella",
    ),
    RegisterRequest(
        email="pedro@consultoriodrperez-demo.com",
        password="test1234",
        full_name="Pedro Pérez",
        business_name="Consultorio Dr. Pérez",
    ),
]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        for account in SEED_ACCOUNTS:
            try:
                user = await auth_service.register(db, account)
                print(f"Created {account.business_name!r} owned by {user.email}")
            except EmailAlreadyExistsError:
                print(f"Skipping {account.email} — already seeded")


if __name__ == "__main__":
    asyncio.run(seed())
