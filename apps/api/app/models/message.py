import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPkMixin


class MessageRole(str, enum.Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"
    TOOL = "TOOL"


class Message(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="message_role"), nullable=False
    )
    content: Mapped[str | None] = mapped_column(String(8000), nullable=True)
    # Provider-shaped extras needed to replay history to the LLM: tool_calls
    # requested by an ASSISTANT message, or the tool_call_id a TOOL message
    # answers. Never shown to the end customer — that's `content`'s job.
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # WhatsApp's own message id, set only on inbound USER messages that came
    # from the webhook. The unique constraint is the real idempotency
    # guarantee against Meta redelivering the same event — an app-level
    # "have I seen this id" check alone can't close that race.
    whatsapp_message_id: Mapped[str | None] = mapped_column(
        String(128), unique=True, index=True, nullable=True
    )
