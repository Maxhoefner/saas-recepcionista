import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_business_role
from app.core.db import get_db
from app.models.audit_log import AuditLog
from app.models.membership import Role
from app.schemas.audit_log import AuditLogRead
from app.services import audit_service

router = APIRouter(prefix="/businesses/{business_id}/audit-logs", tags=["audit-logs"])

_access = require_business_role(Role.OWNER, Role.ADMIN)


@router.get("", response_model=list[AuditLogRead], dependencies=[Depends(_access)])
async def list_audit_logs(
    business_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[AuditLog]:
    return await audit_service.list_for_business(db, business_id=business_id)
