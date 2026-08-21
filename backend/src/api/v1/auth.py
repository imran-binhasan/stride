"""Authentication API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_db_session
from src.core.ratelimit import rate_limit
from src.core.rbac import get_current_user
from src.models.auth import User
from src.schemas.auth import (
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserProfileResponse,
    UserRegisterRequest,
)
from src.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, scope="register"))],
)
async def register_user(
    payload: UserRegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Register a new user account and initialize organization."""
    service = AuthService(db)
    user_profile, token_data = await service.register(payload)
    return {
        "success": True,
        "data": {
            "user": user_profile,
            "tokens": token_data,
        },
    }


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, scope="login"))],
)
async def login_user(
    payload: UserLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    """Authenticate with email and password to receive JWT tokens."""
    service = AuthService(db)
    return await service.login(payload)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60, scope="refresh"))],
)
async def refresh_tokens(
    payload: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenResponse:
    """Rotate and issue a new access and refresh token pair."""
    service = AuthService(db)
    return await service.refresh_tokens(payload.refresh_token)


@router.post("/logout")
async def logout(
    payload: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """Revoke a refresh token (logout)."""
    service = AuthService(db)
    return await service.logout(payload.refresh_token)


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserProfileResponse:
    """Retrieve profile of the currently authenticated user."""
    return UserProfileResponse.model_validate(current_user)
