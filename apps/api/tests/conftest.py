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
from app.models import *  # noqa: F401,F403 (import every model so metadata sees them)

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture
async def db_session_factory() -> AsyncGenerator[async_sessionmaker, None]:
    """Fresh engine/schema per test, scoped to that test's own event loop.

    asyncpg connections are bound to the event loop they were created on, and
    pytest-asyncio gives each test function its own loop — a module-level
    engine shared across tests breaks with "Event loop is closed" /
    "another operation is in progress".

    Exposed (not just used internally) so tests can open a raw session to set
    up fixtures the API has no endpoint for yet — e.g. attaching a second
    membership to a business to exercise role checks.
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
        yield session_factory
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


@pytest.fixture
async def db_session(
    db_session_factory: async_sessionmaker,
) -> AsyncGenerator[AsyncSession, None]:
    async with db_session_factory() as session:
        yield session


@pytest.fixture
async def client(db_session_factory: async_sessionmaker) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def owner(client: AsyncClient) -> dict:
    """Registers a fresh user (OWNER of a fresh business) and returns their
    token/business_id/headers, ready to use in a test."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner@example.com",
            "password": "supersecret123",
            "full_name": "Business Owner",
            "business_name": "Negocio de Prueba",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    businesses = await client.get(
        "/api/v1/businesses", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    business_id = businesses.json()[0]["id"]
    return {
        "user_id": body["user"]["id"],
        "token": body["access_token"],
        "business_id": business_id,
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
    }
