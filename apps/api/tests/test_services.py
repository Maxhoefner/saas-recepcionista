from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.membership import Membership, Role
from app.models.user import User


async def _add_staff_member(db_session: AsyncSession, business_id: str) -> dict:
    user = User(
        email="staff@example.com", password_hash=hash_password("staffpass123"), full_name="Staff"
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(Membership(user_id=user.id, business_id=business_id, role=Role.STAFF))
    await db_session.commit()
    return {"email": "staff@example.com", "password": "staffpass123"}


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_owner_can_crud_a_service(client: AsyncClient, owner: dict) -> None:
    create = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/services",
        json={"name": "Corte", "price_cents": 15000, "duration_minutes": 45},
        headers=owner["headers"],
    )
    assert create.status_code == 201, create.text
    service = create.json()
    assert service["name"] == "Corte"
    assert service["active"] is True

    listed = await client.get(
        f"/api/v1/businesses/{owner['business_id']}/services", headers=owner["headers"]
    )
    assert len(listed.json()) == 1

    updated = await client.patch(
        f"/api/v1/businesses/{owner['business_id']}/services/{service['id']}",
        json={"price_cents": 18000},
        headers=owner["headers"],
    )
    assert updated.status_code == 200
    assert updated.json()["price_cents"] == 18000
    assert updated.json()["duration_minutes"] == 45  # untouched fields survive a partial update

    deleted = await client.delete(
        f"/api/v1/businesses/{owner['business_id']}/services/{service['id']}",
        headers=owner["headers"],
    )
    assert deleted.status_code == 204

    listed_after = await client.get(
        f"/api/v1/businesses/{owner['business_id']}/services", headers=owner["headers"]
    )
    assert listed_after.json() == []


async def test_staff_can_read_but_not_write_services(
    client: AsyncClient, owner: dict, db_session: AsyncSession
) -> None:
    creds = await _add_staff_member(db_session, owner["business_id"])
    staff_headers = await _login(client, **creds)

    read = await client.get(
        f"/api/v1/businesses/{owner['business_id']}/services", headers=staff_headers
    )
    assert read.status_code == 200

    write = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/services",
        json={"name": "Corte", "price_cents": 15000, "duration_minutes": 45},
        headers=staff_headers,
    )
    assert write.status_code == 403


async def test_services_are_isolated_between_businesses(client: AsyncClient, owner: dict) -> None:
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
    other_business = (
        await client.get("/api/v1/businesses", headers=other_headers)
    ).json()[0]["id"]

    created = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/services",
        json={"name": "Corte", "price_cents": 15000, "duration_minutes": 45},
        headers=owner["headers"],
    )
    service_id = created.json()["id"]

    # Owner of a different business can't even see this business's services...
    cross_list = await client.get(
        f"/api/v1/businesses/{owner['business_id']}/services", headers=other_headers
    )
    assert cross_list.status_code == 403

    # ...nor reach it by id through their own business (correctly scoped: 404,
    # not a leak of "it exists, just not for you").
    cross_get = await client.get(
        f"/api/v1/businesses/{other_business}/services/{service_id}", headers=other_headers
    )
    assert cross_get.status_code == 404
