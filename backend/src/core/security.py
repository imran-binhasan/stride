"""Security, password hashing, and JWT token management."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import argon2
import jwt
from src.config import settings
from src.core.exceptions import AuthenticationError

ph = argon2.PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password with Argon2."""
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2 hash."""
    try:
        return ph.verify(hashed_password, plain_password)
    except Exception:
        return False


def create_access_token(
    subject: str,
    claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Generate a signed JWT access token."""
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if claims:
        payload.update(claims)

    encoded_jwt = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        raise AuthenticationError("Access token has expired") from e
    except jwt.InvalidTokenError as e:
        raise AuthenticationError("Invalid access token") from e


def generate_refresh_token() -> str:
    """Generate a high-entropy URL-safe random string for refresh tokens."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Deterministically hash a refresh token for at-rest storage/lookup (SHA-256)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
