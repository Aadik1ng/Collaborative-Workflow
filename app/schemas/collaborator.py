"""Collaborator schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.core.permissions import Role


class CollaboratorInvite(BaseModel):
    """Schema for inviting a collaborator."""

    email: EmailStr
    role: Role = Role.VIEWER
    message: str | None = Field(None, max_length=500)


class CollaboratorRoleUpdate(BaseModel):
    """Schema for updating collaborator role."""

    role: Role


class CollaboratorResponse(BaseModel):
    """Schema for collaborator response."""

    id: UUID
    user_id: UUID
    username: str
    email: str
    full_name: str | None = None
    role: str
    invited_at: datetime
    accepted_at: datetime | None = None

    class Config:
        from_attributes = True


class CollaboratorListResponse(BaseModel):
    """Schema for collaborator list."""

    items: list[CollaboratorResponse]
    total: int


class InvitationAccept(BaseModel):
    """Schema for accepting an invitation."""

    token: str


class InvitationResponse(BaseModel):
    """Schema for invitation response."""

    project_id: UUID
    project_name: str
    inviter_name: str
    role: str
    expires_at: datetime
