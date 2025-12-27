"""Integration tests for projects API."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sql.project import Project
from app.models.sql.user import User


@pytest.mark.asyncio
class TestProjectsAPI:
    """Integration tests for project endpoints."""

    async def test_create_project(self, client: AsyncClient, test_user: User, auth_headers: dict):
        """Test project creation."""
        response = await client.post(
            "/api/v1/projects",
            headers=auth_headers,
            json={
                "name": "Test Project",
                "description": "A test project",
                "is_public": False,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Project"
        assert data["description"] == "A test project"
        assert data["is_public"] is False
        assert data["owner_id"] == str(test_user.id)

    async def test_create_project_minimal(self, client: AsyncClient, auth_headers: dict):
        """Test project creation with minimal data."""
        response = await client.post(
            "/api/v1/projects",
            headers=auth_headers,
            json={"name": "Minimal Project"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Project"
        assert data["is_public"] is False

    async def test_create_project_unauthenticated(self, client: AsyncClient):
        """Test project creation without auth fails."""
        response = await client.post(
            "/api/v1/projects",
            json={"name": "Test Project"},
        )

        assert response.status_code == 401

    async def test_list_projects(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test listing projects."""
        # Create some projects
        for i in range(3):
            project = Project(
                name=f"Project {i}",
                owner_id=test_user.id,
            )
            db_session.add(project)
        await db_session.commit()

        response = await client.get("/api/v1/projects", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] == 3
        assert len(data["items"]) == 3

    async def test_list_projects_pagination(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test project listing with pagination."""
        # Create 25 projects
        for i in range(25):
            project = Project(name=f"Project {i}", owner_id=test_user.id)
            db_session.add(project)
        await db_session.commit()

        # Get first page
        response = await client.get(
            "/api/v1/projects",
            headers=auth_headers,
            params={"page": 1, "page_size": 10},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["total"] == 25
        assert data["pages"] == 3

    async def test_get_project(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test getting a specific project."""
        project = Project(
            name="Test Project",
            description="Test Description",
            owner_id=test_user.id,
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        response = await client.get(
            f"/api/v1/projects/{project.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Project"
        assert data["description"] == "Test Description"

    async def test_get_nonexistent_project(self, client: AsyncClient, auth_headers: dict):
        """Test getting nonexistent project fails."""
        from uuid import uuid4

        response = await client.get(
            f"/api/v1/projects/{uuid4()}",
            headers=auth_headers,
        )

        assert response.status_code == 404

    async def test_update_project(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test updating a project."""
        project = Project(name="Original Name", owner_id=test_user.id)
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        response = await client.patch(
            f"/api/v1/projects/{project.id}",
            headers=auth_headers,
            json={"name": "Updated Name", "is_public": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["is_public"] is True

    async def test_delete_project(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test deleting a project."""
        project = Project(name="To Delete", owner_id=test_user.id)
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        response = await client.delete(
            f"/api/v1/projects/{project.id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verify deleted
        response = await client.get(
            f"/api/v1/projects/{project.id}",
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_project_name_validation(self, client: AsyncClient, auth_headers: dict):
        """Test project name validation."""
        # Empty name should fail
        response = await client.post(
            "/api/v1/projects",
            headers=auth_headers,
            json={"name": ""},
        )

        assert response.status_code == 422
