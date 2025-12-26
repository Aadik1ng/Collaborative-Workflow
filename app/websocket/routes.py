"""WebSocket routes for real-time collaboration."""

import json
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.security import verify_access_token
from app.db.postgres import async_session_factory
from app.models.sql.user import User
from app.models.sql.workspace import Workspace
from app.websocket.handlers import (
    handle_cursor_update,
    handle_file_change,
    handle_message,
    handle_user_join,
    handle_user_leave,
)
from app.websocket.manager import connection_manager

logger = logging.getLogger(__name__)

router = APIRouter()


async def authenticate_websocket(token: str) -> Optional[User]:
    """Authenticate WebSocket connection using JWT token."""
    try:
        payload = verify_access_token(token)
        user_id = UUID(payload["sub"])

        async with async_session_factory() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if user and user.is_active:
                return user
    except Exception as e:
        logger.warning(f"WebSocket authentication failed: {e}")

    return None


async def verify_workspace_access(
    workspace_id: UUID,
    user_id: UUID,
) -> Optional[Workspace]:
    """Verify user has access to the workspace."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        workspace = result.scalar_one_or_none()

        if workspace is None:
            return None

        # Import here to avoid circular imports
        from app.api.deps import ProjectPermission
        from app.core.permissions import Role

        try:
            # Check project access
            perm = ProjectPermission(Role.VIEWER)
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if user:
                await perm(workspace.project_id, user, session)
                return workspace
        except Exception:
            return None

    return None


@router.websocket("/ws/workspace/{workspace_id}")
async def workspace_websocket(
    websocket: WebSocket,
    workspace_id: UUID,
    token: str = Query(...),
):
    """WebSocket endpoint for workspace collaboration.

    Connect with: ws://host/ws/workspace/{workspace_id}?token={jwt_token}

    Supported message types:
    - file.change: File modification events
    - cursor.update: Cursor position updates
    - message: Chat messages
    """
    # Authenticate user
    user = await authenticate_websocket(token)
    if user is None:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    # Verify workspace access
    workspace = await verify_workspace_access(workspace_id, user.id)
    if workspace is None:
        await websocket.close(code=4003, reason="Workspace access denied")
        return

    # Accept connection
    connection_id = await connection_manager.connect(
        websocket=websocket,
        workspace_id=str(workspace_id),
        user_id=str(user.id),
        username=user.username,
    )

    try:
        # Send join event
        await handle_user_join(
            connection_id=connection_id,
            workspace_id=str(workspace_id),
            user_id=str(user.id),
            username=user.username,
        )

        # Message loop
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                msg_type = message.get("type")
                payload = message.get("data", {})

                if msg_type == "file.change":
                    await handle_file_change(
                        connection_id=connection_id,
                        workspace_id=str(workspace_id),
                        user_id=str(user.id),
                        username=user.username,
                        payload=payload,
                    )
                elif msg_type == "cursor.update":
                    await handle_cursor_update(
                        connection_id=connection_id,
                        workspace_id=str(workspace_id),
                        user_id=str(user.id),
                        username=user.username,
                        payload=payload,
                    )
                elif msg_type == "message":
                    await handle_message(
                        connection_id=connection_id,
                        workspace_id=str(workspace_id),
                        user_id=str(user.id),
                        username=user.username,
                        payload=payload,
                    )
                elif msg_type == "ping":
                    await connection_manager.send_to_connection(
                        connection_id,
                        {"type": "pong", "data": {}},
                    )
                else:
                    await connection_manager.send_to_connection(
                        connection_id,
                        {"type": "error", "data": {"message": f"Unknown message type: {msg_type}"}},
                    )

            except json.JSONDecodeError:
                await connection_manager.send_to_connection(
                    connection_id,
                    {"type": "error", "data": {"message": "Invalid JSON"}},
                )

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Clean up connection
        conn_info = await connection_manager.disconnect(connection_id)

        if conn_info:
            await handle_user_leave(
                workspace_id=str(workspace_id),
                user_id=str(user.id),
                username=user.username,
                connected_at=conn_info.connected_at,
            )


@router.get("/ws/workspace/{workspace_id}/users")
async def get_workspace_users(workspace_id: UUID):
    """Get list of active users in a workspace."""
    users = connection_manager.get_workspace_users(str(workspace_id))
    return {
        "workspace_id": str(workspace_id),
        "users": users,
        "count": len(users),
    }
