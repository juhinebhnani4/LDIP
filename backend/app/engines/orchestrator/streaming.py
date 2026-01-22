"""Streaming Orchestrator for SSE chat responses.

Story 11.3: Streaming Response with Engine Trace
Task 3: Implement orchestrator streaming integration (AC: #1-3)

Wraps QueryOrchestrator to emit streaming events during execution:
- Typing indicator when processing starts
- Engine start/complete events with timing
- Token-by-token response streaming
- Complete event with full trace summary

CRITICAL: This integrates with existing Story 6-2 QueryOrchestrator.
CRITICAL: Session memory integration via Story 7-1 SessionMemoryService.
"""

import asyncio
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import structlog

from app.engines.orchestrator.orchestrator import (
    QueryOrchestrator,
    get_query_orchestrator,
)
from app.models.chat import (
    EngineTraceEvent,
    SourceReferenceEvent,
    StreamCompleteEvent,
    StreamEvent,
    StreamEventType,
    TokenEvent,
)
from app.models.orchestrator import OrchestratorResult
from app.services.memory.session import SessionMemoryService, get_session_memory_service

logger = structlog.get_logger(__name__)

# Simulated streaming delay (ms between tokens)
# In production, this would be driven by actual LLM streaming
TOKEN_STREAM_DELAY_MS = 5

# Batch size for token streaming (characters per event)
TOKEN_BATCH_SIZE = 3


