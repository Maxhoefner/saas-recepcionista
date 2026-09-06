import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.membership import Role


class BusinessCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    timezone: str = "America/Argentina/Buenos_Aires"
    locale: str = "es"


class BusinessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    timezone: str
    locale: str


class BusinessWithRole(BusinessRead):
    role: Role
