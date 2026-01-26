"""Chat Streaming Models.

Story 11.3: Streaming Response with Engine Trace
Task 2: Create streaming event models (AC: #1-3)

Models for SSE streaming events during chat responses:
- StreamEventType: Event type enum
- StreamEvent: Base event model
- EngineTraceEvent: Engine execution trace
- TokenEvent: Streaming token
- StreamCompleteEvent: Completion event with full trace
- ChatStreamRequest: Request model for streaming chat

CRITICAL: Events are serialized as JSON for SSE transport.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# Stream Event Types (Task 2.2)
# =============================================================================


class StreamEventType(str, Enum):
    """Event types for SSE streaming.

    Story 11.3: AC #1-3 - Different phases of streaming response.

    Values:
        TYPING: Processing started, show typing indicator
        ENGINE_START: Engine execution began
        ENGINE_COMPLETE: Engine finished with results
        TOKEN: Streamed response token
        COMPLETE: Full response complete with trace
        ERROR: Error occurred during processing
    """

    TYPING = "typing"
    ENGINE_START = "engine_start"
    ENGINE_COMPLETE = "engine_complete"
    TOKEN = "token"
    COMPLETE = "complete"
    ERROR = "error"


# =============================================================================
# Event Models (Task 2.1, 2.3-2.5)
# =============================================================================


class StreamEvent(BaseModel):
    """Base model for stream events.

    Story 11.3: Task 2.1 - Base event structure.
    """

    type: StreamEventType = Field(description="Event type")
    data: dict[str, Any] = Field(default_factory=dict, description="Event payload")


class EngineTraceEvent(BaseModel):
    """Engine execution trace for AC #2-3.

    Story 11.3: Task 2.3 - Detailed engine execution info.

    Attributes:
        engine: Engine identifier (citation, timeline, contradiction, rag)
        execution_time_ms: Time taken in milliseconds
        findings_count: Number of findings produced
        success: Whether execution succeeded
        error: Error message if failed
    """

    engine: str = Field(description="Engine identifier")
    execution_time_ms: int = Field(ge=0, description="Execution time in ms")
    findings_count: int = Field(ge=0, default=0, description="Number of findings")
    success: bool = Field(description="Whether execution succeeded")
    error: str | None = Field(default=None, description="Error message if failed")


class TokenEvent(BaseModel):
    """Streaming token event for AC #1.

    Story 11.3: Token-by-token response streaming.

    Attributes:
        token: Single token or character
        accumulated: Full text so far
    """

    token: str = Field(description="Single token/character")
    accumulated: str = Field(description="Full accumulated text so far")


class SourceReferenceEvent(BaseModel):
    """Source reference from engine results.

    Story 11.3: Source references for citations.
    """

    document_id: str = Field(description="Document UUID")
    document_name: str | None = Field(default=None, description="Document filename")
    page: int | None = Field(default=None, description="Page number")
    chunk_id: str | None = Field(default=None, description="Chunk UUID")
    confidence: float | None = Field(default=None, description="Relevance score")
    bbox_ids: list[str] | None = Field(default=None, description="Bounding box UUIDs for highlighting")


class StreamCompleteEvent(BaseModel):
    """Completion event with full trace for AC #2-3.

    Story 11.3: Task 2.4 - Final event with all metadata.

    Attributes:
        response: Full response text
        sources: Source references from all engines
        engine_traces: Trace from each engine executed
        total_time_ms: Total processing time
        confidence: Overall response confidence
        message_id: ID of the saved assistant message
        search_mode: Search mode used (hybrid, bm25_fallback, bm25_only)
        search_notice: User-friendly notice about search mode (if degraded)
    """

    response: str = Field(description="Full response text")
    sources: list[SourceReferenceEvent] = Field(
        default_factory=list, description="Source references"
    )
    engine_traces: list[EngineTraceEvent] = Field(
        default_factory=list, description="Engine execution traces"
    )
    total_time_ms: int = Field(ge=0, description="Total processing time in ms")
    confidence: float = Field(ge=0.0, le=1.0, description="Response confidence")
    message_id: str | None = Field(default=None, description="Saved message ID")
    search_mode: str | None = Field(
        default=None,
        description="Search mode: 'hybrid', 'bm25_fallback', or 'bm25_only'"
    )
    search_notice: str | None = Field(
        default=None,
        description="User-friendly notice if search was degraded (e.g., rate limit)"
    )
    # Response completeness indicators
    truncated: bool = Field(
        default=False,
        description="True if response was truncated due to length"
    )
    more_available: bool = Field(
        default=False,
        description="True if more results are available beyond what was shown"
    )
    total_results_hint: int | None = Field(
        default=None,
        description="Total results available (if more_available is True)"
    )
    # Query safety rewrite metadata
    query_was_rewritten: bool = Field(
        default=False,
        description="True if query was automatically rewritten for safety"
    )
    original_query: str | None = Field(
        default=None,
        description="Original query before safety rewrite (if rewritten)"
    )


class ChatStreamRequest(BaseModel):
    """Request model for streaming chat.

    Story 11.3: Task 2.5 - Input for chat streaming endpoint.

    Attributes:
        query: User's question
        session_id: Optional session ID for context
    """

    query: str = Field(min_length=1, max_length=4000, description="User's question")
    session_id: str | None = Field(default=None, description="Session ID for context")


# =============================================================================
# Response Wrappers (following project-context.md API format)
# =============================================================================


class ChatStreamErrorResponse(BaseModel):
    """Error response for chat streaming.

    Follows project-context.md API error format.
    """

    error: dict[str, Any] = Field(description="Error details")


class ChatMessageResponse(BaseModel):
    """Response for saved chat message.

    Used after streaming completes to confirm message saved.
    """

    id: str = Field(description="Message UUID")
    role: str = Field(description="Message role (user/assistant)")
    content: str = Field(description="Message content")
    timestamp: str = Field(description="ISO8601 timestamp")
    sources: list[SourceReferenceEvent] = Field(
        default_factory=list, description="Source references"
    )
    engine_traces: list[EngineTraceEvent] = Field(
        default_factory=list, description="Engine traces (assistant only)"
    )
