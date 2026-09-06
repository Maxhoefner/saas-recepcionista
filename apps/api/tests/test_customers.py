from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.membership import Membership, Role
from app.models.user import User


async def test_create_get_update_customer(client: AsyncClient, owner: dict) -> None:
    created = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/customers",
        json={"phone": "+5491122334455", "name": "Juan Pérez"},
        headers=owner["headers"],
    )
    assert created.status_code == 201, created.text
    customer = created.json()

    fetched = await client.get(
        f"/api/v1/businesses/{owner['business_id']}/customers/{customer['id']}",
        headers=owner["headers"],
    )
    assert fetched.status_code == 200
    assert fetched.json()["phone"] == "+5491122334455"

    updated = await client.patch(
        f"/api/v1/businesses/{owner['business_id']}/customers/{customer['id']}",
        json={"notes": "Prefiere turnos por la tarde"},
        headers=owner["headers"],
    )
    assert updated.status_code == 200
    assert updated.json()["notes"] == "Prefiere turnos por la tarde"
    assert updated.json()["phone"] == "+5491122334455"


async def test_duplicate_phone_in_same_business_is_rejected(
    client: AsyncClient, owner: dict
) -> None:
    payload = {"phone": "+5491122334455", "name": "Juan Pérez"}
    first = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/customers",
        json=payload,
        headers=owner["headers"],
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/customers",
        json=payload,
        headers=owner["headers"],
    )
    assert second.status_code == 409


async def test_same_phone_allowed_across_different_businesses(
    client: AsyncClient, owner: dict
) -> None:
    other = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "other-owner@example.com",
            "password": "supersecret123",
            "full_name": "Other Owner",
            "business_name": "Otro Negocio",
        },
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

    payload = {"phone": "+5491122334455", "name": "Juan Pérez"}
    first = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/customers",
        json=payload,
        headers=owner["headers"],
    )
    assert first.status_code == 201

    other_business_id = (
        await client.get("/api/v1/businesses", headers=other_headers)
    ).json()[0]["id"]
    second = await client.post(
        f"/api/v1/businesses/{other_business_id}/customers",
        json=payload,
        headers=other_headers,
    )
    assert second.status_code == 201


async def test_staff_can_manage_customers(
    client: AsyncClient, owner: dict, db_session: AsyncSession
) -> None:
    user = User(
        email="staff@example.com", password_hash=hash_password("staffpass123"), full_name="Staff"
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(Membership(user_id=user.id, business_id=owner["business_id"], role=Role.STAFF))
    await db_session.commit()

    login = await client.post(
        "/api/v1/auth/login", json={"email": "staff@example.com", "password": "staffpass123"}
    )
    staff_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    created = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/customers",
        json={"phone": "+5491122334455", "name": "Juan Pérez"},
        headers=staff_headers,
    )
    assert created.status_code == 201
