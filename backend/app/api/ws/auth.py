"""WebSocket authentication helpers.

Validates JWT tokens passed via query parameter for WebSocket connections.
Reuses the core security module's JWT decoding logic.
"""

import structlog
from fastapi import WebSocket
from jwt.exceptions import PyJWTError

from app.core.config import get_settings
from app.core.security import _decode_jwt
from app.models.auth import AuthenticatedUser
from app.services.matter_service import MatterService
from app.services.supabase.client import get_service_client

logger = structlog.get_logger(__name__)


# WebSocket close codes (4000-4999 are application-defined)
WS_CLOSE_AUTH_FAILED = 4001
WS_CLOSE_ACCESS_DENIED = 4003
WS_CLOSE_INVALID_MATTER = 4004
WS_CLOSE_SERVER_ERROR = 4500


class WebSocketAuthError(Exception):
    """Raised when WebSocket authentication fails."""

    def __init__(self, code: str, message: str, close_code: int = WS_CLOSE_AUTH_FAILED):
        self.code = code
        self.message = message
        self.close_code = close_code
        super().__init__(message)


async def authenticate_websocket(
    websocket: WebSocket,
    token: str | None,
) -> AuthenticatedUser:
    """Authenticate a WebSocket connection using JWT token.

    Args:
        websocket: The WebSocket connection.
        token: JWT token from query parameter.

    Returns:
        AuthenticatedUser if authentication succeeds.

    Raises:
        WebSocketAuthError: If authentication fails.
    """
    if not token:
        logger.debug("websocket_auth_failed", reason="missing_token")
        raise WebSocketAuthError(
            "MISSING_TOKEN",
            "Authentication token required",
            WS_CLOSE_AUTH_FAILED,
        )

    settings = get_settings()

    if not settings.supabase_url:
        logger.error("websocket_auth_failed", reason="missing_supabase_url")
        raise WebSocketAuthError(
            "SERVER_ERROR",
            "Authentication service misconfigured",
            WS_CLOSE_SERVER_ERROR,
        )

    try:
        payload = _decode_jwt(token, settings)

        user = AuthenticatedUser(
            id=payload["sub"],
            email=payload.get("email"),
            role=payload.get("role", "authenticated"),
            session_id=payload.get("session_id"),
        )

        # Bind user context for logging
        structlog.contextvars.bind_contextvars(user_id=user.id)

        logger.debug(
            "websocket_auth_success",
            user_id=user.id,
        )

        return user

    except PyJWTError as e:
        logger.warning(
            "websocket_auth_failed",
            reason="invalid_token",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise WebSocketAuthError(
            "INVALID_TOKEN",
            "Invalid or expired token",
            WS_CLOSE_AUTH_FAILED,
        ) from e

    except Exception as e:
        logger.warning(
            "websocket_auth_error",
            reason="unexpected_error",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise WebSocketAuthError(
            "AUTH_ERROR",
            "Authentication failed",
            WS_CLOSE_AUTH_FAILED,
        ) from e


async def validate_matter_access(
    user: AuthenticatedUser,
    matter_id: str,
) -> bool:
    """Validate user has access to a matter.

    Uses MatterService to check user's role on the matter.
    Any role (owner, editor, viewer) grants WebSocket access.

    Args:
        user: Authenticated user.
        matter_id: Matter ID to check access for.

    Returns:
        True if user has access, False otherwise.
    """
    client = get_service_client()
    if not client:
        logger.error("websocket_matter_access_check_failed", reason="no_db_client")
        return False

    try:
        matter_service = MatterService(client)
        role = matter_service.get_user_role(matter_id, user.id)

        if role is not None:
            logger.debug(
                "websocket_matter_access_granted",
                user_id=user.id,
                matter_id=matter_id,
                role=role.value,
            )
            return True
        else:
            logger.debug(
                "websocket_matter_access_denied",
                user_id=user.id,
                matter_id=matter_id,
                reason="no_role",
            )
            return False

    except Exception as e:
        logger.warning(
            "websocket_matter_access_check_failed",
            user_id=user.id,
            matter_id=matter_id,
            error=str(e),
        )
        return False


async def close_with_error(
    websocket: WebSocket,
    code: int,
    reason: str,
) -> None:
    """Close WebSocket with an error message.

    Args:
        websocket: The WebSocket to close.
        code: WebSocket close code (4000-4999 for application errors).
        reason: Human-readable close reason.
    """
    try:
        await websocket.close(code=code, reason=reason)
    except Exception:
        pass  # Connection may already be closed
