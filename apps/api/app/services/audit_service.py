import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def record(
    db: AsyncSession,
    *,
    business_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: str,
    entity: str,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Adds an audit row to the current transaction — does NOT commit.
    Call this right before (or right after building) the response of the
    mutation it's recording, so it lands in the same commit as the change
    itself rather than risking one succeeding without the other."""
    db.add(
        AuditLog(
            business_id=business_id,
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            details=details or {},
        )
    )


async def list_for_business(db: AsyncSession, *, business_id: uuid.UUID) -> list[AuditLog]:
    result = await db.scalars(
        select(AuditLog)
        .where(AuditLog.business_id == business_id)
        .order_by(AuditLog.created_at.desc())
        .limit(500)
    )
    return list(result)
