from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.membership import Membership


class Business(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "businesses"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Argentina/Buenos_Aires")
    locale: Mapped[str] = mapped_column(String(8), default="es")
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="business", cascade="all, delete-orphan"
    )
