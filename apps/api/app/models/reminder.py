import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPkMixin


class ReminderStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Reminder(UUIDPkMixin, TimestampMixin, Base):
    """One reminder per appointment (MVP). Kept in sync with its appointment
    by app.services.reminder_service.sync_reminder_for_appointment, called
    from appointment_service on create/reschedule/cancel — it never drifts
    from the appointment it belongs to."""

    __tablename__ = "reminders"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(ReminderStatus, name="reminder_status"),
        nullable=False,
        default=ReminderStatus.PENDING,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
