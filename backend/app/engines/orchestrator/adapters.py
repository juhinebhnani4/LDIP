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
    Enhancement: Returns pre-computed contradictions from database.

    Uses StatementQueryEngine for entity-specific analysis, or
    ContradictionListService for pre-computed contradictions.
    """

    @property
    def engine_type(self) -> EngineType:
        return EngineType.CONTRADICTION

    def __init__(self) -> None:
        """Initialize contradiction engine adapter."""
        self._query_engine = None
        self._list_service = None
        logger.debug("contradiction_adapter_initialized")

    def _get_query_engine(self):
        """Lazy-load statement query engine."""
        if self._query_engine is None:
            from app.engines.contradiction import get_statement_query_engine

            self._query_engine = get_statement_query_engine()
        return self._query_engine

    def _get_list_service(self):
        """Lazy-load contradiction list service."""
        if self._list_service is None:
            from app.services.contradiction_list_service import ContradictionListService

            self._list_service = ContradictionListService()
        return self._list_service

    async def execute(
        self,
        matter_id: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> EngineExecutionResult:
        """Execute contradiction analysis for the matter.

        Returns pre-computed contradictions from the database, or
        entity-specific analysis if entity_id is provided.

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
                # Return pre-computed contradictions from database
                list_service = self._get_list_service()
                response = await list_service.get_all_contradictions(
                    matter_id=matter_id,
                    page=1,
                    per_page=10,  # Limit for chat
                )

                if response.data:
                    # Build human-readable summary
                    total_contradictions = sum(
                        len(entity.contradictions) for entity in response.data
                    )
                    entity_count = len(response.data)

                    # Build detailed answer
                    answer_parts = [
                        f"Found **{total_contradictions} contradiction(s)** "
                        f"involving **{entity_count} entities**:\n"
                    ]

                    for entity in response.data[:5]:  # Limit to 5 entities
                        entity_name = entity.entity_name
                        answer_parts.append(f"\n**{entity_name}:**")
                        for c in entity.contradictions[:2]:  # 2 per entity
                            severity = c.severity.value.upper()
                            stmt1 = c.statement_a.excerpt[:100] if c.statement_a else ""
                            stmt2 = c.statement_b.excerpt[:100] if c.statement_b else ""
                            answer_parts.append(
                                f"- [{severity}] \"{stmt1}...\" vs \"{stmt2}...\""
                            )

                    contradiction_data = {
                        "analysis_ready": True,
                        "answer": "\n".join(answer_parts),
                        "total_contradictions": total_contradictions,
                        "entity_count": entity_count,
                        "entities": [
                            {
                                "entity_id": e.entity_id,
                                "entity_name": e.entity_name,
                                "contradiction_count": len(e.contradictions),
                            }
                            for e in response.data
                        ],
                    }
                else:
                    contradiction_data = {
                        "analysis_ready": True,
                        "answer": "No contradictions have been detected in this matter's documents.",
                        "total_contradictions": 0,
                        "entity_count": 0,
                        "entities": [],
                    }

            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "contradiction_adapter_success",
                matter_id=matter_id,
                entity_id=entity_id,
                has_precomputed=entity_id is None,
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
        1. Hybrid search with library integration (searches matter + linked library docs)
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
            # Step 1: Hybrid search with library integration
            # Searches both matter documents AND linked library documents
            search = self._get_search()
            settings = get_settings()
            results = await search.search_with_library(
                query=query,
                matter_id=matter_id,
                limit=settings.rag_rerank_top_n,  # Final result limit
                library_limit=10,  # Library results before merge
            )

            # Step 2: Get document names for matter documents
            # Library documents already have titles in the result
            matter_doc_ids = list({
                item.document_id for item in results.results
                if not item.is_library
            })
            doc_names = await self._get_document_names(matter_doc_ids)

            # Step 3: Prepare chunks for generation with document names
            def get_doc_name(item):
                """Get document name - use library_document_title for library docs."""
                if item.is_library and item.library_document_title:
                    return item.library_document_title
                return doc_names.get(item.document_id, "Unknown Document")

            chunks_for_generation = [
                {
                    "chunk_id": item.id,
                    "document_id": item.document_id,
                    "document_name": get_doc_name(item),
                    "content": item.content,
                    "page_number": item.page_number,
                    "relevance_score": item.rrf_score,  # RRF score as relevance
                    "is_library": item.is_library,
                }
                for item in results.results
            ]

            # Step 4: Generate answer with Gemini
            generator = self._get_generator()
            answer_result = await generator.generate_answer(
                query=query,
                chunks=chunks_for_generation,
            )

            # Count library results for logging
            library_count = sum(1 for item in results.results if item.is_library)

            # Build response data
            rag_data = {
                "answer": answer_result.answer,
                "total_candidates": results.total_candidates,
                "rerank_used": False,  # RRF fusion, not Cohere rerank
                "generation_time_ms": answer_result.generation_time_ms,
                "model_used": answer_result.model_used,
                # Search mode info for frontend UX (rate limit fallback indicator)
                "search_mode": results.search_mode,
                "fallback_reason": results.fallback_reason,
                "library_results_count": library_count,
                "results": [
                    {
                        "chunk_id": item.id,
                        "document_id": item.document_id,
                        "document_name": get_doc_name(item),
                        "content": item.content[:500],  # Preview for UI
                        "page_number": item.page_number,
                        "relevance_score": item.rrf_score,
                        "is_library": item.is_library,
                    }
                    for item in results.results
                ],
            }

            execution_time_ms = int((time.time() - start_time) * 1000)

            # Calculate confidence based on top result relevance
            confidence = 0.7  # Default
            if results.results and results.results[0].rrf_score:
                # RRF scores are typically 0-0.05 range, normalize
                confidence = min(results.results[0].rrf_score * 10, 0.95)

            logger.info(
                "rag_adapter_success",
                matter_id=matter_id,
                total_candidates=results.total_candidates,
                results_returned=len(results.results),
                library_results=library_count,
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
# Document Discovery Engine Adapter
# =============================================================================


class DocumentDiscoveryEngineAdapter(EngineAdapter):
    """Adapter for Document Discovery queries (metadata-based).

    Handles queries like "What documents are in this matter?" by querying
    document metadata directly, without semantic search.
    """

    @property
    def engine_type(self) -> EngineType:
        return EngineType.DOCUMENT_DISCOVERY

    def __init__(self) -> None:
        """Initialize document discovery adapter."""
        self._supabase = None
        logger.debug("document_discovery_adapter_initialized")

    def _get_supabase(self):
        """Lazy-load Supabase client."""
        if self._supabase is None:
            from app.services.supabase.client import get_supabase_client
            self._supabase = get_supabase_client()
        return self._supabase

    async def execute(
        self,
        matter_id: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> EngineExecutionResult:
        """Execute document discovery query.

        Args:
            matter_id: Matter UUID.
            query: User's query.
            context: Optional context.

        Returns:
            EngineExecutionResult with document listing.
        """
        start_time = time.time()

        try:
            supabase = self._get_supabase()

            if supabase is None:
                return self._create_error_result(
                    error="Database client not configured",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            # Query documents for this matter
            result = (
                supabase.table("documents")
                .select("id, filename, document_type, page_count, status, created_at")
                .eq("matter_id", matter_id)
                .order("created_at", desc=True)
                .execute()
            )

            documents = result.data or []
            total_pages = sum(doc.get("page_count", 0) or 0 for doc in documents)

            # Build human-readable response
            if not documents:
                answer = "No documents have been uploaded to this matter yet."
            else:
                doc_list = []
                for i, doc in enumerate(documents, 1):
                    filename = doc.get("filename", "Unknown")
                    pages = doc.get("page_count", 0) or 0
                    status = doc.get("status", "unknown")
                    doc_list.append(f"{i}. **{filename}** ({pages} pages, {status})")

                answer = (
                    f"This matter contains **{len(documents)} document(s)** "
                    f"with a total of **{total_pages} pages**:\n\n"
                    + "\n".join(doc_list)
                )

            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "document_discovery_success",
                matter_id=matter_id,
                document_count=len(documents),
                total_pages=total_pages,
                execution_time_ms=execution_time_ms,
            )

            return self._create_success_result(
                data={
                    "answer": answer,
                    "documents": documents,
                    "total_documents": len(documents),
                    "total_pages": total_pages,
                },
                execution_time_ms=execution_time_ms,
                confidence=0.95,  # High confidence for metadata queries
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "document_discovery_error",
                matter_id=matter_id,
                error=str(e),
            )
            return self._create_error_result(
                error=str(e),
                execution_time_ms=execution_time_ms,
            )


# =============================================================================
# Entity Lookup Engine Adapter
# =============================================================================


class EntityLookupEngineAdapter(EngineAdapter):
    """Adapter for Entity Lookup queries (person/party focused).

    Handles queries like "Who are the parties?" by querying the entity
    database directly for comprehensive entity information.
    """

    @property
    def engine_type(self) -> EngineType:
        return EngineType.ENTITY_LOOKUP

    def __init__(self) -> None:
        """Initialize entity lookup adapter."""
        self._supabase = None
        logger.debug("entity_lookup_adapter_initialized")

    def _get_supabase(self):
        """Lazy-load Supabase client."""
        if self._supabase is None:
            from app.services.supabase.client import get_supabase_client
            self._supabase = get_supabase_client()
        return self._supabase

    async def execute(
        self,
        matter_id: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> EngineExecutionResult:
        """Execute entity lookup query.

        Args:
            matter_id: Matter UUID.
            query: User's query.
            context: Optional context.

        Returns:
            EngineExecutionResult with entity information.
        """
        start_time = time.time()

        try:
            supabase = self._get_supabase()

            if supabase is None:
                return self._create_error_result(
                    error="Database client not configured",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            # Query entities for this matter (identity_nodes table)
            result = (
                supabase.table("identity_nodes")
                .select("id, canonical_name, entity_type, aliases, metadata, mention_count")
                .eq("matter_id", matter_id)
                .order("mention_count", desc=True)
                .limit(50)
                .execute()
            )

            entities = result.data or []

            # Group entities by type
            entities_by_type: dict[str, list] = {}
            for entity in entities:
                entity_type = entity.get("entity_type", "other")
                if entity_type not in entities_by_type:
                    entities_by_type[entity_type] = []
                entities_by_type[entity_type].append(entity)

            # Build human-readable response
            if not entities:
                answer = "No entities have been identified in this matter yet."
            else:
                # Prioritize PERSON entities for party-related queries
                sections = []

                # Key parties (persons with roles)
                persons = entities_by_type.get("PERSON", [])
                if persons:
                    person_lines = []
                    for p in persons[:10]:  # Limit to top 10
                        name = p.get("canonical_name", "Unknown")
                        # Role might be in metadata
                        metadata = p.get("metadata") or {}
                        role = metadata.get("role", "") if isinstance(metadata, dict) else ""
                        mentions = p.get("mention_count", 0)
                        role_str = f" ({role})" if role else ""
                        person_lines.append(f"- **{name}**{role_str} - mentioned {mentions} times")
                    sections.append("**Key Persons:**\n" + "\n".join(person_lines))

                # Organizations
                orgs = entities_by_type.get("ORG", []) + entities_by_type.get("ORGANIZATION", [])
                if orgs:
                    org_lines = [f"- {o.get('canonical_name', 'Unknown')}" for o in orgs[:5]]
                    sections.append("**Organizations:**\n" + "\n".join(org_lines))

                answer = (
                    f"Found **{len(entities)} entities** in this matter:\n\n"
                    + "\n\n".join(sections)
                )

            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "entity_lookup_success",
                matter_id=matter_id,
                entity_count=len(entities),
                execution_time_ms=execution_time_ms,
            )

            return self._create_success_result(
                data={
                    "answer": answer,
                    "entities": entities,
                    "entities_by_type": entities_by_type,
                    "total_entities": len(entities),
                },
                execution_time_ms=execution_time_ms,
                confidence=0.9,
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "entity_lookup_error",
                matter_id=matter_id,
                error=str(e),
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
    EngineType.DOCUMENT_DISCOVERY: DocumentDiscoveryEngineAdapter,
    EngineType.ENTITY_LOOKUP: EntityLookupEngineAdapter,
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


@lru_cache(maxsize=6)
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
