import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPkMixin


class AppointmentStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


class Appointment(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "appointments"
    __table_args__ = (
        # A professional can't be double-booked: any two non-cancelled
        # appointments for the same professional must not overlap in time.
        # Enforced at the DB level (not just in application code) since
        # that's the only place a race between two concurrent bookings can
        # actually be closed.
        ExcludeConstraint(
            ("professional_id", "="),
            (text("tstzrange(start_datetime, end_datetime)"), "&&"),
            where=text("status <> 'CANCELLED'"),
            using="gist",
            name="ck_appointments_no_double_booking",
        ),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, name="appointment_status"),
        nullable=False,
        default=AppointmentStatus.PENDING,
    )
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
