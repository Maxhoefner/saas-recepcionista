import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin


class AISettings(TimestampMixin, Base):
    """One row per business — business_id doubles as the primary key since
    this is a strict 1:1 relationship, configured lazily (created on first
    read/write, not at business-creation time)."""

    __tablename__ = "ai_settings"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), primary_key=True
    )
    assistant_name: Mapped[str] = mapped_column(String(100), default="Sofi")
    tone: Mapped[str] = mapped_column(
        String(500), default="Amable, profesional y cercana."
    )
    language: Mapped[str] = mapped_column(String(8), default="es")
    welcome_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    extra_instructions: Mapped[str | None] = mapped_column(String(4000), nullable=True)
