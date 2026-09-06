import uuid

from pydantic import BaseModel, ConfigDict, Field


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    price_cents: int = Field(ge=0)
    duration_minutes: int = Field(gt=0)
    active: bool = True


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    price_cents: int | None = Field(default=None, ge=0)
    duration_minutes: int | None = Field(default=None, gt=0)
    active: bool | None = None


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    price_cents: int
    duration_minutes: int
    active: bool
