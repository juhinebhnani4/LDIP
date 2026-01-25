"""Result Aggregator for combining engine outputs.

Story 6-2: Engine Execution Ordering (AC: #4)
Story 8-3: Language Policing Integration (Task 7: Integrate with Engine Outputs)
Story 8-4: Verification Metadata Tracking (Task 6: Integrate with Engine Outputs)

Aggregates results from multiple engines into a unified response:
- Merges and deduplicates source references
- Calculates overall confidence (weighted average)
- Formats unified human-readable response
- Applies language policing to sanitize output (Story 8-3)
- Tracks verification requirements based on confidence (Story 8-4)

CRITICAL: Sources must include engine attribution for traceability.
CRITICAL: All unified_response text must pass through language policing (Story 8-3).
"""

from functools import lru_cache

import structlog

from app.core.config import get_settings
from app.engines.orchestrator.models import CompoundIntent
from app.models.orchestrator import (
    EngineExecutionResult,
    EngineType,
    OrchestratorResult,
    SourceReference,
)
from app.core.ocr_cleaner import get_ocr_cleaner
from app.services.safety.language_police import (
    LanguagePolice,
    get_language_police,
)
from app.services.verification import get_verification_service

# Section titles for parallel_merge strategy
ENGINE_SECTION_TITLES: dict[EngineType, str] = {
    EngineType.RAG: "Summary",
    EngineType.TIMELINE: "Timeline",
    EngineType.CITATION: "Citations Found",
    EngineType.CONTRADICTION: "Contradictions Identified",
    EngineType.DOCUMENT_DISCOVERY: "Documents",
    EngineType.ENTITY_LOOKUP: "Key Entities",
}

# Engine order for parallel_merge (RAG first for context)
ENGINE_ORDER: list[EngineType] = [
    EngineType.DOCUMENT_DISCOVERY,
    EngineType.ENTITY_LOOKUP,
    EngineType.RAG,
    EngineType.TIMELINE,
    EngineType.CITATION,
    EngineType.CONTRADICTION,
]

logger = structlog.get_logger(__name__)


# =============================================================================
# Engine Weights for Confidence Calculation
# =============================================================================


