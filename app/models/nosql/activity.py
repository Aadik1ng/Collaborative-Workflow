"""Activity event models for MongoDB."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ActivityType(str, Enum):
    """Types of activity events."""

    USER_JOIN = "user.join"
    USER_LEAVE = "user.leave"
    FILE_CHANGE = "file.change"
    CURSOR_UPDATE = "cursor.update"
    MESSAGE = "message"
    PROJECT_UPDATE = "project.update"
    WORKSPACE_UPDATE = "workspace.update"


class ActivityEvent(BaseModel):
    """Activity event model for MongoDB storage."""

    id: Optional[str] = Field(None, alias="_id")
    project_id: str
    workspace_id: Optional[str] = None
    user_id: str
    username: str
    event_type: ActivityType
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        use_enum_values = True

    def to_mongo(self) -> Dict[str, Any]:
        """Convert to MongoDB document format."""
        data = self.model_dump(by_alias=True, exclude_none=True)
        if data.get("_id") is None:
            data.pop("_id", None)
        return data

    @classmethod
    def from_mongo(cls, data: Dict[str, Any]) -> "ActivityEvent":
        """Create from MongoDB document."""
        if data.get("_id"):
            data["_id"] = str(data["_id"])
        return cls(**data)


class UserJoinPayload(BaseModel):
    """Payload for user join events."""

    connection_id: Optional[str] = None


class UserLeavePayload(BaseModel):
    """Payload for user leave events."""

    reason: Optional[str] = None
    duration_seconds: Optional[int] = None


class FileChangePayload(BaseModel):
    """Payload for file change events."""

    file_path: str
    operation: str  # create, update, delete, rename
    content_hash: Optional[str] = None
    old_path: Optional[str] = None  # For rename operations


class CursorUpdatePayload(BaseModel):
    """Payload for cursor update events."""

    file_path: str
    line: int
    column: int
    selection_start: Optional[Dict[str, int]] = None
    selection_end: Optional[Dict[str, int]] = None
