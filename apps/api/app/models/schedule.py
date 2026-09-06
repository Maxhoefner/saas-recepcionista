import uuid
from datetime import date, datetime, time

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPkMixin

_WEEKDAY_CHECK = CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_weekday_range")


class BusinessHours(UUIDPkMixin, TimestampMixin, Base):
    """Weekly opening hours for a business. Multiple rows per weekday are
    allowed (e.g. 09:00-13:00 and 16:00-20:00 for a split shift)."""

    __tablename__ = "business_hours"
    __table_args__ = (_WEEKDAY_CHECK,)

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday .. 6=Sunday
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)


class ProfessionalHours(UUIDPkMixin, TimestampMixin, Base):
    """Optional per-professional override of the business's weekly hours."""

    __tablename__ = "professional_hours"
    __table_args__ = (_WEEKDAY_CHECK,)

    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)


class BlockedTime(UUIDPkMixin, TimestampMixin, Base):
    """A one-off block of unavailable time — a business closure, a
    professional's day off, a maintenance window, etc."""

    __tablename__ = "blocked_times"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    professional_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Holiday(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "holidays"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
