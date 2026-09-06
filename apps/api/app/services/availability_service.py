import uuid
from datetime import UTC, datetime, time, timedelta
from datetime import date as date_type
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, AppointmentStatus
from app.models.business import Business
from app.models.professional import Professional, ProfessionalService
from app.models.schedule import BlockedTime, BusinessHours, Holiday, ProfessionalHours
from app.models.service import Service
from app.services.exceptions import NotFoundError, ServiceError

Interval = tuple[datetime, datetime]


class SlotUnavailableError(ServiceError):
    pass


async def _business_timezone(db: AsyncSession, business_id: uuid.UUID) -> ZoneInfo:
    business = await db.scalar(select(Business).where(Business.id == business_id))
    if business is None:
        raise NotFoundError(business_id)
    return ZoneInfo(business.timezone)


async def _get_active_service(
    db: AsyncSession, *, business_id: uuid.UUID, service_id: uuid.UUID
) -> Service:
    service = await db.scalar(
        select(Service).where(
            Service.id == service_id, Service.business_id == business_id, Service.active.is_(True)
        )
    )
    if service is None:
        raise NotFoundError(service_id)
    return service


async def _qualified_professional_ids(
    db: AsyncSession,
    *,
    business_id: uuid.UUID,
    service_id: uuid.UUID,
    professional_id: uuid.UUID | None,
) -> list[uuid.UUID]:
    base = (
        select(Professional.id)
        .join(ProfessionalService, ProfessionalService.professional_id == Professional.id)
        .where(
            Professional.business_id == business_id,
            Professional.active.is_(True),
            ProfessionalService.service_id == service_id,
        )
    )
    if professional_id is not None:
        result = await db.scalar(base.where(Professional.id == professional_id))
        if result is None:
            raise NotFoundError(professional_id)
        return [professional_id]
    return list(await db.scalars(base))


async def _is_holiday(db: AsyncSession, business_id: uuid.UUID, day: date_type) -> bool:
    holiday = await db.scalar(
        select(Holiday.id).where(Holiday.business_id == business_id, Holiday.holiday_date == day)
    )
    return holiday is not None


async def _open_windows(
    db: AsyncSession, *, business_id: uuid.UUID, professional_id: uuid.UUID, weekday: int
) -> list[tuple[time, time]]:
    """A professional's hours for that weekday, or the business's if the
    professional has no override configured."""
    prof_rows = list(
        await db.scalars(
            select(ProfessionalHours).where(
                ProfessionalHours.professional_id == professional_id,
                ProfessionalHours.weekday == weekday,
            )
        )
    )
    rows = prof_rows or list(
        await db.scalars(
            select(BusinessHours).where(
                BusinessHours.business_id == business_id, BusinessHours.weekday == weekday
            )
        )
    )
    return [(r.start_time, r.end_time) for r in rows]


