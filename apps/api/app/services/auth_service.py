import uuid
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import RegisterRequest, TokenResponse
from app.services.business_service import create_business_for_user
from app.services.exceptions import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)

settings = get_settings()


async def register(db: AsyncSession, data: RegisterRequest) -> User:
    existing = await db.scalar(select(User).where(User.email == data.email))
    if existing is not None:
        raise EmailAlreadyExistsError(data.email)

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
    )
    db.add(user)
    await db.flush()

    await create_business_for_user(
        db,
        user_id=user.id,
        name=data.business_name,
        timezone="America/Argentina/Buenos_Aires",
        locale="es",
    )
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError()
    return user


async def issue_tokens(db: AsyncSession, user: User) -> TokenResponse:
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


async def _get_valid_refresh_token(db: AsyncSession, refresh_token: str) -> RefreshToken:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except jwt.InvalidTokenError as exc:
        raise InvalidRefreshTokenError() from exc

    token_row = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token))
    )
    if (
        token_row is None
        or token_row.revoked_at is not None
        or token_row.expires_at < datetime.now(UTC)
        or str(token_row.user_id) != payload["sub"]
    ):
        raise InvalidRefreshTokenError()
    return token_row


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> TokenResponse:
    token_row = await _get_valid_refresh_token(db, refresh_token)
    token_row.revoked_at = datetime.now(UTC)

    user = await db.scalar(select(User).where(User.id == token_row.user_id))
    if user is None or not user.is_active:
        raise InvalidRefreshTokenError()

    return await issue_tokens(db, user)


async def logout(db: AsyncSession, refresh_token: str) -> None:
    token_row = await _get_valid_refresh_token(db, refresh_token)
    token_row.revoked_at = datetime.now(UTC)
    await db.commit()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.scalar(select(User).where(User.id == user_id))
