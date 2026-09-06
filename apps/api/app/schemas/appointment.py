import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.appointment import AppointmentStatus


class AppointmentCreate(BaseModel):
    customer_id: uuid.UUID
    professional_id: uuid.UUID
    service_id: uuid.UUID
    start_datetime: datetime
    notes: str | None = Field(default=None, max_length=2000)


class AppointmentReschedule(BaseModel):
    start_datetime: datetime


class AppointmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    professional_id: uuid.UUID
    service_id: uuid.UUID
    start_datetime: datetime
    end_datetime: datetime
    status: AppointmentStatus
    notes: str | None


class AvailabilityQuery(BaseModel):
    service_id: uuid.UUID
    day: date
    professional_id: uuid.UUID | None = None


class AvailabilitySlots(BaseModel):
    professional_id: uuid.UUID
    slots: list[datetime]