async def _blocked_intervals(
    db: AsyncSession,
    *,
    business_id: uuid.UUID,
    professional_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> list[Interval]:
    rows = await db.scalars(
        select(BlockedTime).where(
            BlockedTime.business_id == business_id,
            or_(
                BlockedTime.professional_id == professional_id,
                BlockedTime.professional_id.is_(None),
            ),
            BlockedTime.start_datetime < window_end,
            BlockedTime.end_datetime > window_start,
        )
    )
    return [(r.start_datetime, r.end_datetime) for r in rows]


async def _busy_from_appointments(
    db: AsyncSession,
    *,
    business_id: uuid.UUID,
    professional_id: uuid.UUID,
    window_start: datetime,
    window_end: datetime,
) -> list[Interval]:
    rows = await db.scalars(
        select(Appointment).where(
            Appointment.business_id == business_id,
            Appointment.professional_id == professional_id,
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.start_datetime < window_end,
            Appointment.end_datetime > window_start,
        )
    )
    return [(r.start_datetime, r.end_datetime) for r in rows]


def _subtract(free: list[Interval], busy: list[Interval]) -> list[Interval]:
    for b_start, b_end in sorted(busy):
        next_free: list[Interval] = []
        for f_start, f_end in free:
            if b_end <= f_start or b_start >= f_end:
                next_free.append((f_start, f_end))
                continue
            if b_start > f_start:
                next_free.append((f_start, min(b_start, f_end)))
            if b_end < f_end:
                next_free.append((max(b_end, f_start), f_end))
        free = next_free
    return [interval for interval in free if interval[1] > interval[0]]


def _generate_slots(free: list[Interval], duration: timedelta) -> list[datetime]:
    slots: list[datetime] = []
    for start, end in sorted(free):
        cursor = start
        while cursor + duration <= end:
            slots.append(cursor)
            cursor += duration
    return slots


async def check_availability(
    db: AsyncSession,
    *,
    business_id: uuid.UUID,
    service_id: uuid.UUID,
    day: date_type,
    professional_id: uuid.UUID | None = None,
) -> list[dict]:
    """Available start times for a service on a given day, per qualified
    professional. Returns `[]` for a professional/day with no open hours,
    not an error — that's a legitimate "nothing available" answer the AI
    agent (Fase 5) needs to be able to give without special-casing it."""
    service = await _get_active_service(db, business_id=business_id, service_id=service_id)
    professional_ids = await _qualified_professional_ids(
        db, business_id=business_id, service_id=service_id, professional_id=professional_id
    )

    if await _is_holiday(db, business_id, day):
        return [{"professional_id": pid, "slots": []} for pid in professional_ids]

    tz = await _business_timezone(db, business_id)
    day_start = datetime.combine(day, time.min, tzinfo=tz).astimezone(UTC)
    day_end = day_start + timedelta(days=1)
    duration = timedelta(minutes=service.duration_minutes)

    availability = []
    for pid in professional_ids:
        windows = await _open_windows(
            db, business_id=business_id, professional_id=pid, weekday=day.weekday()
        )
        open_intervals = [
            (
                datetime.combine(day, w_start, tzinfo=tz).astimezone(UTC),
                datetime.combine(day, w_end, tzinfo=tz).astimezone(UTC),
            )
            for w_start, w_end in windows
        ]
        busy = await _blocked_intervals(
            db,
            business_id=business_id,
            professional_id=pid,
            window_start=day_start,
            window_end=day_end,
        )
        busy += await _busy_from_appointments(
            db,
            business_id=business_id,
            professional_id=pid,
            window_start=day_start,
            window_end=day_end,
        )
        free = _subtract(open_intervals, busy)
        availability.append({"professional_id": pid, "slots": _generate_slots(free, duration)})

    return availability


async def validate_slot_available(
    db: AsyncSession,
    *,
    business_id: uuid.UUID,
    professional_id: uuid.UUID,
    start_datetime: datetime,
    end_datetime: datetime,
) -> None:
    """Checks business hours, professional hours, holidays and blocked times.

    Deliberately does NOT check other appointments for overlap — that race
    is closed by the DB exclusion constraint on `appointments`, which is the
    only place that's actually safe against two concurrent booking requests.
    """
    tz = await _business_timezone(db, business_id)
    local_start = start_datetime.astimezone(tz)
    local_end = end_datetime.astimezone(tz)
    day = local_start.date()

    if await _is_holiday(db, business_id, day):
        raise SlotUnavailableError("El negocio no atiende ese día (feriado)")

    windows = await _open_windows(
        db, business_id=business_id, professional_id=professional_id, weekday=day.weekday()
    )
    fits_a_window = local_end.date() == day and any(
        local_start.time() >= w_start and local_end.time() <= w_end for w_start, w_end in windows
    )
    if not fits_a_window:
        raise SlotUnavailableError("Fuera del horario de atención")

    day_start = datetime.combine(day, time.min, tzinfo=tz).astimezone(UTC)
    day_end = day_start + timedelta(days=1)
    blocked = await _blocked_intervals(
        db,
        business_id=business_id,
        professional_id=professional_id,
        window_start=day_start,
        window_end=day_end,
    )
    if any(start_datetime < b_end and end_datetime > b_start for b_start, b_end in blocked):
        raise SlotUnavailableError("Ese horario está bloqueado")
