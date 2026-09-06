import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, AppointmentStatus
from app.models.customer import Customer
from app.models.professional import Professional
from app.models.reminder import Reminder, ReminderStatus
from app.models.service import Service
from app.services import reminder_service
from tests.conftest import FakeWhatsAppProvider

_ALL_DAY_HOURS = [
    {"weekday": w, "start_time": "00:00:00", "end_time": "23:59:00"} for w in range(7)
]


async def _setup_bookable(client: AsyncClient, owner: dict) -> dict:
    biz, headers = owner["business_id"], owner["headers"]
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


async def _book(client: AsyncClient, owner: dict, setup: dict, start_datetime: str) -> dict:
    response = await client.post(
        f"/api/v1/businesses/{owner['business_id']}/appointments",
        json={
            "customer_id": setup["customer"]["id"],
            "professional_id": setup["professional"]["id"],
            "service_id": setup["service"]["id"],
            "start_datetime": start_datetime,
        },
        headers=owner["headers"],
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_reminder_settings_defaults_and_update(client: AsyncClient, owner: dict) -> None:
    biz, headers = owner["business_id"], owner["headers"]

    defaults = await client.get(f"/api/v1/businesses/{biz}/reminder-settings", headers=headers)
    assert defaults.status_code == 200
    assert defaults.json()["enabled"] is True
    assert defaults.json()["hours_before"] == 24

    updated = await client.put(
        f"/api/v1/businesses/{biz}/reminder-settings", json={"hours_before": 2}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["hours_before"] == 2


async def test_creating_an_appointment_schedules_a_reminder(
    client: AsyncClient, owner: dict
) -> None:
    setup = await _setup_bookable(client, owner)
    appointment = await _book(client, owner, setup, "2026-12-15T10:00:00Z")

    reminders = (
        await client.get(
            f"/api/v1/businesses/{owner['business_id']}/reminders", headers=owner["headers"]
        )
    ).json()
    assert len(reminders) == 1
    assert reminders[0]["appointment_id"] == appointment["id"]
    assert reminders[0]["status"] == "PENDING"
    assert reminders[0]["scheduled_for"] == "2026-12-14T10:00:00Z"


async def test_cancelling_appointment_cancels_its_reminder(
    client: AsyncClient, owner: dict
) -> None:
    setup = await _setup_bookable(client, owner)
    appointment = await _book(client, owner, setup, "2026-12-15T10:00:00Z")

    await client.post(
        f"/api/v1/businesses/{owner['business_id']}/appointments/{appointment['id']}/cancel",
        headers=owner["headers"],
    )

    reminders = (
        await client.get(
            f"/api/v1/businesses/{owner['business_id']}/reminders", headers=owner["headers"]
        )
    ).json()
    assert reminders[0]["status"] == "CANCELLED"


async def test_rescheduling_appointment_moves_its_reminder(
    client: AsyncClient, owner: dict
) -> None:
    setup = await _setup_bookable(client, owner)
    appointment = await _book(client, owner, setup, "2026-12-15T10:00:00Z")

    await client.post(
        f"/api/v1/businesses/{owner['business_id']}/appointments/{appointment['id']}/reschedule",
        json={"start_datetime": "2026-12-16T14:00:00Z"},
        headers=owner["headers"],
    )

    reminders = (
        await client.get(
            f"/api/v1/businesses/{owner['business_id']}/reminders", headers=owner["headers"]
        )
    ).json()
    assert reminders[0]["scheduled_for"] == "2026-12-15T14:00:00Z"
    assert reminders[0]["status"] == "PENDING"


async def test_disabling_reminders_cancels_pending_ones_on_next_appointment_change(
    client: AsyncClient, owner: dict
) -> None:
    setup = await _setup_bookable(client, owner)
    appointment = await _book(client, owner, setup, "2026-12-15T10:00:00Z")

    await client.put(
        f"/api/v1/businesses/{owner['business_id']}/reminder-settings",
        json={"enabled": False},
        headers=owner["headers"],
    )
    # Confirming re-runs the sync — with reminders disabled it should cancel.
    await client.post(
        f"/api/v1/businesses/{owner['business_id']}/appointments/{appointment['id']}/confirm",
        headers=owner["headers"],
    )

    reminders = (
        await client.get(
            f"/api/v1/businesses/{owner['business_id']}/reminders", headers=owner["headers"]
        )
    ).json()
    assert reminders[0]["status"] == "CANCELLED"


async def test_send_due_reminder_sends_via_whatsapp_and_marks_sent(
    client: AsyncClient,
    owner: dict,
    db_session: AsyncSession,
    fake_whatsapp_provider: FakeWhatsAppProvider,
) -> None:
    setup = await _setup_bookable(client, owner)
    biz, headers = owner["business_id"], owner["headers"]
    await client.put(
        f"/api/v1/businesses/{biz}/whatsapp-account",
        json={
            "phone_number_id": "123456",
            "waba_id": "waba_1",
            "display_phone_number": "+5491100000000",
            "access_token": "token",
        },
        headers=headers,
    )
    appointment = await _book(client, owner, setup, "2026-12-15T10:00:00Z")

    # Force the reminder to be "due" without waiting for real time to pass.
    reminder = await db_session.scalar(
        select(Reminder).where(Reminder.appointment_id == uuid.UUID(appointment["id"]))
    )
    assert reminder is not None
    reminder.scheduled_for = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    due = await reminder_service.list_due_reminders(db_session, now=datetime.now(UTC))
    assert len(due) == 1
    await reminder_service.send_reminder(
        db_session, reminder=due[0], whatsapp_provider=fake_whatsapp_provider
    )

    assert len(fake_whatsapp_provider.sent) == 1
    assert fake_whatsapp_provider.sent[0]["to"] == "+5491122334455"
    assert "Juan Pérez" in fake_whatsapp_provider.sent[0]["text"]
    assert "Corte" in fake_whatsapp_provider.sent[0]["text"]

    reminders = (
        await client.get(f"/api/v1/businesses/{biz}/reminders", headers=headers)
    ).json()
    assert reminders[0]["status"] == "SENT"


async def test_send_due_reminder_for_a_past_appointment_is_cancelled_not_sent(
    db_session: AsyncSession, owner: dict, fake_whatsapp_provider: FakeWhatsAppProvider
) -> None:
    """A reminder can end up "due" for an appointment that already happened
    (e.g. the worker was down for a while) — it must not send a confusing
    reminder for the past, just quietly cancel itself."""
    business_id = uuid.UUID(owner["business_id"])

    service = Service(
        business_id=business_id, name="Corte", price_cents=1000, duration_minutes=30
    )
    professional = Professional(business_id=business_id, name="María")
    customer = Customer(business_id=business_id, phone="+5491100000001", name="Cliente Viejo")
    db_session.add_all([service, professional, customer])
    await db_session.flush()

    past_start = datetime.now(UTC) - timedelta(days=2)
    appointment = Appointment(
        business_id=business_id,
        customer_id=customer.id,
        professional_id=professional.id,
        service_id=service.id,
        start_datetime=past_start,
        end_datetime=past_start + timedelta(minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(appointment)
    await db_session.flush()

    reminder = Reminder(
        business_id=business_id,
        appointment_id=appointment.id,
        scheduled_for=past_start - timedelta(hours=24),
        status=ReminderStatus.PENDING,
    )
    db_session.add(reminder)
    await db_session.commit()

    await reminder_service.send_reminder(
        db_session, reminder=reminder, whatsapp_provider=fake_whatsapp_provider
    )

    assert fake_whatsapp_provider.sent == []
    await db_session.refresh(reminder)
    assert reminder.status == ReminderStatus.CANCELLED
