"""Role-based access control (RBAC) for the application."""

from collections.abc import Callable
from enum import Enum
from functools import wraps

from fastapi import HTTPException, status


class Role(str, Enum):
    """User roles within a project."""

    OWNER = "owner"
    COLLABORATOR = "collaborator"
    VIEWER = "viewer"


# Permission definitions
class Permission(str, Enum):
    """Available permissions in the system."""

    # Project permissions
    PROJECT_CREATE = "project:create"
    PROJECT_READ = "project:read"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"

    # Workspace permissions
    WORKSPACE_CREATE = "workspace:create"
    WORKSPACE_READ = "workspace:read"
    WORKSPACE_UPDATE = "workspace:update"
    WORKSPACE_DELETE = "workspace:delete"

    # Collaborator permissions
    COLLABORATOR_INVITE = "collaborator:invite"
    COLLABORATOR_REMOVE = "collaborator:remove"
    COLLABORATOR_UPDATE_ROLE = "collaborator:update_role"

    # Job permissions
    JOB_CREATE = "job:create"
    JOB_READ = "job:read"
    JOB_CANCEL = "job:cancel"


# Role-permission mapping
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.OWNER: {
        Permission.PROJECT_CREATE,
        Permission.PROJECT_READ,
        Permission.PROJECT_UPDATE,
        Permission.PROJECT_DELETE,
        Permission.WORKSPACE_CREATE,
        Permission.WORKSPACE_READ,
        Permission.WORKSPACE_UPDATE,
        Permission.WORKSPACE_DELETE,
        Permission.COLLABORATOR_INVITE,
        Permission.COLLABORATOR_REMOVE,
        Permission.COLLABORATOR_UPDATE_ROLE,
        Permission.JOB_CREATE,
        Permission.JOB_READ,
        Permission.JOB_CANCEL,
    },
    Role.COLLABORATOR: {
        Permission.PROJECT_READ,
        Permission.PROJECT_UPDATE,
        Permission.WORKSPACE_CREATE,
        Permission.WORKSPACE_READ,
        Permission.WORKSPACE_UPDATE,
        Permission.JOB_CREATE,
        Permission.JOB_READ,
        Permission.JOB_CANCEL,
    },
    Role.VIEWER: {
        Permission.PROJECT_READ,
        Permission.WORKSPACE_READ,
        Permission.JOB_READ,
    },
}


def has_permission(role: Role, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    return permission in ROLE_PERMISSIONS.get(role, set())


def has_any_permission(role: Role, permissions: list[Permission]) -> bool:
    """Check if a role has any of the specified permissions."""
    role_perms = ROLE_PERMISSIONS.get(role, set())
    return any(perm in role_perms for perm in permissions)


def has_all_permissions(role: Role, permissions: list[Permission]) -> bool:
    """Check if a role has all of the specified permissions."""
    role_perms = ROLE_PERMISSIONS.get(role, set())
    return all(perm in role_perms for perm in permissions)


def require_permission(permission: Permission) -> Callable:
    """Decorator to require a specific permission for an endpoint."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get user_role from kwargs (should be injected by dependency)
            user_role = kwargs.get("user_role")
            if user_role is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Permission denied: No role found",
                )

            if isinstance(user_role, str):
                user_role = Role(user_role)

            if not has_permission(user_role, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission.value} required",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


class PermissionChecker:
    """Permission checker dependency for FastAPI."""

    def __init__(self, required_permission: Permission):
        self.required_permission = required_permission

    def __call__(self, user_role: Role) -> bool:
        if not has_permission(user_role, self.required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {self.required_permission.value} required",
            )
        return True
