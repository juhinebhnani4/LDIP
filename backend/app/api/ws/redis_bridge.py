"""Redis Pub/Sub to WebSocket bridge.

Subscribes to Redis channels and forwards messages to WebSocket clients.
Handles channel patterns, connection lifecycle, and graceful shutdown.
"""

import asyncio
import json
from datetime import UTC, datetime

import redis.asyncio as aioredis
import structlog

from app.api.ws.connection_manager import get_ws_manager
from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class RedisBridge:
    """Bridges Redis Pub/Sub to WebSocket connections.

    Subscribes to channel patterns and routes messages to the
    appropriate WebSocket connections via the connection manager.

    Channel Patterns (matching pubsub_service.py):
    - matter:*:document:*:status - Document status updates
    - processing:* - Job progress
    - citations:* - Citation extraction progress
    - features:*:document:* - Feature availability
    - discoveries:* - Entity/timeline discovery updates

    Example:
        >>> bridge = get_redis_bridge()
        >>> await bridge.start()
        >>> # ... messages flow automatically ...
        >>> await bridge.stop()
    """

    # Channel patterns to subscribe (matching pubsub_service.py)
    CHANNEL_PATTERNS = [
        "matter:*:document:*:status",  # Document status updates
        "processing:*",  # Job progress
        "citations:*",  # Citation extraction
        "features:*:document:*",  # Feature availability
        "discoveries:*",  # Entity/timeline discovery updates
    ]

    def __init__(self) -> None:
        """Initialize the Redis bridge."""
        self._redis: aioredis.Redis | None = None
        self._pubsub: aioredis.client.PubSub | None = None
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the Redis bridge.

        Connects to Redis and begins listening for messages.
        """
        if self._running:
            logger.debug("redis_bridge_already_running")
            return

        settings = get_settings()
        try:
            self._redis = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            self._pubsub = self._redis.pubsub()

            # Subscribe to all channel patterns
            for pattern in self.CHANNEL_PATTERNS:
                await self._pubsub.psubscribe(pattern)
                logger.info("redis_pattern_subscribed", pattern=pattern)

            self._running = True
            self._task = asyncio.create_task(self._listen_loop())
            logger.info(
                "redis_bridge_started",
                patterns=self.CHANNEL_PATTERNS,
            )

        except Exception as e:
            logger.error("redis_bridge_start_failed", error=str(e))
            await self._cleanup()
            raise

    async def stop(self) -> None:
        """Stop the Redis bridge gracefully."""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        await self._cleanup()
        logger.info("redis_bridge_stopped")

    async def _cleanup(self) -> None:
        """Clean up Redis connections."""
        if self._pubsub:
            try:
                await self._pubsub.punsubscribe()
                await self._pubsub.close()
            except Exception:
                pass
            self._pubsub = None

        if self._redis:
            try:
                await self._redis.close()
            except Exception:
                pass
            self._redis = None

    async def _listen_loop(self) -> None:
        """Main loop listening for Redis messages."""
        manager = get_ws_manager()

        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )

                if message is None:
                    continue

                if message["type"] == "pmessage":
                    await self._handle_message(
                        pattern=message["pattern"],
                        channel=message["channel"],
                        data=message["data"],
                        manager=manager,
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("redis_bridge_error", error=str(e))
                await asyncio.sleep(1)  # Brief pause before retry

    async def _handle_message(
        self,
        pattern: str,
        channel: str,
        data: str,
        manager,
    ) -> None:
        """Route a Redis message to WebSocket clients.

        Args:
            pattern: The channel pattern that matched.
            channel: The actual channel name.
            data: The message data (JSON string).
            manager: WebSocket connection manager.
        """
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("invalid_json_message", channel=channel)
            return

        # Extract matter_id from the channel
        matter_id = self._extract_matter_id(channel)

        if not matter_id:
            logger.warning("no_matter_id_in_channel", channel=channel)
            return

        # Skip if no connections for this matter (optimization)
        if not manager.has_matter_connections(matter_id):
            return

        # Determine message type from channel pattern
        message_type = self._get_message_type(channel)

        # Wrap payload with metadata for frontend
        ws_message = {
            "type": message_type,
            "channel": channel,
            "data": payload,
            "timestamp": payload.get("timestamp") or datetime.now(UTC).isoformat(),
        }

        # Broadcast to all clients subscribed to this matter
        sent_count = await manager.broadcast_to_matter(matter_id, ws_message)

        if sent_count > 0:
            logger.debug(
                "redis_message_forwarded",
                channel=channel,
                message_type=message_type,
                matter_id=matter_id,
                recipients=sent_count,
            )

    def _extract_matter_id(self, channel: str) -> str | None:
        """Extract matter_id from a channel name.

        Channel patterns:
        - matter:{matter_id}:document:{document_id}:status
        - processing:{matter_id}
        - citations:{matter_id}
        - features:{matter_id}:document:{document_id}
        - discoveries:{matter_id}
        """
        parts = channel.split(":")

        if channel.startswith("matter:") and len(parts) >= 2:
            return parts[1]
        elif channel.startswith("processing:") and len(parts) >= 2:
            return parts[1]
        elif channel.startswith("citations:") and len(parts) >= 2:
            return parts[1]
        elif channel.startswith("features:") and len(parts) >= 2:
            return parts[1]
        elif channel.startswith("discoveries:") and len(parts) >= 2:
            return parts[1]

        return None

    def _get_message_type(self, channel: str) -> str:
        """Determine the message type from the channel name."""
        if "document" in channel and "status" in channel:
            return "document_status"
        elif channel.startswith("processing:"):
            return "job_progress"
        elif channel.startswith("citations:"):
            return "citation_update"
        elif channel.startswith("features:"):
            return "feature_ready"
        elif channel.startswith("discoveries:"):
            return "discovery_update"
        return "unknown"

    @property
    def is_running(self) -> bool:
        """Check if the bridge is currently running."""
        return self._running


# =============================================================================
# Singleton Factory
# =============================================================================

_bridge: RedisBridge | None = None


def get_redis_bridge() -> RedisBridge:
    """Get the singleton Redis bridge instance.

    Returns:
        RedisBridge singleton instance.
    """
    global _bridge
    if _bridge is None:
        _bridge = RedisBridge()
    return _bridge
