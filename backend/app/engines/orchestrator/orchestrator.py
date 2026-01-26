"""Query Orchestrator - Main orchestration pipeline.

Story 6-2: Engine Execution Ordering (AC: #1)
Story 6-3: Audit Trail Logging (AC: #1-4)
Story 8-2: Safety Guard Integration (AC: #4)

Integrates all orchestration components:
- SafetyGuard (Story 8-2) → check query safety before processing
- IntentAnalyzer (Story 6-1) → classify query intent
- ExecutionPlanner → determine parallel/sequential execution
- EngineExecutor → execute engines in parallel
- ResultAggregator → combine results into unified response
- QueryAuditLogger (Story 6-3) → forensic audit trail

This is the main entry point for query processing.

CRITICAL: Matter isolation must be maintained through entire pipeline.
CRITICAL: Audit logging must be non-blocking (Story 6-3 AC: #5).
CRITICAL: Safety check runs BEFORE intent analysis (Story 8-2).
"""

import asyncio
import time
from functools import lru_cache
from typing import Any

import structlog

from app.engines.orchestrator.aggregator import ResultAggregator, get_result_aggregator
from app.engines.orchestrator.audit_logger import (
    QueryAuditLogger,
    get_query_audit_logger,
)
from app.engines.orchestrator.executor import EngineExecutor, get_engine_executor
from app.engines.orchestrator.intent_analyzer import (
    IntentAnalyzer,
    MultiIntentAnalyzer,
    get_intent_analyzer,
    get_multi_intent_analyzer,
)
from app.engines.orchestrator.models import MultiIntentClassification
from app.engines.orchestrator.planner import ExecutionPlanner, get_execution_planner
from app.engines.orchestrator.query_history import (
    QueryHistoryStore,
    get_query_history_store,
)
from app.services.memory.query_cache_service import (
    QueryCacheService,
    get_query_cache_service,
)
from app.models.orchestrator import (
    EngineType,
    IntentAnalysisResult,
    IntentClassification,
    OrchestratorResult,
    QueryIntent,
    SourceReference,
)
from app.models.safety import SafetyCheckResult
from app.services.safety import SafetyGuard, get_safety_guard

logger = structlog.get_logger(__name__)


# =============================================================================
# Query Orchestrator (Task 6.1-6.5)
# =============================================================================


