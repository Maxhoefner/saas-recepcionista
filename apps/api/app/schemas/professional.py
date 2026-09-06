import uuid

from pydantic import BaseModel, ConfigDict, Field


class ProfessionalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    active: bool = True
    service_ids: list[uuid.UUID] = Field(default_factory=list)


class ProfessionalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    active: bool | None = None
    service_ids: list[uuid.UUID] | None = None


class ProfessionalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    active: bool
    service_ids: list[uuid.UUID]
