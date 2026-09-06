import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_business_role
from app.core.db import get_db
from app.models.appointment import Appointment, AppointmentStatus
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentRead,
    AppointmentReschedule,
    AvailabilitySlots,
)
from app.services import appointment_service, availability_service
from app.services.appointment_service import DoubleBookingError, InvalidStatusTransitionError
from app.services.availability_service import SlotUnavailableError
from app.services.exceptions import NotFoundError

router = APIRouter(prefix="/businesses/{business_id}", tags=["appointments"])

# Booking is day-to-day operational work — open to any membership role,
# same as customers (unlike catalog/schedule config, which is OWNER/ADMIN).
_access = require_business_role()


@router.get(
    "/appointments", response_model=list[AppointmentRead], dependencies=[Depends(_access)]
)
async def list_appointments(
    business_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    professional_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    status_: AppointmentStatus | None = Query(default=None, alias="status"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[Appointment]:
    return await appointment_service.list_appointments(
        db,
        business_id=business_id,
        professional_id=professional_id,
        customer_id=customer_id,
        status=status_,
        date_from=date_from,
        date_to=date_to,
    )


@router.post(
    "/appointments",
    response_model=AppointmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_access)],
)
async def create_appointment(
    business_id: uuid.UUID, data: AppointmentCreate, db: AsyncSession = Depends(get_db)
) -> Appointment:
    try:
        return await appointment_service.create_appointment(db, business_id=business_id, data=data)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except SlotUnavailableError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except DoubleBookingError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.get(
    "/appointments/{appointment_id}",
    response_model=AppointmentRead,
    dependencies=[Depends(_access)],
)
async def get_appointment(
    business_id: uuid.UUID, appointment_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Appointment:
    try:
        return await appointment_service.get_appointment(
            db, business_id=business_id, appointment_id=appointment_id
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turno no encontrado") from exc


@router.post(
    "/appointments/{appointment_id}/cancel",
    response_model=AppointmentRead,
    dependencies=[Depends(_access)],
)
async def cancel_appointment(
    business_id: uuid.UUID, appointment_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Appointment:
    try:
        return await appointment_service.cancel_appointment(
            db, business_id=business_id, appointment_id=appointment_id
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turno no encontrado") from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post(
    "/appointments/{appointment_id}/reschedule",
    response_model=AppointmentRead,
    dependencies=[Depends(_access)],
)
async def reschedule_appointment(
    business_id: uuid.UUID,
    appointment_id: uuid.UUID,
    data: AppointmentReschedule,
    db: AsyncSession = Depends(get_db),
) -> Appointment:
    try:
        return await appointment_service.reschedule_appointment(
            db,
            business_id=business_id,
            appointment_id=appointment_id,
            start_datetime=data.start_datetime,
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turno no encontrado") from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except SlotUnavailableError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except DoubleBookingError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post(
    "/appointments/{appointment_id}/confirm",
    response_model=AppointmentRead,
    dependencies=[Depends(_access)],
)
async def confirm_appointment(
    business_id: uuid.UUID, appointment_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Appointment:
    try:
        return await appointment_service.confirm_appointment(
            db, business_id=business_id, appointment_id=appointment_id
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turno no encontrado") from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post(
    "/appointments/{appointment_id}/complete",
    response_model=AppointmentRead,
    dependencies=[Depends(_access)],
)
async def complete_appointment(
    business_id: uuid.UUID, appointment_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Appointment:
    try:
        return await appointment_service.complete_appointment(
            db, business_id=business_id, appointment_id=appointment_id
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turno no encontrado") from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post(
    "/appointments/{appointment_id}/no-show",
    response_model=AppointmentRead,
    dependencies=[Depends(_access)],
)
async def mark_no_show(
    business_id: uuid.UUID, appointment_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> Appointment:
    try:
        return await appointment_service.mark_no_show(
            db, business_id=business_id, appointment_id=appointment_id
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Turno no encontrado") from exc
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.get(
    "/availability", response_model=list[AvailabilitySlots], dependencies=[Depends(_access)]
)
async def get_availability(
    business_id: uuid.UUID,
    service_id: uuid.UUID,
    day: date,
    professional_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    try:
        return await availability_service.check_availability(
            db,
            business_id=business_id,
            service_id=service_id,
            day=day,
            professional_id=professional_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
