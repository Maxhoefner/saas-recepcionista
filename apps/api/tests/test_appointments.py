from httpx import AsyncClient

_ALL_DAY_HOURS = [
    {"weekday": w, "start_time": "00:00:00", "end_time": "23:59:00"} for w in range(7)
]


async def _setup_bookable(client: AsyncClient, owner: dict) -> dict:
    """Business open 24/7 (so tests don't depend on which weekday `today`
    falls on), one service, one professional who performs it, one customer.
    """
    biz = owner["business_id"]
    headers = owner["headers"]

    await client.put(
        f"/api/v1/businesses/{biz}/business-hours", json=_ALL_DAY_HOURS, headers=headers
    )

    service = (
        await client.post(
            f"/api/v1/businesses/{biz}/services",
            json={"name": "Corte", "price_cents": 15000, "duration_minutes": 30},
            headers=headers,
        )
    ).json()

    professional = (
        await client.post(
            f"/api/v1/businesses/{biz}/professionals",
            json={"name": "María", "service_ids": [service["id"]]},
            headers=headers,
        )
    ).json()

    customer = (
        await client.post(
            f"/api/v1/businesses/{biz}/customers",
            json={"phone": "+5491122334455", "name": "Juan Pérez"},
            headers=headers,
        )
    ).json()

    return {"service": service, "professional": professional, "customer": customer}


