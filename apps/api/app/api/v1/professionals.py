import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_business_role
from app.core.db import get_db
from app.models.membership import Role
from app.models.schedule import ProfessionalHours
from app.models.user import User
from app.schemas.professional import ProfessionalCreate, ProfessionalRead, ProfessionalUpdate
from app.schemas.schedule import WeeklyHoursEntry, WeeklyHoursRead
from app.services import audit_service, catalog_service
from app.services.exceptions import NotFoundError

router = APIRouter(prefix="/businesses/{business_id}/professionals", tags=["professionals"])

_read_access = require_business_role()
_write_access = require_business_role(Role.OWNER, Role.ADMIN)


@router.get("", response_model=list[ProfessionalRead], dependencies=[Depends(_read_access)])
async def list_professionals(
    business_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[dict]:
    professionals = await catalog_service.list_professionals(db, business_id=business_id)
    return [await catalog_service.professional_to_read_dict(db, p) for p in professionals]


@router.post(
    "",
    response_model=ProfessionalRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_write_access)],
)
async def create_professional(
    business_id: uuid.UUID, data: ProfessionalCreate, db: AsyncSession = Depends(get_db)
) -> dict:
    try:
        professional = await catalog_service.create_professional(
            db, business_id=business_id, data=data
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return await catalog_service.professional_to_read_dict(db, professional)


@router.get(
    "/{professional_id}", response_model=ProfessionalRead, dependencies=[Depends(_read_access)]
)
async def get_professional(
    business_id: uuid.UUID, professional_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> dict:
    try:
        professional = await catalog_service.get_professional(
            db, business_id=business_id, professional_id=professional_id
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profesional no encontrado") from exc
    return await catalog_service.professional_to_read_dict(db, professional)


@router.patch(
    "/{professional_id}", response_model=ProfessionalRead, dependencies=[Depends(_write_access)]
)
async def update_professional(
    business_id: uuid.UUID,
    professional_id: uuid.UUID,
    data: ProfessionalUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        professional = await catalog_service.update_professional(
            db, business_id=business_id, professional_id=professional_id, data=data
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return await catalog_service.professional_to_read_dict(db, professional)


@router.delete(
    "/{professional_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_write_access)],
)
async def delete_professional(
    business_id: uuid.UUID,
    professional_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    try:
        await catalog_service.delete_professional(
            db, business_id=business_id, professional_id=professional_id
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profesional no encontrado") from exc
    await audit_service.record(
        db,
        business_id=business_id,
        user_id=user.id,
        action="professional.delete",
        entity="professional",
        entity_id=str(professional_id),
    )
    await db.commit()


@router.get(
    "/{professional_id}/hours",
    response_model=list[WeeklyHoursRead],
    dependencies=[Depends(_read_access)],
)
async def get_professional_hours(
    business_id: uuid.UUID, professional_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[ProfessionalHours]:
    await catalog_service.get_professional(
        db, business_id=business_id, professional_id=professional_id
    )
    result = await db.scalars(
        select(ProfessionalHours)
        .where(ProfessionalHours.professional_id == professional_id)
        .order_by(ProfessionalHours.weekday, ProfessionalHours.start_time)
    )
    return list(result)


@router.put(
    "/{professional_id}/hours",
    response_model=list[WeeklyHoursRead],
    dependencies=[Depends(_write_access)],
)
async def replace_professional_hours(
    business_id: uuid.UUID,
    professional_id: uuid.UUID,
    entries: list[WeeklyHoursEntry],
    db: AsyncSession = Depends(get_db),
) -> list[ProfessionalHours]:
    try:
        await catalog_service.get_professional(
            db, business_id=business_id, professional_id=professional_id
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profesional no encontrado") from exc

    await db.execute(
        delete(ProfessionalHours).where(ProfessionalHours.professional_id == professional_id)
    )
    for entry in entries:
        db.add(ProfessionalHours(professional_id=professional_id, **entry.model_dump()))
    await db.commit()

    result = await db.scalars(
        select(ProfessionalHours)
        .where(ProfessionalHours.professional_id == professional_id)
        .order_by(ProfessionalHours.weekday, ProfessionalHours.start_time)
    )
    return list(result)
