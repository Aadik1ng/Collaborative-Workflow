"""Workspace endpoints."""

from math import ceil
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ProjectPermission,
    get_current_user,
    require_project_collaborator,
    require_project_viewer,
)
from app.core.permissions import Role
from app.db.postgres import get_db
from app.models.sql.project import Project
from app.models.sql.user import User
from app.models.sql.workspace import Workspace
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceListResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)

router = APIRouter()


@router.get(
    "/projects/{project_id}/workspaces",
    response_model=WorkspaceListResponse,
    summary="List workspaces in a project",
)
async def list_workspaces(
    project_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    project_data: tuple[Project, Role] = Depends(require_project_viewer),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceListResponse:
    """List all workspaces in a project."""
    project, _ = project_data

    query = select(Workspace).where(Workspace.project_id == project.id)

    # Apply search filter
    if search:
        query = query.where(Workspace.name.ilike(f"%{search}%"))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    query = query.order_by(Workspace.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    workspaces = result.scalars().all()

    return WorkspaceListResponse(
        items=list(workspaces),
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if total > 0 else 1,
    )


@router.post(
    "/projects/{project_id}/workspaces",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace",
)
async def create_workspace(
    project_id: UUID,
    workspace_data: WorkspaceCreate,
    project_data: tuple[Project, Role] = Depends(require_project_collaborator),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    """Create a new workspace in a project."""
    project, _ = project_data

    workspace = Workspace(
        name=workspace_data.name,
        description=workspace_data.description,
        project_id=project.id,
        settings=workspace_data.settings,
    )
    db.add(workspace)
    await db.flush()
    await db.refresh(workspace)
    return workspace


@router.get(
    "/workspaces/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Get workspace details",
)
async def get_workspace(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    """Get workspace details."""
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # Check project access
    project_perm = ProjectPermission(Role.VIEWER)
    await project_perm(workspace.project_id, current_user, db)

    return workspace


@router.patch(
    "/workspaces/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Update a workspace",
)
async def update_workspace(
    workspace_id: UUID,
    update_data: WorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    """Update workspace details."""
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # Check project access (collaborator or higher)
    project_perm = ProjectPermission(Role.COLLABORATOR)
    await project_perm(workspace.project_id, current_user, db)

    if update_data.name is not None:
        workspace.name = update_data.name
    if update_data.description is not None:
        workspace.description = update_data.description
    if update_data.settings is not None:
        workspace.settings = update_data.settings

    await db.flush()
    await db.refresh(workspace)
    return workspace


@router.delete(
    "/workspaces/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a workspace",
)
async def delete_workspace(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a workspace (collaborator or higher)."""
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()

    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # Check project access (collaborator or higher)
    project_perm = ProjectPermission(Role.COLLABORATOR)
    await project_perm(workspace.project_id, current_user, db)

    await db.delete(workspace)
    await db.flush()
