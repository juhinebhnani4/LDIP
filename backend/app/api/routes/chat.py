"""Chat Streaming API Route.

Story 11.3: Streaming Response with Engine Trace
Task 1: Create backend SSE streaming endpoint (AC: #1)

Story 6.2: Add SSE Error Rate Logging endpoint

Implements:
- POST /api/chat/{matter_id}/stream - SSE streaming chat endpoint
- POST /api/chat/report-sse-error - SSE error reporting endpoint

CRITICAL: Requires authentication via get_current_user.
CRITICAL: Requires matter access via validate_matter_access.
CRITICAL: Response is text/event-stream for SSE protocol.
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.api.deps import (
    MatterAccessContext,
    get_current_user,
    validate_matter_access,
)
from app.core.rate_limit import CRITICAL_RATE_LIMIT, STANDARD_RATE_LIMIT, limiter
from app.core.reliability_logging import log_sse_parse_error, log_sse_stream_status
from app.engines.orchestrator.streaming import (
    StreamingOrchestrator,
    get_streaming_orchestrator,
)
from app.models.auth import AuthenticatedUser
from app.models.chat import ChatStreamRequest, StreamEventType
from app.services.llm_error_handler import classify_error
from app.services.memory.query_cache_service import get_query_cache_service
from app.services.summary_service import get_summary_service
from app.services.timeline_cache import get_timeline_cache_service

logger = structlog.get_logger(__name__)

# Document statuses that indicate active processing (not yet queryable).
# Full pipeline: pending → processing → ocr_complete → chunking → embedding → searchable → completed
# Terminal statuses (completed, failed, *_failed) are NOT included.
# "searchable" is NOT included — it means chunks + embeddings exist, Q&A works.
_PROCESSING_STATUSES = (
    "pending",
    "processing",
    "ocr_complete",
    "pending_review",
    "chunking",
    "embedding",
)


@dataclass(frozen=True)
class ProcessingStatus:
    """Snapshot of a matter's document processing and embedding state."""

    processing_count: int  # docs still in pipeline
    total_count: int  # all docs in matter
    total_chunks: int  # chunks created so far
    embedded_chunks: int  # chunks with embeddings

    @property
    def all_done(self) -> bool:
        return self.processing_count == 0

    @property
    def has_usable_chunks(self) -> bool:
        return self.embedded_chunks > 0

    @property
    def embedding_pct(self) -> float:
        if self.total_chunks == 0:
            return 0.0
        return self.embedded_chunks / self.total_chunks * 100


async def _check_processing_status(matter_id: str) -> ProcessingStatus:
    """Check how many documents are still processing and embedding state.

    Single convergence point for the processing guard — called by both
    stream_chat() and send_message(). Two lightweight COUNT queries.
    """
    from app.services.supabase.client import get_supabase_client

    try:
        supabase = get_supabase_client()

        def _query() -> ProcessingStatus:
            # Query 1: document processing status
            all_docs = (
                supabase.table("documents")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .execute()
            )
            processing_docs = (
                supabase.table("documents")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .in_("status", list(_PROCESSING_STATUSES))
                .execute()
            )

            # Query 2: chunk/embedding counts
            total_chunks_resp = (
                supabase.table("chunks")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .execute()
            )
            embedded_resp = (
                supabase.table("chunks")
                .select("id", count="exact")
                .eq("matter_id", matter_id)
                .not_.is_("embedding", "null")
                .execute()
            )

            return ProcessingStatus(
                processing_count=processing_docs.count or 0,
                total_count=all_docs.count or 0,
                total_chunks=total_chunks_resp.count or 0,
                embedded_chunks=embedded_resp.count or 0,
            )

        return await asyncio.to_thread(_query)

    except Exception as e:
        logger.warning(
            "processing_status_check_failed", matter_id=matter_id, error=str(e)
        )
        # On failure, assume ready — don't block queries due to a check failure
        return ProcessingStatus(
            processing_count=0, total_count=0, total_chunks=0, embedded_chunks=0
        )


# =============================================================================
# Router Setup
# =============================================================================

router = APIRouter(prefix="/chat", tags=["chat"])


# =============================================================================
# Request Models for Story 6.2
# =============================================================================


class SSEErrorReportRequest(BaseModel):
    """Request model for SSE error reporting.

    Story 6.2: SSE error reporting from frontend.
    """

    session_id: str = Field(..., max_length=100, description="SSE session ID")
    matter_id: str | None = Field(
        None, max_length=100, description="Matter ID from stream URL"
    )
    error_type: str = Field(
        ..., max_length=100, description="Type of error (sse_json_parse_failed, etc.)"
    )
    error_message: str = Field(..., max_length=2000, description="Error message")
    raw_chunk: str | None = Field(
        None, max_length=2000, description="Raw chunk content (truncated)"
    )
    timestamp: str = Field(..., max_length=50, description="ISO timestamp of error")


