import os
from collections.abc import AsyncGenerator, Iterator

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_receptionist_test",
)

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.providers import get_llm_provider
from app.ai.providers.base import AgentTurnResult, LLMProvider
from app.core.db import Base, get_db
from app.core.rate_limit import limiter
from app.main import app
from app.models import *  # noqa: F401,F403 (import every model so metadata sees them)
from app.whatsapp.providers import get_whatsapp_provider
from app.whatsapp.providers.base import WhatsAppProvider

TEST_DATABASE_URL = os.environ["DATABASE_URL"]

# httpx's ASGITransport gives every request the same fake client address, so
# without this every test would share one rate-limit bucket per route (e.g.
# register's 5/hour) and start failing once enough tests had run — not a
# real rate-limiting bug, just an artifact of the test transport. Disabled
# by default here; test_rate_limiting.py re-enables it for its own
# assertions and turns it back off when done.
limiter.enabled = False


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
        # Needed for the appointments table's anti-double-booking EXCLUDE
        # constraint (GiST + plain `=` on a uuid column). Alembic does this
        # in the real migration; create_all doesn't run migrations.
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
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


class FakeProvider(LLMProvider):
    """Scripted stand-in for a real LLM in tests — no network calls, no API
    key, fully deterministic. Queue responses with `.queue(...)`; each
    `.generate()` call pops the next one and records what it was asked."""

    def __init__(self) -> None:
        self.script: list[AgentTurnResult] = []
        self.calls: list[dict] = []

    def queue(self, result: AgentTurnResult) -> None:
        self.script.append(result)

    async def generate(self, *, system: str, messages: list, tools: list) -> AgentTurnResult:
        self.calls.append({"system": system, "messages": list(messages), "tools": tools})
        if not self.script:
            raise AssertionError("FakeProvider script exhausted — queue more responses")
        return self.script.pop(0)


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture(autouse=True)
def _override_llm_provider(fake_provider: FakeProvider) -> Iterator[None]:
    app.dependency_overrides[get_llm_provider] = lambda: fake_provider
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)


class FakeWhatsAppProvider(WhatsAppProvider):
    """Records outgoing messages instead of calling Meta's API."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_text_message(
        self, *, phone_number_id: str, access_token: str, to: str, text: str
    ) -> None:
        self.sent.append(
            {
                "phone_number_id": phone_number_id,
                "access_token": access_token,
                "to": to,
                "text": text,
            }
        )


@pytest.fixture
def fake_whatsapp_provider() -> FakeWhatsAppProvider:
    return FakeWhatsAppProvider()


@pytest.fixture(autouse=True)
def _override_whatsapp_provider(fake_whatsapp_provider: FakeWhatsAppProvider) -> Iterator[None]:
    app.dependency_overrides[get_whatsapp_provider] = lambda: fake_whatsapp_provider
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_whatsapp_provider, None)
