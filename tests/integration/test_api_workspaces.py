"""Integration tests for workspaces API."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.sql.project import Project
from app.models.sql.user import User
from app.models.sql.workspace import Workspace

@pytest.mark.asyncio
class TestWorkspacesAPI:
    """Integration tests for workspace endpoints."""

    async def test_create_workspace(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test workspace creation."""
        # Create a project first
        project = Project(name="Project for Workspace", owner_id=test_user.id)
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        response = await client.post(
            f"/api/v1/projects/{project.id}/workspaces",
            headers=auth_headers,
            json={
                "name": "New Workspace",
                "description": "A fresh workspace",
                "settings": {"theme": "dark"}
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Workspace"
        assert data["project_id"] == str(project.id)

    async def test_list_workspaces(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test listing workspaces in a project."""
        project = Project(name="List Project", owner_id=test_user.id)
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        # Add 3 workspaces
        for i in range(3):
            ws = Workspace(name=f"WS {i}", project_id=project.id)
            db_session.add(ws)
        await db_session.commit()

        response = await client.get(
            f"/api/v1/projects/{project.id}/workspaces",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    async def test_update_workspace(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test updating a workspace."""
        project = Project(name="Update Project", owner_id=test_user.id)
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        ws = Workspace(name="Old Name", project_id=project.id)
        db_session.add(ws)
        await db_session.commit()
        await db_session.refresh(ws)

        response = await client.patch(
            f"/api/v1/workspaces/{ws.id}",
            headers=auth_headers,
            json={"name": "Updated Name"}
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    async def test_delete_workspace(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test deleting a workspace."""
        project = Project(name="Delete Project", owner_id=test_user.id)
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        ws = Workspace(name="Bye Bye", project_id=project.id)
        db_session.add(ws)
        await db_session.commit()
        await db_session.refresh(ws)

        response = await client.delete(
            f"/api/v1/workspaces/{ws.id}",
            headers=auth_headers
        )
        assert response.status_code == 204

        # Verify 404
        get_res = await client.get(f"/api/v1/workspaces/{ws.id}", headers=auth_headers)
        assert get_res.status_code == 404