class SSEStreamStatusRequest(BaseModel):
    """Request model for SSE stream status reporting.

    Story 6.2: Track stream completion vs interruption.
    """

    session_id: str = Field(..., description="SSE session ID")
    matter_id: str | None = Field(None, description="Matter ID from stream URL")
    status: str = Field(..., description="complete or interrupted")
    parse_error_count: int = Field(0, description="Parse errors during stream")
    total_chunks: int = Field(0, description="Total chunks received")
    duration_ms: int | None = Field(None, description="Stream duration in ms")


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
    from app.core.correlation import bind_cost_user_id

    bind_cost_user_id(current_user.id)

    logger.info(
        "stream_chat_request",
        matter_id=matter_id,
        user_id=current_user.id,
        query_length=len(body.query),
    )

    # --- Processing guard: check before spending LLM resources ---
    proc_status = await _check_processing_status(matter_id)

    async def event_generator() -> AsyncGenerator[dict[str, Any], None]:
        """Generate SSE events from streaming orchestrator."""
        # Gate 1: All docs processing, zero usable chunks → block entirely
        if not proc_status.all_done and not proc_status.has_usable_chunks:
            if proc_status.processing_count == proc_status.total_count:
                msg = (
                    "Your documents are still being processed. "
                    "Q&A will be available once processing completes."
                )
            else:
                msg = (
                    f"{proc_status.processing_count} of {proc_status.total_count} documents "
                    "are still being processed and no searchable content is available yet. "
                    "Please wait for processing to complete."
                )
            logger.info(
                "chat_blocked_documents_processing",
                matter_id=matter_id,
                processing_count=proc_status.processing_count,
                total_count=proc_status.total_count,
                total_chunks=proc_status.total_chunks,
                embedded_chunks=proc_status.embedded_chunks,
            )
            yield {
                "event": StreamEventType.ERROR.value,
                "data": json.dumps(
                    {
                        "error": msg,
                        "code": "DOCUMENTS_PROCESSING",
                        "retry_suggested": True,
                        "retry_after_seconds": 30,
                    }
                ),
            }
            return

        # Gate 2: Some docs processing but usable chunks exist → warn via search_notice
        # (The warning is injected into the streaming orchestrator's result via
        # the existing search_notice/searchNotice pipeline. We log it here for
        # observability; the actual notice is set in _extract_search_mode when
        # hybrid_search detects incomplete embeddings.)
        if not proc_status.all_done:
            logger.info(
                "chat_proceeding_with_processing_warning",
                matter_id=matter_id,
                processing_count=proc_status.processing_count,
                total_count=proc_status.total_count,
                embedding_pct=round(proc_status.embedding_pct, 1),
            )

        try:
            async for event in streaming_orchestrator.process_streaming(
                matter_id=matter_id,
                user_id=current_user.id,
                query=body.query,
                session_id=body.session_id,
                provider_context={
                    "embedding_provider": body.embedding_provider,
                    "rerank_provider": body.rerank_provider,
                    "search_filters": body.search_filters,
                },
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
            # Story 5.5: Classify error for user-friendly message
            llm_error = classify_error(e, provider="gemini")
            logger.error(
                "stream_chat_error",
                error=str(e),
                error_type=type(e).__name__,
                error_code=llm_error.code.value,
                matter_id=matter_id,
                user_id=current_user.id,
            )
            yield {
                "event": StreamEventType.ERROR.value,
                "data": json.dumps(
                    {
                        "error": llm_error.message,
                        "code": llm_error.code.value,
                        "retry_suggested": llm_error.retry_suggested,
                        "retry_after_seconds": llm_error.retry_after_seconds,
                    }
                ),
            }

    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache, no-store, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
        ping=15,
    )


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
    from app.core.correlation import bind_cost_user_id

    bind_cost_user_id(current_user.id)

    logger.info(
        "send_message_request",
        matter_id=matter_id,
        user_id=current_user.id,
        query_length=len(body.query),
    )

    # --- Processing guard: same check as stream_chat ---
    proc_status = await _check_processing_status(matter_id)
    if not proc_status.all_done and not proc_status.has_usable_chunks:
        if proc_status.processing_count == proc_status.total_count:
            msg = (
                "Your documents are still being processed. "
                "Q&A will be available once processing completes."
            )
        else:
            msg = (
                f"{proc_status.processing_count} of {proc_status.total_count} documents "
                "are still being processed and no searchable content is available yet. "
                "Please wait for processing to complete."
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "DOCUMENTS_PROCESSING",
                    "message": msg,
                    "retry_suggested": True,
                    "retry_after_seconds": 30,
                }
            },
        )

    try:
        # Collect all events to build final response
        response_data: dict[str, Any] = {}

        async for event in streaming_orchestrator.process_streaming(
            matter_id=matter_id,
            user_id=current_user.id,
            query=body.query,
            session_id=body.session_id,
            provider_context={
                "embedding_provider": body.embedding_provider,
                "rerank_provider": body.rerank_provider,
                "search_filters": body.search_filters,
            },
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
        # Story 5.5: Classify error for user-friendly message
        llm_error = classify_error(e, provider="gemini")
        logger.error(
            "send_message_error",
            error=str(e),
            error_code=llm_error.code.value,
            matter_id=matter_id,
            user_id=current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": llm_error.code.value,
                    "message": llm_error.message,
                    "retry_suggested": llm_error.retry_suggested,
                    "retry_after_seconds": llm_error.retry_after_seconds,
                }
            },
        ) from e


