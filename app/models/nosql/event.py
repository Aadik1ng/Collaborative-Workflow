"""Job result models for MongoDB."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job processing status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobResult(BaseModel):
    """Job result model for MongoDB storage."""

    id: str = Field(..., alias="_id")  # Job ID (used for idempotency)
    user_id: str
    task_type: str
    status: JobStatus = JobStatus.PENDING
    input_data: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    attempts: int = 0
    max_retries: int = 3
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    class Config:
        populate_by_name = True
        use_enum_values = True

    def to_mongo(self) -> dict[str, Any]:
        """Convert to MongoDB document format."""
        return self.model_dump(by_alias=True)

    @classmethod
    def from_mongo(cls, data: dict[str, Any]) -> "JobResult":
        """Create from MongoDB document."""
        return cls(**data)


class CodeExecutionInput(BaseModel):
    """Input for code execution jobs."""

    code: str
    language: str
    timeout_seconds: int = 30
    memory_limit_mb: int = 128


class CodeExecutionResult(BaseModel):
    """Result from code execution jobs."""

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time_ms: int = 0
    memory_used_mb: float = 0.0
