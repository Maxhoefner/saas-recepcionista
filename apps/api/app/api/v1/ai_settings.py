import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_business_role
from app.core.db import get_db
from app.models.ai_settings import AISettings
from app.models.membership import Role
from app.models.user import User
from app.schemas.ai_settings import AISettingsRead, AISettingsUpdate
from app.services import ai_settings_service, audit_service

router = APIRouter(prefix="/businesses/{business_id}/ai-settings", tags=["ai-settings"])

_read_access = require_business_role()
_write_access = require_business_role(Role.OWNER, Role.ADMIN)


@router.get("", response_model=AISettingsRead, dependencies=[Depends(_read_access)])
async def get_ai_settings(
    business_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> AISettings:
    return await ai_settings_service.get_or_create_ai_settings(db, business_id=business_id)


@router.put("", response_model=AISettingsRead, dependencies=[Depends(_write_access)])
async def update_ai_settings(
    business_id: uuid.UUID,
    data: AISettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AISettings:
    settings = await ai_settings_service.update_ai_settings(db, business_id=business_id, data=data)
    await audit_service.record(
        db,
        business_id=business_id,
        user_id=user.id,
        action="ai_settings.update",
        entity="ai_settings",
        details=data.model_dump(exclude_unset=True),
    )
    await db.commit()
    return settings
