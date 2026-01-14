"""Query Orchestrator - Main orchestration pipeline.

Story 6-2: Engine Execution Ordering (AC: #1)
Story 6-3: Audit Trail Logging (AC: #1-4)

Integrates all orchestration components:
- IntentAnalyzer (Story 6-1) → classify query intent
- ExecutionPlanner → determine parallel/sequential execution
- EngineExecutor → execute engines in parallel
- ResultAggregator → combine results into unified response
- QueryAuditLogger (Story 6-3) → forensic audit trail

This is the main entry point for query processing.

CRITICAL: Matter isolation must be maintained through entire pipeline.
CRITICAL: Audit logging must be non-blocking (Story 6-3 AC: #5).
"""

import asyncio
import time
from functools import lru_cache
from typing import Any

import structlog

from app.engines.orchestrator.aggregator import ResultAggregator, get_result_aggregator
from app.engines.orchestrator.audit_logger import QueryAuditLogger, get_query_audit_logger
from app.engines.orchestrator.executor import EngineExecutor, get_engine_executor
from app.engines.orchestrator.intent_analyzer import IntentAnalyzer, get_intent_analyzer
from app.engines.orchestrator.planner import ExecutionPlanner, get_execution_planner
from app.engines.orchestrator.query_history import QueryHistoryStore, get_query_history_store
from app.models.orchestrator import (
    IntentAnalysisResult,
    OrchestratorResult,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Query Orchestrator (Task 6.1-6.5)
# =============================================================================


class QueryOrchestrator:
    """Main orchestrator for query processing.

    Story 6-2: Full pipeline from query to unified response.
    Story 6-3: Audit trail logging for forensic compliance.

    Pipeline:
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
        intent_analyzer: IntentAnalyzer | None = None,
        planner: ExecutionPlanner | None = None,
        executor: EngineExecutor | None = None,
        aggregator: ResultAggregator | None = None,
        audit_logger: QueryAuditLogger | None = None,
        history_store: QueryHistoryStore | None = None,
    ) -> None:
        """Initialize query orchestrator.

        Task 6.3: Wire up all components.
        Story 6-3: Add audit logging components.

        Args:
            intent_analyzer: Optional custom intent analyzer.
            planner: Optional custom execution planner.
            executor: Optional custom engine executor.
            aggregator: Optional custom result aggregator.
            audit_logger: Optional custom audit logger (Story 6-3).
            history_store: Optional custom history store (Story 6-3).
        """
        self._intent_analyzer = intent_analyzer or get_intent_analyzer()
        self._planner = planner or get_execution_planner()
        self._executor = executor or get_engine_executor()
        self._aggregator = aggregator or get_result_aggregator()
        self._audit_logger = audit_logger or get_query_audit_logger()
        self._history_store = history_store or get_query_history_store()

        logger.info("query_orchestrator_initialized")

    async def process_query(
        self,
        matter_id: str,
        query: str,
        user_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> OrchestratorResult:
        """Process user query through full orchestration pipeline.

        Task 6.2: Full pipeline: intent → plan → execute → aggregate.
        Story 6-3: Add audit logging (non-blocking).

        Args:
            matter_id: Matter UUID for isolation.
            query: User's natural language query.
            user_id: User ID for audit trail (Story 6-3). Optional for backward compat.
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

        # Step 1: Analyze intent and determine required engines
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

        # Step 3: Aggregate results
        wall_clock_time_ms = int((time.time() - start_time) * 1000)

        result = self._aggregator.aggregate_results(
            matter_id=matter_id,
            query=query,
            results=engine_results,
            wall_clock_time_ms=wall_clock_time_ms,
        )

        logger.info(
            "process_query_complete",
            matter_id=matter_id,
            successful_engines=[e.value for e in result.successful_engines],
            failed_engines=[e.value for e in result.failed_engines],
            confidence=result.confidence,
            wall_clock_time_ms=result.wall_clock_time_ms,
        )

        # Step 4: Audit logging (non-blocking, fire-and-forget)
        # Story 6-3: AC #5 - audit failures should not fail the query
        if user_id:
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

    @property
    def intent_analyzer(self) -> IntentAnalyzer:
        """Get the intent analyzer instance."""
        return self._intent_analyzer

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
