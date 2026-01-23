"""WebSocket API routes for real-time streaming.

Provides WebSocket endpoints for:
- Matter-level subscriptions (all events for a matter)
- Health checks and connection statistics
"""

import asyncio
import json
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from app.api.ws.auth import (
    WS_CLOSE_ACCESS_DENIED,
    WS_CLOSE_AUTH_FAILED,
    WebSocketAuthError,
    authenticate_websocket,
    close_with_error,
    validate_matter_access,
)
from app.api.ws.connection_manager import WebSocketManager, get_ws_manager
from app.core.config import get_settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/{matter_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    matter_id: str,
    token: Annotated[str | None, Query()] = None,
) -> None:
    """WebSocket endpoint for matter-level real-time updates.

    Streams all events for a matter:
    - Document status changes
    - Job progress updates
    - Citation extraction progress
    - Feature availability

    Query Parameters:
        token: JWT authentication token (required)

    Message Format (outbound from server):
        {
            "type": "document_status" | "job_progress" | "citation_update" | "feature_ready",
            "channel": "matter:xxx:document:yyy:status",
            "data": { ... event payload ... },
            "timestamp": "2024-01-15T10:30:00Z"
        }

    Message Format (inbound from client):
        { "type": "ping" }  -> Server responds with { "type": "pong" }

    Close Codes:
        4001: Authentication failed (invalid/expired token)
        4003: Access denied (user not member of matter)
    """
    settings = get_settings()
    manager = get_ws_manager()

    # Authenticate
    try:
        user = await authenticate_websocket(websocket, token)
    except WebSocketAuthError as e:
        # Must accept before closing with custom code
        await websocket.accept()
        await close_with_error(websocket, e.close_code, e.message)
        return

    # Validate matter access
    has_access = await validate_matter_access(user, matter_id)
    if not has_access:
        # Must accept before closing with custom code
        await websocket.accept()
        await close_with_error(websocket, WS_CLOSE_ACCESS_DENIED, "Access denied to matter")
        return

    # Bind logging context
    structlog.contextvars.bind_contextvars(matter_id=matter_id, user_id=user.id)

    # Accept the WebSocket connection directly (not through manager)
    await websocket.accept()

    # Register with manager for message routing
    try:
        conn = await manager.register(websocket, user.id, matter_id)
    except Exception as reg_err:
        logger.error(
            "websocket_register_failed",
            user_id=user.id,
            matter_id=matter_id,
            error=str(reg_err),
            exc_info=True,
        )
        conn = None

    # Send connection confirmation
    try:
        await websocket.send_json({
            "type": "connected",
            "matter_id": matter_id,
            "user_id": user.id,
        })
        logger.info(
            "websocket_connected_message_sent",
            user_id=user.id,
            matter_id=matter_id,
        )
    except Exception as send_err:
        logger.error(
            "websocket_connected_message_failed",
            user_id=user.id,
            matter_id=matter_id,
            error=str(send_err),
            exc_info=True,
        )
        await manager.disconnect(conn)
        return

    logger.info(
        "websocket_loop_starting",
        user_id=user.id,
        matter_id=matter_id,
    )

    try:
        # Message receive loop using low-level receive() for better control
        while True:
            try:
                # Use receive() which returns a dict with 'type' key
                # Types: 'websocket.receive' (has 'text' or 'bytes'), 'websocket.disconnect'
                message = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=float(settings.websocket_ping_interval),
                )

                msg_type = message.get("type", "")

                if msg_type == "websocket.disconnect":
                    logger.info(
                        "websocket_client_initiated_disconnect",
                        user_id=user.id,
                        matter_id=matter_id,
                        code=message.get("code", 1000),
                    )
                    break

                if msg_type == "websocket.receive":
                    # Get text data if present
                    text_data = message.get("text")
                    if text_data:
                        try:
                            msg = json.loads(text_data)
                            if msg.get("type") == "ping":
                                await websocket.send_json({"type": "pong"})
                        except json.JSONDecodeError:
                            pass  # Ignore invalid JSON

            except asyncio.TimeoutError:
                # No message received - send server ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    logger.debug("websocket_ping_failed", user_id=user.id, matter_id=matter_id)
                    break  # Connection lost

    except WebSocketDisconnect as wsd:
        logger.info(
            "websocket_client_disconnected",
            user_id=user.id,
            matter_id=matter_id,
            code=getattr(wsd, "code", 1000),
        )
    except Exception as e:
        logger.error(
            "websocket_error",
            user_id=user.id,
            matter_id=matter_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
    finally:
        logger.info(
            "websocket_cleanup",
            user_id=user.id,
            matter_id=matter_id,
        )
        if conn:
            await manager.disconnect(conn)


@router.get("/stats")
async def websocket_stats(
    manager: WebSocketManager = Depends(get_ws_manager),
) -> dict:
    """Get WebSocket connection statistics.

    Returns:
        Dictionary with connection counts and active matters.
    """
    connected_matters = manager.get_connected_matters()
    return {
        "total_connections": manager.get_total_connections(),
        "active_matter_count": len(connected_matters),
        "matter_connections": {
            matter_id: manager.get_matter_connection_count(matter_id)
            for matter_id in connected_matters
        },
    }
