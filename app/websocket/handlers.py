"""WebSocket event handlers."""

import logging
from datetime import UTC, datetime
from typing import Any

from app.db.mongodb import get_activities_collection
from app.models.nosql.activity import ActivityEvent, ActivityType
from app.websocket.manager import connection_manager
from app.websocket.pubsub import publish_workspace_event

logger = logging.getLogger(__name__)


async def handle_user_join(
    connection_id: str,
    workspace_id: str,
    user_id: str,
    username: str,
) -> None:
    """Handle user join event."""
    # Get current users in workspace
    active_users = connection_manager.get_workspace_users(workspace_id)

    # Broadcast join event to other users
    await connection_manager.broadcast_to_workspace(
        workspace_id,
        {
            "type": ActivityType.USER_JOIN.value,
            "data": {
                "user_id": user_id,
                "username": username,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        },
        exclude_connection=connection_id,
    )

    # Send current users list to the joining user
    await connection_manager.send_to_connection(
        connection_id,
        {
            "type": "workspace.state",
            "data": {
                "active_users": active_users,
                "user_count": len(active_users),
            },
        },
    )

    # Publish to Redis for cross-instance communication
    await publish_workspace_event(
        workspace_id,
        ActivityType.USER_JOIN.value,
        {
            "user_id": user_id,
            "username": username,
        },
        sender_id=user_id,
    )

    # Log activity to MongoDB
    await _log_activity(
        workspace_id=workspace_id,
        user_id=user_id,
        username=username,
        event_type=ActivityType.USER_JOIN,
        payload={"connection_id": connection_id},
    )


async def handle_user_leave(
    workspace_id: str,
    user_id: str,
    username: str,
    connected_at: datetime,
) -> None:
    """Handle user leave event."""
    duration_seconds = int((datetime.now(UTC) - connected_at).total_seconds())

    # Broadcast leave event
    await connection_manager.broadcast_to_workspace(
        workspace_id,
        {
            "type": ActivityType.USER_LEAVE.value,
            "data": {
                "user_id": user_id,
                "username": username,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        },
    )

    # Publish to Redis
    await publish_workspace_event(
        workspace_id,
        ActivityType.USER_LEAVE.value,
        {
            "user_id": user_id,
            "username": username,
            "duration_seconds": duration_seconds,
        },
        sender_id=user_id,
    )

    # Log activity
    await _log_activity(
        workspace_id=workspace_id,
        user_id=user_id,
        username=username,
        event_type=ActivityType.USER_LEAVE,
        payload={"duration_seconds": duration_seconds},
    )


async def handle_file_change(
    connection_id: str,
    workspace_id: str,
    user_id: str,
    username: str,
    payload: dict[str, Any],
) -> None:
    """Handle file change event."""
    event_data = {
        "user_id": user_id,
        "username": username,
        "file_path": payload.get("file_path"),
        "operation": payload.get("operation"),
        "content_hash": payload.get("content_hash"),
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Broadcast to other users
    await connection_manager.broadcast_to_workspace(
        workspace_id,
        {
            "type": ActivityType.FILE_CHANGE.value,
            "data": event_data,
        },
        exclude_connection=connection_id,
    )

    # Publish to Redis
    await publish_workspace_event(
        workspace_id,
        ActivityType.FILE_CHANGE.value,
        event_data,
        sender_id=user_id,
    )

    # Log activity
    await _log_activity(
        workspace_id=workspace_id,
        user_id=user_id,
        username=username,
        event_type=ActivityType.FILE_CHANGE,
        payload=payload,
    )


async def handle_cursor_update(
    connection_id: str,
    workspace_id: str,
    user_id: str,
    username: str,
    payload: dict[str, Any],
) -> None:
    """Handle cursor update event (throttled, not logged to DB)."""
    event_data = {
        "user_id": user_id,
        "username": username,
        "file_path": payload.get("file_path"),
        "position": payload.get("position"),
        "selection": payload.get("selection"),
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Broadcast to other users (no persistence for cursor updates)
    await connection_manager.broadcast_to_workspace(
        workspace_id,
        {
            "type": ActivityType.CURSOR_UPDATE.value,
            "data": event_data,
        },
        exclude_connection=connection_id,
    )


async def handle_message(
    connection_id: str,
    workspace_id: str,
    user_id: str,
    username: str,
    payload: dict[str, Any],
) -> None:
    """Handle chat message event."""
    event_data = {
        "user_id": user_id,
        "username": username,
        "message": payload.get("message"),
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Broadcast to all users including sender
    await connection_manager.broadcast_to_workspace(
        workspace_id,
        {
            "type": ActivityType.MESSAGE.value,
            "data": event_data,
        },
    )

    # Log activity
    await _log_activity(
        workspace_id=workspace_id,
        user_id=user_id,
        username=username,
        event_type=ActivityType.MESSAGE,
        payload={"message": payload.get("message")},
    )


async def _log_activity(
    workspace_id: str,
    user_id: str,
    username: str,
    event_type: ActivityType,
    payload: dict[str, Any],
    project_id: str = "",
) -> None:
    """Log activity to MongoDB."""
    try:
        collection = get_activities_collection()

        activity = ActivityEvent(
            project_id=project_id,
            workspace_id=workspace_id,
            user_id=user_id,
            username=username,
            event_type=event_type,
            payload=payload,
        )

        await collection.insert_one(activity.to_mongo())
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")
