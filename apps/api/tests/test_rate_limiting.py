import pytest
from httpx import AsyncClient

from app.core.rate_limit import limiter


@pytest.fixture
def enable_rate_limiting():
    """conftest.py disables the limiter globally (see the comment there) —
    only this test needs it on, and only for its own duration."""
    limiter.reset()
    limiter.enabled = True
    try:
        yield
    finally:
        limiter.enabled = False
        limiter.reset()


async def test_login_is_rate_limited_per_ip(
    client: AsyncClient, enable_rate_limiting: None
) -> None:
    payload = {"email": "nobody@example.com", "password": "wrong-password"}

    responses = [await client.post("/api/v1/auth/login", json=payload) for _ in range(11)]
    statuses = [r.status_code for r in responses]

    # First 10 are wrong credentials (under the 10/minute limit on /auth/login).
    assert statuses[:10] == [401] * 10
    # The 11th in the same window is throttled before it even checks credentials.
    assert statuses[10] == 429
