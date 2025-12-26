"""Unit tests for role-based access control."""

import pytest

from app.core.permissions import (
    Permission,
    Role,
    has_all_permissions,
    has_any_permission,
    has_permission,
    ROLE_PERMISSIONS,
)


class TestRolePermissions:
    """Tests for RBAC functionality."""

    def test_owner_has_all_permissions(self):
        """Verify owner role has all permissions."""
        for permission in Permission:
            assert has_permission(Role.OWNER, permission) is True

    def test_viewer_limited_permissions(self):
        """Verify viewer role has limited permissions."""
        # Viewer should have read permissions
        assert has_permission(Role.VIEWER, Permission.PROJECT_READ) is True
        assert has_permission(Role.VIEWER, Permission.WORKSPACE_READ) is True
        assert has_permission(Role.VIEWER, Permission.JOB_READ) is True

        # Viewer should NOT have write permissions
        assert has_permission(Role.VIEWER, Permission.PROJECT_CREATE) is False
        assert has_permission(Role.VIEWER, Permission.PROJECT_UPDATE) is False
        assert has_permission(Role.VIEWER, Permission.PROJECT_DELETE) is False
        assert has_permission(Role.VIEWER, Permission.COLLABORATOR_INVITE) is False

    def test_collaborator_moderate_permissions(self):
        """Verify collaborator role has moderate permissions."""
        # Collaborator should have these permissions
        assert has_permission(Role.COLLABORATOR, Permission.PROJECT_READ) is True
        assert has_permission(Role.COLLABORATOR, Permission.PROJECT_UPDATE) is True
        assert has_permission(Role.COLLABORATOR, Permission.WORKSPACE_CREATE) is True
        assert has_permission(Role.COLLABORATOR, Permission.JOB_CREATE) is True

        # Collaborator should NOT have these permissions
        assert has_permission(Role.COLLABORATOR, Permission.PROJECT_DELETE) is False
        assert has_permission(Role.COLLABORATOR, Permission.COLLABORATOR_INVITE) is False
        assert has_permission(Role.COLLABORATOR, Permission.COLLABORATOR_REMOVE) is False

    def test_has_any_permission(self):
        """Verify has_any_permission function."""
        permissions = [Permission.PROJECT_CREATE, Permission.PROJECT_DELETE]

        # Owner has all
        assert has_any_permission(Role.OWNER, permissions) is True

        # Viewer has none
        assert has_any_permission(Role.VIEWER, permissions) is False

        # Collaborator has none of these specific ones
        assert has_any_permission(Role.COLLABORATOR, permissions) is False

    def test_has_all_permissions(self):
        """Verify has_all_permissions function."""
        read_permissions = [Permission.PROJECT_READ, Permission.WORKSPACE_READ]

        # All roles should have read permissions
        assert has_all_permissions(Role.OWNER, read_permissions) is True
        assert has_all_permissions(Role.COLLABORATOR, read_permissions) is True
        assert has_all_permissions(Role.VIEWER, read_permissions) is True

        # Only owner has all admin permissions
        admin_permissions = [Permission.PROJECT_DELETE, Permission.COLLABORATOR_REMOVE]
        assert has_all_permissions(Role.OWNER, admin_permissions) is True
        assert has_all_permissions(Role.COLLABORATOR, admin_permissions) is False

    def test_role_enum_values(self):
        """Verify role enum values."""
        assert Role.OWNER.value == "owner"
        assert Role.COLLABORATOR.value == "collaborator"
        assert Role.VIEWER.value == "viewer"

    def test_role_permissions_mapping_complete(self):
        """Verify all roles have permissions mapped."""
        for role in Role:
            assert role in ROLE_PERMISSIONS
            assert isinstance(ROLE_PERMISSIONS[role], set)
