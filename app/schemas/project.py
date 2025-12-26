"""Project schemas."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.auth import UserResponse


class ProjectCreate(BaseModel):
    """Schema for creating a project."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    is_public: bool = False


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    is_public: Optional[bool] = None


class ProjectResponse(BaseModel):
    """Schema for project response."""

    id: UUID
    name: str
    description: Optional[str] = None
    owner_id: UUID
    is_public: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectDetailResponse(ProjectResponse):
    """Schema for detailed project response with owner info."""

    owner: UserResponse
    workspace_count: int = 0
    collaborator_count: int = 0


class ProjectListResponse(BaseModel):
    """Schema for paginated project list."""

    items: List[ProjectResponse]
    total: int
    page: int
    page_size: int
    pages: int
