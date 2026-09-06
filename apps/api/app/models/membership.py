import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.user import User


class Role(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    STAFF = "STAFF"


class Membership(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "business_id", name="uq_membership_user_business"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[Role] = mapped_column(Enum(Role, name="membership_role"), nullable=False)

    user: Mapped["User"] = relationship(back_populates="memberships")
    business: Mapped["Business"] = relationship(back_populates="memberships")
