"""API dependencies for dependency injection."""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import verify_access_token
from app.db.postgres import get_db
from app.models.sql.project import Project
from app.models.sql.role import ProjectCollaborator
from app.models.sql.user import User

# Security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get the current authenticated user."""
    try:
        payload = verify_access_token(credentials.credentials)
        user_id = UUID(payload["sub"])
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get the current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Get the current user if authenticated, otherwise None."""
    if credentials is None:
        return None

    try:
        payload = verify_access_token(credentials.credentials)
        user_id = UUID(payload["sub"])
    except ValueError:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


class ProjectPermission:
    """Dependency for checking project permissions."""

    def __init__(self, required_role: Optional[Role] = None):
        self.required_role = required_role

    async def __call__(
        self,
        project_id: UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> tuple[Project, Role]:
        """Check if user has access to the project and return the project and role."""
        # Get project
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()

        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )

        # Check if user is owner
        if project.owner_id == current_user.id:
            user_role = Role.OWNER
        else:
            # Check if user is collaborator
            result = await db.execute(
                select(ProjectCollaborator).where(
                    ProjectCollaborator.project_id == project_id,
                    ProjectCollaborator.user_id == current_user.id,
                    ProjectCollaborator.accepted_at.isnot(None),
                )
            )
            collaborator = result.scalar_one_or_none()

            if collaborator is None:
                # Check if project is public
                if project.is_public:
                    user_role = Role.VIEWER
                else:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You don't have access to this project",
                    )
            else:
                user_role = Role(collaborator.role)

        # Check required role
        if self.required_role is not None:
            role_hierarchy = {Role.VIEWER: 0, Role.COLLABORATOR: 1, Role.OWNER: 2}
            if role_hierarchy[user_role] < role_hierarchy[self.required_role]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"This action requires {self.required_role.value} role or higher",
                )

        return project, user_role


# Common permission dependencies
require_project_viewer = ProjectPermission(Role.VIEWER)
require_project_collaborator = ProjectPermission(Role.COLLABORATOR)
require_project_owner = ProjectPermission(Role.OWNER)