async def test_create_appointment_and_check_availability(client: AsyncClient, owner: dict) -> None:
    setup = await _setup_bookable(client, owner)
    biz, headers = owner["business_id"], owner["headers"]

    before = await client.get(
        f"/api/v1/businesses/{biz}/availability",
        params={"service_id": setup["service"]["id"], "day": "2026-12-15"},
        headers=headers,
    )
    assert before.status_code == 200
    slots_before = before.json()[0]["slots"]
    assert "2026-12-15T10:00:00Z" in slots_before

    created = await client.post(
        f"/api/v1/businesses/{biz}/appointments",
        json={
            "customer_id": setup["customer"]["id"],
            "professional_id": setup["professional"]["id"],
            "service_id": setup["service"]["id"],
            "start_datetime": "2026-12-15T10:00:00Z",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    appointment = created.json()
    assert appointment["status"] == "PENDING"
    assert appointment["end_datetime"] == "2026-12-15T10:30:00Z"

    after = await client.get(
        f"/api/v1/businesses/{biz}/availability",
        params={"service_id": setup["service"]["id"], "day": "2026-12-15"},
        headers=headers,
    )
    assert "2026-12-15T10:00:00Z" not in after.json()[0]["slots"]


async def test_double_booking_is_rejected(client: AsyncClient, owner: dict) -> None:
    setup = await _setup_bookable(client, owner)
    biz, headers = owner["business_id"], owner["headers"]
    payload = {
        "customer_id": setup["customer"]["id"],
        "professional_id": setup["professional"]["id"],
        "service_id": setup["service"]["id"],
        "start_datetime": "2026-12-15T10:00:00Z",
    }

    first = await client.post(
        f"/api/v1/businesses/{biz}/appointments", json=payload, headers=headers
    )
    assert first.status_code == 201

    # Overlapping, not identical: 10:15-10:45 vs the existing 10:00-10:30.
    overlapping = dict(payload, start_datetime="2026-12-15T10:15:00Z")
    second = await client.post(
        f"/api/v1/businesses/{biz}/appointments", json=overlapping, headers=headers
    )
    assert second.status_code == 409


async def test_cancelling_frees_up_the_slot(client: AsyncClient, owner: dict) -> None:
    setup = await _setup_bookable(client, owner)
    biz, headers = owner["business_id"], owner["headers"]
    payload = {
        "customer_id": setup["customer"]["id"],
        "professional_id": setup["professional"]["id"],
        "service_id": setup["service"]["id"],
        "start_datetime": "2026-12-15T10:00:00Z",
    }

    created = await client.post(
        f"/api/v1/businesses/{biz}/appointments", json=payload, headers=headers
    )
    appointment_id = created.json()["id"]

    cancelled = await client.post(
        f"/api/v1/businesses/{biz}/appointments/{appointment_id}/cancel", headers=headers
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"

    rebooked = await client.post(
        f"/api/v1/businesses/{biz}/appointments", json=payload, headers=headers
    )
    assert rebooked.status_code == 201


async def test_reschedule_moves_the_appointment(client: AsyncClient, owner: dict) -> None:
    setup = await _setup_bookable(client, owner)
    biz, headers = owner["business_id"], owner["headers"]

    created = await client.post(
        f"/api/v1/businesses/{biz}/appointments",
        json={
            "customer_id": setup["customer"]["id"],
            "professional_id": setup["professional"]["id"],
            "service_id": setup["service"]["id"],
            "start_datetime": "2026-12-15T10:00:00Z",
        },
        headers=headers,
    )
    appointment_id = created.json()["id"]

    rescheduled = await client.post(
        f"/api/v1/businesses/{biz}/appointments/{appointment_id}/reschedule",
        json={"start_datetime": "2026-12-15T14:00:00Z"},
        headers=headers,
    )
    assert rescheduled.status_code == 200, rescheduled.text
    assert rescheduled.json()["start_datetime"] == "2026-12-15T14:00:00Z"
    assert rescheduled.json()["end_datetime"] == "2026-12-15T14:30:00Z"


async def test_appointment_outside_business_hours_is_rejected(
    client: AsyncClient, owner: dict
) -> None:
    biz, headers = owner["business_id"], owner["headers"]
    # No business-hours configured at all -> nothing is ever open.
    service = (
        await client.post(
            f"/api/v1/businesses/{biz}/services",
            json={"name": "Corte", "price_cents": 15000, "duration_minutes": 30},
            headers=headers,
        )
    ).json()
    professional = (
        await client.post(
            f"/api/v1/businesses/{biz}/professionals",
            json={"name": "María", "service_ids": [service["id"]]},
            headers=headers,
        )
    ).json()
    customer = (
        await client.post(
            f"/api/v1/businesses/{biz}/customers",
            json={"phone": "+5491122334455", "name": "Juan Pérez"},
            headers=headers,
        )
    ).json()

    response = await client.post(
        f"/api/v1/businesses/{biz}/appointments",
        json={
            "customer_id": customer["id"],
            "professional_id": professional["id"],
            "service_id": service["id"],
            "start_datetime": "2026-12-15T10:00:00Z",
        },
        headers=headers,
    )
    assert response.status_code == 422


async def test_status_transitions_are_enforced(client: AsyncClient, owner: dict) -> None:
    setup = await _setup_bookable(client, owner)
    biz, headers = owner["business_id"], owner["headers"]

    created = await client.post(
        f"/api/v1/businesses/{biz}/appointments",
        json={
            "customer_id": setup["customer"]["id"],
            "professional_id": setup["professional"]["id"],
            "service_id": setup["service"]["id"],
            "start_datetime": "2026-12-15T10:00:00Z",
        },
        headers=headers,
    )
    appointment_id = created.json()["id"]

    completed = await client.post(
        f"/api/v1/businesses/{biz}/appointments/{appointment_id}/complete", headers=headers
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"

    # A completed appointment can't be cancelled after the fact.
    cancel_after_complete = await client.post(
        f"/api/v1/businesses/{biz}/appointments/{appointment_id}/cancel", headers=headers
    )
    assert cancel_after_complete.status_code == 409


async def test_appointments_are_isolated_between_businesses(
    client: AsyncClient, owner: dict
) -> None:
    setup = await _setup_bookable(client, owner)
    biz, headers = owner["business_id"], owner["headers"]

    created = await client.post(
        f"/api/v1/businesses/{biz}/appointments",
        json={
            "customer_id": setup["customer"]["id"],
            "professional_id": setup["professional"]["id"],
            "service_id": setup["service"]["id"],
            "start_datetime": "2026-12-15T10:00:00Z",
        },
        headers=headers,
    )
    appointment_id = created.json()["id"]

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

    cross = await client.get(
        f"/api/v1/businesses/{other_business_id}/appointments/{appointment_id}",
        headers=other_headers,
    )
    assert cross.status_code == 404
