"""WebSocket API package for real-time streaming.

Provides WebSocket infrastructure for real-time push notifications,
bridging Redis PubSub events to frontend clients.

Components:
- connection_manager: Track and route WebSocket connections
- redis_bridge: Subscribe to Redis and forward to WebSocket
- auth: JWT authentication for WebSocket connections
"""

from app.api.ws.connection_manager import (
    ConnectionInfo,
    WebSocketManager,
    get_ws_manager,
)
from app.api.ws.redis_bridge import RedisBridge, get_redis_bridge

__all__ = [
    "ConnectionInfo",
    "WebSocketManager",
    "get_ws_manager",
    "RedisBridge",
    "get_redis_bridge",
]
