import uuid
from datetime import date as date_type
from datetime import datetime

from pydantic import BaseModel, Field

from app.ai.tools.base import NoArgs, ToolContext, ToolDefinition, find_by_name
from app.models.appointment import Appointment, AppointmentStatus
from app.schemas.appointment import AppointmentCreate
from app.services import appointment_service, availability_service, catalog_service
from app.services.appointment_service import DoubleBookingError, InvalidStatusTransitionError
from app.services.availability_service import SlotUnavailableError
from app.services.exceptions import NotFoundError


async def _active_services(ctx: ToolContext) -> list:
    services = await catalog_service.list_services(ctx.db, business_id=ctx.business_id)
    return [s for s in services if s.active]


async def _active_professionals(ctx: ToolContext) -> list:
    professionals = await catalog_service.list_professionals(ctx.db, business_id=ctx.business_id)
    return [p for p in professionals if p.active]


class CheckAvailabilityArgs(BaseModel):
    service_name: str
    day: date_type = Field(description="Fecha a consultar, formato YYYY-MM-DD")
    professional_name: str | None = Field(
        default=None, description="Si el cliente pidió un profesional específico"
    )


async def check_availability(ctx: ToolContext, args: CheckAvailabilityArgs) -> dict:
    service, error = find_by_name(await _active_services(ctx), args.service_name)
    if error:
        return {"error": error}
    assert service is not None

    professionals = await _active_professionals(ctx)
    professional_id = None
    if args.professional_name:
        professional, error = find_by_name(professionals, args.professional_name)
        if error:
            return {"error": error}
        assert professional is not None
        professional_id = professional.id

    try:
        availability = await availability_service.check_availability(
            ctx.db,
            business_id=ctx.business_id,
            service_id=service.id,
            day=args.day,
            professional_id=professional_id,
        )
    except NotFoundError as exc:
        return {"error": str(exc)}

    names = {p.id: p.name for p in professionals}
    return {
        "availability": [
            {
                "professional": names.get(entry["professional_id"], "?"),
                "slots": [slot.isoformat() for slot in entry["slots"]],
            }
            for entry in availability
        ]
    }


class CreateAppointmentArgs(BaseModel):
    service_name: str
    start_datetime: datetime = Field(description="Fecha y hora de inicio, con timezone")
    professional_name: str | None = Field(
        default=None, description="Si no se da, se asigna cualquier profesional disponible"
    )


async def create_appointment(ctx: ToolContext, args: CreateAppointmentArgs) -> dict:
    service, error = find_by_name(await _active_services(ctx), args.service_name)
    if error:
        return {"error": error}
    assert service is not None

    professionals = await _active_professionals(ctx)
    if args.professional_name:
        professional, error = find_by_name(professionals, args.professional_name)
        if error:
            return {"error": error}
        assert professional is not None
    else:
        availability = await availability_service.check_availability(
            ctx.db,
            business_id=ctx.business_id,
            service_id=service.id,
            day=args.start_datetime.date(),
        )
        match = next(
            (entry for entry in availability if args.start_datetime in entry["slots"]), None
        )
        if match is None:
            return {
                "error": "No hay ningún profesional disponible en ese horario para ese servicio."
            }
        professional = next(p for p in professionals if p.id == match["professional_id"])

    try:
        appointment = await appointment_service.create_appointment(
            ctx.db,
            business_id=ctx.business_id,
            data=AppointmentCreate(
                customer_id=ctx.conversation.customer_id,
                professional_id=professional.id,
                service_id=service.id,
                start_datetime=args.start_datetime,
            ),
        )
    except (NotFoundError, SlotUnavailableError, DoubleBookingError) as exc:
        return {"error": str(exc)}

    return {
        "appointment_id": str(appointment.id),
        "service": service.name,
        "professional": professional.name,
        "start_datetime": appointment.start_datetime.isoformat(),
        "end_datetime": appointment.end_datetime.isoformat(),
        "status": appointment.status.value,
    }


