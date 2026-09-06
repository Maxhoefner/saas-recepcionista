import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import decode_token
from app.models.membership import Role
from app.models.user import User
from app.services.auth_service import get_user_by_id
from app.services.business_service import list_businesses_for_user

_bearer_scheme = HTTPBearer(auto_error=False)

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No se pudo validar la sesión",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise credentials_exception
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user_id = uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
        raise credentials_exception from exc

    user = await get_user_by_id(db, user_id)
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_business_role(*allowed_roles: Role):
    """Dependency factory: verifies the current user belongs to `business_id`
    (a path parameter) with one of `allowed_roles`. Used by tenant-scoped
    endpoints from Fase 3 onward.
    """

    async def dependency(
        business_id: uuid.UUID,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> Role:
        memberships = await list_businesses_for_user(db, user.id)
        membership = next((m for m in memberships if m.business_id == business_id), None)
        if membership is None or (allowed_roles and membership.role not in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés acceso a este negocio",
            )
        return membership.role

    return dependency
