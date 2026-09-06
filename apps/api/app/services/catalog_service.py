import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.professional import Professional, ProfessionalService
from app.models.service import Service
from app.schemas.professional import ProfessionalCreate, ProfessionalUpdate
from app.schemas.service import ServiceCreate, ServiceUpdate
from app.services.exceptions import NotFoundError


async def create_service(
    db: AsyncSession, *, business_id: uuid.UUID, data: ServiceCreate
) -> Service:
    service = Service(business_id=business_id, **data.model_dump())
    db.add(service)
    await db.commit()
    await db.refresh(service)
    return service


async def list_services(db: AsyncSession, *, business_id: uuid.UUID) -> list[Service]:
    result = await db.scalars(select(Service).where(Service.business_id == business_id))
    return list(result)


async def get_service(
    db: AsyncSession, *, business_id: uuid.UUID, service_id: uuid.UUID
) -> Service:
    service = await db.scalar(
        select(Service).where(Service.id == service_id, Service.business_id == business_id)
    )
    if service is None:
        raise NotFoundError(service_id)
    return service


async def update_service(
    db: AsyncSession, *, business_id: uuid.UUID, service_id: uuid.UUID, data: ServiceUpdate
) -> Service:
    service = await get_service(db, business_id=business_id, service_id=service_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(service, field, value)
    await db.commit()
    await db.refresh(service)
    return service


async def delete_service(
    db: AsyncSession, *, business_id: uuid.UUID, service_id: uuid.UUID
) -> None:
    service = await get_service(db, business_id=business_id, service_id=service_id)
    await db.delete(service)
    await db.commit()


async def _service_ids_for_professional(
    db: AsyncSession, professional_id: uuid.UUID
) -> list[uuid.UUID]:
    result = await db.scalars(
        select(ProfessionalService.service_id).where(
            ProfessionalService.professional_id == professional_id
        )
    )
    return list(result)


async def _set_professional_services(
    db: AsyncSession,
    *,
    business_id: uuid.UUID,
    professional_id: uuid.UUID,
    service_ids: list[uuid.UUID],
) -> None:
    if service_ids:
        valid_ids = set(
            await db.scalars(
                select(Service.id).where(
                    Service.business_id == business_id, Service.id.in_(service_ids)
                )
            )
        )
        unknown = set(service_ids) - valid_ids
        if unknown:
            raise NotFoundError(f"Servicios inexistentes en este negocio: {unknown}")

    await db.execute(
        delete(ProfessionalService).where(ProfessionalService.professional_id == professional_id)
    )
    for service_id in service_ids:
        db.add(ProfessionalService(professional_id=professional_id, service_id=service_id))


async def create_professional(
    db: AsyncSession, *, business_id: uuid.UUID, data: ProfessionalCreate
) -> Professional:
    professional = Professional(business_id=business_id, name=data.name, active=data.active)
    db.add(professional)
    await db.flush()
    await _set_professional_services(
        db,
        business_id=business_id,
        professional_id=professional.id,
        service_ids=data.service_ids,
    )
    await db.commit()
    await db.refresh(professional)
    return professional


async def list_professionals(db: AsyncSession, *, business_id: uuid.UUID) -> list[Professional]:
    result = await db.scalars(select(Professional).where(Professional.business_id == business_id))
    return list(result)


async def get_professional(
    db: AsyncSession, *, business_id: uuid.UUID, professional_id: uuid.UUID
) -> Professional:
    professional = await db.scalar(
        select(Professional).where(
            Professional.id == professional_id, Professional.business_id == business_id
        )
    )
    if professional is None:
        raise NotFoundError(professional_id)
    return professional


async def update_professional(
    db: AsyncSession,
    *,
    business_id: uuid.UUID,
    professional_id: uuid.UUID,
    data: ProfessionalUpdate,
) -> Professional:
    professional = await get_professional(
        db, business_id=business_id, professional_id=professional_id
    )
    payload = data.model_dump(exclude_unset=True, exclude={"service_ids"})
    for field, value in payload.items():
        setattr(professional, field, value)
    if data.service_ids is not None:
        await _set_professional_services(
            db,
            business_id=business_id,
            professional_id=professional.id,
            service_ids=data.service_ids,
        )
    await db.commit()
    await db.refresh(professional)
    return professional


async def delete_professional(
    db: AsyncSession, *, business_id: uuid.UUID, professional_id: uuid.UUID
) -> None:
    professional = await get_professional(
        db, business_id=business_id, professional_id=professional_id
    )
    await db.delete(professional)
    await db.commit()


async def professional_to_read_dict(db: AsyncSession, professional: Professional) -> dict:
    return {
        "id": professional.id,
        "name": professional.name,
        "active": professional.active,
        "service_ids": await _service_ids_for_professional(db, professional.id),
    }
