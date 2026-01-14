"""Execution Planner for engine orchestration.

Story 6-2: Engine Execution Ordering (AC: #3)

Creates execution plans that determine which engines can run in parallel
vs which must wait for dependencies.

CRITICAL: All current engines are independent - they query the database
directly for MIG data rather than depending on other engine outputs.
This allows maximum parallelization.
"""

from functools import lru_cache

import structlog

from app.models.orchestrator import (
    EngineType,
    ExecutionPlan,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Engine Dependencies (Task 3.2)
# =============================================================================

# Define which engines depend on others' outputs (not shared data).
# Currently all engines are independent - they access DB/MIG directly.
ENGINE_DEPENDENCIES: dict[EngineType, list[EngineType]] = {
    EngineType.CITATION: [],  # Independent - can always run
    EngineType.TIMELINE: [],  # Independent - can always run
    EngineType.CONTRADICTION: [],  # Independent - uses MIG data directly from DB
    EngineType.RAG: [],  # Independent - always available
}


# =============================================================================
# Execution Planner (Task 3.1, 3.3-3.6)
# =============================================================================


class ExecutionPlanner:
    """Creates execution plans for engine orchestration.

    Story 6-2: Determines parallel vs sequential execution groups.

    Since all current engines are independent (they query DB directly),
    all engines can run in parallel. The planner is designed to handle
    future dependencies if needed.

    Example:
        >>> planner = get_execution_planner()
        >>> plan = planner.create_execution_plan([
        ...     EngineType.CITATION,
        ...     EngineType.TIMELINE,
        ... ])
        >>> plan.parallel_groups
        [[EngineType.CITATION, EngineType.TIMELINE]]
    """

    def __init__(self) -> None:
        """Initialize execution planner."""
        self._dependencies = ENGINE_DEPENDENCIES
        logger.info("execution_planner_initialized")

    def create_execution_plan(
        self,
        engines: list[EngineType],
    ) -> ExecutionPlan:
        """Create execution plan for given engines.

        Task 3.3: Determine parallel vs sequential groups.

        Args:
            engines: List of engines to execute.

        Returns:
            ExecutionPlan with parallel groups and metadata.
        """
        if not engines:
            logger.debug("create_execution_plan_empty_engines")
            return ExecutionPlan(
                parallel_groups=[],
                total_engines=0,
                estimated_parallelism=1.0,
            )

        # Resolve dependencies and create execution groups
        parallel_groups = self._resolve_dependencies(engines)

        # Calculate parallelism factor
        total = len(engines)
        num_groups = len(parallel_groups)
        estimated_parallelism = total / num_groups if num_groups > 0 else 1.0

        logger.info(
            "execution_plan_created",
            total_engines=total,
            num_groups=num_groups,
            parallelism=estimated_parallelism,
            groups=[[e.value for e in group] for group in parallel_groups],
        )

        return ExecutionPlan(
            parallel_groups=parallel_groups,
            total_engines=total,
            estimated_parallelism=estimated_parallelism,
        )

    def _resolve_dependencies(
        self,
        engines: list[EngineType],
    ) -> list[list[EngineType]]:
        """Resolve engine dependencies using topological sort.

        Task 3.4: Determine execution order based on dependencies.

        Currently all engines are independent, so they all go in one group.
        This method handles future dependencies using Kahn's algorithm.

        Args:
            engines: Engines to order.

        Returns:
            List of parallel groups in execution order.
        """
        engine_set = set(engines)

        # Build dependency graph for requested engines only
        in_degree: dict[EngineType, int] = {e: 0 for e in engines}
        dependents: dict[EngineType, list[EngineType]] = {e: [] for e in engines}

        for engine in engines:
            deps = self._dependencies.get(engine, [])
            for dep in deps:
                if dep in engine_set:
                    in_degree[engine] += 1
                    dependents[dep].append(engine)

        # Kahn's algorithm: group engines by level
        groups: list[list[EngineType]] = []
        remaining = set(engines)

        while remaining:
            # Find all engines with no pending dependencies
            ready = [e for e in remaining if in_degree[e] == 0]

            if not ready:
                # Circular dependency detected - should not happen with current engines
                logger.error(
                    "circular_dependency_detected",
                    remaining=[e.value for e in remaining],
                )
                # Break cycle by including remaining engines
                ready = list(remaining)

            groups.append(ready)

            # Update in-degrees for next round
            for engine in ready:
                remaining.discard(engine)
                for dependent in dependents[engine]:
                    in_degree[dependent] -= 1

        return groups

    def _can_run_parallel(
        self,
        engine_a: EngineType,
        engine_b: EngineType,
    ) -> bool:
        """Check if two engines can run in parallel.

        Task 3.5: Engines can run in parallel if neither depends on the other.

        Args:
            engine_a: First engine.
            engine_b: Second engine.

        Returns:
            True if engines can run in parallel.
        """
        deps_a = self._dependencies.get(engine_a, [])
        deps_b = self._dependencies.get(engine_b, [])

        # Can run in parallel if neither depends on the other
        return engine_b not in deps_a and engine_a not in deps_b

    def get_dependencies(self, engine: EngineType) -> list[EngineType]:
        """Get dependencies for an engine.

        Args:
            engine: Engine to check.

        Returns:
            List of engines this engine depends on.
        """
        return self._dependencies.get(engine, [])

    def has_dependencies(self, engine: EngineType) -> bool:
        """Check if engine has any dependencies.

        Args:
            engine: Engine to check.

        Returns:
            True if engine has dependencies.
        """
        return len(self.get_dependencies(engine)) > 0


# =============================================================================
# Factory Function (Task 3.6)
# =============================================================================


@lru_cache(maxsize=1)
def get_execution_planner() -> ExecutionPlanner:
    """Get singleton execution planner instance.

    Returns:
        ExecutionPlanner instance.
    """
    return ExecutionPlanner()
