import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.faq import FAQ
from app.schemas.faq import FAQCreate, FAQUpdate
from app.services.exceptions import NotFoundError


async def create_faq(db: AsyncSession, *, business_id: uuid.UUID, data: FAQCreate) -> FAQ:
    faq = FAQ(business_id=business_id, **data.model_dump())
    db.add(faq)
    await db.commit()
    await db.refresh(faq)
    return faq


async def list_faqs(
    db: AsyncSession, *, business_id: uuid.UUID, active_only: bool = False
) -> list[FAQ]:
    stmt = select(FAQ).where(FAQ.business_id == business_id)
    if active_only:
        stmt = stmt.where(FAQ.active.is_(True))
    return list(await db.scalars(stmt))


async def update_faq(
    db: AsyncSession, *, business_id: uuid.UUID, faq_id: uuid.UUID, data: FAQUpdate
) -> FAQ:
    faq = await db.scalar(select(FAQ).where(FAQ.id == faq_id, FAQ.business_id == business_id))
    if faq is None:
        raise NotFoundError(faq_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(faq, field, value)
    await db.commit()
    await db.refresh(faq)
    return faq


async def delete_faq(db: AsyncSession, *, business_id: uuid.UUID, faq_id: uuid.UUID) -> None:
    faq = await db.scalar(select(FAQ).where(FAQ.id == faq_id, FAQ.business_id == business_id))
    if faq is None:
        raise NotFoundError(faq_id)
    await db.delete(faq)
    await db.commit()
