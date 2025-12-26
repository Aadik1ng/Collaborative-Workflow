"""Redis Pub/Sub for cross-instance WebSocket communication."""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional

from app.db.redis import get_redis

logger = logging.getLogger(__name__)


class RedisPubSub:
    """Redis Pub/Sub manager for cross-instance communication."""

    def __init__(self):
        self._subscriptions: Dict[str, asyncio.Task] = {}
        self._callbacks: Dict[str, Callable] = {}

    async def publish(self, channel: str, message: Dict[str, Any]) -> None:
        """Publish a message to a Redis channel."""
        try:
            redis = get_redis()
            await redis.publish(channel, json.dumps(message))
            logger.debug(f"Published message to channel {channel}")
        except Exception as e:
            logger.error(f"Failed to publish to channel {channel}: {e}")

    async def subscribe(
        self,
        channel: str,
        callback: Callable[[Dict[str, Any]], None],
    ) -> None:
        """Subscribe to a Redis channel with a callback."""
        if channel in self._subscriptions:
            logger.warning(f"Already subscribed to channel {channel}")
            return

        self._callbacks[channel] = callback

        async def listener():
            try:
                redis = get_redis()
                pubsub = redis.pubsub()
                await pubsub.subscribe(channel)

                async for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            data = json.loads(message["data"])
                            await callback(data)
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in message: {message['data']}")
                        except Exception as e:
                            logger.error(f"Error in callback for channel {channel}: {e}")
            except asyncio.CancelledError:
                logger.info(f"Subscription to channel {channel} cancelled")
            except Exception as e:
                logger.error(f"Error in subscription to channel {channel}: {e}")

        self._subscriptions[channel] = asyncio.create_task(listener())
        logger.info(f"Subscribed to channel {channel}")

    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a Redis channel."""
        if channel not in self._subscriptions:
            return

        task = self._subscriptions.pop(channel)
        task.cancel()
        self._callbacks.pop(channel, None)

        try:
            await task
        except asyncio.CancelledError:
            pass

        logger.info(f"Unsubscribed from channel {channel}")

    async def unsubscribe_all(self) -> None:
        """Unsubscribe from all channels."""
        for channel in list(self._subscriptions.keys()):
            await self.unsubscribe(channel)

    @staticmethod
    def workspace_channel(workspace_id: str) -> str:
        """Get the channel name for a workspace."""
        return f"workspace:{workspace_id}"

    @staticmethod
    def user_channel(user_id: str) -> str:
        """Get the channel name for a user."""
        return f"user:{user_id}"

    @staticmethod
    def broadcast_channel() -> str:
        """Get the global broadcast channel name."""
        return "broadcast:all"


# Global pubsub instance
redis_pubsub = RedisPubSub()


async def publish_workspace_event(
    workspace_id: str,
    event_type: str,
    data: Dict[str, Any],
    sender_id: Optional[str] = None,
) -> None:
    """Publish an event to a workspace channel."""
    message = {
        "type": event_type,
        "workspace_id": workspace_id,
        "data": data,
        "sender_id": sender_id,
    }
    await redis_pubsub.publish(
        RedisPubSub.workspace_channel(workspace_id),
        message,
    )


async def publish_user_event(
    user_id: str,
    event_type: str,
    data: Dict[str, Any],
) -> None:
    """Publish an event to a user channel."""
    message = {
        "type": event_type,
        "data": data,
    }
    await redis_pubsub.publish(
        RedisPubSub.user_channel(user_id),
        message,
    )
