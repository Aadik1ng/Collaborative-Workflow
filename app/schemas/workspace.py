"""Workspace schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    """Schema for creating a workspace."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    settings: Dict[str, Any] = Field(default_factory=dict)


class WorkspaceUpdate(BaseModel):
    """Schema for updating a workspace."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    settings: Optional[Dict[str, Any]] = None


class WorkspaceResponse(BaseModel):
    """Schema for workspace response."""

    id: UUID
    name: str
    description: Optional[str] = None
    project_id: UUID
    settings: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkspaceListResponse(BaseModel):
    """Schema for paginated workspace list."""

    items: List[WorkspaceResponse]
    total: int
    page: int
    page_size: int
    pages: int


class WorkspaceConnectionInfo(BaseModel):
    """Schema for workspace WebSocket connection info."""

    workspace_id: UUID
    websocket_url: str
    active_users: int = 0