async def get_customer_appointments(ctx: ToolContext, _: NoArgs) -> dict:
    appointments = await appointment_service.list_appointments(
        ctx.db, business_id=ctx.business_id, customer_id=ctx.conversation.customer_id
    )
    upcoming = [
        a
        for a in appointments
        if a.status in (AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED)
    ]
    services = await catalog_service.list_services(ctx.db, business_id=ctx.business_id)
    service_names = {s.id: s.name for s in services}
    professional_names = {p.id: p.name for p in await _active_professionals(ctx)}
    return {
        "appointments": [
            {
                "appointment_id": str(a.id),
                "service": service_names.get(a.service_id, "?"),
                "professional": professional_names.get(a.professional_id, "?"),
                "start_datetime": a.start_datetime.isoformat(),
                "status": a.status.value,
            }
            for a in upcoming
        ]
    }


class AppointmentIdArgs(BaseModel):
    appointment_id: uuid.UUID = Field(
        description="Id del turno, obtenido antes con get_customer_appointments"
    )


async def _load_owned_appointment(
    ctx: ToolContext, appointment_id: uuid.UUID
) -> tuple[Appointment | None, dict | None]:
    try:
        appointment = await appointment_service.get_appointment(
            ctx.db, business_id=ctx.business_id, appointment_id=appointment_id
        )
    except NotFoundError:
        return None, {"error": "Turno no encontrado."}
    if appointment.customer_id != ctx.conversation.customer_id:
        # Never let a conversation act on another customer's appointment,
        # even within the same business.
        return None, {"error": "Ese turno no pertenece a este cliente."}
    return appointment, None


async def cancel_appointment(ctx: ToolContext, args: AppointmentIdArgs) -> dict:
    appointment, error = await _load_owned_appointment(ctx, args.appointment_id)
    if error:
        return error
    assert appointment is not None
    try:
        appointment = await appointment_service.cancel_appointment(
            ctx.db, business_id=ctx.business_id, appointment_id=appointment.id
        )
    except InvalidStatusTransitionError as exc:
        return {"error": str(exc)}
    return {"appointment_id": str(appointment.id), "status": appointment.status.value}


class RescheduleAppointmentArgs(BaseModel):
    appointment_id: uuid.UUID
    new_start_datetime: datetime


async def reschedule_appointment(ctx: ToolContext, args: RescheduleAppointmentArgs) -> dict:
    appointment, error = await _load_owned_appointment(ctx, args.appointment_id)
    if error:
        return error
    assert appointment is not None
    try:
        appointment = await appointment_service.reschedule_appointment(
            ctx.db,
            business_id=ctx.business_id,
            appointment_id=appointment.id,
            start_datetime=args.new_start_datetime,
        )
    except (InvalidStatusTransitionError, SlotUnavailableError, DoubleBookingError) as exc:
        return {"error": str(exc)}
    return {
        "appointment_id": str(appointment.id),
        "start_datetime": appointment.start_datetime.isoformat(),
        "end_datetime": appointment.end_datetime.isoformat(),
        "status": appointment.status.value,
    }


TOOLS = [
    ToolDefinition(
        name="check_availability",
        description="Consulta horarios disponibles reales para un servicio (y opcionalmente un "
        "profesional) en una fecha. Llamar siempre antes de ofrecer un horario — nunca inventar "
        "disponibilidad.",
        args_model=CheckAvailabilityArgs,
        handler=check_availability,
    ),
    ToolDefinition(
        name="create_appointment",
        description="Reserva un turno para el cliente de esta conversación. Confirmar con el "
        "cliente antes de llamar esta tool (día, hora y servicio).",
        args_model=CreateAppointmentArgs,
        handler=create_appointment,
    ),
    ToolDefinition(
        name="get_customer_appointments",
        description="Lista los turnos futuros (pendientes o confirmados) del cliente de esta "
        "conversación. Usar antes de cancelar/reprogramar para saber a cuál se refiere.",
        args_model=NoArgs,
        handler=get_customer_appointments,
    ),
    ToolDefinition(
        name="cancel_appointment",
        description="Cancela un turno del cliente de esta conversación, por su appointment_id.",
        args_model=AppointmentIdArgs,
        handler=cancel_appointment,
    ),
    ToolDefinition(
        name="reschedule_appointment",
        description="Reprograma un turno existente del cliente de esta conversación a un nuevo "
        "horario. Confirmar el nuevo horario con el cliente antes de llamar esta tool.",
        args_model=RescheduleAppointmentArgs,
        handler=reschedule_appointment,
    ),
]
