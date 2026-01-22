"""Engine Adapters for normalizing engine interfaces.

Story 6-2: Engine Execution Ordering (AC: #1-4)

Adapters wrap existing engines with a common interface for the orchestrator.
Each adapter handles the engine-specific call pattern and normalizes results.

CRITICAL: Adapters must propagate matter_id to ensure matter isolation.
"""

import time
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

import structlog

from app.core.config import get_settings
from app.models.orchestrator import (
    EngineExecutionResult,
    EngineType,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Abstract Base Adapter (Task 5.1)
# =============================================================================


class EngineAdapter(ABC):
    """Abstract adapter for normalizing engine interfaces.

    Story 6-2: Provides common interface for all engine types.

    Implementations must:
    - Call the underlying engine with matter_id
    - Return EngineExecutionResult with success/failure status
    - Track execution time

    Example:
        >>> adapter = CitationEngineAdapter()
        >>> result = await adapter.execute(
        ...     matter_id="matter-123",
        ...     query="What citations are in the case?",
        ... )
        >>> result.success
        True
    """

    @property
    @abstractmethod
    def engine_type(self) -> EngineType:
        """Get the engine type this adapter handles."""
        ...

    @abstractmethod
    async def execute(
        self,
        matter_id: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> EngineExecutionResult:
        """Execute the underlying engine and return normalized result.

        Args:
            matter_id: Matter UUID for isolation.
            query: User's query.
            context: Optional conversation context.

        Returns:
            EngineExecutionResult with success status and data/error.
        """
        ...

    def _create_success_result(
        self,
        data: dict[str, Any],
        execution_time_ms: int,
        confidence: float | None = None,
    ) -> EngineExecutionResult:
        """Create a successful result.

        Args:
            data: Engine-specific result data.
            execution_time_ms: Execution time in milliseconds.
            confidence: Optional confidence score.

        Returns:
            Successful EngineExecutionResult.
        """
        return EngineExecutionResult(
            engine=self.engine_type,
            success=True,
            data=data,
            execution_time_ms=execution_time_ms,
            confidence=confidence,
        )

    def _create_error_result(
        self,
        error: str,
        execution_time_ms: int,
    ) -> EngineExecutionResult:
        """Create a failed result.

        Args:
            error: Error message.
            execution_time_ms: Execution time in milliseconds.

        Returns:
            Failed EngineExecutionResult.
        """
        return EngineExecutionResult(
            engine=self.engine_type,
            success=False,
            error=error,
            execution_time_ms=execution_time_ms,
        )


# =============================================================================
# Citation Engine Adapter (Task 5.2)
# =============================================================================


class CitationEngineAdapter(EngineAdapter):
    """Adapter for Citation Verification Engine (Epic 3).

    Story 6-2: Wraps citation discovery and verification for orchestrator.

    Uses ActDiscoveryService for citation queries.
    """

    @property
    def engine_type(self) -> EngineType:
        return EngineType.CITATION

    def __init__(self) -> None:
        """Initialize citation engine adapter."""
        self._discovery = None
        logger.debug("citation_adapter_initialized")

    def _get_discovery(self):
        """Lazy-load citation discovery service."""
        if self._discovery is None:
            from app.engines.citation import get_act_discovery_service

            self._discovery = get_act_discovery_service()
        return self._discovery

    async def execute(
        self,
        matter_id: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> EngineExecutionResult:
        """Execute citation discovery for the matter.

        Args:
            matter_id: Matter UUID.
            query: User's query (used for logging).
            context: Optional context.

        Returns:
            EngineExecutionResult with citation discovery data.
        """
        start_time = time.time()

        try:
            discovery = self._get_discovery()
            report = await discovery.get_discovery_report(
                matter_id=matter_id,
                include_available=True,
            )

            # Convert report to dict format
            citations_data = {
                "total_acts": len(report),
                "acts": [
                    {
                        "act_name": item.act_name,
                        "act_name_normalized": item.act_name_normalized,
                        "citation_count": item.citation_count,
                        "resolution_status": item.resolution_status.value,
                        "user_action": item.user_action.value if item.user_action else None,
                        "referenced_sections": item.referenced_sections,
                    }
                    for item in report
                ],
            }

            # Calculate total citations
            total_citations = sum(item.citation_count for item in report)
            citations_data["total_citations"] = total_citations

            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "citation_adapter_success",
                matter_id=matter_id,
                total_acts=len(report),
                total_citations=total_citations,
                execution_time_ms=execution_time_ms,
            )

            return self._create_success_result(
                data=citations_data,
                execution_time_ms=execution_time_ms,
                confidence=0.95,  # High confidence for citation discovery
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.error(
                "citation_adapter_error",
                matter_id=matter_id,
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

            return self._create_error_result(
                error=str(e),
                execution_time_ms=execution_time_ms,
            )


# =============================================================================
# Timeline Engine Adapter (Task 5.3)
# =============================================================================


class TimelineEngineAdapter(EngineAdapter):
    """Adapter for Timeline Construction Engine (Epic 4).

    Story 6-2: Wraps timeline builder for orchestrator.

    Uses TimelineBuilder for timeline queries.
    """

    @property
    def engine_type(self) -> EngineType:
        return EngineType.TIMELINE

    def __init__(self) -> None:
        """Initialize timeline engine adapter."""
        self._builder = None
        logger.debug("timeline_adapter_initialized")

    def _get_builder(self):
        """Lazy-load timeline builder."""
        if self._builder is None:
            from app.engines.timeline import get_timeline_builder

            self._builder = get_timeline_builder()
        return self._builder

    async def execute(
        self,
        matter_id: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> EngineExecutionResult:
        """Execute timeline construction for the matter.

        Args:
            matter_id: Matter UUID.
            query: User's query (used for logging).
            context: Optional context.

        Returns:
            EngineExecutionResult with timeline data.
        """
        start_time = time.time()

        try:
            builder = self._get_builder()
            settings = get_settings()
            timeline = await builder.build_timeline(
                matter_id=matter_id,
                include_entities=True,
                page=1,
                per_page=settings.timeline_default_page_size,
            )

            # Convert timeline to dict format
            timeline_data = {
                "total_events": timeline.statistics.total_events,
                "events": [
                    {
                        "event_id": event.event_id,
                        "event_date": str(event.event_date),
                        "event_type": event.event_type.value,
                        "description": event.description,
                        "document_id": event.document_id,
                        "document_name": event.document_name,
                        "source_page": event.source_page,
                        "confidence": event.confidence,
                        "entities": [
                            {
                                "entity_id": e.entity_id,
                                "name": e.canonical_name,
                                "type": e.entity_type.value,
                            }
                            for e in event.entities
                        ],
                    }
                    for event in timeline.events
                ],
                "date_range": {
                    "start": str(timeline.statistics.date_range_start)
                    if timeline.statistics.date_range_start else None,
                    "end": str(timeline.statistics.date_range_end)
                    if timeline.statistics.date_range_end else None,
                },
                "events_by_type": timeline.statistics.events_by_type,
            }

            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "timeline_adapter_success",
                matter_id=matter_id,
                total_events=timeline.statistics.total_events,
                execution_time_ms=execution_time_ms,
            )

            return self._create_success_result(
                data=timeline_data,
                execution_time_ms=execution_time_ms,
                confidence=0.9,
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.error(
                "timeline_adapter_error",
                matter_id=matter_id,
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

            return self._create_error_result(
                error=str(e),
                execution_time_ms=execution_time_ms,
            )


# =============================================================================
# Contradiction Engine Adapter (Task 5.4)
# =============================================================================


class ContradictionEngineAdapter(EngineAdapter):
    """Adapter for Contradiction Detection Engine (Epic 5).

    Story 6-2: Wraps contradiction detection for orchestrator.

    Uses StatementQueryEngine to find entity-grouped statements.
    Full contradiction detection requires entity_id which comes from
    the query context.
    """

    @property
    def engine_type(self) -> EngineType:
        return EngineType.CONTRADICTION

    def __init__(self) -> None:
        """Initialize contradiction engine adapter."""
        self._query_engine = None
        logger.debug("contradiction_adapter_initialized")

    def _get_query_engine(self):
        """Lazy-load statement query engine."""
        if self._query_engine is None:
            from app.engines.contradiction import get_statement_query_engine

            self._query_engine = get_statement_query_engine()
        return self._query_engine

    async def execute(
        self,
        matter_id: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> EngineExecutionResult:
        """Execute contradiction analysis for the matter.

        If entity_id is provided in context, performs entity-specific
        contradiction analysis. Otherwise, returns general capability info.

        Args:
            matter_id: Matter UUID.
            query: User's query.
            context: Optional context with entity_id.

        Returns:
            EngineExecutionResult with contradiction data.
        """
        start_time = time.time()

        try:
            # Check if entity_id is provided in context
            entity_id = context.get("entity_id") if context else None

            if entity_id:
                # Entity-specific contradiction analysis
                query_engine = self._get_query_engine()
                statements = await query_engine.get_statements_for_entity(
                    entity_id=entity_id,
                    matter_id=matter_id,
                )

                contradiction_data = {
                    "entity_id": entity_id,
                    "total_documents": len(statements.documents),
                    "total_statements": statements.total_statements,
                    "documents": [
                        {
                            "document_id": doc.document_id,
                            "document_name": doc.document_name,
                            "statement_count": doc.statement_count,
                        }
                        for doc in statements.documents
                    ],
                    "analysis_ready": True,
                    "message": f"Found {statements.total_statements} statements for entity analysis",
                }
            else:
                # No entity specified - return capability info
                contradiction_data = {
                    "analysis_ready": False,
                    "message": "Contradiction analysis requires an entity to analyze. "
                              "Please specify which person or entity you want to check for contradictions.",
                    "suggestion": "Try asking about a specific person, e.g., "
                                 "'Are there contradictions in what John Doe said?'",
                }

            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "contradiction_adapter_success",
                matter_id=matter_id,
                entity_id=entity_id,
                execution_time_ms=execution_time_ms,
            )

            return self._create_success_result(
                data=contradiction_data,
                execution_time_ms=execution_time_ms,
                confidence=0.85,
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.error(
                "contradiction_adapter_error",
                matter_id=matter_id,
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

            return self._create_error_result(
                error=str(e),
                execution_time_ms=execution_time_ms,
            )


# =============================================================================
# RAG Engine Adapter (Task 5.5)
# =============================================================================


class RAGEngineAdapter(EngineAdapter):
    """Adapter for RAG Hybrid Search + Answer Generation (Epic 2B, Story 6-2).

    Story 6-2: Wraps hybrid search with reranking and LLM answer synthesis.

    Pipeline:
    1. Hybrid search (BM25 + semantic) with RRF fusion
    2. Cohere reranking for top results
    3. Gemini answer generation from retrieved chunks
    """

    @property
    def engine_type(self) -> EngineType:
        return EngineType.RAG

    def __init__(self) -> None:
        """Initialize RAG engine adapter."""
        self._search = None
        self._generator = None
        self._supabase = None
        logger.debug("rag_adapter_initialized")

    def _get_search(self):
        """Lazy-load hybrid search service."""
        if self._search is None:
            from app.services.rag import get_hybrid_search_service

            self._search = get_hybrid_search_service()
        return self._search

    def _get_generator(self):
        """Lazy-load RAG answer generator."""
        if self._generator is None:
            from app.engines.rag.generator import get_rag_generator

            self._generator = get_rag_generator()
        return self._generator

    def _get_supabase(self):
        """Lazy-load Supabase client for document lookups."""
        if self._supabase is None:
            from app.services.supabase.client import get_supabase_client

            self._supabase = get_supabase_client()
        return self._supabase

    async def _get_document_names(
        self,
        document_ids: list[str],
    ) -> dict[str, str]:
        """Fetch document filenames for given IDs.

        Args:
            document_ids: List of document UUIDs.

        Returns:
            Dict mapping document_id to filename.
        """
        if not document_ids:
            logger.debug("rag_document_names_empty_ids")
            return {}

        try:
            supabase = self._get_supabase()
            logger.debug(
                "rag_document_names_query",
                document_ids=[d[:8] for d in document_ids],
            )
            result = (
                supabase.table("documents")
                .select("id, filename")
                .in_("id", document_ids)
                .execute()
            )

            # DEBUG: Log what we got back from the database
            logger.debug(
                "rag_document_names_result",
                result_count=len(result.data) if result.data else 0,
                sample_data=[
                    {"id": doc.get("id", "")[:8], "filename": doc.get("filename")}
                    for doc in (result.data or [])[:3]
                ],
            )

            doc_names = {
                str(doc["id"]): doc.get("filename", "Unknown Document")
                for doc in result.data
            }

            logger.debug(
                "rag_document_names_mapped",
                mapped_count=len(doc_names),
                sample_names=list(doc_names.items())[:2],
            )

            return doc_names
        except Exception as e:
            logger.warning(
                "rag_document_names_failed",
                error=str(e),
                error_type=type(e).__name__,
                document_count=len(document_ids),
            )
            return {}

    async def execute(
        self,
        matter_id: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> EngineExecutionResult:
        """Execute RAG search and generate answer.

        Pipeline:
        1. Hybrid search with reranking
        2. Fetch document names for citations
        3. Generate grounded answer with Gemini

        Args:
            matter_id: Matter UUID.
            query: User's query.
            context: Optional context.

        Returns:
            EngineExecutionResult with generated answer and sources.
        """
        start_time = time.time()

        try:
            # Step 1: Hybrid search with reranking
            search = self._get_search()
            settings = get_settings()
            results = await search.search_with_rerank(
                matter_id=matter_id,
                query=query,
                hybrid_limit=settings.rag_search_limit,
                rerank_top_n=settings.rag_rerank_top_n,
            )

            # Step 2: Get document names for citations
            document_ids = list({item.document_id for item in results.results})
            doc_names = await self._get_document_names(document_ids)

            # Step 3: Prepare chunks for generation with document names
            chunks_for_generation = [
                {
                    "chunk_id": item.id,
                    "document_id": item.document_id,
                    "document_name": doc_names.get(item.document_id, "Unknown Document"),
                    "content": item.content,
                    "page_number": item.page_number,
                    "relevance_score": item.relevance_score,
                }
                for item in results.results
            ]

            # Step 4: Generate answer with Gemini
            generator = self._get_generator()
            answer_result = await generator.generate_answer(
                query=query,
                chunks=chunks_for_generation,
            )

            # Build response data
            rag_data = {
                "answer": answer_result.answer,
                "total_candidates": results.total_candidates,
                "rerank_used": results.rerank_used,
                "generation_time_ms": answer_result.generation_time_ms,
                "model_used": answer_result.model_used,
                "results": [
                    {
                        "chunk_id": item.id,
                        "document_id": item.document_id,
                        "document_name": doc_names.get(item.document_id, "Unknown Document"),
                        "content": item.content[:500],  # Preview for UI
                        "page_number": item.page_number,
                        "relevance_score": item.relevance_score,
                    }
                    for item in results.results
                ],
            }

            execution_time_ms = int((time.time() - start_time) * 1000)

            # Calculate confidence based on top result relevance
            confidence = 0.7  # Default
            if results.results and results.results[0].relevance_score:
                confidence = min(results.results[0].relevance_score, 0.95)

            logger.info(
                "rag_adapter_success",
                matter_id=matter_id,
                total_candidates=results.total_candidates,
                results_returned=len(results.results),
                rerank_used=results.rerank_used,
                answer_length=len(answer_result.answer),
                execution_time_ms=execution_time_ms,
            )

            return self._create_success_result(
                data=rag_data,
                execution_time_ms=execution_time_ms,
                confidence=confidence,
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.error(
                "rag_adapter_error",
                matter_id=matter_id,
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

            return self._create_error_result(
                error=str(e),
                execution_time_ms=execution_time_ms,
            )


# =============================================================================
# Adapter Registry (Task 5.6)
# =============================================================================

# Registry mapping engine types to adapter classes
ADAPTER_REGISTRY: dict[EngineType, type[EngineAdapter]] = {
    EngineType.CITATION: CitationEngineAdapter,
    EngineType.TIMELINE: TimelineEngineAdapter,
    EngineType.CONTRADICTION: ContradictionEngineAdapter,
    EngineType.RAG: RAGEngineAdapter,
}


def get_adapter(engine_type: EngineType) -> EngineAdapter:
    """Get adapter instance for engine type.

    Args:
        engine_type: Engine type to get adapter for.

    Returns:
        EngineAdapter instance.

    Raises:
        ValueError: If engine type has no registered adapter.
    """
    adapter_class = ADAPTER_REGISTRY.get(engine_type)
    if adapter_class is None:
        raise ValueError(f"No adapter registered for engine type: {engine_type.value}")
    return adapter_class()


@lru_cache(maxsize=4)
def get_cached_adapter(engine_type: EngineType) -> EngineAdapter:
    """Get cached adapter instance for engine type.

    Caches adapter instances to avoid repeated initialization.

    Args:
        engine_type: Engine type to get adapter for.

    Returns:
        EngineAdapter instance.
    """
    return get_adapter(engine_type)


def clear_adapter_cache() -> None:
    """Clear the adapter cache (for testing/reload)."""
    get_cached_adapter.cache_clear()
