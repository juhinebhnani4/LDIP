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
from app.core.ocr_cleaner import clean_for_display
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

        Provides lawyer-focused analysis of citation ISSUES, not just counts.

        Args:
            matter_id: Matter UUID.
            query: User's query (used for logging).
            context: Optional context.

        Returns:
            EngineExecutionResult with citation issues analysis.
        """
        start_time = time.time()

        try:
            from app.models.citation import ActResolutionStatus

            discovery = self._get_discovery()
            report = await discovery.get_discovery_report(
                matter_id=matter_id,
                include_available=True,
            )

            # Categorize by resolution status for issue analysis
            missing_acts = []
            available_acts = []
            needs_manual_upload = []
            skipped_acts = []

            for item in report:
                act_info = {
                    "name": item.act_name,
                    "citations": item.citation_count,
                    "has_document": item.act_document_id is not None,
                }
                if item.resolution_status == ActResolutionStatus.MISSING:
                    missing_acts.append(act_info)
                elif item.resolution_status == ActResolutionStatus.NOT_ON_INDIACODE:
                    needs_manual_upload.append(act_info)
                elif item.resolution_status == ActResolutionStatus.SKIPPED:
                    skipped_acts.append(act_info)
                elif item.resolution_status in (
                    ActResolutionStatus.AVAILABLE,
                    ActResolutionStatus.AUTO_FETCHED,
                ):
                    available_acts.append(act_info)

            # Calculate totals
            total_citations = sum(item.citation_count for item in report)
            unverifiable_citations = sum(a["citations"] for a in missing_acts)
            unverifiable_citations += sum(a["citations"] for a in needs_manual_upload)

            # Build lawyer-focused answer about ISSUES
            answer_parts = []

            if missing_acts or needs_manual_upload:
                issue_count = len(missing_acts) + len(needs_manual_upload)
                answer_parts.append(
                    f"**{issue_count} Act(s) Missing** - {unverifiable_citations} citations cannot be verified:\n"
                )
                # List missing acts sorted by citation count
                all_missing = sorted(
                    missing_acts + needs_manual_upload,
                    key=lambda x: x["citations"],
                    reverse=True,
                )
                for act in all_missing[:5]:  # Top 5
                    answer_parts.append(f"- **{act['name']}** ({act['citations']} citations)")
                if len(all_missing) > 5:
                    answer_parts.append(f"- ...and {len(all_missing) - 5} more")
                answer_parts.append("")

            if available_acts:
                verified_citations = sum(a["citations"] for a in available_acts)
                answer_parts.append(
                    f"**{len(available_acts)} Act(s) Available** - {verified_citations} citations can be verified"
                )

            if skipped_acts:
                skipped_citations = sum(a["citations"] for a in skipped_acts)
                answer_parts.append(
                    f"\n**{len(skipped_acts)} Act(s) Skipped** - {skipped_citations} citations marked as skip"
                )

            # Summary recommendation
            if missing_acts or needs_manual_upload:
                answer_parts.append(
                    f"\n**Action Required:** Upload missing Act documents to verify {unverifiable_citations} citations."
                )
            elif not report:
                answer_parts.append("No Act citations found in this matter.")
            else:
                answer_parts.append("\n**All referenced Acts are available for verification.**")

            answer = "\n".join(answer_parts)

            # Build data for API
            citations_data = {
                "answer": answer,
                "total_acts": len(report),
                "total_citations": total_citations,
                "missing_acts_count": len(missing_acts) + len(needs_manual_upload),
                "unverifiable_citations": unverifiable_citations,
                "available_acts_count": len(available_acts),
                "acts": [
                    {
                        "act_name": item.act_name,
                        "citation_count": item.citation_count,
                        "resolution_status": item.resolution_status.value,
                        "act_document_id": item.act_document_id,
                    }
                    for item in report
                ],
            }

            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "citation_adapter_success",
                matter_id=matter_id,
                total_acts=len(report),
                total_citations=total_citations,
                missing_acts=len(missing_acts),
                execution_time_ms=execution_time_ms,
            )

            return self._create_success_result(
                data=citations_data,
                execution_time_ms=execution_time_ms,
                confidence=0.95,
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.error(
                "citation_adapter_error",
                matter_id=matter_id,
                error=str(e),
                error_type=type(e).__name__,
                execution_time_ms=execution_time_ms,
                exc_info=True,
            )

            return self._create_error_result(
                error=f"Citation engine error: {e}",
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
                            # Clean OCR artifacts from excerpts before display
                            stmt1_raw = c.statement_a.excerpt[:100] if c.statement_a else ""
                            stmt2_raw = c.statement_b.excerpt[:100] if c.statement_b else ""
                            stmt1 = clean_for_display(stmt1_raw)
                            stmt2 = clean_for_display(stmt2_raw)
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

    Handles two types of queries:
    1. Specific entity questions: "Who is Respondent No. 2?" -> searches for match
    2. General listing: "Who are the parties?" -> lists all entities

    Uses fuzzy matching to find entities by name, alias, or role.
    """

    @property
    def engine_type(self) -> EngineType:
        return EngineType.ENTITY_LOOKUP

    # Common patterns for extracting entity references from queries
    ENTITY_PATTERNS = [
        r"who\s+is\s+(?:the\s+)?(.+?)(?:\?|$)",  # "who is X?" or "who is the X?"
        r"what\s+is\s+(.+?)(?:\?|$)",  # "what is X?"
        r"tell\s+me\s+about\s+(.+?)(?:\?|$)",  # "tell me about X"
        r"information\s+(?:about|on)\s+(.+?)(?:\?|$)",  # "information about X"
        r"describe\s+(.+?)(?:\?|$)",  # "describe X"
    ]

    def __init__(self) -> None:
        """Initialize entity lookup adapter."""
        self._supabase = None
        self._compiled_patterns = None
        self._search = None
        self._generator = None
        logger.debug("entity_lookup_adapter_initialized")

    def _get_search(self):
        """Lazy-load hybrid search service for entity context retrieval."""
        if self._search is None:
            from app.services.rag import get_hybrid_search_service
            self._search = get_hybrid_search_service()
        return self._search

    def _get_generator(self):
        """Lazy-load RAG answer generator for comprehensive entity answers."""
        if self._generator is None:
            from app.engines.rag.generator import get_rag_generator
            self._generator = get_rag_generator()
        return self._generator

    def _get_supabase(self):
        """Lazy-load Supabase client."""
        if self._supabase is None:
            from app.services.supabase.client import get_supabase_client
            self._supabase = get_supabase_client()
        return self._supabase

    def _get_patterns(self):
        """Get compiled regex patterns."""
        if self._compiled_patterns is None:
            import re
            self._compiled_patterns = [
                re.compile(p, re.IGNORECASE) for p in self.ENTITY_PATTERNS
            ]
        return self._compiled_patterns

    def _extract_entity_reference(self, query: str) -> str | None:
        """Extract the entity being asked about from the query.

        Args:
            query: User's question.

        Returns:
            Extracted entity reference or None if not a specific entity query.
        """
        query_lower = query.lower().strip()

        # Check for specific entity question patterns
        for pattern in self._get_patterns():
            match = pattern.search(query_lower)
            if match:
                return match.group(1).strip()

        return None

    def _normalize_for_matching(self, text: str) -> str:
        """Normalize text for fuzzy matching.

        Args:
            text: Text to normalize.

        Returns:
            Normalized text (lowercase, punctuation and extra spaces removed).
        """
        import re
        # Lowercase and normalize whitespace
        normalized = text.lower().strip()
        # Remove common punctuation
        normalized = re.sub(r'[.,;:!?\-\'\"()]', '', normalized)
        # Normalize spaces around numbers (e.g., "no 2" -> "no2", "no.2" -> "no2")
        normalized = re.sub(r'\s+', '', normalized)  # Remove all spaces for matching
        return normalized

    def _find_matching_entity(
        self,
        entity_ref: str,
        entities: list[dict],
    ) -> dict | None:
        """Find entity matching the reference using fuzzy matching.

        Searches canonical_name, aliases, and metadata.role.

        Args:
            entity_ref: Entity reference from query.
            entities: List of entities to search.

        Returns:
            Best matching entity or None.
        """
        ref_normalized = self._normalize_for_matching(entity_ref)

        best_match = None
        best_score = 0

        for entity in entities:
            # Check canonical name
            canonical = entity.get("canonical_name", "")
            canonical_norm = self._normalize_for_matching(canonical)

            # Exact match
            if ref_normalized == canonical_norm:
                return entity

            # Substring match (entity ref in canonical or vice versa)
            if ref_normalized in canonical_norm or canonical_norm in ref_normalized:
                score = len(ref_normalized) / max(len(canonical_norm), 1)
                if score > best_score:
                    best_score = score
                    best_match = entity

            # Check aliases
            aliases = entity.get("aliases") or []
            for alias in aliases:
                alias_norm = self._normalize_for_matching(alias)
                if ref_normalized == alias_norm:
                    return entity
                if ref_normalized in alias_norm or alias_norm in ref_normalized:
                    score = len(ref_normalized) / max(len(alias_norm), 1)
                    if score > best_score:
                        best_score = score
                        best_match = entity

            # Check metadata.role (e.g., "Respondent No. 2")
            metadata = entity.get("metadata") or {}
            if isinstance(metadata, dict):
                role = metadata.get("role", "")
                if role:
                    role_norm = self._normalize_for_matching(role)
                    if ref_normalized == role_norm:
                        return entity
                    if ref_normalized in role_norm or role_norm in ref_normalized:
                        score = len(ref_normalized) / max(len(role_norm), 1)
                        if score > best_score:
                            best_score = score
                            best_match = entity

        # Return best match if score is reasonable (> 0.3)
        return best_match if best_score > 0.3 else None

    def _format_entity_answer(self, entity: dict, all_entities: list[dict]) -> str:
        """Format a detailed answer about a specific entity.

        Args:
            entity: The matched entity.
            all_entities: All entities for context.

        Returns:
            Formatted answer string.
        """
        name = entity.get("canonical_name", "Unknown")
        entity_type = entity.get("entity_type", "UNKNOWN")
        mentions = entity.get("mention_count", 0)
        aliases = entity.get("aliases") or []
        metadata = entity.get("metadata") or {}

        # Build answer
        parts = [f"**{name}**"]

        # Add type
        type_display = entity_type.replace("_", " ").title()
        parts.append(f"\n- **Type:** {type_display}")

        # Add role if available
        if isinstance(metadata, dict) and metadata.get("role"):
            parts.append(f"- **Role:** {metadata['role']}")

        # Add aliases if any
        if aliases:
            alias_str = ", ".join(aliases[:5])
            parts.append(f"- **Also known as:** {alias_str}")

        # Add mention count
        parts.append(f"- **Mentioned:** {mentions} times in the documents")

        # Check for related entities (same type, high mentions)
        related = [
            e for e in all_entities
            if e.get("id") != entity.get("id")
            and e.get("entity_type") == entity_type
        ][:3]
        if related:
            related_names = [e.get("canonical_name", "Unknown") for e in related]
            parts.append(f"\n**Other {type_display}s:** {', '.join(related_names)}")

        return "\n".join(parts)

    async def _get_entity_context_from_rag(
        self,
        entity: dict,
        matter_id: str,
        original_query: str,
    ) -> str | None:
        """Get comprehensive entity context using RAG search.

        Searches for chunks mentioning the entity and synthesizes a comprehensive
        answer about who they are and what they did in the case.

        Args:
            entity: The matched entity with canonical_name, aliases, etc.
            matter_id: Matter UUID.
            original_query: The user's original query.

        Returns:
            Comprehensive answer string, or None if RAG search fails.
        """
        try:
            entity_name = entity.get("canonical_name", "")
            aliases = entity.get("aliases") or []

            # Build search query using entity name
            # Use the entity name as the search query to find relevant chunks
            search_query = f"who is {entity_name} and what is their role in this case"

            logger.debug(
                "entity_lookup_rag_search_start",
                matter_id=matter_id,
                entity_name=entity_name,
                search_query=search_query,
            )

            # Do hybrid search for entity context
            search = self._get_search()
            from app.core.config import get_settings
            settings = get_settings()

            results = await search.search_with_library(
                query=search_query,
                matter_id=matter_id,
                limit=8,  # Get top 8 relevant chunks
                library_limit=0,  # No library docs for entity context
            )

            if not results.results:
                logger.debug(
                    "entity_lookup_rag_no_results",
                    matter_id=matter_id,
                    entity_name=entity_name,
                )
                return None

            # Get document names for citations
            supabase = self._get_supabase()
            doc_ids = list({item.document_id for item in results.results})
            doc_names_result = (
                supabase.table("documents")
                .select("id, filename")
                .in_("id", doc_ids)
                .execute()
            )
            doc_names = {
                str(doc["id"]): doc.get("filename", "Unknown Document")
                for doc in (doc_names_result.data or [])
            }

            # Prepare chunks for generation
            chunks_for_generation = [
                {
                    "chunk_id": item.id,
                    "document_id": item.document_id,
                    "document_name": doc_names.get(item.document_id, "Unknown Document"),
                    "content": item.content,
                    "page_number": item.page_number,
                    "relevance_score": item.rrf_score,
                    "is_library": False,
                }
                for item in results.results
            ]

            # Build entity metadata for context
            entity_type = entity.get("entity_type", "UNKNOWN").replace("_", " ").title()
            metadata = entity.get("metadata") or {}
            role = metadata.get("role", "") if isinstance(metadata, dict) else ""
            alias_str = ", ".join(aliases[:3]) if aliases else "none"

            # Create enhanced query with entity context for better generation
            enhanced_query = (
                f"Based on the documents, provide a comprehensive answer about {entity_name}. "
                f"This is a {entity_type}"
                + (f" with role '{role}'" if role else "")
                + f". Also known as: {alias_str}. "
                f"Include: their role in the case, key actions they took, relationships with other parties, "
                f"and any significant events involving them."
            )

            # Generate comprehensive answer
            generator = self._get_generator()
            answer_result = await generator.generate_answer(
                query=enhanced_query,
                chunks=chunks_for_generation,
            )

            logger.info(
                "entity_lookup_rag_success",
                matter_id=matter_id,
                entity_name=entity_name,
                chunks_used=len(results.results),
                answer_length=len(answer_result.answer),
            )

            return answer_result.answer

        except Exception as e:
            logger.warning(
                "entity_lookup_rag_error",
                matter_id=matter_id,
                entity_name=entity.get("canonical_name", "unknown"),
                error=str(e),
            )
            return None

    async def execute(
        self,
        matter_id: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> EngineExecutionResult:
        """Execute entity lookup query.

        Handles both specific entity questions and general listing.

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

            if not entities:
                answer = "No entities have been identified in this matter yet."
                return self._create_success_result(
                    data={
                        "answer": answer,
                        "entities": [],
                        "entities_by_type": {},
                        "total_entities": 0,
                        "query_type": "listing",
                    },
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    confidence=0.9,
                )

            # Check if this is a specific entity question
            entity_ref = self._extract_entity_reference(query)

            if entity_ref:
                # Specific entity lookup
                matched_entity = self._find_matching_entity(entity_ref, entities)

                if matched_entity:
                    # Try to get comprehensive context from RAG
                    rag_answer = await self._get_entity_context_from_rag(
                        entity=matched_entity,
                        matter_id=matter_id,
                        original_query=query,
                    )

                    if rag_answer:
                        # Use RAG-synthesized comprehensive answer
                        # Add entity metadata header for context
                        entity_name = matched_entity.get("canonical_name", "Unknown")
                        entity_type = matched_entity.get("entity_type", "UNKNOWN").replace("_", " ").title()
                        aliases = matched_entity.get("aliases") or []
                        alias_str = ", ".join(aliases[:3]) if aliases else None

                        header = f"**{entity_name}** ({entity_type})"
                        if alias_str:
                            header += f"\n*Also known as: {alias_str}*"

                        answer = f"{header}\n\n{rag_answer}"
                        query_type = "specific_comprehensive"
                        confidence = 0.95
                    else:
                        # Fall back to basic entity info if RAG fails
                        answer = self._format_entity_answer(matched_entity, entities)
                        query_type = "specific"
                        confidence = 0.85
                else:
                    # No match found - provide suggestions
                    top_entities = [e.get("canonical_name", "Unknown") for e in entities[:5]]
                    answer = (
                        f"Could not find an entity matching **\"{entity_ref}\"** in this matter.\n\n"
                        f"**Available entities include:**\n"
                        + "\n".join(f"- {name}" for name in top_entities)
                    )
                    query_type = "specific_no_match"
                    confidence = 0.7
            else:
                # General entity listing
                entities_by_type: dict[str, list] = {}
                for entity in entities:
                    entity_type = entity.get("entity_type", "other")
                    if entity_type not in entities_by_type:
                        entities_by_type[entity_type] = []
                    entities_by_type[entity_type].append(entity)

                sections = []

                # Key parties (persons with roles)
                persons = entities_by_type.get("PERSON", [])
                if persons:
                    person_lines = []
                    for p in persons[:10]:
                        name = p.get("canonical_name", "Unknown")
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
                query_type = "listing"
                confidence = 0.9

            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "entity_lookup_success",
                matter_id=matter_id,
                entity_count=len(entities),
                query_type=query_type,
                entity_ref=entity_ref,
                execution_time_ms=execution_time_ms,
            )

            return self._create_success_result(
                data={
                    "answer": answer,
                    "entities": entities,
                    "total_entities": len(entities),
                    "query_type": query_type,
                },
                execution_time_ms=execution_time_ms,
                confidence=confidence,
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
