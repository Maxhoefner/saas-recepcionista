import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_business_role
from app.core.db import get_db
from app.models.membership import Role
from app.models.reminder import Reminder
from app.models.reminder_settings import ReminderSettings
from app.schemas.reminder import ReminderRead, ReminderSettingsRead, ReminderSettingsUpdate
from app.services import reminder_service

router = APIRouter(prefix="/businesses/{business_id}", tags=["reminders"])

_read_access = require_business_role()
_write_access = require_business_role(Role.OWNER, Role.ADMIN)


@router.get(
    "/reminder-settings", response_model=ReminderSettingsRead, dependencies=[Depends(_read_access)]
)
async def get_reminder_settings(
    business_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> ReminderSettings:
    return await reminder_service.get_or_create_settings(db, business_id=business_id)


@router.put(
    "/reminder-settings", response_model=ReminderSettingsRead, dependencies=[Depends(_write_access)]
)
async def update_reminder_settings(
    business_id: uuid.UUID, data: ReminderSettingsUpdate, db: AsyncSession = Depends(get_db)
) -> ReminderSettings:
    return await reminder_service.update_settings(db, business_id=business_id, data=data)


@router.get("/reminders", response_model=list[ReminderRead], dependencies=[Depends(_read_access)])
async def list_reminders(
    business_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[Reminder]:
    return await reminder_service.list_reminders(db, business_id=business_id)
