import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_business_role
from app.core.db import get_db
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from app.services import customer_service
from app.services.exceptions import NotFoundError

router = APIRouter(prefix="/businesses/{business_id}/customers", tags=["customers"])

# Any membership role can manage customers — it's day-to-day operational data,
# unlike catalog/schedule config which is restricted to OWNER/ADMIN.
_access = require_business_role()


@router.get("", response_model=list[CustomerRead], dependencies=[Depends(_access)])
async def list_customers(
    business_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[Customer]:
    return await customer_service.list_customers(db, business_id=business_id)


@router.post(
    "",
    response_model=CustomerRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_access)],
)
async def create_customer(
    business_id: uuid.UUID, data: CustomerCreate, db: AsyncSession = Depends(get_db)
) -> Customer:
    try:
        return await customer_service.create_customer(db, business_id=business_id, data=data)
    except customer_service.DuplicatePhoneError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ya existe un cliente con ese teléfono en este negocio"
        ) from exc


@router.get("/{customer_id}", response_model=CustomerRead, dependencies=[Depends(_access)])
async def get_customer(
    business_id: uuid.UUID, customer_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Customer:
    try:
        return await customer_service.get_customer(
            db, business_id=business_id, customer_id=customer_id
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente no encontrado") from exc


@router.patch("/{customer_id}", response_model=CustomerRead, dependencies=[Depends(_access)])
async def update_customer(
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
    data: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
) -> Customer:
    try:
        return await customer_service.update_customer(
            db, business_id=business_id, customer_id=customer_id, data=data
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente no encontrado") from exc
