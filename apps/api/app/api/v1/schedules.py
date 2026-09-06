import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_business_role
from app.core.db import get_db
from app.models.membership import Role
from app.models.schedule import BlockedTime, BusinessHours, Holiday
from app.schemas.schedule import (
    BlockedTimeCreate,
    BlockedTimeRead,
    HolidayCreate,
    HolidayRead,
    WeeklyHoursEntry,
    WeeklyHoursRead,
)
from app.services import schedule_service
from app.services.exceptions import NotFoundError

router = APIRouter(prefix="/businesses/{business_id}", tags=["schedules"])

_read_access = require_business_role()
_write_access = require_business_role(Role.OWNER, Role.ADMIN)


@router.get(
    "/business-hours",
    response_model=list[WeeklyHoursRead],
    dependencies=[Depends(_read_access)],
)
async def get_business_hours(
    business_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[BusinessHours]:
    return await schedule_service.list_business_hours(db, business_id=business_id)


@router.put(
    "/business-hours",
    response_model=list[WeeklyHoursRead],
    dependencies=[Depends(_write_access)],
)
async def replace_business_hours(
    business_id: uuid.UUID,
    entries: list[WeeklyHoursEntry],
    db: AsyncSession = Depends(get_db),
) -> list[BusinessHours]:
    return await schedule_service.replace_business_hours(
        db, business_id=business_id, entries=entries
    )


@router.get(
    "/blocked-times",
    response_model=list[BlockedTimeRead],
    dependencies=[Depends(_read_access)],
)
async def list_blocked_times(
    business_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[BlockedTime]:
    return await schedule_service.list_blocked_times(db, business_id=business_id)


@router.post(
    "/blocked-times",
    response_model=BlockedTimeRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_write_access)],
)
async def create_blocked_time(
    business_id: uuid.UUID, data: BlockedTimeCreate, db: AsyncSession = Depends(get_db)
) -> BlockedTime:
    try:
        return await schedule_service.create_blocked_time(db, business_id=business_id, data=data)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profesional no encontrado") from exc


@router.delete(
    "/blocked-times/{blocked_time_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_write_access)],
)
async def delete_blocked_time(
    business_id: uuid.UUID, blocked_time_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    try:
        await schedule_service.delete_blocked_time(
            db, business_id=business_id, blocked_time_id=blocked_time_id
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bloqueo no encontrado") from exc


@router.get(
    "/holidays", response_model=list[HolidayRead], dependencies=[Depends(_read_access)]
)
async def list_holidays(
    business_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[Holiday]:
    return await schedule_service.list_holidays(db, business_id=business_id)


@router.post(
    "/holidays",
    response_model=HolidayRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_write_access)],
)
async def create_holiday(
    business_id: uuid.UUID, data: HolidayCreate, db: AsyncSession = Depends(get_db)
) -> Holiday:
    return await schedule_service.create_holiday(db, business_id=business_id, data=data)


@router.delete(
    "/holidays/{holiday_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_write_access)],
)
async def delete_holiday(
    business_id: uuid.UUID, holiday_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    try:
        await schedule_service.delete_holiday(db, business_id=business_id, holiday_id=holiday_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Feriado no encontrado") from exc
