"""Integration tests for WebSocket-related API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.sql.project import Project
from app.models.sql.user import User
from app.models.sql.workspace import Workspace

@pytest.mark.asyncio
class TestWebSocketAPI:
    """Integration tests for WebSocket-related helper endpoints."""

    async def test_get_workspace_users(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test getting active users in a workspace."""
        # Setup workspace
        project = Project(name="WS Users Project", owner_id=test_user.id)
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        ws = Workspace(name="Active WS", project_id=project.id)
        db_session.add(ws)
        await db_session.commit()
        await db_session.refresh(ws)

        response = await client.get(
            f"/ws/workspace/{ws.id}/users",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert isinstance(data["users"], list)