# =============================================================================
# Story 6.2: SSE Error Reporting Endpoints
# =============================================================================


@router.post("/report-sse-error")
@limiter.limit(STANDARD_RATE_LIMIT)
async def report_sse_error(
    request: Request,  # Required for rate limiter
    body: SSEErrorReportRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, str]:
    """Report SSE parse error from frontend.

    Story 6.2: SSE Error Rate Logging
    NFR12: SSE parse errors trackable per user session.

    This endpoint receives error reports from the frontend when SSE
    JSON parsing fails, enabling backend logging and monitoring.

    Args:
        body: SSE error report details.
        current_user: Authenticated user.

    Returns:
        Acknowledgement message.
    """
    log_sse_parse_error(
        user_id=current_user.id,
        matter_id=body.matter_id,
        session_id=body.session_id,
        error_type=body.error_type,
        error_message=body.error_message,
        raw_chunk=body.raw_chunk,
    )

    return {"status": "logged"}


@router.post("/report-sse-status")
@limiter.limit(STANDARD_RATE_LIMIT)
async def report_sse_status(
    request: Request,  # Required for rate limiter
    body: SSEStreamStatusRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, str]:
    """Report SSE stream completion status from frontend.

    Story 6.2: Track stream completion vs interruption.

    This endpoint receives status reports from the frontend when an
    SSE stream completes or is interrupted.

    Args:
        body: SSE stream status details.
        current_user: Authenticated user.

    Returns:
        Acknowledgement message.
    """
    log_sse_stream_status(
        user_id=current_user.id,
        matter_id=body.matter_id,
        session_id=body.session_id,
        status=body.status,
        parse_error_count=body.parse_error_count,
        total_chunks=body.total_chunks,
        duration_ms=body.duration_ms,
    )

    return {"status": "logged"}


# =============================================================================
# Cache Management Endpoints
# =============================================================================


class CacheClearResponse(BaseModel):
    """Response model for cache clear operation."""

    query_cache_cleared: int = Field(
        ..., description="Number of query cache entries cleared"
    )
    summary_cache_cleared: bool = Field(
        ..., description="Whether summary cache was cleared"
    )
    timeline_cache_cleared: bool = Field(
        ..., description="Whether timeline cache was cleared"
    )


@router.delete("/{matter_id}/cache")
@limiter.limit(STANDARD_RATE_LIMIT)
async def clear_chat_cache(
    request: Request,  # Required for rate limiter
    matter_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    access: MatterAccessContext = Depends(validate_matter_access()),
) -> dict[str, Any]:
    """Clear all chat-related caches for a matter.

    Clears:
    - Query cache (cached Q&A responses)
    - Summary cache (executive summaries)
    - Timeline cache (timeline data)

    This forces fresh results on next query.

    Args:
        matter_id: Matter UUID (from path).
        current_user: Authenticated user.
        access: Matter access context.

    Returns:
        Cache clear statistics.
    """
    logger.info(
        "clear_chat_cache_request",
        matter_id=matter_id,
        user_id=current_user.id,
    )

    try:
        # Clear query cache
        query_cache_service = get_query_cache_service()
        query_cleared = await query_cache_service.invalidate_on_document_upload(
            matter_id
        )

        # Clear summary cache
        summary_service = get_summary_service()
        summary_cleared = await summary_service.invalidate_cache(matter_id)

        # Clear timeline cache
        timeline_cache = get_timeline_cache_service()
        timeline_deleted = await timeline_cache.invalidate_timeline(matter_id)
        timeline_cleared = timeline_deleted > 0

        logger.info(
            "clear_chat_cache_complete",
            matter_id=matter_id,
            user_id=current_user.id,
            query_cleared=query_cleared,
            summary_cleared=summary_cleared,
            timeline_cleared=timeline_cleared,
        )

        return {
            "data": {
                "query_cache_cleared": query_cleared,
                "summary_cache_cleared": summary_cleared,
                "timeline_cache_cleared": timeline_cleared,
            }
        }

    except Exception as e:
        logger.error(
            "clear_chat_cache_error",
            error=str(e),
            matter_id=matter_id,
            user_id=current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "CACHE_CLEAR_ERROR",
                    "message": "Failed to clear cache",
                    "details": {},
                }
            },
        ) from e
