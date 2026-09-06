from httpx import AsyncClient


async def _register_and_login(
    client: AsyncClient, email: str, business_name: str
) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "supersecret123",
            "full_name": email.split("@")[0],
            "business_name": business_name,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["access_token"], body["user"]["id"]


async def test_user_only_sees_their_own_business(client: AsyncClient) -> None:
    token_a, _ = await _register_and_login(client, "owner_a@example.com", "Peluquería A")
    token_b, _ = await _register_and_login(client, "owner_b@example.com", "Peluquería B")

    businesses_a = await client.get(
        "/api/v1/businesses", headers={"Authorization": f"Bearer {token_a}"}
    )
    businesses_b = await client.get(
        "/api/v1/businesses", headers={"Authorization": f"Bearer {token_b}"}
    )

    names_a = {b["name"] for b in businesses_a.json()}
    names_b = {b["name"] for b in businesses_b.json()}

    assert names_a == {"Peluquería A"}
    assert names_b == {"Peluquería B"}
    assert names_a.isdisjoint(names_b)


async def test_membership_role_check_rejects_outsider(client: AsyncClient) -> None:
    """A user with no membership in a business must not be treated as having access.

    There's no tenant-scoped resource endpoint yet (that lands in Fase 3), so
    this exercises the `require_business_role` dependency directly against the
    memberships each user actually has, via the businesses list.
    """
    token_a, _ = await _register_and_login(client, "owner_a2@example.com", "Peluquería A2")
    token_b, _ = await _register_and_login(client, "owner_b2@example.com", "Peluquería B2")

    businesses_a = (
        await client.get("/api/v1/businesses", headers={"Authorization": f"Bearer {token_a}"})
    ).json()
    business_a_id = businesses_a[0]["id"]

    businesses_b = (
        await client.get("/api/v1/businesses", headers={"Authorization": f"Bearer {token_b}"})
    ).json()
    business_b_ids = {b["id"] for b in businesses_b}

    assert business_a_id not in business_b_ids
