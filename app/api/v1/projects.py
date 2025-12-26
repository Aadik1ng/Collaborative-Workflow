"""Project endpoints."""

from math import ceil
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    ProjectPermission,
    get_current_user,
    require_project_owner,
    require_project_viewer,
)
from app.core.permissions import Role
from app.db.postgres import get_db
from app.models.sql.project import Project
from app.models.sql.role import ProjectCollaborator
from app.models.sql.user import User
from app.models.sql.workspace import Workspace
from app.schemas.project import (
    ProjectCreate,
    ProjectDetailResponse,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter()


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List user's projects",
)
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    """List all projects the user owns or collaborates on."""
    # Base query for owned projects
    owned_query = select(Project.id).where(Project.owner_id == current_user.id)

    # Query for collaborated projects
    collab_query = select(ProjectCollaborator.project_id).where(
        ProjectCollaborator.user_id == current_user.id,
        ProjectCollaborator.accepted_at.isnot(None),
    )

    # Combine queries
    project_ids = owned_query.union(collab_query).subquery()

    query = select(Project).where(Project.id.in_(select(project_ids)))

    # Apply search filter
    if search:
        query = query.where(Project.name.ilike(f"%{search}%"))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    query = query.order_by(Project.updated_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    projects = result.scalars().all()

    return ProjectListResponse(
        items=list(projects),
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if total > 0 else 1,
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """Create a new project."""
    project = Project(
        name=project_data.name,
        description=project_data.description,
        owner_id=current_user.id,
        is_public=project_data.is_public,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return project


@router.get(
    "/{project_id}",
    response_model=ProjectDetailResponse,
    summary="Get project details",
)
async def get_project(
    project_id: UUID,
    project_data: tuple[Project, Role] = Depends(require_project_viewer),
    db: AsyncSession = Depends(get_db),
) -> ProjectDetailResponse:
    """Get project details with owner information."""
    project, _ = project_data

    # Get workspace count
    workspace_count = (
        await db.execute(
            select(func.count()).where(Workspace.project_id == project.id)
        )
    ).scalar() or 0

    # Get collaborator count
    collab_count = (
        await db.execute(
            select(func.count()).where(
                ProjectCollaborator.project_id == project.id,
                ProjectCollaborator.accepted_at.isnot(None),
            )
        )
    ).scalar() or 0

    # Load owner
    result = await db.execute(
        select(Project)
        .where(Project.id == project.id)
        .options(selectinload(Project.owner))
    )
    project = result.scalar_one()

    return ProjectDetailResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        owner_id=project.owner_id,
        is_public=project.is_public,
        created_at=project.created_at,
        updated_at=project.updated_at,
        owner=project.owner,
        workspace_count=workspace_count,
        collaborator_count=collab_count,
    )


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update a project",
)
async def update_project(
    project_id: UUID,
    update_data: ProjectUpdate,
    project_data: tuple[Project, Role] = Depends(
        ProjectPermission(Role.COLLABORATOR)
    ),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """Update project details."""
    project, user_role = project_data

    # Only owner can change is_public
    if update_data.is_public is not None and user_role != Role.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owner can change project visibility",
        )

    if update_data.name is not None:
        project.name = update_data.name
    if update_data.description is not None:
        project.description = update_data.description
    if update_data.is_public is not None:
        project.is_public = update_data.is_public

    await db.flush()
    await db.refresh(project)
    return project


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project",
)
async def delete_project(
    project_id: UUID,
    project_data: tuple[Project, Role] = Depends(require_project_owner),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a project (owner only)."""
    project, _ = project_data
    await db.delete(project)
    await db.flush()
