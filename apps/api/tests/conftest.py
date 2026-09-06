import os
from collections.abc import AsyncGenerator

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_receptionist_test",
)

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import Base, get_db
from app.main import app
from app.models import Business, Membership, RefreshToken, User  # noqa: F401

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture(autouse=True)
async def _db_session() -> AsyncGenerator[None, None]:
    """Fresh engine/schema per test, scoped to that test's own event loop.

    asyncpg connections are bound to the event loop they were created on, and
    pytest-asyncio gives each test function its own loop — a module-level
    engine shared across tests breaks with "Event loop is closed" /
    "another operation is in progress".
    """
    engine = create_async_engine(TEST_DATABASE_URL, future=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
