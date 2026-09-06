import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.services.exceptions import NotFoundError, ServiceError


class DuplicatePhoneError(ServiceError):
    pass


async def create_customer(
    db: AsyncSession, *, business_id: uuid.UUID, data: CustomerCreate
) -> Customer:
    existing = await db.scalar(
        select(Customer).where(Customer.business_id == business_id, Customer.phone == data.phone)
    )
    if existing is not None:
        raise DuplicatePhoneError(data.phone)

    customer = Customer(business_id=business_id, **data.model_dump())
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


async def list_customers(db: AsyncSession, *, business_id: uuid.UUID) -> list[Customer]:
    result = await db.scalars(
        select(Customer).where(Customer.business_id == business_id).order_by(Customer.name)
    )
    return list(result)


async def get_customer(
    db: AsyncSession, *, business_id: uuid.UUID, customer_id: uuid.UUID
) -> Customer:
    customer = await db.scalar(
        select(Customer).where(Customer.id == customer_id, Customer.business_id == business_id)
    )
    if customer is None:
        raise NotFoundError(customer_id)
    return customer


async def update_customer(
    db: AsyncSession, *, business_id: uuid.UUID, customer_id: uuid.UUID, data: CustomerUpdate
) -> Customer:
    customer = await get_customer(db, business_id=business_id, customer_id=customer_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    await db.commit()
    await db.refresh(customer)
    return customer


async def get_or_create_by_phone(
    db: AsyncSession, *, business_id: uuid.UUID, phone: str, name: str
) -> Customer:
    """Used by the WhatsApp webhook (Fase 6) to resolve a customer from their
    phone number, creating a bare profile the first time they write in."""
    customer = await db.scalar(
        select(Customer).where(Customer.business_id == business_id, Customer.phone == phone)
    )
    if customer is not None:
        return customer

    customer = Customer(business_id=business_id, phone=phone, name=name)
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer
