from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.rate_limit import limiter
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.schemas.user import UserRead
from app.services import auth_service
from app.services.exceptions import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
async def register(
    request: Request, data: RegisterRequest, db: AsyncSession = Depends(get_db)
) -> RegisterResponse:
    try:
        user = await auth_service.register(db, data)
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Ese email ya está registrado"
        ) from exc

    tokens = await auth_service.issue_tokens(db, user)
    return RegisterResponse(user=UserRead.model_validate(user), **tokens.model_dump())


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request, data: LoginRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    try:
        user = await auth_service.authenticate(db, data.email, data.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas"
        ) from exc
    return await auth_service.issue_tokens(db, user)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(
    request: Request, data: RefreshRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    try:
        return await auth_service.refresh_tokens(db, data.refresh_token)
    except InvalidRefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido"
        ) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: LogoutRequest, db: AsyncSession = Depends(get_db)) -> None:
    try:
        await auth_service.logout(db, data.refresh_token)
    except InvalidRefreshTokenError:
        # Logging out with an already-invalid token is a no-op, not an error.
        pass


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> User:
    return user
