"""Engine Executor for parallel engine execution.

Story 6-2: Engine Execution Ordering (AC: #1-2)

Orchestrates multiple engine calls with parallel execution support.
Uses asyncio.gather for concurrent execution of independent engines.

CRITICAL: 30 second timeout per engine to prevent blocking.
CRITICAL: Matter isolation must be maintained through all engine calls.
"""

import asyncio
import time
from functools import lru_cache
from typing import Any

import structlog

from app.engines.orchestrator.adapters import get_cached_adapter
from app.engines.orchestrator.planner import get_execution_planner
from app.models.orchestrator import (
    EngineExecutionResult,
    EngineType,
    ExecutionPlan,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Timeout per engine in seconds
ENGINE_TIMEOUT_SECONDS = 30.0


# =============================================================================
# Engine Executor (Task 2.1-2.6)
# =============================================================================


class EngineExecutor:
    """Executes engines with parallel execution support.

    Story 6-2: Orchestrates multiple engine calls efficiently.

    Pipeline:
    1. Get execution plan from planner (parallel groups)
    2. Execute each group sequentially
    3. Within each group, execute engines in parallel
    4. Track execution time and costs

    Example:
        >>> executor = get_engine_executor()
        >>> results = await executor.execute_engines(
        ...     matter_id="matter-123",
        ...     query="What are the citations and timeline?",
        ...     engines=[EngineType.CITATION, EngineType.TIMELINE],
        ... )
        >>> len(results)
        2
    """

    def __init__(self) -> None:
        """Initialize engine executor."""
        self._planner = get_execution_planner()
        logger.info("engine_executor_initialized")

    async def execute_engines(
        self,
        matter_id: str,
        query: str,
        engines: list[EngineType],
        context: dict[str, Any] | None = None,
    ) -> list[EngineExecutionResult]:
        """Execute multiple engines with parallel optimization.

        Task 2.2: Main orchestration method.

        Args:
            matter_id: Matter UUID for isolation.
            query: User's query.
            engines: Engines to execute.
            context: Optional conversation context.

        Returns:
            List of EngineExecutionResult from all engines.
        """
        if not engines:
            logger.debug("execute_engines_empty_list", matter_id=matter_id)
            return []

        start_time = time.time()

        # Get execution plan
        plan = self._planner.create_execution_plan(engines)

        logger.info(
            "execute_engines_start",
            matter_id=matter_id,
            total_engines=len(engines),
            num_groups=len(plan.parallel_groups),
            parallelism=plan.estimated_parallelism,
        )

        # Execute groups sequentially, engines within groups in parallel
        all_results: list[EngineExecutionResult] = []

        for group_idx, group in enumerate(plan.parallel_groups):
            group_results = await self._execute_parallel_group(
                matter_id=matter_id,
                query=query,
                engines=group,
                context=context,
                group_index=group_idx,
            )
            all_results.extend(group_results)

        wall_clock_time = int((time.time() - start_time) * 1000)
        total_engine_time = sum(r.execution_time_ms for r in all_results)

        successful = sum(1 for r in all_results if r.success)
        failed = sum(1 for r in all_results if not r.success)

        logger.info(
            "execute_engines_complete",
            matter_id=matter_id,
            total_engines=len(engines),
            successful=successful,
            failed=failed,
            wall_clock_time_ms=wall_clock_time,
            total_engine_time_ms=total_engine_time,
        )

        return all_results

    async def _execute_parallel_group(
        self,
        matter_id: str,
        query: str,
        engines: list[EngineType],
        context: dict[str, Any] | None,
        group_index: int,
    ) -> list[EngineExecutionResult]:
        """Execute a group of engines in parallel.

        Task 2.3: Run independent engines concurrently with asyncio.gather.

        Args:
            matter_id: Matter UUID.
            query: User's query.
            engines: Engines to execute in parallel.
            context: Optional context.
            group_index: Index of this group (for logging).

        Returns:
            List of results from all engines in the group.
        """
        logger.debug(
            "execute_parallel_group_start",
            matter_id=matter_id,
            group_index=group_index,
            engines=[e.value for e in engines],
        )

        # Create tasks for parallel execution
        tasks = [
            self._execute_single_engine(
                matter_id=matter_id,
                query=query,
                engine=engine,
                context=context,
            )
            for engine in engines
        ]

        # Execute all tasks in parallel, catching exceptions
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results, converting exceptions to error results
        processed_results: list[EngineExecutionResult] = []
        for engine, result in zip(engines, results):
            if isinstance(result, Exception):
                logger.error(
                    "parallel_group_exception",
                    matter_id=matter_id,
                    engine=engine.value,
                    error=str(result),
                )
                processed_results.append(
                    EngineExecutionResult(
                        engine=engine,
                        success=False,
                        error=f"Unexpected error: {result}",
                        execution_time_ms=0,
                    )
                )
            else:
                processed_results.append(result)

        return processed_results

    async def _execute_single_engine(
        self,
        matter_id: str,
        query: str,
        engine: EngineType,
        context: dict[str, Any] | None = None,
    ) -> EngineExecutionResult:
        """Execute a single engine with error handling and timeout.

        Task 2.4: Call individual engine with error handling.

        Args:
            matter_id: Matter UUID.
            query: User's query.
            engine: Engine to execute.
            context: Optional context.

        Returns:
            EngineExecutionResult from the engine.
        """
        start_time = time.time()

        try:
            adapter = get_cached_adapter(engine)

            # Execute with timeout
            result = await asyncio.wait_for(
                adapter.execute(
                    matter_id=matter_id,
                    query=query,
                    context=context,
                ),
                timeout=ENGINE_TIMEOUT_SECONDS,
            )

            logger.debug(
                "execute_single_engine_success",
                matter_id=matter_id,
                engine=engine.value,
                success=result.success,
                execution_time_ms=result.execution_time_ms,
            )

            return result

        except TimeoutError:
            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.warning(
                "engine_timeout",
                engine=engine.value,
                matter_id=matter_id,
                timeout_seconds=ENGINE_TIMEOUT_SECONDS,
            )

            return EngineExecutionResult(
                engine=engine,
                success=False,
                error=f"Engine timed out after {ENGINE_TIMEOUT_SECONDS} seconds",
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)

            logger.error(
                "engine_execution_failed",
                engine=engine.value,
                matter_id=matter_id,
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

            return EngineExecutionResult(
                engine=engine,
                success=False,
                error=str(e),
                execution_time_ms=execution_time_ms,
            )

    def get_execution_plan(self, engines: list[EngineType]) -> ExecutionPlan:
        """Get execution plan for engines.

        Task 2.6: Expose planning for external inspection.

        Args:
            engines: Engines to plan for.

        Returns:
            ExecutionPlan with parallel groups.
        """
        return self._planner.create_execution_plan(engines)


# =============================================================================
# Factory Function (Task 2.5)
# =============================================================================


@lru_cache(maxsize=1)
def get_engine_executor() -> EngineExecutor:
    """Get singleton engine executor instance.

    Returns:
        EngineExecutor instance.
    """
    return EngineExecutor()
