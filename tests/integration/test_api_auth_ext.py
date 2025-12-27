"""Extended integration tests for authentication API."""

import pytest
from httpx import AsyncClient

from app.models.sql.user import User


@pytest.mark.asyncio
class TestAuthAPIExtended:
    """Tests for refresh, logout, and password change."""

    async def test_refresh_token_flow(self, client: AsyncClient, test_user: User):
        """Test token refresh flow."""
        # 1. Login to get refresh token
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "testpass123"},
        )
        refresh_token = login_res.json()["refresh_token"]

        # 2. Refresh the token
        refresh_res = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_res.status_code == 200
        data = refresh_res.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_logout(self, client: AsyncClient, auth_headers: dict):
        """Test logout invalidates refresh token."""
        # Logout
        logout_res = await client.post("/api/v1/auth/logout", headers=auth_headers)
        assert logout_res.status_code == 204

        # Verify profile still accessible (access token valid till expiry)
        res = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert res.status_code == 200

    async def test_change_password(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test password change."""
        response = await client.post(
            "/api/v1/auth/change-password",
            headers=auth_headers,
            json={"current_password": "testpass123", "new_password": "newsecurepass123"},
        )
        assert response.status_code == 204

        # Verify old password fails
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "testpass123"},
        )
        assert login_res.status_code == 401

        # Verify new password works
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "newsecurepass123"},
        )
        assert login_res.status_code == 200
