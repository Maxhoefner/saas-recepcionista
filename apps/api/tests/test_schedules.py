from httpx import AsyncClient


async def test_business_hours_replace_and_get(client: AsyncClient, owner: dict) -> None:
    payload = [
        {"weekday": 0, "start_time": "09:00:00", "end_time": "13:00:00"},
        {"weekday": 0, "start_time": "16:00:00", "end_time": "20:00:00"},
    ]
    replaced = await client.put(
        f"/api/v1/businesses/{owner['business_id']}/business-hours",
        json=payload,
        headers=owner["headers"],
    )
    assert replaced.status_code == 200, replaced.text
    assert len(replaced.json()) == 2

    fetched = await client.get(
        f"/api/v1/businesses/{owner['business_id']}/business-hours", headers=owner["headers"]
    )
    assert len(fetched.json()) == 2

    # Replacing again fully overwrites the previous week, not appends to it.
    replaced_again = await client.put(
        f"/api/v1/businesses/{owner['business_id']}/business-hours",
        json=[{"weekday": 1, "start_time": "10:00:00", "end_time": "14:00:00"}],
        headers=owner["headers"],
    )
    assert len(replaced_again.json()) == 1


async def test_blocked_time_create_list_delete(client: AsyncClient, owner: dict) -> None:
    created = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/blocked-times",
        json={
            "start_datetime": "2026-12-25T00:00:00Z",
            "end_datetime": "2026-12-26T00:00:00Z",
            "reason": "Navidad",
        },
        headers=owner["headers"],
    )
    assert created.status_code == 201, created.text
    blocked_id = created.json()["id"]

    listed = await client.get(
        f"/api/v1/businesses/{owner['business_id']}/blocked-times", headers=owner["headers"]
    )
    assert len(listed.json()) == 1

    deleted = await client.delete(
        f"/api/v1/businesses/{owner['business_id']}/blocked-times/{blocked_id}",
        headers=owner["headers"],
    )
    assert deleted.status_code == 204


async def test_blocked_time_rejects_professional_from_another_business(
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
    foreign_professional = await client.post(
        f"/api/v1/businesses/{other_business_id}/professionals",
        json={"name": "Juan"},
        headers=other_headers,
    )
    foreign_professional_id = foreign_professional.json()["id"]

    response = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/blocked-times",
        json={
            "professional_id": foreign_professional_id,
            "start_datetime": "2026-12-25T00:00:00Z",
            "end_datetime": "2026-12-26T00:00:00Z",
        },
        headers=owner["headers"],
    )
    assert response.status_code == 404


async def test_holiday_create_list_delete(client: AsyncClient, owner: dict) -> None:
    created = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/holidays",
        json={"holiday_date": "2026-12-25", "description": "Navidad"},
        headers=owner["headers"],
    )
    assert created.status_code == 201, created.text
    holiday_id = created.json()["id"]

    listed = await client.get(
        f"/api/v1/businesses/{owner['business_id']}/holidays", headers=owner["headers"]
    )
    assert len(listed.json()) == 1

    deleted = await client.delete(
        f"/api/v1/businesses/{owner['business_id']}/holidays/{holiday_id}",
        headers=owner["headers"],
    )
    assert deleted.status_code == 204
