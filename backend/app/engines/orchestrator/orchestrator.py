"""Query Orchestrator - Main orchestration pipeline.

Story 6-2: Engine Execution Ordering (AC: #1)

Integrates all orchestration components:
- IntentAnalyzer (Story 6-1) → classify query intent
- ExecutionPlanner → determine parallel/sequential execution
- EngineExecutor → execute engines in parallel
- ResultAggregator → combine results into unified response

This is the main entry point for query processing.

CRITICAL: Matter isolation must be maintained through entire pipeline.
"""

import time
from functools import lru_cache
from typing import Any

import structlog

from app.engines.orchestrator.aggregator import ResultAggregator, get_result_aggregator
from app.engines.orchestrator.executor import EngineExecutor, get_engine_executor
from app.engines.orchestrator.intent_analyzer import IntentAnalyzer, get_intent_analyzer
from app.engines.orchestrator.planner import ExecutionPlanner, get_execution_planner
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

    Pipeline:
    1. IntentAnalyzer → classify query, determine required engines
    2. ExecutionPlanner → create execution plan (parallel groups)
    3. EngineExecutor → execute engines with parallel optimization
    4. ResultAggregator → combine results into unified response

    Example:
        >>> orchestrator = get_query_orchestrator()
        >>> result = await orchestrator.process_query(
        ...     matter_id="matter-123",
        ...     query="What citations are in this case?",
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
    ) -> None:
        """Initialize query orchestrator.

        Task 6.3: Wire up all components.

        Args:
            intent_analyzer: Optional custom intent analyzer.
            planner: Optional custom execution planner.
            executor: Optional custom engine executor.
            aggregator: Optional custom result aggregator.
        """
        self._intent_analyzer = intent_analyzer or get_intent_analyzer()
        self._planner = planner or get_execution_planner()
        self._executor = executor or get_engine_executor()
        self._aggregator = aggregator or get_result_aggregator()

        logger.info("query_orchestrator_initialized")

    async def process_query(
        self,
        matter_id: str,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> OrchestratorResult:
        """Process user query through full orchestration pipeline.

        Task 6.2: Full pipeline: intent → plan → execute → aggregate.

        Args:
            matter_id: Matter UUID for isolation.
            query: User's natural language query.
            context: Optional conversation context.

        Returns:
            OrchestratorResult with unified response from all engines.
        """
        start_time = time.time()

        logger.info(
            "process_query_start",
            matter_id=matter_id,
            query_length=len(query),
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

        return result

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