class StreamingOrchestrator:
    """Wraps QueryOrchestrator to emit streaming events.

    Story 11.3: Task 3.1-3.8 - Streaming orchestration.

    Pipeline with events:
    1. Emit TYPING event
    2. Process through QueryOrchestrator
    3. Emit ENGINE_COMPLETE events for each engine
    4. Emit TOKEN events for response content
    5. Emit COMPLETE event with full trace

    Example:
        >>> streaming = get_streaming_orchestrator()
        >>> async for event in streaming.process_streaming(
        ...     matter_id="matter-123",
        ...     user_id="user-456",
        ...     query="What are the citations?",
        ... ):
        ...     print(event.type, event.data)
    """

    def __init__(
        self,
        orchestrator: QueryOrchestrator | None = None,
        session_service: SessionMemoryService | None = None,
    ) -> None:
        """Initialize streaming orchestrator.

        Args:
            orchestrator: Optional QueryOrchestrator (injected for testing).
            session_service: Optional SessionMemoryService (injected for testing).
        """
        self._orchestrator = orchestrator
        self._session_service = session_service
        logger.info("streaming_orchestrator_initialized")

    @property
    def orchestrator(self) -> QueryOrchestrator:
        """Lazy-load orchestrator."""
        if self._orchestrator is None:
            self._orchestrator = get_query_orchestrator()
        return self._orchestrator

    @property
    def session_service(self) -> SessionMemoryService:
        """Lazy-load session service."""
        if self._session_service is None:
            self._session_service = get_session_memory_service()
        return self._session_service

    async def process_streaming(
        self,
        matter_id: str,
        user_id: str,
        query: str,
        session_id: str | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Process query and stream events.

        Story 11.3: Task 3.2-3.8 - Main streaming pipeline.

        Args:
            matter_id: Matter UUID for isolation.
            user_id: User UUID for session tracking.
            query: User's natural language query.
            session_id: Optional session ID for context.

        Yields:
            StreamEvent objects for each phase of processing.
        """
        start_time = time.perf_counter()
        engine_traces: list[EngineTraceEvent] = []
        message_id = str(uuid.uuid4())

        logger.info(
            "streaming_start",
            matter_id=matter_id,
            user_id=user_id,
            query_length=len(query),
        )

        try:
            # Task 3.3: Emit typing event when processing starts
            yield StreamEvent(
                type=StreamEventType.TYPING,
                data={"status": "processing", "message": "LDIP is thinking..."},
            )

            # Task 4.1-4.3: Load session context and save user message
            session_context = await self._prepare_session(
                matter_id=matter_id,
                user_id=user_id,
                query=query,
            )

            # Process through orchestrator
            result = await self.orchestrator.process_query(
                matter_id=matter_id,
                query=query,
                user_id=user_id,
                context=session_context,
            )

            # Check if query was blocked by safety guard
            if result.blocked:
                yield StreamEvent(
                    type=StreamEventType.ERROR,
                    data={
                        "error": result.blocked_reason or "Query blocked by safety guard",
                        "code": "QUERY_BLOCKED",
                        "suggested_rewrite": result.suggested_rewrite,
                    },
                )
                return

            # Task 3.5: Emit engine_complete events with timing
            for engine_result in result.engine_results:
                findings_count = 0
                if engine_result.data:
                    # Count findings from various engine result formats
                    findings_count = len(
                        engine_result.data.get("findings", [])
                        or engine_result.data.get("citations", [])
                        or engine_result.data.get("events", [])
                        or engine_result.data.get("contradictions", [])
                        or engine_result.data.get("chunks", [])
                    )

                trace = EngineTraceEvent(
                    engine=engine_result.engine.value,
                    execution_time_ms=engine_result.execution_time_ms,
                    findings_count=findings_count,
                    success=engine_result.success,
                    error=engine_result.error,
                )
                engine_traces.append(trace)

                yield StreamEvent(
                    type=StreamEventType.ENGINE_COMPLETE,
                    data=trace.model_dump(),
                )

            # Task 3.6: Stream response tokens
            response_text = result.unified_response
            async for token_event in self._stream_tokens(response_text):
                yield StreamEvent(
                    type=StreamEventType.TOKEN,
                    data=token_event.model_dump(),
                )

            # Calculate total time
            total_time_ms = int((time.perf_counter() - start_time) * 1000)

            # Convert sources to event format (needed for both save and SSE event)
            sources = self._convert_sources(result)

            # Task 4.4: Save assistant response to session (with sources)
            await self._save_assistant_response(
                matter_id=matter_id,
                user_id=user_id,
                response=response_text,
                message_id=message_id,
                sources=sources,
            )

            # RAG Production Gaps - Feature 2: Auto-evaluation hook
            # Trigger async evaluation if enabled (non-blocking)
            await self._trigger_auto_evaluation(
                matter_id=matter_id,
                query=query,
                response=response_text,
                result=result,
                message_id=message_id,
            )

            # Task 3.7: Emit complete event with full trace summary
            complete_event = StreamCompleteEvent(
                response=response_text,
                sources=sources,
                engine_traces=engine_traces,
                total_time_ms=total_time_ms,
                confidence=result.confidence,
                message_id=message_id,
            )

            yield StreamEvent(
                type=StreamEventType.COMPLETE,
                data=complete_event.model_dump(),
            )

            logger.info(
                "streaming_complete",
                matter_id=matter_id,
                total_time_ms=total_time_ms,
                engines_count=len(engine_traces),
                response_length=len(response_text),
            )

        except Exception as e:
            # Task 3.8: Handle errors with error event type
            logger.error(
                "streaming_error",
                error=str(e),
                error_type=type(e).__name__,
                matter_id=matter_id,
            )
            yield StreamEvent(
                type=StreamEventType.ERROR,
                data={
                    "error": str(e),
                    "code": "STREAM_ERROR",
                },
            )

    async def _prepare_session(
        self,
        matter_id: str,
        user_id: str,
        query: str,
    ) -> dict[str, Any] | None:
        """Prepare session context for query processing.

        Story 11.3: Task 4.1-4.3 - Session integration.

        Args:
            matter_id: Matter UUID.
            user_id: User UUID.
            query: User's query to save.

        Returns:
            Session context dict or None if session unavailable.
        """
        try:
            # Task 4.1: Load session context
            session = await self.session_service.get_session(
                matter_id=matter_id,
                user_id=user_id,
                auto_create=True,
            )

            # Task 4.3: Save user message to session
            await self.session_service.add_message(
                matter_id=matter_id,
                user_id=user_id,
                role="user",
                content=query,
            )

            # Task 4.2: Return context for pronoun resolution
            if session:
                return {
                    "session_id": session.session_id,
                    "messages": [
                        {"role": m.role, "content": m.content}
                        for m in session.messages[-5:]  # Last 5 for context
                    ],
                    "entities": list(session.entities_mentioned.keys()),
                }

        except Exception as e:
            logger.warning(
                "session_prepare_failed",
                matter_id=matter_id,
                error=str(e),
            )

        return None

    async def _save_assistant_response(
        self,
        matter_id: str,
        user_id: str,
        response: str,
        message_id: str,
        sources: list[SourceReferenceEvent] | None = None,
    ) -> None:
        """Save assistant response to session memory.

        Story 11.3: Task 4.4 - Save response after streaming.

        Args:
            matter_id: Matter UUID.
            user_id: User UUID.
            response: Full assistant response.
            message_id: Message ID for tracking.
            sources: Optional source references from engine results.
        """
        try:
            # Convert SourceReferenceEvent to dicts for session storage
            source_refs = None
            if sources:
                source_refs = [
                    {
                        "document_id": s.document_id,
                        "document_name": s.document_name or "Unknown Document",
                        "page": s.page,
                    }
                    for s in sources
                ]

            await self.session_service.add_message(
                matter_id=matter_id,
                user_id=user_id,
                role="assistant",
                content=response,
                source_refs=source_refs,
            )
            logger.debug(
                "assistant_response_saved",
                matter_id=matter_id,
                message_id=message_id,
                sources_count=len(sources) if sources else 0,
            )
        except Exception as e:
            logger.warning(
                "assistant_response_save_failed",
                matter_id=matter_id,
                error=str(e),
            )

    async def _trigger_auto_evaluation(
        self,
        matter_id: str,
        query: str,
        response: str,
        result: OrchestratorResult,
        message_id: str,
    ) -> None:
        """Trigger async evaluation of chat response if enabled.

        RAG Production Gaps - Feature 2: Auto-evaluation hook.

        This queues an evaluation task to run asynchronously via Celery.
        The task is non-blocking and failures don't affect the chat response.

        Args:
            matter_id: Matter UUID.
            query: User's question.
            response: Generated response.
            result: Orchestrator result with sources/contexts.
            message_id: Message ID for linking.
        """
        try:
            from app.core.config import get_settings

            settings = get_settings()

            if not settings.auto_evaluation_enabled:
                return

            # Extract contexts from RAG results
            contexts: list[str] = []
            for engine_result in result.engine_results:
                if engine_result.data:
                    chunks = engine_result.data.get("chunks", [])
                    for chunk in chunks:
                        if isinstance(chunk, dict) and "content" in chunk:
                            contexts.append(chunk["content"])
                        elif isinstance(chunk, str):
                            contexts.append(chunk)

            if not contexts:
                logger.debug(
                    "auto_evaluation_skipped_no_contexts",
                    matter_id=matter_id,
                    message_id=message_id,
                )
                return

            # Queue async evaluation task
            from app.workers.tasks.evaluation_tasks import evaluate_chat_response

            evaluate_chat_response.delay(
                matter_id=matter_id,
                question=query,
                answer=response,
                contexts=contexts[:10],  # Limit contexts
                chat_message_id=message_id,
            )

            logger.debug(
                "auto_evaluation_triggered",
                matter_id=matter_id,
                message_id=message_id,
                context_count=len(contexts),
            )

        except Exception as e:
            # Non-blocking: log warning but don't fail chat
            logger.warning(
                "auto_evaluation_trigger_failed",
                matter_id=matter_id,
                error=str(e),
            )

    async def _stream_tokens(
        self,
        text: str,
    ) -> AsyncGenerator[TokenEvent, None]:
        """Stream text as token events.

        Story 11.3: Task 3.6 - Token-by-token streaming.

        In production, this would be driven by actual LLM streaming.
        For now, we simulate streaming by batching characters.

        Args:
            text: Full response text to stream.

        Yields:
            TokenEvent for each batch of characters.
        """
        accumulated = ""

        for i in range(0, len(text), TOKEN_BATCH_SIZE):
            batch = text[i : i + TOKEN_BATCH_SIZE]
            accumulated += batch

            yield TokenEvent(
                token=batch,
                accumulated=accumulated,
            )

            # Simulate streaming delay
            await asyncio.sleep(TOKEN_STREAM_DELAY_MS / 1000)

    def _convert_sources(
        self,
        result: OrchestratorResult,
    ) -> list[SourceReferenceEvent]:
        """Convert orchestrator sources to event format.

        Args:
            result: Orchestrator result with source references.

        Returns:
            List of SourceReferenceEvent objects.
        """
        sources: list[SourceReferenceEvent] = []

        for source in result.sources:
            # DEBUG: Log document_name during conversion
            logger.debug(
                "convert_source",
                document_id=source.document_id[:8] if source.document_id else None,
                document_name=source.document_name,
                has_doc_name=source.document_name is not None,
            )
            sources.append(
                SourceReferenceEvent(
                    document_id=source.document_id,
                    document_name=source.document_name,
                    page=source.page_number,
                    chunk_id=source.chunk_id,
                    confidence=source.confidence,
                )
            )

        return sources


# =============================================================================
# Factory Function
# =============================================================================

_streaming_orchestrator: StreamingOrchestrator | None = None


def get_streaming_orchestrator() -> StreamingOrchestrator:
    """Get singleton streaming orchestrator instance.

    Returns:
        StreamingOrchestrator instance.
    """
    global _streaming_orchestrator

    if _streaming_orchestrator is None:
        _streaming_orchestrator = StreamingOrchestrator()

    return _streaming_orchestrator


def reset_streaming_orchestrator() -> None:
    """Reset singleton for testing."""
    global _streaming_orchestrator
    _streaming_orchestrator = None
