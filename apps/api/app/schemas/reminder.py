import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.reminder import ReminderStatus


class ReminderSettingsUpdate(BaseModel):
    enabled: bool | None = None
    hours_before: int | None = Field(default=None, ge=1, le=168)
    message_template: str | None = Field(default=None, min_length=1, max_length=1000)


class ReminderSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enabled: bool
    hours_before: int
    message_template: str


class ReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    appointment_id: uuid.UUID
    scheduled_for: datetime
    status: ReminderStatus
    sent_at: datetime | None
