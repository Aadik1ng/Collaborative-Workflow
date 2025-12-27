"""Unit tests for authentication utilities."""

from uuid import uuid4

import pytest

from app.core.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_invitation_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_access_token,
    verify_invitation_token,
    verify_password,
    verify_refresh_token,
)


class TestPasswordHashing:
    """Tests for password hashing utilities."""

    def test_hash_password_creates_hash(self):
        """Verify password hashing produces a hash."""
        password = "securepassword123"
        hashed = hash_password(password)

        assert hashed != password
        assert len(hashed) > 0

    def test_verify_password_correct(self):
        """Verify correct password verification."""
        password = "securepassword123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Verify incorrect password fails verification."""
        password = "securepassword123"
        hashed = hash_password(password)

        assert verify_password("wrongpassword", hashed) is False

    def test_different_passwords_produce_different_hashes(self):
        """Verify different passwords produce different hashes."""
        hash1 = hash_password("password1")
        hash2 = hash_password("password2")

        assert hash1 != hash2


class TestJWTTokens:
    """Tests for JWT token creation and verification."""

    def test_create_access_token(self):
        """Verify access token creation."""
        user_id = uuid4()
        token = create_access_token(user_id)

        assert token is not None
        assert len(token) > 0

    def test_create_refresh_token(self):
        """Verify refresh token creation."""
        user_id = uuid4()
        token = create_refresh_token(user_id)

        assert token is not None
        assert len(token) > 0

    def test_verify_access_token(self):
        """Verify access token verification."""
        user_id = uuid4()
        token = create_access_token(user_id)

        payload = verify_access_token(token)

        assert payload["sub"] == str(user_id)
        assert payload["type"] == ACCESS_TOKEN_TYPE

    def test_verify_refresh_token(self):
        """Verify refresh token verification."""
        user_id = uuid4()
        token = create_refresh_token(user_id)

        payload = verify_refresh_token(token)

        assert payload["sub"] == str(user_id)
        assert payload["type"] == REFRESH_TOKEN_TYPE

    def test_access_token_with_additional_claims(self):
        """Verify access token with additional claims."""
        user_id = uuid4()
        additional = {"role": "admin", "org_id": "org123"}
        token = create_access_token(user_id, additional_claims=additional)

        payload = verify_access_token(token)

        assert payload["role"] == "admin"
        assert payload["org_id"] == "org123"

    def test_verify_access_token_rejects_refresh_token(self):
        """Verify access token verification rejects refresh tokens."""
        user_id = uuid4()
        refresh_token = create_refresh_token(user_id)

        with pytest.raises(ValueError, match="Invalid token type"):
            verify_access_token(refresh_token)

    def test_verify_refresh_token_rejects_access_token(self):
        """Verify refresh token verification rejects access tokens."""
        user_id = uuid4()
        access_token = create_access_token(user_id)

        with pytest.raises(ValueError, match="Invalid token type"):
            verify_refresh_token(access_token)

    def test_decode_invalid_token(self):
        """Verify invalid token raises error."""
        with pytest.raises(ValueError, match="Invalid token"):
            decode_token("invalid.token.here")


class TestInvitationTokens:
    """Tests for invitation token functionality."""

    def test_create_invitation_token(self):
        """Verify invitation token creation."""
        project_id = uuid4()
        inviter_id = uuid4()
        email = "invitee@example.com"
        role = "collaborator"

        token = create_invitation_token(project_id, inviter_id, email, role)

        assert token is not None
        assert len(token) > 0

    def test_verify_invitation_token(self):
        """Verify invitation token verification."""
        project_id = uuid4()
        inviter_id = uuid4()
        email = "invitee@example.com"
        role = "collaborator"

        token = create_invitation_token(project_id, inviter_id, email, role)
        payload = verify_invitation_token(token)

        assert payload["project_id"] == str(project_id)
        assert payload["inviter_id"] == str(inviter_id)
        assert payload["email"] == email
        assert payload["role"] == role

    def test_verify_invitation_token_rejects_access_token(self):
        """Verify invitation verification rejects access tokens."""
        access_token = create_access_token(uuid4())

        with pytest.raises(ValueError, match="Invalid token type"):
            verify_invitation_token(access_token)
