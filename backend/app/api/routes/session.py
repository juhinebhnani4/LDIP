"""Session Memory API Routes.

Story 11.2: Q&A Conversation History
Provides endpoints for:
- GET /api/v1/session/{matter_id}/{user_id} - Get conversation history
- GET /api/v1/session/{matter_id}/{user_id}/archived - Get archived messages

CRITICAL: Requires authentication via get_current_user.
CRITICAL: User can only access their own session (user_id must match JWT).
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Request

from app.api.deps import get_current_user, validate_matter_access, MatterAccessContext
from app.core.rate_limit import READONLY_RATE_LIMIT, limiter
from app.models.auth import AuthenticatedUser
from app.services.memory.session import (
    SessionMemoryService,
    get_session_memory_service,
)

router = APIRouter(prefix="/v1/session", tags=["session"])
logger = structlog.get_logger(__name__)


def get_session_service() -> SessionMemoryService:
    """Get session memory service dependency."""
    return get_session_memory_service()


@router.get(
    "/{matter_id}/{user_id}",
    summary="Get Conversation History",
    description="""
    Get the current session context with conversation history.

    Returns the sliding window of messages (max 20) from the session memory.
    Session is scoped by matter_id + user_id.

    If no session exists, a new one is created automatically.
    If a previous session was archived, context is restored from archive.
    """,
    responses={
        200: {
            "description": "Session context retrieved",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "session_id": "uuid",
                            "matter_id": "uuid",
                            "user_id": "uuid",
                            "messages": [
                                {
                                    "role": "user",
                                    "content": "What is the timeline?",
                                    "timestamp": "2026-01-22T10:00:00Z",
                                }
                            ],
                            "entities": [],
                            "has_archived": False,
                        }
                    }
                }
            },
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Cannot access another user's session"},
        404: {"description": "Matter not found or no access"},
    },
)
@limiter.limit(READONLY_RATE_LIMIT)
async def get_conversation_history(
    request: Request,  # Required for rate limiter
    matter_id: str = Path(..., description="Matter UUID"),
    user_id: str = Path(..., description="User UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    access: MatterAccessContext = Depends(validate_matter_access()),
    session_service: SessionMemoryService = Depends(get_session_service),
) -> dict:
    """Get conversation history for a matter/user session.

    Args:
        matter_id: Matter UUID (from path).
        user_id: User UUID (from path).
        current_user: Authenticated user (from JWT).
        access: Matter access context (validates access).
        session_service: Session memory service instance.

    Returns:
        Session context with messages.

    Raises:
        HTTPException: 401 if not authenticated.
        HTTPException: 403 if user_id doesn't match current user.
        HTTPException: 404 if matter not found or no access.
    """
    # Security: User can only access their own session
    if user_id != current_user.id:
        logger.warning(
            "session_access_denied",
            matter_id=matter_id,
            requested_user_id=user_id,
            current_user_id=current_user.id,
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Cannot access another user's session",
                    "details": {},
                }
            },
        )

    try:
        logger.info(
            "get_conversation_history",
            matter_id=matter_id,
            user_id=user_id,
        )

        # Get or create session (auto-creates if not exists, restores from archive)
        context = await session_service.get_session(
            matter_id=matter_id,
            user_id=user_id,
            auto_create=True,
            extend_ttl=True,
            restore_from_archive=True,
        )

        # Transform to API response format
        messages = []
        for msg in context.messages:
            message_data = {
                "id": f"{context.session_id}_{msg.timestamp}",  # Generate stable ID
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp,
            }
            if msg.entity_refs:
                message_data["entity_refs"] = msg.entity_refs
            if msg.source_refs:
                message_data["source_refs"] = [
                    {
                        "document_id": ref.document_id,
                        "document_name": ref.document_name,
                        "page": ref.page,
                        "bbox_ids": ref.bbox_ids,
                    }
                    for ref in msg.source_refs
                ]
            messages.append(message_data)

        # Check if there's archived content
        has_archived = len(context.entities_mentioned) > 0 or context.query_count > len(
            context.messages
        )

        return {
            "data": {
                "session_id": context.session_id,
                "matter_id": context.matter_id,
                "user_id": context.user_id,
                "messages": messages,
                "entities": list(context.entities_mentioned.keys()),
                "has_archived": has_archived,
            }
        }

    except ValueError as e:
        logger.error(
            "session_validation_error",
            matter_id=matter_id,
            user_id=user_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(e),
                    "details": {},
                }
            },
        ) from e
    except RuntimeError as e:
        logger.error(
            "session_service_error",
            matter_id=matter_id,
            user_id=user_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "SERVICE_ERROR",
                    "message": "Failed to retrieve session",
                    "details": {},
                }
            },
        ) from e


@router.get(
    "/{matter_id}/{user_id}/archived",
    summary="Get Archived Messages",
    description="""
    Get archived messages from Matter Memory.

    Called when user wants to load older messages that have been
    archived from the session sliding window.
    """,
    responses={
        200: {
            "description": "Archived messages retrieved",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "messages": [
                                {
                                    "role": "user",
                                    "content": "Old question",
                                    "timestamp": "2026-01-20T10:00:00Z",
                                }
                            ],
                            "has_more": False,
                        }
                    }
                }
            },
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Cannot access another user's session"},
        404: {"description": "Matter not found or no access"},
    },
)
@limiter.limit(READONLY_RATE_LIMIT)
async def get_archived_messages(
    request: Request,  # Required for rate limiter
    matter_id: str = Path(..., description="Matter UUID"),
    user_id: str = Path(..., description="User UUID"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    access: MatterAccessContext = Depends(validate_matter_access()),
    session_service: SessionMemoryService = Depends(get_session_service),
) -> dict:
    """Get archived messages from Matter Memory.

    Args:
        matter_id: Matter UUID (from path).
        user_id: User UUID (from path).
        current_user: Authenticated user (from JWT).
        access: Matter access context (validates access).
        session_service: Session memory service instance.

    Returns:
        Archived messages with has_more flag.

    Raises:
        HTTPException: 401 if not authenticated.
        HTTPException: 403 if user_id doesn't match current user.
        HTTPException: 404 if matter not found or no access.
    """
    # Security: User can only access their own session
    if user_id != current_user.id:
        logger.warning(
            "archived_session_access_denied",
            matter_id=matter_id,
            requested_user_id=user_id,
            current_user_id=current_user.id,
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Cannot access another user's session",
                    "details": {},
                }
            },
        )

    try:
        logger.info(
            "get_archived_messages",
            matter_id=matter_id,
            user_id=user_id,
        )

        # Get matter memory to retrieve archived session
        from app.services.memory.matter import get_matter_memory_repository

        matter_memory = get_matter_memory_repository()
        archive = await matter_memory.get_latest_archived_session(matter_id, user_id)

        if archive is None:
            # No archived messages
            return {
                "data": {
                    "messages": [],
                    "has_more": False,
                }
            }

        # Transform archived messages to API format
        messages = []
        for msg in archive.last_messages:
            message_data = {
                "id": f"{archive.session_id}_{msg.timestamp}",
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp,
            }
            if msg.entity_refs:
                message_data["entity_refs"] = msg.entity_refs
            if msg.source_refs:
                message_data["source_refs"] = [
                    {
                        "document_id": ref.document_id,
                        "document_name": ref.document_name,
                        "page": ref.page,
                        "bbox_ids": ref.bbox_ids,
                    }
                    for ref in msg.source_refs
                ]
            messages.append(message_data)

        return {
            "data": {
                "messages": messages,
                "has_more": False,  # Currently we only store one archive per user/matter
            }
        }

    except Exception as e:
        logger.error(
            "get_archived_messages_error",
            matter_id=matter_id,
            user_id=user_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "SERVICE_ERROR",
                    "message": "Failed to retrieve archived messages",
                    "details": {},
                }
            },
        ) from e
