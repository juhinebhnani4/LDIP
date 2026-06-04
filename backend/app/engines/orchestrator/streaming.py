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
from app.services.memory.summarizer import get_conversation_summarizer
from app.services.rag.query_rewriter import rewrite_query

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
        provider_context: dict[str, str | None] | None = None,
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

            # Task 4.1-4.3: Load session context, rewrite query, save user message
            session_context, rewritten_query = await self._prepare_session(
                matter_id=matter_id,
                user_id=user_id,
                query=query,
            )

            # Use rewritten query for retrieval (original query kept for display)
            search_query = rewritten_query or query

            # Merge provider_context into session context for engine adapters
            merged_context = session_context or {}
            if provider_context:
                merged_context = {**merged_context, **provider_context}
            # Gap 10: Inject user_id into context so RAG adapter can use it
            # for deterministic hash-based A/B traffic routing
            merged_context["user_id"] = user_id

            # Process through orchestrator with rewritten query.
            # Run in background task with keepalive pings to prevent
            # Railway's HTTP/2 proxy from killing idle SSE connections (~12s timeout).
            KEEPALIVE_INTERVAL_S = 5
            processing_messages = [
                "Analyzing documents...",
                "Searching for relevant passages...",
                "Cross-referencing sources...",
                "Synthesizing findings...",
                "Preparing response...",
            ]
            task = asyncio.create_task(
                self.orchestrator.process_query(
                    matter_id=matter_id,
                    query=search_query,
                    user_id=user_id,
                    context=merged_context or None,
                )
            )
            ping_count = 0
            while not task.done():
                try:
                    await asyncio.wait_for(
                        asyncio.shield(task), timeout=KEEPALIVE_INTERVAL_S
                    )
                except TimeoutError:
                    # Task still running — send keepalive ping
                    msg = processing_messages[
                        min(ping_count, len(processing_messages) - 1)
                    ]
                    yield StreamEvent(
                        type=StreamEventType.TYPING,
                        data={"status": "processing", "message": msg},
                    )
                    ping_count += 1

            result: OrchestratorResult = task.result()

            # Send a keepalive ping AFTER process_query completes to re-prime
            # Railway's proxy buffer before the burst of ENGINE_COMPLETE/TOKEN events.
            yield StreamEvent(
                type=StreamEventType.TYPING,
                data={"status": "processing", "message": "Formatting response..."},
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
                        or engine_result.data.get("results", [])
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

            # Extract search mode from RAG engine results (if applicable)
            search_mode, search_notice = self._extract_search_mode(result)

            # Extract completeness indicators
            truncated, more_available, total_results_hint = self._extract_completeness(result)

            # Task 3.7: Emit complete event with full trace summary
            # IMPORTANT: Yield COMPLETE before save/eval so failures there
            # don't prevent the client from receiving the response.
            complete_event = StreamCompleteEvent(
                response=response_text,
                sources=sources,
                engine_traces=engine_traces,
                total_time_ms=total_time_ms,
                confidence=result.confidence,
                message_id=message_id,
                search_mode=search_mode,
                search_notice=search_notice,
                truncated=truncated,
                more_available=more_available,
                total_results_hint=total_results_hint,
                # Query safety rewrite metadata
                query_was_rewritten=result.query_was_rewritten,
                original_query=result.original_query if result.query_was_rewritten else None,
                rewritten_query=result.rewritten_query if result.query_was_rewritten else None,
                # A/B testing provider metadata
                # Read actual provider from RAG engine result (adapter may have overridden
                # via percentage-based routing), falling back to request-level context
                embedding_provider=self._extract_actual_provider(result, "embedding_provider")
                    or (provider_context or {}).get("embedding_provider")
                    or "openai",
                rerank_provider=self._extract_actual_provider(result, "rerank_provider")
                    or (provider_context or {}).get("rerank_provider")
                    or "cohere",
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

            # Task 4.4: Save assistant response to session (with sources)
            # Done AFTER yielding COMPLETE so save failures don't block the response.
            try:
                await self._save_assistant_response(
                    matter_id=matter_id,
                    user_id=user_id,
                    response=response_text,
                    message_id=message_id,
                    sources=sources,
                    engine_traces=engine_traces,
                )
            except Exception as save_err:
                logger.error(
                    "post_complete_save_failed",
                    error=str(save_err),
                    matter_id=matter_id,
                    message_id=message_id,
                )

            # RAG Production Gaps - Feature 2: Auto-evaluation hook
            # Trigger async evaluation if enabled (non-blocking)
            try:
                await self._trigger_auto_evaluation(
                    matter_id=matter_id,
                    query=query,
                    response=response_text,
                    result=result,
                    message_id=message_id,
                )
            except Exception as eval_err:
                logger.error(
                    "post_complete_evaluation_failed",
                    error=str(eval_err),
                    matter_id=matter_id,
                    message_id=message_id,
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
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Prepare session context and rewrite query for retrieval.

        Story 11.3: Task 4.1-4.3 - Session integration.
        G1: Generate conversation summary.
        G2 (revised): Use summary to REWRITE query (not inject into prompt).

        Args:
            matter_id: Matter UUID.
            user_id: User UUID.
            query: User's query to save.

        Returns:
            Tuple of (session context dict or None, rewritten query or None).
        """
        try:
            # Task 4.1: Load session context
            session = await self.session_service.get_session(
                matter_id=matter_id,
                user_id=user_id,
                auto_create=True,
            )

            # Task 4.3: Save user message to session
            # NOTE: Save AFTER loading so the summary doesn't include the current query
            await self.session_service.add_message(
                matter_id=matter_id,
                user_id=user_id,
                role="user",
                content=query,
            )

            # Task 4.2: Return context for pronoun resolution
            if session:
                entities = list(session.entities_mentioned.keys())

                # G1: Generate conversation summary
                conversation_summary = None
                try:
                    summarizer = get_conversation_summarizer()
                    conversation_summary = await summarizer.get_summary(
                        matter_id=matter_id,
                        user_id=user_id,
                        messages=session.messages,
                    )
                except Exception as e:
                    logger.debug(
                        "conversation_summary_failed",
                        matter_id=matter_id,
                        error=str(e),
                    )

                # G2 (revised): Rewrite query using summary for better retrieval
                rewritten_query = None
                if conversation_summary:
                    try:
                        rewritten_query = await rewrite_query(
                            query=query,
                            conversation_summary=conversation_summary,
                            entities=entities,
                            matter_id=matter_id,
                        )
                        # If rewriter returned the same query, treat as no rewrite
                        if rewritten_query == query:
                            rewritten_query = None
                    except Exception as e:
                        logger.debug(
                            "query_rewrite_failed",
                            matter_id=matter_id,
                            error=str(e),
                        )

                context = {
                    "session_id": session.session_id,
                    "messages": [
                        {"role": m.role, "content": m.content}
                        for m in session.messages[-5:]  # Last 5 for context
                    ],
                    "entities": entities,
                }

                return context, rewritten_query

        except Exception as e:
            logger.warning(
                "session_prepare_failed",
                matter_id=matter_id,
                error=str(e),
            )

        return None, None

    async def _save_assistant_response(
        self,
        matter_id: str,
        user_id: str,
        response: str,
        message_id: str,
        sources: list[SourceReferenceEvent] | None = None,
        engine_traces: list[EngineTraceEvent] | None = None,
    ) -> None:
        """Save assistant response to session memory.

        Story 11.3: Task 4.4 - Save response after streaming.

        Args:
            matter_id: Matter UUID.
            user_id: User UUID.
            response: Full assistant response.
            message_id: Message ID for tracking.
            sources: Optional source references from engine results.
            engine_traces: Optional engine execution traces.
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

            # Convert EngineTraceEvent to dicts for session storage
            trace_dicts = None
            if engine_traces:
                trace_dicts = [
                    {
                        "engine": t.engine,
                        "execution_time_ms": t.execution_time_ms,
                        "findings_count": t.findings_count,
                        "success": t.success,
                        "error": t.error,
                    }
                    for t in engine_traces
                ]

            await self.session_service.add_message(
                matter_id=matter_id,
                user_id=user_id,
                role="assistant",
                content=response,
                source_refs=source_refs,
                engine_traces=trace_dicts,
            )
            logger.debug(
                "assistant_response_saved",
                matter_id=matter_id,
                message_id=message_id,
                sources_count=len(sources) if sources else 0,
                traces_count=len(engine_traces) if engine_traces else 0,
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
                    chunks = engine_result.data.get("chunks", []) or engine_result.data.get("results", [])
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

    def _extract_completeness(
        self,
        result: OrchestratorResult,
    ) -> tuple[bool, bool, int | None]:
        """Extract completeness indicators from engine results.

        Args:
            result: Orchestrator result with engine results.

        Returns:
            Tuple of (truncated, more_available, total_results_hint).
        """
        truncated = False
        more_available = False
        total_results_hint = None

        for engine_result in result.engine_results:
            if engine_result.data and engine_result.success:
                data = engine_result.data

                # Check for truncation in RAG results
                if "total_candidates" in data:
                    total = data.get("total_candidates", 0)
                    shown = len(data.get("results", []))
                    if total > shown:
                        more_available = True
                        total_results_hint = total

                # Check for truncation in timeline events
                if "total_events" in data:
                    total = data.get("total_events", 0)
                    shown = len(data.get("events", []))
                    if total > shown:
                        more_available = True
                        total_results_hint = (total_results_hint or 0) + total

                # Check for truncation in document discovery
                if "total_documents" in data:
                    total = data.get("total_documents", 0)
                    shown = len(data.get("documents", []))
                    if total > shown:
                        more_available = True
                        total_results_hint = total

                # Check for truncation in entity results
                if "total_entities" in data:
                    total = data.get("total_entities", 0)
                    shown = len(data.get("entities", []))
                    if total > shown:
                        more_available = True
                        total_results_hint = total

        # Check if response itself was truncated (very long responses)
        if len(result.unified_response) >= 8000:
            truncated = True

        return truncated, more_available, total_results_hint

    @staticmethod
    def _extract_actual_provider(
        result: OrchestratorResult,
        key: str,
    ) -> str | None:
        """Extract actual provider used from RAG engine result data.

        The RAG adapter stores the provider it actually used (which may differ
        from the request-level provider due to A/B routing) in rag_data.
        """
        for er in result.engine_results:
            if er.data and key in er.data:
                return er.data[key]
        return None

    def _extract_search_mode(
        self,
        result: OrchestratorResult,
    ) -> tuple[str | None, str | None]:
        """Extract search mode from RAG engine results.

        Args:
            result: Orchestrator result with engine results.

        Returns:
            Tuple of (search_mode, search_notice).
            search_mode: 'hybrid', 'bm25_fallback', or 'bm25_only'
            search_notice: User-friendly notice if search was degraded
        """
        search_mode = None
        search_notice = None

        for engine_result in result.engine_results:
            if engine_result.data and engine_result.success:
                # Check for search mode in RAG results
                mode = engine_result.data.get("search_mode")
                if mode:
                    search_mode = mode
                    # Generate user-friendly notice for degraded modes
                    if mode == "bm25_fallback":
                        fallback_reason = engine_result.data.get(
                            "fallback_reason", "semantic search unavailable"
                        )
                        search_notice = (
                            f"Using keyword search only ({fallback_reason}). "
                            "Results may be less comprehensive."
                        )
                    elif mode == "bm25_only":
                        search_notice = (
                            "Using keyword search only. "
                            "Semantic search is being indexed."
                        )
                    break

        return search_mode, search_notice

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
                    bbox_ids=source.bbox_ids,
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
