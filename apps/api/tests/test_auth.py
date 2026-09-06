from httpx import AsyncClient


async def _register(client: AsyncClient, email: str = "max@example.com") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecret123",
            "full_name": "Max Hoefner",
            "business_name": "Peluquería Max",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_register_creates_user_and_business(client: AsyncClient) -> None:
    data = await _register(client)
    assert data["user"]["email"] == "max@example.com"
    assert "access_token" in data
    assert "refresh_token" in data

    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "max@example.com"

    businesses = await client.get(
        "/api/v1/businesses", headers={"Authorization": f"Bearer {data['access_token']}"}
    )
    assert businesses.status_code == 200
    assert len(businesses.json()) == 1
    assert businesses.json()[0]["name"] == "Peluquería Max"
    assert businesses.json()[0]["role"] == "OWNER"


async def test_register_duplicate_email_is_rejected(client: AsyncClient) -> None:
    await _register(client)
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "max@example.com",
            "password": "otherpassword123",
            "full_name": "Otro Max",
            "business_name": "Otra Peluquería",
        },
    )
    assert response.status_code == 409


async def test_login_with_correct_and_incorrect_password(client: AsyncClient) -> None:
    await _register(client)

    ok = await client.post(
        "/api/v1/auth/login", json={"email": "max@example.com", "password": "supersecret123"}
    )
    assert ok.status_code == 200
    assert "access_token" in ok.json()

    bad = await client.post(
        "/api/v1/auth/login", json={"email": "max@example.com", "password": "wrongpassword"}
    )
    assert bad.status_code == 401


async def test_me_requires_valid_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


async def test_refresh_rotates_token_and_invalidates_old_one(client: AsyncClient) -> None:
    data = await _register(client)
    old_refresh = data["refresh_token"]

    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    assert new_tokens["access_token"] != data["access_token"]

    reuse_old = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse_old.status_code == 401


async def test_logout_revokes_refresh_token(client: AsyncClient) -> None:
    data = await _register(client)

    logout = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": data["refresh_token"]}
    )
    assert logout.status_code == 204

    reuse = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]}
    )
    assert reuse.status_code == 401
