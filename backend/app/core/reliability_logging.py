"""Reliability Event Logging Module.

Epic 6: Reliability Monitoring & Diagnostics
Story 6.5: Implement Comprehensive Reliability Event Logging

Provides standardized logging for all reliability-related events:
- Citation page accuracy metrics (Story 6.1)
- SSE error rate tracking (Story 6.2)
- WebSocket health metrics (Story 6.3)
- Entity extraction success rates (Story 6.4)

All events follow a consistent schema for easy querying:
- event_type: The type of reliability event
- user_id: User performing the action
- matter_id: Matter context (if applicable)
- document_id: Document context (if applicable)
- timestamp: ISO format timestamp
- details: Additional event-specific data (JSON)

NFR10: All reliability-related errors logged with sufficient context
NFR14: Support staff can access reliability metrics without engineering
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Event Types
# =============================================================================


class ReliabilityEventType(str, Enum):
    """Reliability event types for consistent categorization."""

    # Citation Page Accuracy (Story 6.1)
    CITATION_PAGE_DETECTED_BBOX = "citation_page_detected_bbox"
    CITATION_PAGE_DETECTED_CHUNK = "citation_page_detected_chunk"
    CITATION_PAGE_FALLBACK = "citation_page_fallback"
    CITATION_PAGE_MISSING = "citation_page_missing"

    # SSE Errors (Story 6.2)
    SSE_JSON_PARSE_FAILED = "sse_json_parse_failed"
    SSE_MAX_ERRORS_EXCEEDED = "sse_max_errors_exceeded"
    SSE_STREAM_INTERRUPTED = "sse_stream_interrupted"
    SSE_STREAM_COMPLETE = "sse_stream_complete"

    # WebSocket Health (Story 6.3)
    WEBSOCKET_CONNECTED = "websocket_connected"
    WEBSOCKET_DISCONNECTED = "websocket_disconnected"
    WEBSOCKET_RECONNECT_ATTEMPT = "websocket_reconnect_attempt"
    WEBSOCKET_RECONNECT_SUCCESS = "websocket_reconnect_success"
    WEBSOCKET_RECONNECT_FAILED = "websocket_reconnect_failed"
    WEBSOCKET_HEARTBEAT_TIMEOUT = "websocket_heartbeat_timeout"

    # Entity Extraction (Story 6.4)
    ENTITY_EXTRACTION_SUCCESS = "entity_extraction_success"
    ENTITY_EXTRACTION_ERROR = "entity_extraction_error"
    ENTITY_EXTRACTION_EMPTY = "entity_extraction_empty"

    # Request Timeouts (related to Epic 5)
    REQUEST_TIMEOUT = "request_timeout"
    REQUEST_SLOW = "request_slow"


# =============================================================================
# Logging Functions
# =============================================================================


def log_reliability_event(
    event_type: ReliabilityEventType,
    *,
    user_id: str | None = None,
    matter_id: str | None = None,
    document_id: str | None = None,
    session_id: str | None = None,
    **details: Any,
) -> None:
    """Log a reliability event with standardized schema.

    All reliability events use this function to ensure consistent
    log format for querying and analysis.

    Args:
        event_type: The type of reliability event.
        user_id: User ID (from auth).
        matter_id: Matter UUID (if applicable).
        document_id: Document UUID (if applicable).
        session_id: Session ID (for SSE/WebSocket tracking).
        **details: Additional event-specific data.

    Example:
        >>> log_reliability_event(
        ...     ReliabilityEventType.CITATION_PAGE_DETECTED_BBOX,
        ...     matter_id="uuid",
        ...     document_id="uuid",
        ...     page_number=5,
        ...     detection_method="bbox",
        ... )
    """
    logger.info(
        event_type.value,
        event_category="reliability",
        event_type=event_type.value,
        user_id=user_id,
        matter_id=matter_id,
        document_id=document_id,
        session_id=session_id,
        timestamp=datetime.now(UTC).isoformat(),
        **details,
    )


# =============================================================================
# Story 6.1: Citation Page Accuracy Logging
# =============================================================================


def log_citation_page_detection(
    *,
    matter_id: str,
    document_id: str,
    detection_method: str,  # "bbox" or "chunk"
    page_number: int | None,
    event_id: str | None = None,
    citation_id: str | None = None,
    bbox_id: str | None = None,
    chunk_id: str | None = None,
    confidence: float | None = None,
) -> None:
    """Log citation page detection event for accuracy tracking.

    Story 6.1: Add Citation Page Accuracy Logging

    Logs whether page was detected via bounding box (precise) or
    chunk fallback (approximate) for accuracy metrics calculation:
    - Accuracy = COUNT(bbox) / COUNT(*) per matter

    Args:
        matter_id: Matter UUID.
        document_id: Document UUID.
        detection_method: "bbox" for precise, "chunk" for fallback.
        page_number: Detected page number (None if detection failed).
        event_id: Optional event UUID (for timeline events).
        citation_id: Optional citation UUID (for RAG citations).
        bbox_id: Optional bounding box UUID used.
        chunk_id: Optional chunk UUID used for fallback.
        confidence: Optional confidence score (0-1).

    Example:
        >>> log_citation_page_detection(
        ...     matter_id="uuid",
        ...     document_id="uuid",
        ...     detection_method="bbox",
        ...     page_number=5,
        ...     event_id="event-uuid",
        ...     bbox_id="bbox-uuid",
        ...     confidence=0.95,
        ... )
    """
    if detection_method == "bbox":
        event_type = ReliabilityEventType.CITATION_PAGE_DETECTED_BBOX
    elif detection_method == "chunk":
        event_type = ReliabilityEventType.CITATION_PAGE_DETECTED_CHUNK
    else:
        event_type = ReliabilityEventType.CITATION_PAGE_MISSING

    log_reliability_event(
        event_type,
        matter_id=matter_id,
        document_id=document_id,
        detection_method=detection_method,
        page_number=page_number,
        event_id=event_id,
        citation_id=citation_id,
        bbox_id=bbox_id,
        chunk_id=chunk_id,
        confidence=confidence,
    )


def log_citation_page_fallback(
    *,
    matter_id: str,
    document_id: str,
    event_id: str | None = None,
    reason: str,
    chunk_page: int | None = None,
) -> None:
    """Log when citation page detection falls back to chunk-level.

    Story 6.1: Tracks fallback events for monitoring citation accuracy.
    NFR11: Citation page fallback events countable in dashboards.

    Args:
        matter_id: Matter UUID.
        document_id: Document UUID.
        event_id: Optional event UUID.
        reason: Reason for fallback (e.g., "no_bbox_data", "bbox_no_page").
        chunk_page: Fallback page number from chunk (if available).
    """
    log_reliability_event(
        ReliabilityEventType.CITATION_PAGE_FALLBACK,
        matter_id=matter_id,
        document_id=document_id,
        event_id=event_id,
        fallback_reason=reason,
        chunk_page=chunk_page,
    )


# =============================================================================
# Story 6.2: SSE Error Rate Logging
# =============================================================================


def log_sse_parse_error(
    *,
    user_id: str | None,
    matter_id: str | None,
    session_id: str,
    error_type: str,
    error_message: str,
    raw_chunk: str | None = None,
) -> None:
    """Log SSE JSON parse error for error rate tracking.

    Story 6.2: Add SSE Error Rate Logging
    NFR12: SSE parse errors trackable per user session.

    Args:
        user_id: User ID from auth session.
        matter_id: Matter ID from stream URL.
        session_id: SSE session ID (generated per stream).
        error_type: Type of error ("sse_json_parse_failed", "sse_max_errors_exceeded").
        error_message: Original error message.
        raw_chunk: Raw chunk content (truncated to 1KB max).
    """
    # Truncate raw chunk to 1KB for log storage
    truncated_chunk = raw_chunk[:1024] if raw_chunk and len(raw_chunk) > 1024 else raw_chunk

    event_type = (
        ReliabilityEventType.SSE_MAX_ERRORS_EXCEEDED
        if error_type == "sse_max_errors_exceeded"
        else ReliabilityEventType.SSE_JSON_PARSE_FAILED
    )

    log_reliability_event(
        event_type,
        user_id=user_id,
        matter_id=matter_id,
        session_id=session_id,
        error_type=error_type,
        error_message=error_message,
        raw_chunk=truncated_chunk,
    )


def log_sse_stream_status(
    *,
    user_id: str | None,
    matter_id: str | None,
    session_id: str,
    status: str,  # "complete" or "interrupted"
    parse_error_count: int = 0,
    total_chunks: int = 0,
    duration_ms: int | None = None,
) -> None:
    """Log SSE stream completion or interruption status.

    Story 6.2: Track stream completion for response completeness.

    Args:
        user_id: User ID from auth session.
        matter_id: Matter ID from stream URL.
        session_id: SSE session ID.
        status: "complete" or "interrupted".
        parse_error_count: Number of parse errors during stream.
        total_chunks: Total chunks received.
        duration_ms: Stream duration in milliseconds.
    """
    event_type = (
        ReliabilityEventType.SSE_STREAM_COMPLETE
        if status == "complete"
        else ReliabilityEventType.SSE_STREAM_INTERRUPTED
    )

    log_reliability_event(
        event_type,
        user_id=user_id,
        matter_id=matter_id,
        session_id=session_id,
        stream_status=status,
        parse_error_count=parse_error_count,
        total_chunks=total_chunks,
        duration_ms=duration_ms,
    )


# =============================================================================
# Story 6.3: WebSocket Health Metrics Logging
# =============================================================================


def log_websocket_event(
    *,
    user_id: str | None,
    matter_id: str | None,
    session_id: str | None,
    event_type: ReliabilityEventType,
    reconnect_attempt: int | None = None,
    max_attempts: int | None = None,
    reason: str | None = None,
    latency_ms: int | None = None,
) -> None:
    """Log WebSocket connection event for health monitoring.

    Story 6.3: Add WebSocket Health Metrics Logging
    NFR13: WebSocket reconnection events trackable per hour/day.

    Args:
        user_id: User ID from auth.
        matter_id: Matter ID for the connection.
        session_id: WebSocket session ID.
        event_type: WebSocket event type.
        reconnect_attempt: Current reconnect attempt number.
        max_attempts: Maximum reconnect attempts configured.
        reason: Reason for disconnect/failure.
        latency_ms: Connection latency in milliseconds.
    """
    log_reliability_event(
        event_type,
        user_id=user_id,
        matter_id=matter_id,
        session_id=session_id,
        reconnect_attempt=reconnect_attempt,
        max_attempts=max_attempts,
        reason=reason,
        latency_ms=latency_ms,
    )


def log_websocket_connected(
    *,
    user_id: str | None,
    matter_id: str,
    session_id: str,
    was_reconnect: bool = False,
    previous_attempts: int = 0,
) -> None:
    """Log successful WebSocket connection.

    Args:
        user_id: User ID from auth.
        matter_id: Matter ID for the connection.
        session_id: WebSocket session ID.
        was_reconnect: True if this was a reconnection.
        previous_attempts: Number of reconnect attempts before success.
    """
    event_type = (
        ReliabilityEventType.WEBSOCKET_RECONNECT_SUCCESS
        if was_reconnect
        else ReliabilityEventType.WEBSOCKET_CONNECTED
    )

    log_reliability_event(
        event_type,
        user_id=user_id,
        matter_id=matter_id,
        session_id=session_id,
        was_reconnect=was_reconnect,
        previous_attempts=previous_attempts,
    )


def log_websocket_disconnected(
    *,
    user_id: str | None,
    matter_id: str | None,
    session_id: str,
    reason: str,
    code: int | None = None,
) -> None:
    """Log WebSocket disconnection.

    Args:
        user_id: User ID from auth.
        matter_id: Matter ID for the connection.
        session_id: WebSocket session ID.
        reason: Reason for disconnection.
        code: WebSocket close code.
    """
    log_reliability_event(
        ReliabilityEventType.WEBSOCKET_DISCONNECTED,
        user_id=user_id,
        matter_id=matter_id,
        session_id=session_id,
        disconnect_reason=reason,
        close_code=code,
    )


def log_websocket_reconnect_attempt(
    *,
    user_id: str | None,
    matter_id: str | None,
    session_id: str,
    attempt: int,
    max_attempts: int,
    delay_ms: int,
) -> None:
    """Log WebSocket reconnection attempt.

    Args:
        user_id: User ID from auth.
        matter_id: Matter ID for the connection.
        session_id: WebSocket session ID.
        attempt: Current attempt number.
        max_attempts: Maximum attempts configured.
        delay_ms: Delay before next attempt in milliseconds.
    """
    log_reliability_event(
        ReliabilityEventType.WEBSOCKET_RECONNECT_ATTEMPT,
        user_id=user_id,
        matter_id=matter_id,
        session_id=session_id,
        reconnect_attempt=attempt,
        max_attempts=max_attempts,
        delay_ms=delay_ms,
    )


def log_websocket_reconnect_failed(
    *,
    user_id: str | None,
    matter_id: str | None,
    session_id: str,
    attempts: int,
    reason: str,
) -> None:
    """Log WebSocket reconnection failure (max attempts reached).

    Args:
        user_id: User ID from auth.
        matter_id: Matter ID for the connection.
        session_id: WebSocket session ID.
        attempts: Total attempts made.
        reason: Failure reason.
    """
    log_reliability_event(
        ReliabilityEventType.WEBSOCKET_RECONNECT_FAILED,
        user_id=user_id,
        matter_id=matter_id,
        session_id=session_id,
        reconnect_attempt=attempts,
        failure_reason=reason,
    )


# =============================================================================
# Story 6.4: Entity Extraction Success Rate Logging
# =============================================================================


def log_entity_extraction_result(
    *,
    matter_id: str,
    document_id: str,
    status: str,  # "success", "error", "empty"
    entity_count: int = 0,
    entity_types: dict[str, int] | None = None,
    processing_time_ms: int | None = None,
    error_message: str | None = None,
    error_type: str | None = None,
) -> None:
    """Log entity extraction outcome for success rate tracking.

    Story 6.4: Add Entity Extraction Success Rate Logging

    Tracks success vs failure vs empty results for accuracy metrics:
    - Success rate = COUNT(success) / COUNT(*) per time period

    Args:
        matter_id: Matter UUID.
        document_id: Document UUID.
        status: "success", "error", or "empty".
        entity_count: Number of entities extracted (for success).
        entity_types: Count by entity type (e.g., {"PERSON": 5, "ORG": 3}).
        processing_time_ms: Processing time in milliseconds.
        error_message: Error message (for error status).
        error_type: Error type/code (for error status).
    """
    if status == "success":
        event_type = ReliabilityEventType.ENTITY_EXTRACTION_SUCCESS
    elif status == "error":
        event_type = ReliabilityEventType.ENTITY_EXTRACTION_ERROR
    else:
        event_type = ReliabilityEventType.ENTITY_EXTRACTION_EMPTY

    log_reliability_event(
        event_type,
        matter_id=matter_id,
        document_id=document_id,
        extraction_status=status,
        entity_count=entity_count,
        entity_types=entity_types,
        processing_time_ms=processing_time_ms,
        error_message=error_message,
        error_type=error_type,
    )


# =============================================================================
# Request Timeout Logging (Supporting Epic 5)
# =============================================================================


def log_request_timeout(
    *,
    user_id: str | None,
    matter_id: str | None,
    endpoint: str,
    timeout_ms: int,
    duration_ms: int,
) -> None:
    """Log request timeout event.

    Args:
        user_id: User ID from auth.
        matter_id: Matter ID (if applicable).
        endpoint: API endpoint that timed out.
        timeout_ms: Configured timeout in milliseconds.
        duration_ms: Actual duration before timeout.
    """
    log_reliability_event(
        ReliabilityEventType.REQUEST_TIMEOUT,
        user_id=user_id,
        matter_id=matter_id,
        endpoint=endpoint,
        timeout_ms=timeout_ms,
        duration_ms=duration_ms,
    )


def log_request_slow(
    *,
    user_id: str | None,
    matter_id: str | None,
    endpoint: str,
    threshold_ms: int,
    duration_ms: int,
) -> None:
    """Log slow request event (exceeded threshold but not timeout).

    Args:
        user_id: User ID from auth.
        matter_id: Matter ID (if applicable).
        endpoint: API endpoint.
        threshold_ms: Slow threshold in milliseconds.
        duration_ms: Actual duration.
    """
    log_reliability_event(
        ReliabilityEventType.REQUEST_SLOW,
        user_id=user_id,
        matter_id=matter_id,
        endpoint=endpoint,
        threshold_ms=threshold_ms,
        duration_ms=duration_ms,
    )
