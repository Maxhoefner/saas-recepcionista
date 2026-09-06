import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.conversation import ConversationStatus
from app.models.message import MessageRole


class ConversationCreate(BaseModel):
    customer_id: uuid.UUID


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    status: ConversationStatus
    last_message_at: datetime | None


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: MessageRole
    content: str | None
    created_at: datetime


class IncomingMessage(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class MessageExchange(BaseModel):
    customer_message: MessageRead
    assistant_reply: MessageRead | None
