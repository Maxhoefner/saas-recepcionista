import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin

DEFAULT_REMINDER_TEMPLATE = (
    "Hola {customer_name} 👋 Te recordamos tu turno:\n"
    "📅 {date}\n🕒 {time}\n💇 {service}\n¿Nos vemos?"
)


class ReminderSettings(TimestampMixin, Base):
    """One row per business — same 1:1 pattern as AISettings (business_id is
    the primary key, created lazily on first read/write)."""

    __tablename__ = "reminder_settings"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    hours_before: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    message_template: Mapped[str] = mapped_column(String(1000), default=DEFAULT_REMINDER_TEMPLATE)
