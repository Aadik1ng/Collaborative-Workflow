"""Security utilities for JWT authentication and password hashing."""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

import jwt
from passlib.context import CryptContext

from app.config import settings

# Password hashing configuration
# We use Argon2 as it's the modern winner of the Password Hashing Competition
# and avoids the 72-byte limit and compatibility issues of bcrypt.
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# Token types
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    user_id: UUID,
    additional_claims: Optional[dict[str, Any]] = None,
) -> str:
    """Create a JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": ACCESS_TOKEN_TYPE,
    }
    if additional_claims:
        payload.update(additional_claims)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: UUID) -> str:
    """Create a JWT refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
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
    expire = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
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
