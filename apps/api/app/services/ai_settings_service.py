import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_settings import AISettings
from app.schemas.ai_settings import AISettingsUpdate


async def get_or_create_ai_settings(db: AsyncSession, *, business_id: uuid.UUID) -> AISettings:
    settings = await db.scalar(select(AISettings).where(AISettings.business_id == business_id))
    if settings is not None:
        return settings

    settings = AISettings(business_id=business_id)
    db.add(settings)
    await db.commit()
    await db.refresh(settings)
    return settings


async def update_ai_settings(
    db: AsyncSession, *, business_id: uuid.UUID, data: AISettingsUpdate
) -> AISettings:
    settings = await get_or_create_ai_settings(db, business_id=business_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    await db.commit()
    await db.refresh(settings)
    return settings