def _get_engine_confidence_weights() -> dict[EngineType, float]:
    """Get engine confidence weights from settings.

    Story 6-2: Configurable weights for runtime tuning without code deployment.

    Returns:
        Dict mapping engine types to confidence weights.
    """
    settings = get_settings()
    return {
        EngineType.CITATION: settings.orchestrator_weight_citation,
        EngineType.TIMELINE: settings.orchestrator_weight_timeline,
        EngineType.CONTRADICTION: settings.orchestrator_weight_contradiction,
        EngineType.RAG: settings.orchestrator_weight_rag,
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
        aggregation_strategy: str = "single",
        primary_engine: EngineType | None = None,
        compound_intent: CompoundIntent | None = None,
    ) -> OrchestratorResult:
        """Combine engine results with strategy-based aggregation and language policing.

        Story 8-3: Task 7.3 - Async aggregation with policing.
        Story 6-1 Enhancement: Strategy-based aggregation for multi-intent.

        This is the recommended method that applies:
        1. Strategy-based aggregation for multi-intent queries
        2. Language policing to sanitize the unified response

        Aggregation Strategies:
        - "single": Pass-through for single engine
        - "parallel_merge": Section-based combination (clean sections, no weaving)
        - "weave": Narrative integration with inline references
        - "sequential": Time-ordered structure

        Args:
            matter_id: Matter UUID.
            query: Original user query.
            results: Results from all engine executions.
            wall_clock_time_ms: Actual wall clock time.
            aggregation_strategy: How to combine results (default: "single").
            primary_engine: Lead engine for weave strategy.
            compound_intent: Detected compound intent for context.

        Returns:
            OrchestratorResult with aggregated and sanitized unified response.
        """
        # First, do strategy-based aggregation
        orchestrator_result = await self._aggregate_with_strategy(
            matter_id=matter_id,
            query=query,
            results=results,
            wall_clock_time_ms=wall_clock_time_ms,
            aggregation_strategy=aggregation_strategy,
            primary_engine=primary_engine,
            compound_intent=compound_intent,
        )

        # Apply language policing if enabled
        if self._policing_enabled and orchestrator_result.unified_response:
            orchestrator_result = await self._apply_language_policing(orchestrator_result)

        return orchestrator_result

    async def _aggregate_with_strategy(
        self,
        matter_id: str,
        query: str,
        results: list[EngineExecutionResult],
        wall_clock_time_ms: int,
        aggregation_strategy: str,
        primary_engine: EngineType | None,
        compound_intent: CompoundIntent | None,
    ) -> OrchestratorResult:
        """Apply strategy-based aggregation.

        Story 6-1 Enhancement: Strategy-based result combination.

        Args:
            matter_id: Matter UUID.
            query: Original user query.
            results: Results from all engine executions.
            wall_clock_time_ms: Actual wall clock time.
            aggregation_strategy: How to combine results.
            primary_engine: Lead engine for weave strategy.
            compound_intent: Detected compound intent.

        Returns:
            OrchestratorResult with strategy-appropriate unified response.
        """
        match aggregation_strategy:
            case "single":
                return self._aggregate_results_internal(
                    matter_id=matter_id,
                    query=query,
                    results=results,
                    wall_clock_time_ms=wall_clock_time_ms,
                )
            case "parallel_merge":
                return self._aggregate_parallel_merge(
                    matter_id=matter_id,
                    query=query,
                    results=results,
                    wall_clock_time_ms=wall_clock_time_ms,
                )
            case "weave":
                return await self._aggregate_weave(
                    matter_id=matter_id,
                    query=query,
                    results=results,
                    wall_clock_time_ms=wall_clock_time_ms,
                    primary_engine=primary_engine,
                    compound_intent=compound_intent,
                )
            case "sequential":
                return self._aggregate_sequential(
                    matter_id=matter_id,
                    query=query,
                    results=results,
                    wall_clock_time_ms=wall_clock_time_ms,
                    primary_engine=primary_engine,
                )
            case _:
                # Default to parallel_merge for multi-result, single otherwise
                if len([r for r in results if r.success]) > 1:
                    return self._aggregate_parallel_merge(
                        matter_id=matter_id,
                        query=query,
                        results=results,
                        wall_clock_time_ms=wall_clock_time_ms,
                    )
                return self._aggregate_results_internal(
                    matter_id=matter_id,
                    query=query,
                    results=results,
                    wall_clock_time_ms=wall_clock_time_ms,
                )

    def _aggregate_parallel_merge(
        self,
        matter_id: str,
        query: str,
        results: list[EngineExecutionResult],
        wall_clock_time_ms: int,
    ) -> OrchestratorResult:
        """Section-based combination - clean sections, no weaving.

        Story 6-1 Enhancement: Parallel merge strategy.

        Creates distinct sections for each engine with headers,
        ordered by ENGINE_ORDER (RAG first for context).

        Args:
            matter_id: Matter UUID.
            query: Original query.
            results: Engine results.
            wall_clock_time_ms: Wall clock time.

        Returns:
            OrchestratorResult with sectioned unified response.
        """
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        logger.info(
            "aggregate_parallel_merge",
            matter_id=matter_id,
            successful=[r.engine.value for r in successful],
        )

        sections: list[str] = []

        # Order engines by ENGINE_ORDER, include all successful
        for engine_type in ENGINE_ORDER:
            result = next(
                (r for r in successful if r.engine == engine_type),
                None,
            )
            if result and result.data:
                section_content = self._extract_section_content(result)
                if section_content:
                    section_title = ENGINE_SECTION_TITLES.get(
                        engine_type, engine_type.value.title()
                    )
                    sections.append(f"## {section_title}\n\n{section_content}")

        unified_response = "\n\n".join(sections)

        # Add warning about failed engines if any
        if failed:
            failed_engines = ", ".join(r.engine.value for r in failed)
            unified_response += f"\n\n**Note:** Some engines encountered errors ({failed_engines}). Results may be incomplete."

        # Merge sources and calculate confidence
        all_sources = self._merge_sources(successful)
        overall_confidence = self._calculate_overall_confidence(successful)
        total_execution_time_ms = sum(r.execution_time_ms for r in results)
        verification_metadata = self._calculate_verification_metadata(successful)

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
            verification_metadata=verification_metadata,
        )

    async def _aggregate_weave(
        self,
        matter_id: str,
        query: str,
        results: list[EngineExecutionResult],
        wall_clock_time_ms: int,
        primary_engine: EngineType | None,
        compound_intent: CompoundIntent | None,
    ) -> OrchestratorResult:
        """Narrative integration with inline references from supporting engines.

        Story 6-1 Enhancement: Weave strategy for compound intents.

        Uses primary engine result as narrative backbone and weaves
        in data from supporting engines as inline references.

        Args:
            matter_id: Matter UUID.
            query: Original query.
            results: Engine results.
            wall_clock_time_ms: Wall clock time.
            primary_engine: Lead engine for narrative backbone.
            compound_intent: Compound intent for context.

        Returns:
            OrchestratorResult with woven narrative response.
        """
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        logger.info(
            "aggregate_weave",
            matter_id=matter_id,
            primary_engine=primary_engine.value if primary_engine else None,
            compound_intent=compound_intent.name if compound_intent else None,
        )

        # Find primary engine result
        primary_result = next(
            (r for r in successful if r.engine == primary_engine),
            None,
        ) if primary_engine else None

        if not primary_result:
            # Fallback to parallel_merge if primary missing
            logger.warning(
                "weave_primary_missing",
                primary_engine=primary_engine.value if primary_engine else None,
                fallback="parallel_merge",
            )
            return self._aggregate_parallel_merge(
                matter_id=matter_id,
                query=query,
                results=results,
                wall_clock_time_ms=wall_clock_time_ms,
            )

        # Get primary content as narrative backbone
        primary_content = self._extract_section_content(primary_result)

        # Collect supporting data for weaving
        supporting_data: dict[EngineType, EngineExecutionResult] = {}
        for result in successful:
            if result.engine != primary_engine:
                supporting_data[result.engine] = result

        # Weave supporting data into narrative
        woven_response = self._weave_narrative(
            primary_text=primary_content,
            supporting_data=supporting_data,
            compound_intent=compound_intent,
        )

        # Add failed engine warning
        if failed:
            failed_engines = ", ".join(r.engine.value for r in failed)
            woven_response += f"\n\n**Note:** Some engines encountered errors ({failed_engines})."

        # Merge sources and calculate confidence
        all_sources = self._merge_sources(successful)
        overall_confidence = self._calculate_overall_confidence(successful)
        total_execution_time_ms = sum(r.execution_time_ms for r in results)
        verification_metadata = self._calculate_verification_metadata(successful)

        return OrchestratorResult(
            matter_id=matter_id,
            query=query,
            successful_engines=[r.engine for r in successful],
            failed_engines=[r.engine for r in failed],
            unified_response=woven_response,
            sources=all_sources,
            confidence=overall_confidence,
            engine_results=results,
            total_execution_time_ms=total_execution_time_ms,
            wall_clock_time_ms=wall_clock_time_ms,
            verification_metadata=verification_metadata,
        )

    def _aggregate_sequential(
        self,
        matter_id: str,
        query: str,
        results: list[EngineExecutionResult],
        wall_clock_time_ms: int,
        primary_engine: EngineType | None,
    ) -> OrchestratorResult:
        """Time-ordered structure with content woven per phase.

        Story 6-1 Enhancement: Sequential strategy for chronological intents.

        Uses timeline events as structure, weaves other content per time period.
        If no timeline, falls back to parallel_merge.

        Args:
            matter_id: Matter UUID.
            query: Original query.
            results: Engine results.
            wall_clock_time_ms: Wall clock time.
            primary_engine: Primary engine (usually RAG for sequential).

        Returns:
            OrchestratorResult with time-ordered response.
        """
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        # Check for timeline result
        timeline_result = next(
            (r for r in successful if r.engine == EngineType.TIMELINE),
            None,
        )

        if not timeline_result or not timeline_result.data:
            # No timeline data - fall back to parallel_merge
            return self._aggregate_parallel_merge(
                matter_id=matter_id,
                query=query,
                results=results,
                wall_clock_time_ms=wall_clock_time_ms,
            )

        logger.info(
            "aggregate_sequential",
            matter_id=matter_id,
            has_timeline=True,
        )

        # Build chronological response
        events = timeline_result.data.get("events", [])
        sections: list[str] = []

        # Add summary if RAG result exists
        rag_result = next(
            (r for r in successful if r.engine == EngineType.RAG),
            None,
        )
        if rag_result and rag_result.data:
            rag_content = self._extract_section_content(rag_result)
            if rag_content:
                sections.append(f"## Overview\n\n{rag_content}")

        # Add timeline section
        if events:
            timeline_content = "## Timeline of Events\n\n"
            for event in events[:10]:  # Limit to 10 events
                date = event.get("event_date", "Unknown date")
                description = event.get("description", "")
                timeline_content += f"**{date}**: {description}\n\n"
            sections.append(timeline_content)

        # Add other engine results as additional sections
        for engine_type in [EngineType.CITATION, EngineType.CONTRADICTION]:
            result = next(
                (r for r in successful if r.engine == engine_type),
                None,
            )
            if result and result.data:
                section_content = self._extract_section_content(result)
                if section_content:
                    section_title = ENGINE_SECTION_TITLES.get(
                        engine_type, engine_type.value.title()
                    )
                    sections.append(f"## {section_title}\n\n{section_content}")

        unified_response = "\n\n".join(sections)

        if failed:
            failed_engines = ", ".join(r.engine.value for r in failed)
            unified_response += f"\n\n**Note:** Some engines encountered errors ({failed_engines})."

        # Merge sources and calculate confidence
        all_sources = self._merge_sources(successful)
        overall_confidence = self._calculate_overall_confidence(successful)
        total_execution_time_ms = sum(r.execution_time_ms for r in results)
        verification_metadata = self._calculate_verification_metadata(successful)

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
            verification_metadata=verification_metadata,
        )

    def _extract_section_content(
        self,
        result: EngineExecutionResult,
    ) -> str:
        """Extract formatted content for a section from engine result.

        Story 6-1 Enhancement: Helper for strategy-based aggregation.

        Args:
            result: Engine execution result.

        Returns:
            Formatted content string.
        """
        data = result.data or {}

        if result.engine == EngineType.RAG:
            # Check for synthesized answer first
            answer = data.get("answer")
            if answer:
                return answer

            # Fallback to raw chunks
            results_list = data.get("results", [])
            if not results_list:
                return ""

            previews = "\n".join(
                f"- {r.get('content', '')[:200]}..."
                for r in results_list[:5]
            )
            return f"Found {len(results_list)} relevant passage(s):\n\n{previews}"

        elif result.engine == EngineType.TIMELINE:
            events = data.get("events", [])
            if not events:
                return "No timeline events found."

            date_range = data.get("date_range", {})
            start = date_range.get("start", "unknown")
            end = date_range.get("end", "unknown")

            event_list = "\n".join(
                f"- **{e.get('event_date')}**: {e.get('description', '')[:150]}"
                for e in events[:5]
            )
            return f"Events spanning {start} to {end}:\n\n{event_list}"

        elif result.engine == EngineType.CITATION:
            total_citations = data.get("total_citations", 0)
            if total_citations == 0:
                return "No Act citations found."

            acts = data.get("acts", [])
            acts_list = "\n".join(
                f"- **{a['act_name']}**: {a['citation_count']} citation(s)"
                for a in acts[:5]
            )
            return f"Found {total_citations} citation(s):\n\n{acts_list}"

        elif result.engine == EngineType.CONTRADICTION:
            # Check for synthesized answer (pre-computed contradictions)
            answer = data.get("answer")
            if answer:
                return answer

            if not data.get("analysis_ready"):
                return data.get("message", "Analysis not available.")

            total_statements = data.get("total_statements", 0)
            return f"Analyzed {total_statements} statement(s) for contradictions."

        elif result.engine == EngineType.DOCUMENT_DISCOVERY:
            # Document discovery returns answer directly
            answer = data.get("answer")
            if answer:
                return answer
            return "No documents found."

        elif result.engine == EngineType.ENTITY_LOOKUP:
            # Entity lookup returns answer directly
            answer = data.get("answer")
            if answer:
                return answer
            return "No entities found."

        return ""

    def _weave_narrative(
        self,
        primary_text: str,
        supporting_data: dict[EngineType, EngineExecutionResult],
        compound_intent: CompoundIntent | None,
    ) -> str:
        """Weave supporting engine data into primary narrative.

        Story 6-1 Enhancement: Narrative weaving for compound intents.

        Args:
            primary_text: Primary engine content (narrative backbone).
            supporting_data: Supporting engine results.
            compound_intent: Compound intent for context.

        Returns:
            Woven narrative with inline references.
        """
        woven = primary_text

        # For comprehensive analysis, add distinct sections
        if compound_intent and compound_intent.name == "comprehensive_analysis":
            sections = [woven]

            for engine, result in supporting_data.items():
                section_content = self._extract_section_content(result)
                if section_content:
                    section_title = ENGINE_SECTION_TITLES.get(
                        engine, engine.value.title()
                    )
                    sections.append(f"\n\n## {section_title}\n\n{section_content}")

            return "".join(sections)

        # For other compound intents, add supporting data as notes
        supplementary_notes: list[str] = []

        if EngineType.TIMELINE in supporting_data:
            timeline_result = supporting_data[EngineType.TIMELINE]
            if timeline_result.data:
                events = timeline_result.data.get("events", [])[:3]
                if events:
                    event_list = ", ".join(
                        f"{e.get('event_date')}" for e in events
                    )
                    supplementary_notes.append(
                        f"**Key dates referenced:** {event_list}"
                    )

        if EngineType.CITATION in supporting_data:
            citation_result = supporting_data[EngineType.CITATION]
            if citation_result.data:
                total = citation_result.data.get("total_citations", 0)
                if total > 0:
                    acts = citation_result.data.get("acts", [])[:3]
                    act_list = ", ".join(a.get("act_name", "") for a in acts)
                    supplementary_notes.append(
                        f"**Acts cited:** {act_list} ({total} total citations)"
                    )

        if EngineType.CONTRADICTION in supporting_data:
            contradiction_result = supporting_data[EngineType.CONTRADICTION]
            if contradiction_result.data and contradiction_result.data.get("analysis_ready"):
                total = contradiction_result.data.get("total_statements", 0)
                supplementary_notes.append(
                    f"**Statements analyzed:** {total} for potential contradictions"
                )

        if supplementary_notes:
            woven += "\n\n---\n\n" + "\n\n".join(supplementary_notes)

        return woven

    async def _apply_language_policing(
        self, result: OrchestratorResult
    ) -> OrchestratorResult:
        """Apply OCR cleaning and language policing to the unified response.

        Story 8-3: Task 7.3 - Sanitize output text.
        Enhancement: OCR noise filtering before language policing.

        Args:
            result: OrchestratorResult with unpoliced unified_response.

        Returns:
            OrchestratorResult with sanitized unified_response and metadata.
        """
        try:
            # Step 1: Apply OCR cleaning to remove garbage characters
            ocr_cleaner = get_ocr_cleaner()
            original_text = result.unified_response
            cleaned_text = ocr_cleaner.clean(original_text)
            ocr_cleaned = cleaned_text != original_text

            if ocr_cleaned:
                result.unified_response = cleaned_text
                logger.info(
                    "ocr_cleaning_applied",
                    matter_id=result.matter_id,
                    original_length=len(original_text),
                    cleaned_length=len(cleaned_text),
                    removed_chars=len(original_text) - len(cleaned_text),
                )

            # Step 2: Get or create language police
            if self._language_police is None:
                self._language_police = get_language_police()

            # Step 3: Apply language policing to unified response
            policing_result = await self._language_police.police_output(
                result.unified_response
            )

            # Update result with sanitized text and metadata
            result.unified_response = policing_result.sanitized_text
            result.policing_metadata = {
                "policing_applied": True,
                "ocr_cleaned": ocr_cleaned,
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

        # Story 8-4: Calculate verification metadata
        verification_metadata = self._calculate_verification_metadata(successful)

        logger.info(
            "aggregate_results_complete",
            matter_id=matter_id,
            successful_engines=[r.engine.value for r in successful],
            failed_engines=[r.engine.value for r in failed],
            total_sources=len(all_sources),
            confidence=overall_confidence,
            verification_metadata=verification_metadata,
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
            verification_metadata=verification_metadata,
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
            # RAG results have explicit search results with document names
            for item in data.get("results", []):
                doc_name = item.get("document_name")
                # DEBUG: Log document_name extraction
                logger.debug(
                    "rag_source_extraction",
                    document_id=item.get("document_id", "")[:8],
                    document_name=doc_name,
                    has_doc_name=doc_name is not None,
                )
                sources.append(
                    SourceReference(
                        document_id=item.get("document_id", ""),
                        document_name=doc_name,
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
        Weights are configurable via environment variables for runtime tuning.

        Args:
            results: Successful engine results.

        Returns:
            Overall confidence score (0.0-1.0).
        """
        if not results:
            return 0.0

        total_weight = 0.0
        weighted_sum = 0.0
        weights = _get_engine_confidence_weights()

        for result in results:
            if result.confidence is not None:
                weight = weights.get(result.engine, 1.0)
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
            # Check for synthesized answer (pre-computed contradictions)
            answer = data.get("answer")
            if answer:
                return answer

            if not data.get("analysis_ready"):
                return f"**Contradictions:** {data.get('message', 'Analysis not available.')}"

            total_statements = data.get("total_statements", 0)
            total_documents = data.get("total_documents", 0)

            return (
                f"**Contradictions:** Found {total_statements} statement(s) "
                f"across {total_documents} document(s) for analysis."
            )

        elif result.engine == EngineType.RAG:
            # Check for synthesized answer (new RAG pipeline)
            answer = data.get("answer")
            if answer:
                return answer

            # Fallback for old format (raw chunks only)
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

        elif result.engine == EngineType.DOCUMENT_DISCOVERY:
            # Document discovery returns answer directly
            answer = data.get("answer")
            if answer:
                return answer
            return "**Documents:** No documents found in this matter."

        elif result.engine == EngineType.ENTITY_LOOKUP:
            # Entity lookup returns answer directly
            answer = data.get("answer")
            if answer:
                return answer
            return "**Entities:** No entities found in this matter."

        return ""

    def _calculate_verification_metadata(
        self,
        results: list[EngineExecutionResult],
    ) -> dict:
        """Calculate verification metadata based on result confidences.

        Story 8-4: Task 6.3 - Include verification_requirement in response metadata.

        NOTE: This method calculates verification metadata for the response.
        Actual verification record creation happens when findings are persisted
        to the database (calling VerificationService.create_verification_record).
        The aggregator provides metadata so the UI can show verification badges.

        Counts how many findings from engine results would require
        different levels of verification based on ADR-004 thresholds:
        - > 90%: optional
        - 70-90%: suggested
        - < 70%: required

        Args:
            results: Successful engine results.

        Returns:
            Dict with verification metadata (counts by tier, export_blocking_count).
        """
        verification_service = get_verification_service()

        findings_count = 0
        required_count = 0
        suggested_count = 0
        optional_count = 0

        for result in results:
            if not result.data:
                continue

            # Extract findings/results from engine-specific data structures
            confidence_values = self._extract_confidence_values(result)

            for confidence in confidence_values:
                findings_count += 1
                # Convert 0-1 confidence to 0-100 scale if needed
                confidence_pct = confidence * 100 if confidence <= 1.0 else confidence

                requirement = verification_service.get_verification_requirement(
                    confidence_pct
                )

                if requirement.value == "required":
                    required_count += 1
                elif requirement.value == "suggested":
                    suggested_count += 1
                else:
                    optional_count += 1

        return {
            "findings_count": findings_count,
            "required_verifications": required_count,
            "suggested_verifications": suggested_count,
            "optional_verifications": optional_count,
            "export_blocking_count": required_count,  # Only required blocks export
        }

    def _extract_confidence_values(
        self,
        result: EngineExecutionResult,
    ) -> list[float]:
        """Extract confidence values from engine result data.

        Story 8-4: Task 6.3 - Helper to extract confidences from various engine formats.

        Args:
            result: Engine execution result.

        Returns:
            List of confidence values (0.0-1.0 scale).
        """
        confidences: list[float] = []
        data = result.data or {}

        if result.engine == EngineType.CITATION:
            # Citation engine: citations have individual confidence
            for act in data.get("acts", []):
                for citation in act.get("citations", []):
                    conf = citation.get("confidence", result.confidence or 0.8)
                    confidences.append(conf)

        elif result.engine == EngineType.TIMELINE:
            # Timeline engine: events have confidence
            for event in data.get("events", []):
                conf = event.get("confidence", result.confidence or 0.8)
                confidences.append(conf)

        elif result.engine == EngineType.CONTRADICTION:
            # Contradiction engine: comparisons have confidence
            for comparison in data.get("comparisons", []):
                if comparison.get("result") == "contradiction":
                    conf = comparison.get("confidence", result.confidence or 0.8)
                    confidences.append(conf)

        elif result.engine == EngineType.RAG:
            # RAG results typically don't create "findings" per se
            # They provide context for other engines
            pass

        return confidences


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

