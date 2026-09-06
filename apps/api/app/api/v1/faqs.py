import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_business_role
from app.core.db import get_db
from app.models.faq import FAQ
from app.models.membership import Role
from app.schemas.faq import FAQCreate, FAQRead, FAQUpdate
from app.services import faq_service
from app.services.exceptions import NotFoundError

router = APIRouter(prefix="/businesses/{business_id}/faqs", tags=["faqs"])

_read_access = require_business_role()
_write_access = require_business_role(Role.OWNER, Role.ADMIN)


@router.get("", response_model=list[FAQRead], dependencies=[Depends(_read_access)])
async def list_faqs(business_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[FAQ]:
    return await faq_service.list_faqs(db, business_id=business_id)


@router.post(
    "",
    response_model=FAQRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_write_access)],
)
async def create_faq(
    business_id: uuid.UUID, data: FAQCreate, db: AsyncSession = Depends(get_db)
) -> FAQ:
    return await faq_service.create_faq(db, business_id=business_id, data=data)


@router.patch("/{faq_id}", response_model=FAQRead, dependencies=[Depends(_write_access)])
async def update_faq(
    business_id: uuid.UUID, faq_id: uuid.UUID, data: FAQUpdate, db: AsyncSession = Depends(get_db)
) -> FAQ:
    try:
        return await faq_service.update_faq(db, business_id=business_id, faq_id=faq_id, data=data)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "FAQ no encontrada") from exc


@router.delete(
    "/{faq_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(_write_access)]
)
async def delete_faq(
    business_id: uuid.UUID, faq_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    try:
        await faq_service.delete_faq(db, business_id=business_id, faq_id=faq_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "FAQ no encontrada") from exc
