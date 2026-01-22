"""Chat Streaming API Route.

Story 11.3: Streaming Response with Engine Trace
Task 1: Create backend SSE streaming endpoint (AC: #1)

Implements:
- POST /api/chat/{matter_id}/stream - SSE streaming chat endpoint

CRITICAL: Requires authentication via get_current_user.
CRITICAL: Requires matter access via validate_matter_access.
CRITICAL: Response is text/event-stream for SSE protocol.
"""

import json
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sse_starlette.sse import EventSourceResponse

from app.api.deps import (
    MatterAccessContext,
    get_current_user,
    validate_matter_access,
)
from app.core.rate_limit import CRITICAL_RATE_LIMIT, limiter
from app.engines.orchestrator.streaming import (
    StreamingOrchestrator,
    get_streaming_orchestrator,
)
from app.models.auth import AuthenticatedUser
from app.models.chat import ChatStreamRequest, StreamEventType

logger = structlog.get_logger(__name__)

# =============================================================================
# Router Setup
# =============================================================================

router = APIRouter(prefix="/chat", tags=["chat"])


# =============================================================================
# Dependencies
# =============================================================================


def get_streaming_orchestrator_dep() -> StreamingOrchestrator:
    """Get streaming orchestrator dependency.

    Returns:
        StreamingOrchestrator instance.
    """
    return get_streaming_orchestrator()


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/{matter_id}/stream")
@limiter.limit(CRITICAL_RATE_LIMIT)
async def stream_chat(
    request: Request,  # Required for rate limiter
    matter_id: str,
    body: ChatStreamRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    access: MatterAccessContext = Depends(validate_matter_access()),
    streaming_orchestrator: StreamingOrchestrator = Depends(
        get_streaming_orchestrator_dep
    ),
) -> EventSourceResponse:
    """Stream AI response with engine trace events.

    Story 11.3: Task 1.1-1.7 - SSE streaming endpoint.

    This endpoint streams Server-Sent Events (SSE) for real-time
    response generation with typing indicators and engine traces.

    Event types:
    - typing: Processing started
    - engine_complete: Engine finished with timing
    - token: Streamed response token
    - complete: Full response with trace summary
    - error: Error occurred

    Args:
        matter_id: Matter UUID (from path).
        request: ChatStreamRequest with query and optional session_id.
        current_user: Authenticated user (from JWT).
        access: Matter access context (validates access).
        streaming_orchestrator: StreamingOrchestrator instance.

    Returns:
        EventSourceResponse streaming SSE events.

    Raises:
        HTTPException: 401 if not authenticated.
        HTTPException: 404 if matter not found or no access.
        HTTPException: 400 if request validation fails.
    """
    logger.info(
        "stream_chat_request",
        matter_id=matter_id,
        user_id=current_user.id,
        query_length=len(body.query),
    )

    async def event_generator() -> AsyncGenerator[dict[str, Any], None]:
        """Generate SSE events from streaming orchestrator."""
        try:
            async for event in streaming_orchestrator.process_streaming(
                matter_id=matter_id,
                user_id=current_user.id,
                query=body.query,
                session_id=body.session_id,
            ):
                # DEBUG: Log complete event sources to trace document_name
                if event.type.value == "complete":
                    sources = event.data.get("sources", [])
                    logger.debug(
                        "sse_complete_event_sources",
                        sources_count=len(sources),
                        sample_sources=[
                            {
                                "document_id": s.get("document_id", "")[:8],
                                "document_name": s.get("document_name"),
                                "has_doc_name": s.get("document_name") is not None,
                            }
                            for s in sources[:3]
                        ],
                    )
                yield {
                    "event": event.type.value,
                    "data": json.dumps(event.data),
                }

        except Exception as e:
            logger.error(
                "stream_chat_error",
                error=str(e),
                error_type=type(e).__name__,
                matter_id=matter_id,
                user_id=current_user.id,
            )
            yield {
                "event": StreamEventType.ERROR.value,
                "data": json.dumps({
                    "error": "An error occurred during streaming",
                    "code": "STREAM_ERROR",
                }),
            }

    return EventSourceResponse(event_generator())


@router.post("/{matter_id}/message")
@limiter.limit(CRITICAL_RATE_LIMIT)
async def send_message(
    request: Request,  # Required for rate limiter
    matter_id: str,
    body: ChatStreamRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    access: MatterAccessContext = Depends(validate_matter_access()),
    streaming_orchestrator: StreamingOrchestrator = Depends(
        get_streaming_orchestrator_dep
    ),
) -> dict[str, Any]:
    """Non-streaming chat endpoint for simpler clients.

    Story 11.3: Alternative non-streaming endpoint.

    This endpoint processes the query synchronously and returns
    the complete response. Useful for testing or clients that
    don't support SSE.

    Args:
        matter_id: Matter UUID (from path).
        request: ChatStreamRequest with query.
        current_user: Authenticated user.
        access: Matter access context.
        streaming_orchestrator: StreamingOrchestrator instance.

    Returns:
        Complete response with engine traces.

    Raises:
        HTTPException: 500 if processing fails.
    """
    logger.info(
        "send_message_request",
        matter_id=matter_id,
        user_id=current_user.id,
        query_length=len(body.query),
    )

    try:
        # Collect all events to build final response
        response_data: dict[str, Any] = {}

        async for event in streaming_orchestrator.process_streaming(
            matter_id=matter_id,
            user_id=current_user.id,
            query=body.query,
            session_id=body.session_id,
        ):
            if event.type == StreamEventType.COMPLETE:
                response_data = event.data
            elif event.type == StreamEventType.ERROR:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "error": {
                            "code": event.data.get("code", "PROCESSING_ERROR"),
                            "message": event.data.get("error", "Processing failed"),
                            "details": {},
                        }
                    },
                )

        return {"data": response_data}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "send_message_error",
            error=str(e),
            matter_id=matter_id,
            user_id=current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "PROCESSING_ERROR",
                    "message": "Failed to process message",
                    "details": {},
                }
            },
        ) from e
