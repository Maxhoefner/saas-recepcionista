from httpx import AsyncClient


async def test_connect_and_read_whatsapp_account(client: AsyncClient, owner: dict) -> None:
    biz, headers = owner["business_id"], owner["headers"]

    connected = await client.put(
        f"/api/v1/businesses/{biz}/whatsapp-account",
        json={
            "phone_number_id": "1234567890",
            "waba_id": "waba_1",
            "display_phone_number": "+54 9 11 1234-5678",
            "access_token": "super-secret-token",
        },
        headers=headers,
    )
    assert connected.status_code == 200, connected.text
    body = connected.json()
    assert body["phone_number_id"] == "1234567890"
    assert "access_token" not in body

    fetched = await client.get(f"/api/v1/businesses/{biz}/whatsapp-account", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["waba_id"] == "waba_1"


async def test_whatsapp_account_not_connected_is_404(client: AsyncClient, owner: dict) -> None:
    response = await client.get(
        f"/api/v1/businesses/{owner['business_id']}/whatsapp-account", headers=owner["headers"]
    )
    assert response.status_code == 404


async def test_cannot_connect_a_phone_number_already_used_by_another_business(
    client: AsyncClient, owner: dict
) -> None:
    await client.put(
        f"/api/v1/businesses/{owner['business_id']}/whatsapp-account",
        json={
            "phone_number_id": "1234567890",
            "waba_id": "waba_1",
            "display_phone_number": "+54 9 11 1234-5678",
            "access_token": "token-a",
        },
        headers=owner["headers"],
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

    conflict = await client.put(
        f"/api/v1/businesses/{other_biz}/whatsapp-account",
        json={
            "phone_number_id": "1234567890",
            "waba_id": "waba_2",
            "display_phone_number": "+54 9 11 8765-4321",
            "access_token": "token-b",
        },
        headers=other_headers,
    )
    assert conflict.status_code == 409
