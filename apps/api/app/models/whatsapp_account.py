import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPkMixin


class WhatsAppAccount(UUIDPkMixin, TimestampMixin, Base):
    """A business's connected WhatsApp Business number — one per business
    for the MVP (multiple locations/numbers is a later refinement)."""

    __tablename__ = "whatsapp_accounts"

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    phone_number_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    waba_id: Mapped[str] = mapped_column(String(64), nullable=False)
    display_phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    # Encrypted at rest with app.core.security.encrypt_secret — never stored
    # or returned in plaintext.
    access_token_encrypted: Mapped[str] = mapped_column(String(2000), nullable=False)
