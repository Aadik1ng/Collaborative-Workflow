"""WebSocket connection manager."""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""

    websocket: WebSocket
    user_id: str
    username: str
    workspace_id: str
    connected_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class ConnectionManager:
    """Manages WebSocket connections for real-time collaboration."""

    def __init__(self):
        # workspace_id -> set of connection_ids
        self._workspace_connections: dict[str, set[str]] = {}
        # user_id -> set of connection_ids
        self._user_connections: dict[str, set[str]] = {}
        # connection_id -> ConnectionInfo
        self._connections: dict[str, ConnectionInfo] = {}

    def _generate_connection_id(self, user_id: str, workspace_id: str) -> str:
        """Generate unique connection ID."""
        return f"{workspace_id}:{user_id}:{datetime.now(UTC).timestamp()}"

    async def connect(
        self,
        websocket: WebSocket,
        workspace_id: str,
        user_id: str,
        username: str,
    ) -> str:
        """Accept a new WebSocket connection and return connection ID."""
        await websocket.accept()

        connection_id = self._generate_connection_id(user_id, workspace_id)

        # Store connection info
        self._connections[connection_id] = ConnectionInfo(
            websocket=websocket,
            user_id=user_id,
            username=username,
            workspace_id=workspace_id,
        )

        # Add to workspace connections
        if workspace_id not in self._workspace_connections:
            self._workspace_connections[workspace_id] = set()
        self._workspace_connections[workspace_id].add(connection_id)

        # Add to user connections
        if user_id not in self._user_connections:
            self._user_connections[user_id] = set()
        self._user_connections[user_id].add(connection_id)

        logger.info(f"User {username} connected to workspace {workspace_id}")

        return connection_id

    async def disconnect(self, connection_id: str) -> ConnectionInfo | None:
        """Remove a WebSocket connection."""
        if connection_id not in self._connections:
            return None

        conn_info = self._connections.pop(connection_id)

        # Remove from workspace connections
        workspace_id = conn_info.workspace_id
        if workspace_id in self._workspace_connections:
            self._workspace_connections[workspace_id].discard(connection_id)
            if not self._workspace_connections[workspace_id]:
                del self._workspace_connections[workspace_id]

        # Remove from user connections
        user_id = conn_info.user_id
        if user_id in self._user_connections:
            self._user_connections[user_id].discard(connection_id)
            if not self._user_connections[user_id]:
                del self._user_connections[user_id]

        logger.info(f"User {conn_info.username} disconnected from workspace {workspace_id}")

        return conn_info

    async def broadcast_to_workspace(
        self,
        workspace_id: str,
        message: dict[str, Any],
        exclude_connection: str | None = None,
    ) -> None:
        """Broadcast a message to all connections in a workspace."""
        if workspace_id not in self._workspace_connections:
            return

        message_json = json.dumps(message)
        disconnected = []

        for connection_id in self._workspace_connections[workspace_id]:
            if connection_id == exclude_connection:
                continue

            conn_info = self._connections.get(connection_id)
            if conn_info is None:
                disconnected.append(connection_id)
                continue

            try:
                await conn_info.websocket.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send message to {connection_id}: {e}")
                disconnected.append(connection_id)

        # Clean up disconnected connections
        for connection_id in disconnected:
            await self.disconnect(connection_id)

    async def send_to_user(
        self,
        user_id: str,
        message: dict[str, Any],
    ) -> None:
        """Send a message to all connections of a specific user."""
        if user_id not in self._user_connections:
            return

        message_json = json.dumps(message)
        disconnected = []

        for connection_id in self._user_connections[user_id]:
            conn_info = self._connections.get(connection_id)
            if conn_info is None:
                disconnected.append(connection_id)
                continue

            try:
                await conn_info.websocket.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send message to {connection_id}: {e}")
                disconnected.append(connection_id)

        # Clean up disconnected connections
        for connection_id in disconnected:
            await self.disconnect(connection_id)

    async def send_to_connection(
        self,
        connection_id: str,
        message: dict[str, Any],
    ) -> bool:
        """Send a message to a specific connection."""
        conn_info = self._connections.get(connection_id)
        if conn_info is None:
            return False

        try:
            await conn_info.websocket.send_text(json.dumps(message))
            return True
        except Exception as e:
            logger.warning(f"Failed to send message to {connection_id}: {e}")
            await self.disconnect(connection_id)
            return False

    def get_workspace_users(self, workspace_id: str) -> list[dict[str, Any]]:
        """Get list of users currently in a workspace."""
        if workspace_id not in self._workspace_connections:
            return []

        users = []
        seen_users: set[str] = set()

        for connection_id in self._workspace_connections[workspace_id]:
            conn_info = self._connections.get(connection_id)
            if conn_info and conn_info.user_id not in seen_users:
                seen_users.add(conn_info.user_id)
                users.append(
                    {
                        "user_id": conn_info.user_id,
                        "username": conn_info.username,
                        "connected_at": conn_info.connected_at.isoformat(),
                    }
                )

        return users

    def get_workspace_connection_count(self, workspace_id: str) -> int:
        """Get number of active connections in a workspace."""
        return len(self._workspace_connections.get(workspace_id, set()))

    def get_connection_info(self, connection_id: str) -> ConnectionInfo | None:
        """Get connection info by ID."""
        return self._connections.get(connection_id)


# Global connection manager instance
connection_manager = ConnectionManager()
