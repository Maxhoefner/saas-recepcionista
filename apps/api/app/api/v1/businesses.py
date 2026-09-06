from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.membership import Role
from app.models.user import User
from app.schemas.business import BusinessCreate, BusinessWithRole
from app.services.business_service import create_business_for_user, list_businesses_for_user

router = APIRouter(prefix="/businesses", tags=["businesses"])


@router.get("", response_model=list[BusinessWithRole])
async def list_my_businesses(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[BusinessWithRole]:
    memberships = await list_businesses_for_user(db, user.id)
    return [
        BusinessWithRole(
            id=m.business.id,
            name=m.business.name,
            slug=m.business.slug,
            timezone=m.business.timezone,
            locale=m.business.locale,
            role=m.role,
        )
        for m in memberships
    ]


@router.post("", response_model=BusinessWithRole, status_code=status.HTTP_201_CREATED)
async def create_business(
    data: BusinessCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BusinessWithRole:
    business = await create_business_for_user(
        db,
        user_id=user.id,
        name=data.name,
        timezone=data.timezone,
        locale=data.locale,
        role=Role.OWNER,
    )
    await db.commit()
    await db.refresh(business)
    return BusinessWithRole(
        id=business.id,
        name=business.name,
        slug=business.slug,
        timezone=business.timezone,
        locale=business.locale,
        role=Role.OWNER,
    )
