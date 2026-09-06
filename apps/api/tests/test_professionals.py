from httpx import AsyncClient


async def _create_service(client: AsyncClient, owner: dict, name: str = "Corte") -> str:
    response = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/services",
        json={"name": name, "price_cents": 15000, "duration_minutes": 45},
        headers=owner["headers"],
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_create_professional_with_services(client: AsyncClient, owner: dict) -> None:
    service_id = await _create_service(client, owner)

    created = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/professionals",
        json={"name": "María", "service_ids": [service_id]},
        headers=owner["headers"],
    )
    assert created.status_code == 201, created.text
    professional = created.json()
    assert professional["name"] == "María"
    assert professional["service_ids"] == [service_id]


async def test_professional_cannot_be_linked_to_another_businesss_service(
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
    other_business_id = (
        await client.get("/api/v1/businesses", headers=other_headers)
    ).json()[0]["id"]
    foreign_service_id = await _create_service(
        client, {"business_id": other_business_id, "headers": other_headers}
    )

    response = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/professionals",
        json={"name": "María", "service_ids": [foreign_service_id]},
        headers=owner["headers"],
    )
    assert response.status_code == 400


async def test_update_professional_replaces_service_list(client: AsyncClient, owner: dict) -> None:
    service_a = await _create_service(client, owner, "Corte")
    service_b = await _create_service(client, owner, "Coloración")

    created = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/professionals",
        json={"name": "María", "service_ids": [service_a]},
        headers=owner["headers"],
    )
    professional_id = created.json()["id"]

    updated = await client.patch(
        f"/api/v1/businesses/{owner['business_id']}/professionals/{professional_id}",
        json={"service_ids": [service_b]},
        headers=owner["headers"],
    )
    assert updated.status_code == 200
    assert updated.json()["service_ids"] == [service_b]


async def test_professional_weekly_hours_roundtrip(client: AsyncClient, owner: dict) -> None:
    created = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/professionals",
        json={"name": "María"},
        headers=owner["headers"],
    )
    professional_id = created.json()["id"]

    replaced = await client.put(
        f"/api/v1/businesses/{owner['business_id']}/professionals/{professional_id}/hours",
        json=[{"weekday": 0, "start_time": "09:00:00", "end_time": "13:00:00"}],
        headers=owner["headers"],
    )
    assert replaced.status_code == 200, replaced.text
    assert len(replaced.json()) == 1

    fetched = await client.get(
        f"/api/v1/businesses/{owner['business_id']}/professionals/{professional_id}/hours",
        headers=owner["headers"],
    )
    assert fetched.status_code == 200
    assert fetched.json()[0]["weekday"] == 0


async def test_invalid_hours_range_is_rejected(client: AsyncClient, owner: dict) -> None:
    created = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/professionals",
        json={"name": "María"},
        headers=owner["headers"],
    )
    professional_id = created.json()["id"]

    response = await client.put(
        f"/api/v1/businesses/{owner['business_id']}/professionals/{professional_id}/hours",
        json=[{"weekday": 0, "start_time": "13:00:00", "end_time": "09:00:00"}],
        headers=owner["headers"],
    )
    assert response.status_code == 422
