import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, AppointmentStatus
from app.models.customer import Customer
from app.models.professional import Professional, ProfessionalService
from app.models.service import Service
from app.schemas.appointment import AppointmentCreate
from app.services import availability_service, reminder_service
from app.services.exceptions import NotFoundError, ServiceError


class DoubleBookingError(ServiceError):
    pass


class InvalidStatusTransitionError(ServiceError):
    pass


_CANCELLABLE_FROM = {AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED}
_CONFIRMABLE_FROM = {AppointmentStatus.PENDING}
_COMPLETABLE_FROM = {AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED}
_NO_SHOWABLE_FROM = {AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED}
_RESCHEDULABLE_FROM = {AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED}


async def _load_service_and_professional(
    db: AsyncSession, *, business_id: uuid.UUID, service_id: uuid.UUID, professional_id: uuid.UUID
) -> tuple[Service, Professional]:
    service = await db.scalar(
        select(Service).where(
            Service.id == service_id, Service.business_id == business_id, Service.active.is_(True)
        )
    )
    if service is None:
        raise NotFoundError("Servicio no encontrado o inactivo")

    professional = await db.scalar(
        select(Professional).where(
            Professional.id == professional_id,
            Professional.business_id == business_id,
            Professional.active.is_(True),
        )
    )
    if professional is None:
        raise NotFoundError("Profesional no encontrado o inactivo")

    performs = await db.scalar(
        select(ProfessionalService.id).where(
            ProfessionalService.professional_id == professional_id,
            ProfessionalService.service_id == service_id,
        )
    )
    if performs is None:
        raise NotFoundError("Ese profesional no realiza ese servicio")

    return service, professional


async def create_appointment(
    db: AsyncSession, *, business_id: uuid.UUID, data: AppointmentCreate
) -> Appointment:
    service, professional = await _load_service_and_professional(
        db,
        business_id=business_id,
        service_id=data.service_id,
        professional_id=data.professional_id,
    )
    customer = await db.scalar(
        select(Customer).where(Customer.id == data.customer_id, Customer.business_id == business_id)
    )
    if customer is None:
        raise NotFoundError("Cliente no encontrado")

    end_datetime = data.start_datetime + timedelta(minutes=service.duration_minutes)
    await availability_service.validate_slot_available(
        db,
        business_id=business_id,
        professional_id=professional.id,
        start_datetime=data.start_datetime,
        end_datetime=end_datetime,
    )

    appointment = Appointment(
        business_id=business_id,
        customer_id=customer.id,
        professional_id=professional.id,
        service_id=service.id,
        start_datetime=data.start_datetime,
        end_datetime=end_datetime,
        status=AppointmentStatus.PENDING,
        notes=data.notes,
    )
    db.add(appointment)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise DoubleBookingError("Ese profesional ya tiene un turno en ese horario") from exc
    await db.refresh(appointment)
    await reminder_service.sync_reminder_for_appointment(db, appointment=appointment)
    return appointment


async def list_appointments(
    db: AsyncSession,
    *,
    business_id: uuid.UUID,
    professional_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    status: AppointmentStatus | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[Appointment]:
    stmt = select(Appointment).where(Appointment.business_id == business_id)
    if professional_id is not None:
        stmt = stmt.where(Appointment.professional_id == professional_id)
    if customer_id is not None:
        stmt = stmt.where(Appointment.customer_id == customer_id)
    if status is not None:
        stmt = stmt.where(Appointment.status == status)
    if date_from is not None:
        stmt = stmt.where(Appointment.start_datetime >= date_from)
    if date_to is not None:
        stmt = stmt.where(Appointment.start_datetime < date_to)
    stmt = stmt.order_by(Appointment.start_datetime)
    return list(await db.scalars(stmt))


async def get_appointment(
    db: AsyncSession, *, business_id: uuid.UUID, appointment_id: uuid.UUID
) -> Appointment:
    appointment = await db.scalar(
        select(Appointment).where(
            Appointment.id == appointment_id, Appointment.business_id == business_id
        )
    )
    if appointment is None:
        raise NotFoundError(appointment_id)
    return appointment


async def cancel_appointment(
    db: AsyncSession, *, business_id: uuid.UUID, appointment_id: uuid.UUID
) -> Appointment:
    appointment = await get_appointment(db, business_id=business_id, appointment_id=appointment_id)
    if appointment.status not in _CANCELLABLE_FROM:
        raise InvalidStatusTransitionError(
            f"No se puede cancelar un turno en estado {appointment.status.value}"
        )
    appointment.status = AppointmentStatus.CANCELLED
    await db.commit()
    await db.refresh(appointment)
    await reminder_service.sync_reminder_for_appointment(db, appointment=appointment)
    return appointment


async def reschedule_appointment(
    db: AsyncSession, *, business_id: uuid.UUID, appointment_id: uuid.UUID, start_datetime: datetime
) -> Appointment:
    appointment = await get_appointment(db, business_id=business_id, appointment_id=appointment_id)
    if appointment.status not in _RESCHEDULABLE_FROM:
        raise InvalidStatusTransitionError(
            f"No se puede reprogramar un turno en estado {appointment.status.value}"
        )
    service = await db.scalar(select(Service).where(Service.id == appointment.service_id))
    assert service is not None  # a service is never hard-deleted once referenced by an appointment
    new_end = start_datetime + timedelta(minutes=service.duration_minutes)

    await availability_service.validate_slot_available(
        db,
        business_id=business_id,
        professional_id=appointment.professional_id,
        start_datetime=start_datetime,
        end_datetime=new_end,
    )

    appointment.start_datetime = start_datetime
    appointment.end_datetime = new_end
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise DoubleBookingError("Ese profesional ya tiene un turno en ese horario") from exc
    await db.refresh(appointment)
    await reminder_service.sync_reminder_for_appointment(db, appointment=appointment)
    return appointment


async def _transition(
    db: AsyncSession,
    *,
    business_id: uuid.UUID,
    appointment_id: uuid.UUID,
    allowed_from: set[AppointmentStatus],
    new_status: AppointmentStatus,
) -> Appointment:
    appointment = await get_appointment(db, business_id=business_id, appointment_id=appointment_id)
    if appointment.status not in allowed_from:
        raise InvalidStatusTransitionError(
            f"No se puede pasar de {appointment.status.value} a {new_status.value}"
        )
    appointment.status = new_status
    await db.commit()
    await db.refresh(appointment)
    await reminder_service.sync_reminder_for_appointment(db, appointment=appointment)
    return appointment


async def confirm_appointment(
    db: AsyncSession, *, business_id: uuid.UUID, appointment_id: uuid.UUID
) -> Appointment:
    return await _transition(
        db,
        business_id=business_id,
        appointment_id=appointment_id,
        allowed_from=_CONFIRMABLE_FROM,
        new_status=AppointmentStatus.CONFIRMED,
    )


async def complete_appointment(
    db: AsyncSession, *, business_id: uuid.UUID, appointment_id: uuid.UUID
) -> Appointment:
    return await _transition(
        db,
        business_id=business_id,
        appointment_id=appointment_id,
        allowed_from=_COMPLETABLE_FROM,
        new_status=AppointmentStatus.COMPLETED,
    )


async def mark_no_show(
    db: AsyncSession, *, business_id: uuid.UUID, appointment_id: uuid.UUID
) -> Appointment:
    return await _transition(
        db,
        business_id=business_id,
        appointment_id=appointment_id,
        allowed_from=_NO_SHOWABLE_FROM,
        new_status=AppointmentStatus.NO_SHOW,
    )
