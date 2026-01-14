"""Result Aggregator for combining engine outputs.

Story 6-2: Engine Execution Ordering (AC: #4)
Story 8-3: Language Policing Integration (AC: #7)

Aggregates results from multiple engines into a unified response:
- Merges and deduplicates source references
- Calculates overall confidence (weighted average)
- Formats unified human-readable response
- Applies language policing to sanitize output (Story 8-3)

CRITICAL: Sources must include engine attribution for traceability.
CRITICAL: All unified_response text must pass through language policing (Story 8-3).
"""

from functools import lru_cache
from typing import Any

import structlog

from app.core.config import get_settings
from app.models.orchestrator import (
    EngineExecutionResult,
    EngineType,
    OrchestratorResult,
    SourceReference,
)
from app.services.safety.language_police import (
    LanguagePolice,
    get_language_police,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Engine Weights for Confidence Calculation
# =============================================================================

# Weights for calculating overall confidence
# Higher weight = more influence on final confidence
ENGINE_CONFIDENCE_WEIGHTS: dict[EngineType, float] = {
    EngineType.CITATION: 1.0,
    EngineType.TIMELINE: 1.0,
    EngineType.CONTRADICTION: 1.2,  # Slightly higher - contradiction finding is important
    EngineType.RAG: 0.8,  # Slightly lower - general search is less precise
}


# =============================================================================
# Result Aggregator (Task 4.1-4.6)
# =============================================================================


class ResultAggregator:
    """Aggregates results from multiple engines into unified response.

    Story 6-2: Combines engine outputs for coherent user experience.
    Story 8-3: Applies language policing to sanitize output.

    Pipeline:
    1. Separate successful and failed results
    2. Merge and deduplicate source references
    3. Calculate weighted confidence score
    4. Format unified human-readable response
    5. Apply language policing to sanitize output (Story 8-3)

    Example:
        >>> aggregator = get_result_aggregator()
        >>> orchestrator_result = await aggregator.aggregate_results_async(
        ...     matter_id="matter-123",
        ...     query="What are the citations?",
        ...     results=[citation_result, timeline_result],
        ...     wall_clock_time_ms=150,
        ... )
    """

    def __init__(
        self,
        language_police: LanguagePolice | None = None,
    ) -> None:
        """Initialize result aggregator.

        Story 8-3: Task 7.2 - Initialize with language police.

        Args:
            language_police: Optional language police service (for testing).
        """
        self._language_police = language_police
        self._policing_enabled = get_settings().language_policing_enabled

        logger.info(
            "result_aggregator_initialized",
            language_policing_enabled=self._policing_enabled,
        )

    def aggregate_results(
        self,
        matter_id: str,
        query: str,
        results: list[EngineExecutionResult],
        wall_clock_time_ms: int,
    ) -> OrchestratorResult:
        """Combine engine results into coherent response (sync, no policing).

        Task 4.2: Main aggregation method (backward compatible).

        NOTE: This synchronous method does NOT apply language policing.
        Use aggregate_results_async() for full policing support.

        Args:
            matter_id: Matter UUID.
            query: Original user query.
            results: Results from all engine executions.
            wall_clock_time_ms: Actual wall clock time.

        Returns:
            OrchestratorResult with unified response (unpoliced).
        """
        return self._aggregate_results_internal(
            matter_id=matter_id,
            query=query,
            results=results,
            wall_clock_time_ms=wall_clock_time_ms,
        )

    async def aggregate_results_async(
        self,
        matter_id: str,
        query: str,
        results: list[EngineExecutionResult],
        wall_clock_time_ms: int,
    ) -> OrchestratorResult:
        """Combine engine results with language policing (async).

        Story 8-3: Task 7.3 - Async aggregation with policing.

        This is the recommended method that applies language policing
        to sanitize the unified response before returning.

        Args:
            matter_id: Matter UUID.
            query: Original user query.
            results: Results from all engine executions.
            wall_clock_time_ms: Actual wall clock time.

        Returns:
            OrchestratorResult with sanitized unified response.
        """
        # First, do standard aggregation
        orchestrator_result = self._aggregate_results_internal(
            matter_id=matter_id,
            query=query,
            results=results,
            wall_clock_time_ms=wall_clock_time_ms,
        )

        # Apply language policing if enabled
        if self._policing_enabled and orchestrator_result.unified_response:
            orchestrator_result = await self._apply_language_policing(orchestrator_result)

        return orchestrator_result

    async def _apply_language_policing(
        self, result: OrchestratorResult
    ) -> OrchestratorResult:
        """Apply language policing to the unified response.

        Story 8-3: Task 7.3 - Sanitize output text.

        Args:
            result: OrchestratorResult with unpoliced unified_response.

        Returns:
            OrchestratorResult with sanitized unified_response and metadata.
        """
        try:
            # Get or create language police
            if self._language_police is None:
                self._language_police = get_language_police()

            # Apply policing to unified response
            policing_result = await self._language_police.police_output(
                result.unified_response
            )

            # Update result with sanitized text and metadata
            result.unified_response = policing_result.sanitized_text
            result.policing_metadata = {
                "policing_applied": True,
                "replacements_count": len(policing_result.replacements_made),
                "quotes_preserved_count": len(policing_result.quotes_preserved),
                "llm_policing_applied": policing_result.llm_policing_applied,
                "sanitization_time_ms": round(policing_result.sanitization_time_ms, 2),
                "llm_cost_usd": round(policing_result.llm_cost_usd, 6),
            }

            logger.info(
                "language_policing_applied",
                matter_id=result.matter_id,
                replacements_count=len(policing_result.replacements_made),
                quotes_preserved=len(policing_result.quotes_preserved),
                llm_applied=policing_result.llm_policing_applied,
                time_ms=round(policing_result.sanitization_time_ms, 2),
            )

        except Exception as e:
            # Language policing errors should NOT block output - log and continue
            logger.error(
                "language_policing_error",
                matter_id=result.matter_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            result.policing_metadata = {
                "policing_applied": False,
                "error": str(e),
            }

        return result

    def _aggregate_results_internal(
        self,
        matter_id: str,
        query: str,
        results: list[EngineExecutionResult],
        wall_clock_time_ms: int,
    ) -> OrchestratorResult:
        """Internal aggregation logic (shared by sync and async).

        Task 4.2: Core aggregation logic.

        Args:
            matter_id: Matter UUID.
            query: Original user query.
            results: Results from all engine executions.
            wall_clock_time_ms: Actual wall clock time.

        Returns:
            OrchestratorResult with unified response.
        """
        # Separate successful and failed results
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        logger.info(
            "aggregate_results_start",
            matter_id=matter_id,
            total_results=len(results),
            successful=len(successful),
            failed=len(failed),
        )

        # Merge sources from all successful engines
        all_sources = self._merge_sources(successful)

        # Calculate weighted confidence
        overall_confidence = self._calculate_overall_confidence(successful)

        # Format unified response
        unified_response = self._format_unified_response(
            query=query,
            successful_results=successful,
            failed_results=failed,
        )

        # Calculate total execution time (sum of all engines)
        total_execution_time_ms = sum(r.execution_time_ms for r in results)

        logger.info(
            "aggregate_results_complete",
            matter_id=matter_id,
            successful_engines=[r.engine.value for r in successful],
            failed_engines=[r.engine.value for r in failed],
            total_sources=len(all_sources),
            confidence=overall_confidence,
        )

        return OrchestratorResult(
            matter_id=matter_id,
            query=query,
            successful_engines=[r.engine for r in successful],
            failed_engines=[r.engine for r in failed],
            unified_response=unified_response,
            sources=all_sources,
            confidence=overall_confidence,
            engine_results=results,
            total_execution_time_ms=total_execution_time_ms,
            wall_clock_time_ms=wall_clock_time_ms,
        )

    def _merge_sources(
        self,
        results: list[EngineExecutionResult],
    ) -> list[SourceReference]:
        """Merge and deduplicate source references from all engines.

        Task 4.3: Combine sources while preserving engine attribution.

        Args:
            results: Successful engine results.

        Returns:
            Deduplicated list of source references.
        """
        sources: list[SourceReference] = []
        seen_docs: set[str] = set()

        for result in results:
            if not result.data:
                continue

            engine_sources = self._extract_sources_from_result(result)

            for source in engine_sources:
                # Deduplicate by document_id + chunk_id
                key = f"{source.document_id}:{source.chunk_id or 'doc'}"

                if key not in seen_docs:
                    seen_docs.add(key)
                    sources.append(source)

        # Sort by confidence (highest first)
        sources.sort(
            key=lambda s: s.confidence if s.confidence is not None else 0.0,
            reverse=True,
        )

        return sources

    def _extract_sources_from_result(
        self,
        result: EngineExecutionResult,
    ) -> list[SourceReference]:
        """Extract source references from engine result data.

        Handles different data formats from each engine type.

        Args:
            result: Engine execution result.

        Returns:
            List of source references.
        """
        sources: list[SourceReference] = []
        data = result.data or {}

        if result.engine == EngineType.RAG:
            # RAG results have explicit search results
            for item in data.get("results", []):
                sources.append(
                    SourceReference(
                        document_id=item.get("document_id", ""),
                        chunk_id=item.get("chunk_id"),
                        page_number=item.get("page_number"),
                        text_preview=item.get("content", "")[:200],
                        confidence=item.get("relevance_score") or item.get("rrf_score"),
                        engine=result.engine,
                    )
                )

        elif result.engine == EngineType.TIMELINE:
            # Timeline events have document references
            for event in data.get("events", [])[:10]:  # Limit to 10 events
                if event.get("document_id"):
                    sources.append(
                        SourceReference(
                            document_id=event["document_id"],
                            document_name=event.get("document_name"),
                            page_number=event.get("source_page"),
                            text_preview=event.get("description", "")[:200],
                            confidence=event.get("confidence"),
                            engine=result.engine,
                        )
                    )

        elif result.engine == EngineType.CITATION:
            # Citation acts don't have direct document references
            # They reference Acts, not source documents
            # We don't add source references for citation engine
            pass

        elif result.engine == EngineType.CONTRADICTION:
            # Contradiction engine references documents via statements
            for doc in data.get("documents", []):
                sources.append(
                    SourceReference(
                        document_id=doc.get("document_id", ""),
                        document_name=doc.get("document_name"),
                        confidence=0.8,
                        engine=result.engine,
                    )
                )

        return sources

    def _calculate_overall_confidence(
        self,
        results: list[EngineExecutionResult],
    ) -> float:
        """Calculate weighted average confidence from engine results.

        Task 4.4: Weight each engine's confidence by its importance.

        Args:
            results: Successful engine results.

        Returns:
            Overall confidence score (0.0-1.0).
        """
        if not results:
            return 0.0

        total_weight = 0.0
        weighted_sum = 0.0

        for result in results:
            if result.confidence is not None:
                weight = ENGINE_CONFIDENCE_WEIGHTS.get(result.engine, 1.0)
                weighted_sum += result.confidence * weight
                total_weight += weight

        if total_weight == 0:
            # No confidence scores available - use default
            return 0.7

        confidence = weighted_sum / total_weight

        # Clamp to valid range
        return max(0.0, min(1.0, confidence))

    def _format_unified_response(
        self,
        query: str,
        successful_results: list[EngineExecutionResult],
        failed_results: list[EngineExecutionResult],
    ) -> str:
        """Format unified human-readable response.

        Task 4.5: Create coherent combined response from all engines.

        Args:
            query: Original query.
            successful_results: Successful engine results.
            failed_results: Failed engine results.

        Returns:
            Formatted response string.
        """
        if not successful_results:
            # All engines failed
            failed_engines = ", ".join(r.engine.value for r in failed_results)
            return f"Unable to process query. The following engines encountered errors: {failed_engines}."

        sections: list[str] = []

        # Add sections from each successful engine
        for result in successful_results:
            section = self._format_engine_section(result)
            if section:
                sections.append(section)

        # Combine sections
        response = "\n\n".join(sections)

        # Add warning about failed engines if any
        if failed_results:
            failed_engines = ", ".join(r.engine.value for r in failed_results)
            response += f"\n\n**Note:** Some engines encountered errors ({failed_engines}). Results may be incomplete."

        return response

    def _format_engine_section(
        self,
        result: EngineExecutionResult,
    ) -> str:
        """Format section for a single engine result.

        Args:
            result: Engine execution result.

        Returns:
            Formatted section string.
        """
        data = result.data or {}

        if result.engine == EngineType.CITATION:
            total_acts = data.get("total_acts", 0)
            total_citations = data.get("total_citations", 0)

            if total_citations == 0:
                return "**Citations:** No Act citations found in the documents."

            acts = data.get("acts", [])
            acts_list = ", ".join(
                f"{a['act_name']} ({a['citation_count']} citations)"
                for a in acts[:5]  # Show top 5
            )

            return (
                f"**Citations:** Found {total_citations} citation(s) across {total_acts} Act(s).\n"
                f"Acts referenced: {acts_list}"
            )

        elif result.engine == EngineType.TIMELINE:
            total_events = data.get("total_events", 0)
            date_range = data.get("date_range", {})

            if total_events == 0:
                return "**Timeline:** No timeline events found."

            start = date_range.get("start", "unknown")
            end = date_range.get("end", "unknown")

            events = data.get("events", [])[:3]  # Show top 3 events
            event_list = "\n".join(
                f"  - {e.get('event_date')}: {e.get('description', '')[:100]}"
                for e in events
            )

            return (
                f"**Timeline:** Found {total_events} event(s) spanning {start} to {end}.\n"
                f"Key events:\n{event_list}"
            )

        elif result.engine == EngineType.CONTRADICTION:
            if not data.get("analysis_ready"):
                return f"**Contradictions:** {data.get('message', 'Analysis not available.')}"

            total_statements = data.get("total_statements", 0)
            total_documents = data.get("total_documents", 0)

            return (
                f"**Contradictions:** Found {total_statements} statement(s) "
                f"across {total_documents} document(s) for analysis."
            )

        elif result.engine == EngineType.RAG:
            results_list = data.get("results", [])
            total_candidates = data.get("total_candidates", 0)

            if not results_list:
                return "**Search:** No relevant content found."

            # Show preview of top results
            previews = "\n".join(
                f"  - {r.get('content', '')[:150]}..."
                for r in results_list[:3]
            )

            return (
                f"**Search:** Found {total_candidates} relevant passage(s).\n"
                f"Top results:\n{previews}"
            )

        return ""


# =============================================================================
# Factory Function (Task 4.6)
# =============================================================================


@lru_cache(maxsize=1)
def get_result_aggregator() -> ResultAggregator:
    """Get singleton result aggregator instance.

    Returns:
        ResultAggregator instance.
    """
    return ResultAggregator()
