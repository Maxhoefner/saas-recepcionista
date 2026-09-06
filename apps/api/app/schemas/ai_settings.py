from pydantic import BaseModel, ConfigDict, Field


class AISettingsUpdate(BaseModel):
    assistant_name: str | None = Field(default=None, min_length=1, max_length=100)
    tone: str | None = Field(default=None, min_length=1, max_length=500)
    language: str | None = Field(default=None, min_length=2, max_length=8)
    welcome_message: str | None = Field(default=None, max_length=1000)
    extra_instructions: str | None = Field(default=None, max_length=4000)


class AISettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assistant_name: str
    tone: str
    language: str
    welcome_message: str | None
    extra_instructions: str | None
