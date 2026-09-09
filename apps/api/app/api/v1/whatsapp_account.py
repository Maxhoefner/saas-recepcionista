import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_business_role
from app.core.db import get_db
from app.models.membership import Role
from app.models.user import User
from app.models.whatsapp_account import WhatsAppAccount
from app.schemas.whatsapp_account import WhatsAppAccountConnect, WhatsAppAccountRead
from app.services import audit_service, whatsapp_service
from app.services.exceptions import NotFoundError
from app.services.whatsapp_service import PhoneNumberAlreadyConnectedError

router = APIRouter(prefix="/businesses/{business_id}/whatsapp-account", tags=["whatsapp"])

_read_access = require_business_role()
_write_access = require_business_role(Role.OWNER, Role.ADMIN)


@router.get("", response_model=WhatsAppAccountRead, dependencies=[Depends(_read_access)])
async def get_whatsapp_account(
    business_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> WhatsAppAccount:
    try:
        return await whatsapp_service.get_account_for_business(db, business_id=business_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.put("", response_model=WhatsAppAccountRead, dependencies=[Depends(_write_access)])
async def connect_whatsapp_account(
    business_id: uuid.UUID,
    data: WhatsAppAccountConnect,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WhatsAppAccount:
    try:
        account = await whatsapp_service.connect_account(db, business_id=business_id, data=data)
    except PhoneNumberAlreadyConnectedError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ese número ya está conectado a otro negocio"
        ) from exc

    # Connecting/rotating the credential that lets us send messages as this
    # business is exactly the kind of action that belongs in the audit trail
    # — never log the access token itself, only that it changed.
    await audit_service.record(
        db,
        business_id=business_id,
        user_id=user.id,
        action="whatsapp_account.connect",
        entity="whatsapp_account",
        entity_id=str(account.id),
        details={"phone_number_id": account.phone_number_id},
    )
    await db.commit()
    return account