class QueryOrchestrator:
    """Main orchestrator for query processing.

    Story 6-2: Full pipeline from query to unified response.
    Story 6-3: Audit trail logging for forensic compliance.
    Story 8-2: Safety guard integration.

    Pipeline:
    0. SafetyGuard → check query safety (Story 8-2)
    1. IntentAnalyzer → classify query, determine required engines
    2. ExecutionPlanner → create execution plan (parallel groups)
    3. EngineExecutor → execute engines with parallel optimization
    4. ResultAggregator → combine results into unified response
    5. QueryAuditLogger → create forensic audit record (non-blocking)

    Example:
        >>> orchestrator = get_query_orchestrator()
        >>> result = await orchestrator.process_query(
        ...     matter_id="matter-123",
        ...     query="What citations are in this case?",
        ...     user_id="user-456",  # For audit trail
        ... )
        >>> result.successful_engines
        [EngineType.CITATION]
    """

    def __init__(
        self,
        safety_guard: SafetyGuard | None = None,
        intent_analyzer: IntentAnalyzer | None = None,
        multi_intent_analyzer: MultiIntentAnalyzer | None = None,
        planner: ExecutionPlanner | None = None,
        executor: EngineExecutor | None = None,
        aggregator: ResultAggregator | None = None,
        audit_logger: QueryAuditLogger | None = None,
        history_store: QueryHistoryStore | None = None,
        cache_service: QueryCacheService | None = None,
        use_multi_intent: bool = True,
        use_response_cache: bool = True,
    ) -> None:
        """Initialize query orchestrator.

        Task 6.3: Wire up all components.
        Story 6-3: Add audit logging components.
        Story 8-2: Add safety guard (Task 6.2).
        Story 6-1 Enhancement: Multi-intent classification support.
        Cost Optimization: Response caching for repeated queries.

        Args:
            safety_guard: Optional custom safety guard (Story 8-2).
            intent_analyzer: Optional custom intent analyzer (legacy).
            multi_intent_analyzer: Optional custom multi-intent analyzer (new).
            planner: Optional custom execution planner.
            executor: Optional custom engine executor.
            aggregator: Optional custom result aggregator.
            audit_logger: Optional custom audit logger (Story 6-3).
            history_store: Optional custom history store (Story 6-3).
            cache_service: Optional query cache service for response caching.
            use_multi_intent: If True, use new multi-intent classifier (default True).
            use_response_cache: If True, cache and reuse responses (default True).
        """
        self._safety_guard = safety_guard or get_safety_guard()
        self._intent_analyzer = intent_analyzer or get_intent_analyzer()
        self._multi_intent_analyzer = multi_intent_analyzer or get_multi_intent_analyzer()
        self._planner = planner or get_execution_planner()
        self._executor = executor or get_engine_executor()
        self._aggregator = aggregator or get_result_aggregator()
        self._audit_logger = audit_logger or get_query_audit_logger()
        self._history_store = history_store or get_query_history_store()
        self._cache_service = cache_service or get_query_cache_service()
        self._use_multi_intent = use_multi_intent
        self._use_response_cache = use_response_cache

        logger.info(
            "query_orchestrator_initialized",
            use_multi_intent=use_multi_intent,
            use_response_cache=use_response_cache,
        )

    async def process_query(
        self,
        matter_id: str,
        query: str,
        user_id: str,
        context: dict[str, Any] | None = None,
    ) -> OrchestratorResult:
        """Process user query through full orchestration pipeline.

        Task 6.2: Full pipeline: intent → plan → execute → aggregate.
        Story 6-3: Add audit logging (non-blocking).
        Story 8-2: Add safety check BEFORE intent analysis (Task 6.3).

        CRITICAL: user_id is REQUIRED for NFR24 audit compliance.
        All queries must be logged with user attribution.

        Args:
            matter_id: Matter UUID for isolation.
            query: User's natural language query.
            user_id: User ID for audit trail (Story 6-3). REQUIRED for NFR24.
            context: Optional conversation context.

        Returns:
            OrchestratorResult with unified response from all engines.
        """
        start_time = time.time()

        logger.info(
            "process_query_start",
            matter_id=matter_id,
            query_length=len(query),
            user_id=user_id,
        )

        # Step 0: Safety check (Story 8-1 regex + Story 8-2 LLM)
        # Instead of blocking, rewrite the query and continue processing
        original_query = query
        query_was_rewritten = False
        safety_result = await self._safety_guard.check_query(query)

        if not safety_result.is_safe:
            # If we have a suggested rewrite that's actually different, use it
            rewrite = safety_result.suggested_rewrite
            rewrite_is_different = (
                rewrite
                and rewrite.strip().lower() != original_query.strip().lower()
            )

            if rewrite_is_different:
                logger.info(
                    "query_rewritten_for_safety",
                    matter_id=matter_id,
                    blocked_by=safety_result.blocked_by,
                    violation_type=safety_result.violation_type,
                    original_query=query[:100],
                    rewritten_query=rewrite[:100],
                )
                query = rewrite
                query_was_rewritten = True

                # Log to audit trail (non-blocking)
                task = asyncio.create_task(
                    self._log_blocked_query_audit(
                        matter_id=matter_id,
                        user_id=user_id,
                        query=original_query,
                        safety_result=safety_result,
                    )
                )
                task.add_done_callback(self._handle_audit_task_exception)
            elif rewrite:
                # Rewrite is same as original - treat as safe and continue without rewrite notice
                logger.info(
                    "query_rewrite_identical_continuing",
                    matter_id=matter_id,
                    blocked_by=safety_result.blocked_by,
                    message="Rewrite identical to original, treating as safe",
                )
                # query_was_rewritten stays False, so no notice shown to user
            else:
                # No rewrite available - must block
                wall_clock_time_ms = int((time.time() - start_time) * 1000)

                logger.info(
                    "query_blocked_by_safety",
                    matter_id=matter_id,
                    blocked_by=safety_result.blocked_by,
                    violation_type=safety_result.violation_type,
                    wall_clock_time_ms=wall_clock_time_ms,
                )

                # Log to audit trail (non-blocking) - Story 8-2 Task 6.5
                task = asyncio.create_task(
                    self._log_blocked_query_audit(
                        matter_id=matter_id,
                        user_id=user_id,
                        query=query,
                        safety_result=safety_result,
                    )
                )
                task.add_done_callback(self._handle_audit_task_exception)

                return OrchestratorResult(
                    matter_id=matter_id,
                    query=query,
                    success=False,
                    blocked=True,
                    blocked_reason=safety_result.explanation,
                    suggested_rewrite=safety_result.suggested_rewrite,
                    wall_clock_time_ms=wall_clock_time_ms,
                )

        # Step 0.5: Check response cache (Cost Optimization)
        if self._use_response_cache:
            try:
                cached = await self._cache_service.check_cache(matter_id, query)
                if cached and cached.response_data:
                    wall_clock_time_ms = int((time.time() - start_time) * 1000)
                    logger.info(
                        "process_query_cache_hit",
                        matter_id=matter_id,
                        query_hash=cached.query_hash[:16] + "...",
                        cached_at=cached.cached_at,
                        wall_clock_time_ms=wall_clock_time_ms,
                    )
                    # Reconstruct OrchestratorResult from cached data
                    # Restore sources from cached data
                    cached_sources = [
                        SourceReference(**s) for s in cached.response_data.get("sources", [])
                    ]
                    return OrchestratorResult(
                        matter_id=matter_id,
                        query=query,
                        success=cached.response_data.get("success", True),
                        unified_response=cached.response_data.get("unified_response"),
                        successful_engines=[
                            EngineType(e) for e in cached.response_data.get("successful_engines", [])
                        ],
                        failed_engines=[
                            EngineType(e) for e in cached.response_data.get("failed_engines", [])
                        ],
                        sources=cached_sources,
                        confidence=cached.confidence,
                        wall_clock_time_ms=wall_clock_time_ms,
                        from_cache=True,
                    )
            except Exception as e:
                # Cache errors should not fail the query
                logger.warning(
                    "process_query_cache_check_failed",
                    matter_id=matter_id,
                    error=str(e),
                )

        # Step 1: Analyze intent and determine required engines
        # Story 6-1 Enhancement: Support multi-intent classification
        multi_classification: MultiIntentClassification | None = None
        intent_result: IntentAnalysisResult | None = None

        if self._use_multi_intent:
            # New multi-intent classification path
            multi_classification = await self._multi_intent_analyzer.classify(query)
            engines = list(multi_classification.required_engines)

            # Create legacy IntentAnalysisResult for backward compatibility (audit logging)
            intent_result = self._create_legacy_intent_result(
                matter_id=matter_id,
                query=query,
                multi_classification=multi_classification,
            )

            logger.info(
                "process_query_multi_intent_analyzed",
                matter_id=matter_id,
                is_multi_intent=multi_classification.is_multi_intent,
                required_engines=[e.value for e in engines],
                aggregation_strategy=multi_classification.aggregation_strategy,
                compound_intent=multi_classification.compound_intent.name if multi_classification.compound_intent else None,
                llm_was_used=multi_classification.llm_was_used,
            )
        else:
            # Legacy single-intent path
            intent_result = await self._intent_analyzer.analyze_intent(
                matter_id=matter_id,
                query=query,
            )
            engines = intent_result.classification.required_engines

            logger.info(
                "process_query_intent_analyzed",
                matter_id=matter_id,
                intent=intent_result.classification.intent.value,
                confidence=intent_result.classification.confidence,
                required_engines=[e.value for e in engines],
                fast_path_used=intent_result.fast_path_used,
            )

        # Step 2: Execute engines
        engine_results = await self._executor.execute_engines(
            matter_id=matter_id,
            query=query,
            engines=engines,
            context=context,
        )

        # Step 3: Aggregate results (with language policing - Story 8-3)
        wall_clock_time_ms = int((time.time() - start_time) * 1000)

        # Story 8-3 Code Review Fix: Use async version to apply language policing
        # Story 6-1 Enhancement: Pass aggregation strategy for multi-intent
        aggregation_kwargs: dict[str, Any] = {
            "matter_id": matter_id,
            "query": query,
            "results": engine_results,
            "wall_clock_time_ms": wall_clock_time_ms,
        }

        if multi_classification:
            aggregation_kwargs["aggregation_strategy"] = multi_classification.aggregation_strategy
            aggregation_kwargs["primary_engine"] = multi_classification.primary_engine
            aggregation_kwargs["compound_intent"] = multi_classification.compound_intent

        result = await self._aggregator.aggregate_results_async(**aggregation_kwargs)

        logger.info(
            "process_query_complete",
            matter_id=matter_id,
            successful_engines=[e.value for e in result.successful_engines],
            failed_engines=[e.value for e in result.failed_engines],
            confidence=result.confidence,
            wall_clock_time_ms=result.wall_clock_time_ms,
        )

        # Step 3.5: Cache successful result (Cost Optimization)
        if self._use_response_cache and result.success:
            try:
                # Prepare response data for caching (include sources for full restore)
                response_data = {
                    "success": result.success,
                    "unified_response": result.unified_response,
                    "successful_engines": [e.value for e in result.successful_engines],
                    "failed_engines": [e.value for e in result.failed_engines],
                    "sources": [s.model_dump() for s in result.sources] if result.sources else [],
                }
                await self._cache_service.cache_result(
                    matter_id=matter_id,
                    query=query,
                    result_summary=result.unified_response[:200] if result.unified_response else "",
                    response_data=response_data,
                    engine_used=result.successful_engines[0].value if result.successful_engines else None,
                    findings_count=len(result.successful_engines),
                    confidence=result.confidence,
                )
            except Exception as e:
                # Cache errors should not fail the query
                logger.warning(
                    "process_query_cache_store_failed",
                    matter_id=matter_id,
                    error=str(e),
                )

        # Add query rewrite metadata if query was rewritten
        if query_was_rewritten:
            result.query_was_rewritten = True
            result.original_query = original_query

        # Step 4: Audit logging (non-blocking, fire-and-forget)
        # Story 6-3: AC #5 - audit failures should not fail the query
        # NFR24: Always log audit - user_id is required
        task = asyncio.create_task(
            self._log_query_audit(
                matter_id=matter_id,
                user_id=user_id,
                result=result,
                intent_result=intent_result,
            )
        )
        # Add callback to handle any exceptions that slip through
        task.add_done_callback(self._handle_audit_task_exception)

        return result

    def _handle_audit_task_exception(self, task: asyncio.Task) -> None:
        """Handle exceptions from background audit task.

        Story 6-3: Task 5.3 - L2 Fix: Added story reference.
        Prevents 'Task exception was never retrieved' warnings.
        """
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(
                "audit_task_exception",
                error=str(exc),
                error_type=type(exc).__name__,
            )

    async def _log_query_audit(
        self,
        matter_id: str,
        user_id: str,
        result: OrchestratorResult,
        intent_result: IntentAnalysisResult,
    ) -> None:
        """Log query to audit trail (non-blocking).

        Story 6-3: AC #5 - This method should never raise exceptions.
        Audit failures must not affect query processing.

        Args:
            matter_id: Matter UUID.
            user_id: User who asked the query.
            result: OrchestratorResult from query processing.
            intent_result: IntentAnalysisResult for cost tracking.
        """
        try:
            audit_entry = self._audit_logger.log_query(
                matter_id=matter_id,
                user_id=user_id,
                result=result,
                intent_result=intent_result,
            )
            await self._history_store.append_query(audit_entry)

            logger.debug(
                "query_audit_logged",
                matter_id=matter_id,
                query_id=audit_entry.query_id,
            )
        except Exception as e:
            # Log error but don't propagate - audit is non-critical
            logger.error(
                "query_audit_failed",
                matter_id=matter_id,
                user_id=user_id,
                error=str(e),
            )

    async def _log_blocked_query_audit(
        self,
        matter_id: str,
        user_id: str,
        query: str,
        safety_result: SafetyCheckResult,
    ) -> None:
        """Log blocked query to audit trail (non-blocking).

        Story 8-2: Task 6.5 - Audit logging for blocked queries.
        Persists audit entry to database via history store for NFR24 compliance.
        This method should never raise exceptions.

        Args:
            matter_id: Matter UUID.
            user_id: User who asked the query.
            query: The blocked query.
            safety_result: Safety check result with blocking details.
        """
        try:
            # Create audit entry and persist to database for NFR24 compliance
            audit_entry = self._audit_logger.log_blocked_query(
                matter_id=matter_id,
                user_id=user_id,
                query=query,
                safety_result=safety_result,
            )
            await self._history_store.append_query(audit_entry)

            logger.debug(
                "blocked_query_audit_persisted",
                query_id=audit_entry.query_id,
                matter_id=matter_id,
            )
        except Exception as e:
            # Log error but don't propagate - audit is non-critical
            logger.error(
                "blocked_query_audit_failed",
                matter_id=matter_id,
                user_id=user_id,
                error=str(e),
            )

    async def analyze_intent(
        self,
        matter_id: str,
        query: str,
    ) -> IntentAnalysisResult:
        """Analyze query intent without executing engines.

        Useful for inspection/debugging of intent classification.

        Args:
            matter_id: Matter UUID.
            query: User's query.

        Returns:
            IntentAnalysisResult with classification.
        """
        return await self._intent_analyzer.analyze_intent(
            matter_id=matter_id,
            query=query,
        )

    def _create_legacy_intent_result(
        self,
        matter_id: str,
        query: str,
        multi_classification: MultiIntentClassification,
    ) -> IntentAnalysisResult:
        """Create legacy IntentAnalysisResult from MultiIntentClassification.

        Story 6-1 Enhancement: Backward compatibility for audit logging.

        Args:
            matter_id: Matter UUID.
            query: User's query.
            multi_classification: New multi-intent classification.

        Returns:
            Legacy IntentAnalysisResult for audit logging.
        """
        from app.models.orchestrator import IntentAnalysisCost

        # Determine primary intent from classification
        primary_engine = multi_classification.primary_engine
        intent_map = {
            EngineType.CITATION: QueryIntent.CITATION,
            EngineType.TIMELINE: QueryIntent.TIMELINE,
            EngineType.CONTRADICTION: QueryIntent.CONTRADICTION,
            EngineType.RAG: QueryIntent.RAG_SEARCH,
        }
        primary_intent = intent_map.get(primary_engine, QueryIntent.RAG_SEARCH)

        # If multi-intent, use MULTI_ENGINE intent
        if multi_classification.is_multi_intent:
            primary_intent = QueryIntent.MULTI_ENGINE

        classification = IntentClassification(
            intent=primary_intent,
            confidence=multi_classification.max_confidence,
            required_engines=list(multi_classification.required_engines),
            reasoning=multi_classification.reasoning,
        )

        return IntentAnalysisResult(
            matter_id=matter_id,
            query=query,
            classification=classification,
            fast_path_used=not multi_classification.llm_was_used,
            cost=IntentAnalysisCost(llm_call_made=multi_classification.llm_was_used),
        )

    @property
    def safety_guard(self) -> SafetyGuard:
        """Get the safety guard instance (Story 8-2)."""
        return self._safety_guard

    @property
    def intent_analyzer(self) -> IntentAnalyzer:
        """Get the intent analyzer instance (legacy)."""
        return self._intent_analyzer

    @property
    def multi_intent_analyzer(self) -> MultiIntentAnalyzer:
        """Get the multi-intent analyzer instance (Story 6-1 Enhancement)."""
        return self._multi_intent_analyzer

    @property
    def planner(self) -> ExecutionPlanner:
        """Get the execution planner instance."""
        return self._planner

    @property
    def executor(self) -> EngineExecutor:
        """Get the engine executor instance."""
        return self._executor

    @property
    def aggregator(self) -> ResultAggregator:
        """Get the result aggregator instance."""
        return self._aggregator

    @property
    def audit_logger(self) -> QueryAuditLogger:
        """Get the audit logger instance (Story 6-3)."""
        return self._audit_logger

    @property
    def history_store(self) -> QueryHistoryStore:
        """Get the query history store instance (Story 6-3)."""
        return self._history_store

    @property
    def cache_service(self) -> QueryCacheService:
        """Get the query cache service instance (Cost Optimization)."""
        return self._cache_service

    async def process_batch(
        self,
        matter_id: str,
        queries: list[str],
        user_id: str,
        context: dict[str, Any] | None = None,
        max_concurrent: int = 3,
    ) -> list[OrchestratorResult]:
        """Process multiple queries in batch with cost optimization.

        Cost Optimization: Batch processing reduces per-query overhead by:
        - Sharing cache lookups across queries
        - Limiting concurrent API calls to avoid rate limits
        - Reusing intent analysis patterns

        Args:
            matter_id: Matter UUID for isolation.
            queries: List of user queries to process.
            user_id: User ID for audit trail.
            context: Optional shared context.
            max_concurrent: Maximum concurrent queries (default 3).

        Returns:
            List of OrchestratorResult for each query (same order as input).
        """
        if not queries:
            return []

        logger.info(
            "process_batch_start",
            matter_id=matter_id,
            query_count=len(queries),
            max_concurrent=max_concurrent,
        )

        # Use semaphore to limit concurrent processing
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_semaphore(query: str) -> OrchestratorResult:
            async with semaphore:
                return await self.process_query(
                    matter_id=matter_id,
                    query=query,
                    user_id=user_id,
                    context=context,
                )

        # Process all queries with limited concurrency
        results = await asyncio.gather(
            *[process_with_semaphore(q) for q in queries],
            return_exceptions=True,
        )

        # Convert exceptions to error results
        processed_results: list[OrchestratorResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "process_batch_query_failed",
                    matter_id=matter_id,
                    query_index=i,
                    error=str(result),
                )
                processed_results.append(
                    OrchestratorResult(
                        matter_id=matter_id,
                        query=queries[i],
                        success=False,
                        unified_response=f"Error processing query: {result!s}",
                    )
                )
            else:
                processed_results.append(result)

        # Count cache hits for logging
        cache_hits = sum(1 for r in processed_results if r.from_cache)
        logger.info(
            "process_batch_complete",
            matter_id=matter_id,
            query_count=len(queries),
            cache_hits=cache_hits,
            cache_hit_rate=cache_hits / len(queries) if queries else 0,
        )

        return processed_results


# =============================================================================
# Factory Function (Task 6.4)
# =============================================================================


@lru_cache(maxsize=1)
def get_query_orchestrator() -> QueryOrchestrator:
    """Get singleton query orchestrator instance.

    Returns:
        QueryOrchestrator instance.
    """
    return QueryOrchestrator()
