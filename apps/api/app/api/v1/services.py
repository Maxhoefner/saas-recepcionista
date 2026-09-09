import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_business_role
from app.core.db import get_db
from app.models.membership import Role
from app.models.service import Service
from app.models.user import User
from app.schemas.service import ServiceCreate, ServiceRead, ServiceUpdate
from app.services import audit_service, catalog_service
from app.services.exceptions import NotFoundError

router = APIRouter(prefix="/businesses/{business_id}/services", tags=["services"])

_read_access = require_business_role()
_write_access = require_business_role(Role.OWNER, Role.ADMIN)


@router.get("", response_model=list[ServiceRead], dependencies=[Depends(_read_access)])
async def list_services(
    business_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[Service]:
    return await catalog_service.list_services(db, business_id=business_id)


@router.post(
    "",
    response_model=ServiceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_write_access)],
)
async def create_service(
    business_id: uuid.UUID, data: ServiceCreate, db: AsyncSession = Depends(get_db)
) -> Service:
    return await catalog_service.create_service(db, business_id=business_id, data=data)


@router.get("/{service_id}", response_model=ServiceRead, dependencies=[Depends(_read_access)])
async def get_service(
    business_id: uuid.UUID, service_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Service:
    try:
        return await catalog_service.get_service(db, business_id=business_id, service_id=service_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Servicio no encontrado") from exc


@router.patch("/{service_id}", response_model=ServiceRead, dependencies=[Depends(_write_access)])
async def update_service(
    business_id: uuid.UUID,
    service_id: uuid.UUID,
    data: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
) -> Service:
    try:
        return await catalog_service.update_service(
            db, business_id=business_id, service_id=service_id, data=data
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Servicio no encontrado") from exc


@router.delete(
    "/{service_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(_write_access)]
)
async def delete_service(
    business_id: uuid.UUID,
    service_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    try:
        await catalog_service.delete_service(db, business_id=business_id, service_id=service_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Servicio no encontrado") from exc
    await audit_service.record(
        db,
        business_id=business_id,
        user_id=user.id,
        action="service.delete",
        entity="service",
        entity_id=str(service_id),
    )
    await db.commit()
