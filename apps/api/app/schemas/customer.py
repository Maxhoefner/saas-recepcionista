import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    phone: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    phone: str
    name: str
    email: str | None
    notes: str | None
    last_interaction_at: datetime | None
