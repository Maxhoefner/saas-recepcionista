import logging
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, AppointmentStatus
from app.models.business import Business
from app.models.customer import Customer
from app.models.reminder import Reminder, ReminderStatus
from app.models.reminder_settings import DEFAULT_REMINDER_TEMPLATE, ReminderSettings
from app.models.service import Service
from app.schemas.reminder import ReminderSettingsUpdate
from app.services import whatsapp_service
from app.whatsapp.providers.base import WhatsAppProvider

logger = logging.getLogger(__name__)


async def get_or_create_settings(db: AsyncSession, *, business_id: uuid.UUID) -> ReminderSettings:
    settings = await db.scalar(
        select(ReminderSettings).where(ReminderSettings.business_id == business_id)
    )
    if settings is not None:
        return settings

    settings = ReminderSettings(business_id=business_id)
    db.add(settings)
    await db.commit()
    await db.refresh(settings)
    return settings


async def update_settings(
    db: AsyncSession, *, business_id: uuid.UUID, data: ReminderSettingsUpdate
) -> ReminderSettings:
    settings = await get_or_create_settings(db, business_id=business_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    await db.commit()
    await db.refresh(settings)
    return settings


async def sync_reminder_for_appointment(db: AsyncSession, *, appointment: Appointment) -> None:
    """Creates/updates/cancels the appointment's reminder so it always
    matches the appointment's current time and status. Call this from
    appointment_service after create/reschedule/cancel — reminders are
    never computed independently of the appointment they belong to."""
    settings = await get_or_create_settings(db, business_id=appointment.business_id)
    reminder = await db.scalar(
        select(Reminder).where(Reminder.appointment_id == appointment.id)
    )

    still_active = appointment.status in (AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED)
    if not still_active or not settings.enabled:
        if reminder is not None and reminder.status == ReminderStatus.PENDING:
            reminder.status = ReminderStatus.CANCELLED
            await db.commit()
        return

    scheduled_for = appointment.start_datetime - timedelta(hours=settings.hours_before)
    if reminder is None:
        reminder = Reminder(
            business_id=appointment.business_id,
            appointment_id=appointment.id,
            scheduled_for=scheduled_for,
            status=ReminderStatus.PENDING,
        )
        db.add(reminder)
    else:
        reminder.scheduled_for = scheduled_for
        if reminder.status in (ReminderStatus.CANCELLED, ReminderStatus.SENT):
            reminder.status = ReminderStatus.PENDING
    await db.commit()


async def list_reminders(db: AsyncSession, *, business_id: uuid.UUID) -> list[Reminder]:
    result = await db.scalars(
        select(Reminder)
        .where(Reminder.business_id == business_id)
        .order_by(Reminder.scheduled_for)
    )
    return list(result)


async def list_due_reminders(db: AsyncSession, *, now: datetime) -> list[Reminder]:
    result = await db.scalars(
        select(Reminder).where(
            Reminder.status == ReminderStatus.PENDING, Reminder.scheduled_for <= now
        )
    )
    return list(result)


def _render_message(template: str, **values: str) -> str:
    try:
        return template.format(**values)
    except (KeyError, IndexError):
        logger.warning("Reminder template has an invalid placeholder, using the default one")
        return DEFAULT_REMINDER_TEMPLATE.format(**values)


async def send_reminder(
    db: AsyncSession, *, reminder: Reminder, whatsapp_provider: WhatsAppProvider
) -> None:
    appointment = await db.get(Appointment, reminder.appointment_id)
    now = datetime.now(UTC)
    if (
        appointment is None
        or appointment.status not in (AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED)
        or appointment.start_datetime <= now
    ):
        # The appointment was cancelled/completed, or already happened (e.g.
        # the worker was down) — a reminder for it no longer makes sense.
        reminder.status = ReminderStatus.CANCELLED
        await db.commit()
        return

    customer = await db.get(Customer, appointment.customer_id)
    service = await db.get(Service, appointment.service_id)
    business = await db.get(Business, appointment.business_id)
    settings = await get_or_create_settings(db, business_id=appointment.business_id)
    assert customer is not None and service is not None and business is not None

    local_start = appointment.start_datetime.astimezone(ZoneInfo(business.timezone))
    text = _render_message(
        settings.message_template,
        customer_name=customer.name,
        service=service.name,
        date=local_start.strftime("%d/%m"),
        time=local_start.strftime("%H:%M"),
    )

    try:
        await whatsapp_service.send_message(
            db,
            business_id=appointment.business_id,
            to=customer.phone,
            text=text,
            provider=whatsapp_provider,
        )
        reminder.status = ReminderStatus.SENT
        reminder.sent_at = now
    except Exception:
        logger.exception("Failed to send reminder %s", reminder.id)
        reminder.status = ReminderStatus.FAILED
    await db.commit()
