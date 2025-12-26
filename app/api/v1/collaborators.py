"""Collaborator management endpoints."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    ProjectPermission,
    get_current_user,
    require_project_owner,
)
from app.core.permissions import Role
from app.core.security import create_invitation_token, verify_invitation_token
from app.db.postgres import get_db
from app.models.sql.project import Project
from app.models.sql.role import ProjectCollaborator
from app.models.sql.user import User
from app.schemas.collaborator import (
    CollaboratorInvite,
    CollaboratorListResponse,
    CollaboratorResponse,
    CollaboratorRoleUpdate,
    InvitationAccept,
    InvitationResponse,
)

router = APIRouter()


@router.get(
    "/projects/{project_id}/collaborators",
    response_model=CollaboratorListResponse,
    summary="List project collaborators",
)
async def list_collaborators(
    project_id: UUID,
    project_data: tuple[Project, Role] = Depends(ProjectPermission(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> CollaboratorListResponse:
    """List all collaborators for a project."""
    project, _ = project_data

    # Get collaborators with user info
    result = await db.execute(
        select(ProjectCollaborator)
        .where(ProjectCollaborator.project_id == project.id)
        .options(selectinload(ProjectCollaborator.user))
        .order_by(ProjectCollaborator.invited_at.desc())
    )
    collaborators = result.scalars().all()

    items = [
        CollaboratorResponse(
            id=c.id,
            user_id=c.user_id,
            username=c.user.username,
            email=c.user.email,
            full_name=c.user.full_name,
            role=c.role,
            invited_at=c.invited_at,
            accepted_at=c.accepted_at,
        )
        for c in collaborators
    ]

    return CollaboratorListResponse(items=items, total=len(items))


@router.post(
    "/projects/{project_id}/collaborators",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a collaborator",
)
async def invite_collaborator(
    project_id: UUID,
    invite_data: CollaboratorInvite,
    project_data: tuple[Project, Role] = Depends(require_project_owner),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Invite a user to collaborate on a project."""
    project, _ = project_data

    # Check if user exists
    result = await db.execute(select(User).where(User.email == invite_data.email))
    invited_user = result.scalar_one_or_none()

    if invited_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email not found",
        )

    if invited_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot invite yourself",
        )

    # Check if already a collaborator
    result = await db.execute(
        select(ProjectCollaborator).where(
            ProjectCollaborator.project_id == project.id,
            ProjectCollaborator.user_id == invited_user.id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a collaborator",
        )

    # Create invitation token
    invitation_token = create_invitation_token(
        project_id=project.id,
        inviter_id=current_user.id,
        email=invite_data.email,
        role=invite_data.role.value,
    )

    # Create pending collaborator record
    collaborator = ProjectCollaborator(
        project_id=project.id,
        user_id=invited_user.id,
        role=invite_data.role.value,
        invited_by=current_user.id,
    )
    db.add(collaborator)
    await db.flush()

    return {
        "message": "Invitation sent successfully",
        "invitation_token": invitation_token,
    }


@router.post(
    "/invitations/accept",
    response_model=dict,
    summary="Accept an invitation",
)
async def accept_invitation(
    accept_data: InvitationAccept,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Accept a project invitation."""
    try:
        payload = verify_invitation_token(accept_data.token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if payload["email"] != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This invitation is for a different email",
        )

    project_id = UUID(payload["project_id"])

    # Find pending invitation
    result = await db.execute(
        select(ProjectCollaborator).where(
            ProjectCollaborator.project_id == project_id,
            ProjectCollaborator.user_id == current_user.id,
            ProjectCollaborator.accepted_at.is_(None),
        )
    )
    collaborator = result.scalar_one_or_none()

    if collaborator is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found or already accepted",
        )

    collaborator.accepted_at = datetime.now(timezone.utc)
    await db.flush()

    return {"message": "Invitation accepted successfully"}


@router.get(
    "/invitations/{token}",
    response_model=InvitationResponse,
    summary="Get invitation details",
)
async def get_invitation_details(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InvitationResponse:
    """Get details about an invitation from its token."""
    try:
        payload = verify_invitation_token(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    project_id = UUID(payload["project_id"])
    inviter_id = UUID(payload["inviter_id"])

    # Get project and inviter info
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    result = await db.execute(select(User).where(User.id == inviter_id))
    inviter = result.scalar_one_or_none()

    if project is None or inviter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project or inviter not found",
        )

    from datetime import datetime

    return InvitationResponse(
        project_id=project.id,
        project_name=project.name,
        inviter_name=inviter.full_name or inviter.username,
        role=payload["role"],
        expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
    )


@router.patch(
    "/projects/{project_id}/collaborators/{user_id}",
    response_model=CollaboratorResponse,
    summary="Update collaborator role",
)
async def update_collaborator_role(
    project_id: UUID,
    user_id: UUID,
    role_data: CollaboratorRoleUpdate,
    project_data: tuple[Project, Role] = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
) -> CollaboratorResponse:
    """Update a collaborator's role (owner only)."""
    project, _ = project_data

    result = await db.execute(
        select(ProjectCollaborator)
        .where(
            ProjectCollaborator.project_id == project.id,
            ProjectCollaborator.user_id == user_id,
        )
        .options(selectinload(ProjectCollaborator.user))
    )
    collaborator = result.scalar_one_or_none()

    if collaborator is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collaborator not found",
        )

    # Cannot change to owner role
    if role_data.role == Role.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign owner role. Transfer ownership instead.",
        )

    collaborator.role = role_data.role.value
    await db.flush()
    await db.refresh(collaborator)

    return CollaboratorResponse(
        id=collaborator.id,
        user_id=collaborator.user_id,
        username=collaborator.user.username,
        email=collaborator.user.email,
        full_name=collaborator.user.full_name,
        role=collaborator.role,
        invited_at=collaborator.invited_at,
        accepted_at=collaborator.accepted_at,
    )


@router.delete(
    "/projects/{project_id}/collaborators/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a collaborator",
)
async def remove_collaborator(
    project_id: UUID,
    user_id: UUID,
    project_data: tuple[Project, Role] = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a collaborator from a project (owner only)."""
    project, _ = project_data

    result = await db.execute(
        select(ProjectCollaborator).where(
            ProjectCollaborator.project_id == project.id,
            ProjectCollaborator.user_id == user_id,
        )
    )
    collaborator = result.scalar_one_or_none()

    if collaborator is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collaborator not found",
        )

    await db.delete(collaborator)
    await db.flush()
