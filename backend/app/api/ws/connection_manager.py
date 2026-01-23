"""WebSocket connection manager for real-time streaming.

Manages WebSocket connections per matter with:
- Connection tracking by user_id and matter_id
- Channel subscription management
- Graceful disconnect handling
- Efficient routing of messages to relevant clients
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import WebSocket

logger = structlog.get_logger(__name__)


@dataclass
class ConnectionInfo:
    """Metadata for an active WebSocket connection."""

    websocket: WebSocket
    user_id: str
    matter_id: str
    connected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    subscribed_channels: set[str] = field(default_factory=set)
    last_ping: datetime | None = None


class WebSocketManager:
    """Manages WebSocket connections and message routing.

    Thread-safe connection tracking with efficient routing by:
    - matter_id (for broadcasting to all users on a matter)
    - user_id (for user-specific notifications)
    - channel pattern (for topic-specific subscriptions)

    Example:
        >>> manager = get_ws_manager()
        >>> conn = await manager.connect(websocket, "user-123", "matter-456")
        >>> await manager.broadcast_to_matter("matter-456", {"type": "update"})
        >>> await manager.disconnect(conn)
    """

    def __init__(self) -> None:
        """Initialize the WebSocket manager."""
        # matter_id -> set of ConnectionInfo
        self._connections_by_matter: dict[str, set[ConnectionInfo]] = defaultdict(set)
        # user_id -> set of ConnectionInfo (user may have multiple tabs)
        self._connections_by_user: dict[str, set[ConnectionInfo]] = defaultdict(set)
        # All connections for iteration
        self._all_connections: set[ConnectionInfo] = set()
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        matter_id: str,
    ) -> ConnectionInfo:
        """Register a new WebSocket connection.

        Args:
            websocket: The WebSocket connection.
            user_id: Authenticated user ID.
            matter_id: Matter being subscribed to.

        Returns:
            ConnectionInfo for the new connection.
        """
        await websocket.accept()

        conn = ConnectionInfo(
            websocket=websocket,
            user_id=user_id,
            matter_id=matter_id,
        )

        async with self._lock:
            self._connections_by_matter[matter_id].add(conn)
            self._connections_by_user[user_id].add(conn)
            self._all_connections.add(conn)

        logger.info(
            "websocket_connected",
            user_id=user_id,
            matter_id=matter_id,
            total_connections=len(self._all_connections),
            matter_connections=len(self._connections_by_matter[matter_id]),
        )

        return conn

    async def register(
        self,
        websocket: WebSocket,
        user_id: str,
        matter_id: str,
    ) -> ConnectionInfo:
        """Register a WebSocket connection WITHOUT accepting it.

        Use this when you've already called websocket.accept() yourself.
        This just tracks the connection for routing messages.

        Args:
            websocket: The already-accepted WebSocket connection.
            user_id: Authenticated user ID.
            matter_id: Matter being subscribed to.

        Returns:
            ConnectionInfo for the connection.
        """
        conn = ConnectionInfo(
            websocket=websocket,
            user_id=user_id,
            matter_id=matter_id,
        )

        async with self._lock:
            self._connections_by_matter[matter_id].add(conn)
            self._connections_by_user[user_id].add(conn)
            self._all_connections.add(conn)

        logger.info(
            "websocket_registered",
            user_id=user_id,
            matter_id=matter_id,
            total_connections=len(self._all_connections),
            matter_connections=len(self._connections_by_matter[matter_id]),
        )

        return conn

    async def disconnect(self, conn: ConnectionInfo) -> None:
        """Remove a WebSocket connection.

        Args:
            conn: The connection to remove.
        """
        async with self._lock:
            self._connections_by_matter[conn.matter_id].discard(conn)
            self._connections_by_user[conn.user_id].discard(conn)
            self._all_connections.discard(conn)

            # Cleanup empty sets
            if not self._connections_by_matter[conn.matter_id]:
                del self._connections_by_matter[conn.matter_id]
            if not self._connections_by_user[conn.user_id]:
                del self._connections_by_user[conn.user_id]

        logger.info(
            "websocket_disconnected",
            user_id=conn.user_id,
            matter_id=conn.matter_id,
            total_connections=len(self._all_connections),
        )

    async def broadcast_to_matter(
        self,
        matter_id: str,
        message: dict[str, Any],
    ) -> int:
        """Broadcast a message to all connections for a matter.

        Args:
            matter_id: Target matter ID.
            message: Message to send (will be JSON serialized).

        Returns:
            Number of connections that received the message.
        """
        async with self._lock:
            connections = list(self._connections_by_matter.get(matter_id, set()))

        if not connections:
            return 0

        sent_count = 0
        failed_connections: list[ConnectionInfo] = []

        for conn in connections:
            try:
                await conn.websocket.send_json(message)
                sent_count += 1
            except Exception as e:
                logger.warning(
                    "websocket_send_failed",
                    user_id=conn.user_id,
                    matter_id=matter_id,
                    error=str(e),
                )
                failed_connections.append(conn)

        # Clean up failed connections
        for conn in failed_connections:
            await self.disconnect(conn)

        return sent_count

    async def send_to_user(
        self,
        user_id: str,
        message: dict[str, Any],
    ) -> int:
        """Send a message to all connections for a specific user.

        Args:
            user_id: Target user ID.
            message: Message to send.

        Returns:
            Number of connections that received the message.
        """
        async with self._lock:
            connections = list(self._connections_by_user.get(user_id, set()))

        sent_count = 0
        for conn in connections:
            try:
                await conn.websocket.send_json(message)
                sent_count += 1
            except Exception:
                pass  # Will be cleaned up by heartbeat or next send

        return sent_count

    def get_matter_connection_count(self, matter_id: str) -> int:
        """Get the number of active connections for a matter."""
        return len(self._connections_by_matter.get(matter_id, set()))

    def get_total_connections(self) -> int:
        """Get total active connection count."""
        return len(self._all_connections)

    def get_connected_matters(self) -> list[str]:
        """Get list of matters with active connections."""
        return list(self._connections_by_matter.keys())

    def has_matter_connections(self, matter_id: str) -> bool:
        """Check if a matter has any active connections."""
        return matter_id in self._connections_by_matter


# =============================================================================
# Singleton Factory
# =============================================================================

_manager: WebSocketManager | None = None


def get_ws_manager() -> WebSocketManager:
    """Get the singleton WebSocket manager instance.

    Returns:
        WebSocketManager singleton instance.
    """
    global _manager
    if _manager is None:
        _manager = WebSocketManager()
    return _manager
