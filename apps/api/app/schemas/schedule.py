import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WeeklyHoursEntry(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0=lunes ... 6=domingo")
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _check_range(self) -> "WeeklyHoursEntry":
        if self.end_time <= self.start_time:
            raise ValueError("end_time debe ser posterior a start_time")
        return self


class WeeklyHoursRead(WeeklyHoursEntry):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class WeeklyHoursReplace(BaseModel):
    hours: list[WeeklyHoursEntry]


class BlockedTimeCreate(BaseModel):
    professional_id: uuid.UUID | None = None
    start_datetime: datetime
    end_datetime: datetime
    reason: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _check_range(self) -> "BlockedTimeCreate":
        if self.end_datetime <= self.start_datetime:
            raise ValueError("end_datetime debe ser posterior a start_datetime")
        return self


class BlockedTimeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    professional_id: uuid.UUID | None
    start_datetime: datetime
    end_datetime: datetime
    reason: str | None


class HolidayCreate(BaseModel):
    holiday_date: date
    description: str | None = Field(default=None, max_length=255)


class HolidayRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    holiday_date: date
    description: str | None
