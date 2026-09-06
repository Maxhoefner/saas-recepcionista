import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.professional import Professional
from app.models.schedule import BlockedTime, BusinessHours, Holiday
from app.schemas.schedule import BlockedTimeCreate, HolidayCreate, WeeklyHoursEntry
from app.services.exceptions import NotFoundError


async def list_business_hours(db: AsyncSession, *, business_id: uuid.UUID) -> list[BusinessHours]:
    result = await db.scalars(
        select(BusinessHours)
        .where(BusinessHours.business_id == business_id)
        .order_by(BusinessHours.weekday, BusinessHours.start_time)
    )
    return list(result)


async def replace_business_hours(
    db: AsyncSession, *, business_id: uuid.UUID, entries: list[WeeklyHoursEntry]
) -> list[BusinessHours]:
    await db.execute(delete(BusinessHours).where(BusinessHours.business_id == business_id))
    for entry in entries:
        db.add(BusinessHours(business_id=business_id, **entry.model_dump()))
    await db.commit()
    return await list_business_hours(db, business_id=business_id)


async def _get_professional_or_404(
    db: AsyncSession, *, business_id: uuid.UUID, professional_id: uuid.UUID
) -> Professional:
    professional = await db.scalar(
        select(Professional).where(
            Professional.id == professional_id, Professional.business_id == business_id
        )
    )
    if professional is None:
        raise NotFoundError(professional_id)
    return professional


async def create_blocked_time(
    db: AsyncSession, *, business_id: uuid.UUID, data: BlockedTimeCreate
) -> BlockedTime:
    if data.professional_id is not None:
        await _get_professional_or_404(
            db, business_id=business_id, professional_id=data.professional_id
        )
    blocked = BlockedTime(business_id=business_id, **data.model_dump())
    db.add(blocked)
    await db.commit()
    await db.refresh(blocked)
    return blocked


async def list_blocked_times(db: AsyncSession, *, business_id: uuid.UUID) -> list[BlockedTime]:
    result = await db.scalars(
        select(BlockedTime)
        .where(BlockedTime.business_id == business_id)
        .order_by(BlockedTime.start_datetime)
    )
    return list(result)


async def delete_blocked_time(
    db: AsyncSession, *, business_id: uuid.UUID, blocked_time_id: uuid.UUID
) -> None:
    blocked = await db.scalar(
        select(BlockedTime).where(
            BlockedTime.id == blocked_time_id, BlockedTime.business_id == business_id
        )
    )
    if blocked is None:
        raise NotFoundError(blocked_time_id)
    await db.delete(blocked)
    await db.commit()


async def create_holiday(
    db: AsyncSession, *, business_id: uuid.UUID, data: HolidayCreate
) -> Holiday:
    holiday = Holiday(business_id=business_id, **data.model_dump())
    db.add(holiday)
    await db.commit()
    await db.refresh(holiday)
    return holiday


async def list_holidays(db: AsyncSession, *, business_id: uuid.UUID) -> list[Holiday]:
    result = await db.scalars(
        select(Holiday).where(Holiday.business_id == business_id).order_by(Holiday.holiday_date)
    )
    return list(result)


async def delete_holiday(
    db: AsyncSession, *, business_id: uuid.UUID, holiday_id: uuid.UUID
) -> None:
    holiday = await db.scalar(
        select(Holiday).where(Holiday.id == holiday_id, Holiday.business_id == business_id)
    )
    if holiday is None:
        raise NotFoundError(holiday_id)
    await db.delete(holiday)
    await db.commit()
