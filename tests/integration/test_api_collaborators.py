"""Integration tests for collaborators API."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.sql.project import Project
from app.models.sql.user import User
from app.models.sql.role import ProjectCollaborator
from app.core.permissions import Role

@pytest.mark.asyncio
class TestCollaboratorsAPI:
    """Integration tests for project collaborators."""

    async def test_invite_collaborator(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test inviting a collaborator."""
        project = Project(name="Invite Project", owner_id=test_user.id)
        db_session.add(project)
        
        # Create another user to invite
        invited_user = User(
            email="invitee@example.com",
            username="invitee",
            hashed_password="hashed_password",
        )
        db_session.add(invited_user)
        await db_session.commit()

        response = await client.post(
            f"/api/v1/projects/{project.id}/collaborators",
            headers=auth_headers,
            json={"email": "invitee@example.com", "role": "collaborator"},
        )

        assert response.status_code == 201
        assert "invitation_token" in response.json()

    async def test_list_collaborators(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test listing collaborators."""
        project = Project(name="List Collab Project", owner_id=test_user.id)
        db_session.add(project)
        await db_session.flush()

        # Add owner to collaborators table
        owner_collab = ProjectCollaborator(
            project_id=project.id,
            user_id=test_user.id,
            role=Role.OWNER.value
        )
        db_session.add(owner_collab)
        await db_session.commit()

        response = await client.get(
            f"/api/v1/projects/{project.id}/collaborators",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1  # Just the owner
        assert data["items"][0]["role"] == "owner"

    async def test_update_collaborator_role(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test updating a collaborator's role."""
        project = Project(name="Update Collab Project", owner_id=test_user.id)
        db_session.add(project)
        
        collab_user = User(email="c1@ex.com", username="c1", hashed_password="h")
        db_session.add(collab_user)
        await db_session.commit()

        # Add as collaborator
        collab = ProjectCollaborator(
            project_id=project.id,
            user_id=collab_user.id,
            role=Role.VIEWER.value
        )
        db_session.add(collab)
        await db_session.commit()

        response = await client.patch(
            f"/api/v1/projects/{project.id}/collaborators/{collab_user.id}",
            headers=auth_headers,
            json={"role": "collaborator"}
        )

        assert response.status_code == 200
        assert response.json()["role"] == "collaborator"

    async def test_remove_collaborator(
        self, client: AsyncClient, test_user: User, auth_headers: dict, db_session: AsyncSession
    ):
        """Test removing a collaborator."""
        project = Project(name="Remove Collab Project", owner_id=test_user.id)
        db_session.add(project)
        
        collab_user = User(email="c2@ex.com", username="c2", hashed_password="h")
        db_session.add(collab_user)
        await db_session.commit()

        collab = ProjectCollaborator(project_id=project.id, user_id=collab_user.id, role="viewer")
        db_session.add(collab)
        await db_session.commit()

        response = await client.delete(
            f"/api/v1/projects/{project.id}/collaborators/{collab_user.id}",
            headers=auth_headers
        )
        assert response.status_code == 204
