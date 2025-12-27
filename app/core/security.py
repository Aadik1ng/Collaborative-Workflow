"""Security utilities for JWT authentication and password hashing."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt

from app.config import settings

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError

    ph = PasswordHasher()
except ImportError:
    ph = None

# Token types
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    if ph is None:
        raise RuntimeError("argon2-cffi is not installed")
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    if ph is None:
        raise RuntimeError("argon2-cffi is not installed")
    try:
        return ph.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False


def create_access_token(
    user_id: UUID,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """Create a JWT access token."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": ACCESS_TOKEN_TYPE,
    }
    if additional_claims:
        payload.update(additional_claims)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: UUID) -> str:
    """Create a JWT refresh token."""
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": REFRESH_TOKEN_TYPE,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {e}")


def verify_access_token(token: str) -> dict[str, Any]:
    """Verify an access token and return its payload."""
    payload = decode_token(token)
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise ValueError("Invalid token type")
    return payload


def verify_refresh_token(token: str) -> dict[str, Any]:
    """Verify a refresh token and return its payload."""
    payload = decode_token(token)
    if payload.get("type") != REFRESH_TOKEN_TYPE:
        raise ValueError("Invalid token type")
    return payload


def create_invitation_token(
    project_id: UUID,
    inviter_id: UUID,
    email: str,
    role: str,
    expires_hours: int = 48,
) -> str:
    """Create a JWT token for project invitations."""
    expire = datetime.now(UTC) + timedelta(hours=expires_hours)
    payload = {
        "project_id": str(project_id),
        "inviter_id": str(inviter_id),
        "email": email,
        "role": role,
        "exp": expire,
        "type": "invitation",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_invitation_token(token: str) -> dict[str, Any]:
    """Verify an invitation token and return its payload."""
    payload = decode_token(token)
    if payload.get("type") != "invitation":
        raise ValueError("Invalid token type")
    return payload
