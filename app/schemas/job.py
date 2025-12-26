"""Job schemas for async processing."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.nosql.event import JobStatus


class JobCreate(BaseModel):
    """Schema for creating a job."""

    task_type: str = Field(..., max_length=100)
    input_data: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(None, max_length=255)


class CodeExecutionJobCreate(BaseModel):
    """Schema for code execution job."""

    code: str = Field(..., max_length=50000)
    language: str = Field(..., max_length=50)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    memory_limit_mb: int = Field(default=128, ge=16, le=512)


class JobResponse(BaseModel):
    """Schema for job response."""

    id: str
    user_id: str
    task_type: str
    status: JobStatus
    input_data: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    attempts: int = 0
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class JobListResponse(BaseModel):
    """Schema for paginated job list."""

    items: List[JobResponse]
    total: int
    page: int
    page_size: int
    pages: int


class JobCancelResponse(BaseModel):
    """Schema for job cancellation response."""

    id: str
    status: JobStatus
    message: str
