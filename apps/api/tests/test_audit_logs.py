from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.membership import Membership, Role
from app.models.user import User


async def test_connecting_whatsapp_creates_an_audit_entry(client: AsyncClient, owner: dict) -> None:
    biz, headers = owner["business_id"], owner["headers"]
    await client.put(
        f"/api/v1/businesses/{biz}/whatsapp-account",
        json={
            "phone_number_id": "123456",
            "waba_id": "waba_1",
            "display_phone_number": "+5491100000000",
            "access_token": "super-secret-token",
        },
        headers=headers,
    )

    logs = (await client.get(f"/api/v1/businesses/{biz}/audit-logs", headers=headers)).json()
    assert len(logs) == 1
    assert logs[0]["action"] == "whatsapp_account.connect"
    assert logs[0]["entity"] == "whatsapp_account"
    assert logs[0]["user_id"] == owner["user_id"]
    # The token itself must never end up in the audit trail.
    assert "super-secret-token" not in str(logs[0])


async def test_deleting_a_service_creates_an_audit_entry(client: AsyncClient, owner: dict) -> None:
    biz, headers = owner["business_id"], owner["headers"]
    service = (
        await client.post(
            f"/api/v1/businesses/{biz}/services",
            json={"name": "Corte", "price_cents": 15000, "duration_minutes": 30},
            headers=headers,
        )
    ).json()
    await client.delete(f"/api/v1/businesses/{biz}/services/{service['id']}", headers=headers)

    logs = (await client.get(f"/api/v1/businesses/{biz}/audit-logs", headers=headers)).json()
    assert any(
        log["action"] == "service.delete" and log["entity_id"] == service["id"] for log in logs
    )
    # Creating the service itself is routine catalog maintenance, not logged
    # — only the destructive action is.
    assert not any(log["action"] == "service.create" for log in logs)


async def test_audit_logs_are_isolated_between_businesses(client: AsyncClient, owner: dict) -> None:
    biz, headers = owner["business_id"], owner["headers"]
    await client.put(
        f"/api/v1/businesses/{biz}/ai-settings",
        json={"assistant_name": "Sofi 2"},
        headers=headers,
    )

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
    other_biz = (await client.get("/api/v1/businesses", headers=other_headers)).json()[0]["id"]

    other_logs = (
        await client.get(f"/api/v1/businesses/{other_biz}/audit-logs", headers=other_headers)
    ).json()
    assert other_logs == []


async def test_staff_cannot_read_audit_logs(
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

    response = await client.get(
        f"/api/v1/businesses/{owner['business_id']}/audit-logs", headers=staff_headers
    )
    assert response.status_code == 403
