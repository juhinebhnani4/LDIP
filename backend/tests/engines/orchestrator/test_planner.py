"""Tests for the Execution Planner.

Story 6-2: Engine Execution Ordering

Tests cover:
- Creating execution plans (Task 3.3)
- Dependency resolution (Task 3.4)
- Parallel group detection (Task 3.5)
- Single engine plans
- All engines parallel (current behavior)
"""

import pytest

from app.engines.orchestrator.planner import (
    ENGINE_DEPENDENCIES,
    ExecutionPlanner,
    get_execution_planner,
)
from app.models.orchestrator import EngineType


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def planner():
    """Create ExecutionPlanner instance."""
    get_execution_planner.cache_clear()
    return ExecutionPlanner()


# =============================================================================
# Unit Tests: Execution Plan Creation (Task 3.3)
# =============================================================================


class TestExecutionPlanCreation:
    """Tests for create_execution_plan method."""

    def test_create_plan_empty_engines(self, planner):
        """Empty engine list returns empty plan."""
        plan = planner.create_execution_plan([])

        assert plan.parallel_groups == []
        assert plan.total_engines == 0
        assert plan.estimated_parallelism == 1.0

    def test_create_plan_single_engine(self, planner):
        """Single engine should have one group with one engine."""
        plan = planner.create_execution_plan([EngineType.CITATION])

        assert len(plan.parallel_groups) == 1
        assert plan.parallel_groups[0] == [EngineType.CITATION]
        assert plan.total_engines == 1
        assert plan.estimated_parallelism == 1.0

    def test_create_plan_all_parallel(self, planner):
        """All independent engines should run in parallel (single group)."""
        engines = [EngineType.CITATION, EngineType.TIMELINE, EngineType.RAG]

        plan = planner.create_execution_plan(engines)

        # All engines are independent - should be in one group
        assert len(plan.parallel_groups) == 1
        assert len(plan.parallel_groups[0]) == 3
        assert set(plan.parallel_groups[0]) == set(engines)
        assert plan.total_engines == 3
        assert plan.estimated_parallelism == 3.0

    def test_create_plan_two_engines(self, planner):
        """Two independent engines should be parallel."""
        engines = [EngineType.CITATION, EngineType.TIMELINE]

        plan = planner.create_execution_plan(engines)

        assert len(plan.parallel_groups) == 1
        assert len(plan.parallel_groups[0]) == 2
        assert plan.estimated_parallelism == 2.0

    def test_create_plan_four_engines(self, planner):
        """Four independent engines should all be parallel."""
        engines = [
            EngineType.CITATION,
            EngineType.TIMELINE,
            EngineType.CONTRADICTION,
            EngineType.RAG,
        ]

        plan = planner.create_execution_plan(engines)

        assert len(plan.parallel_groups) == 1
        assert len(plan.parallel_groups[0]) == 4
        assert plan.total_engines == 4
        assert plan.estimated_parallelism == 4.0


# =============================================================================
# Unit Tests: Dependency Resolution (Task 3.4)
# =============================================================================


class TestDependencyResolution:
    """Tests for dependency resolution."""

    def test_engine_dependencies_all_empty(self):
        """All current engines should have no dependencies."""
        for engine in EngineType:
            deps = ENGINE_DEPENDENCIES.get(engine, [])
            assert deps == [], f"{engine.value} should have no dependencies"

    def test_get_dependencies_returns_empty(self, planner):
        """get_dependencies should return empty list for all engines."""
        for engine in EngineType:
            deps = planner.get_dependencies(engine)
            assert deps == []

    def test_has_dependencies_returns_false(self, planner):
        """has_dependencies should return False for all engines."""
        for engine in EngineType:
            assert planner.has_dependencies(engine) is False


# =============================================================================
# Unit Tests: Parallel Detection (Task 3.5)
# =============================================================================


class TestParallelDetection:
    """Tests for parallel execution detection."""

    def test_can_run_parallel_all_engines(self, planner):
        """All current engines can run in parallel with each other."""
        engines = list(EngineType)

        for i, engine_a in enumerate(engines):
            for engine_b in engines[i + 1:]:
                assert planner._can_run_parallel(engine_a, engine_b) is True

    def test_can_run_parallel_citation_timeline(self, planner):
        """Citation and Timeline can run in parallel."""
        assert planner._can_run_parallel(
            EngineType.CITATION, EngineType.TIMELINE
        ) is True

    def test_can_run_parallel_contradiction_rag(self, planner):
        """Contradiction and RAG can run in parallel."""
        assert planner._can_run_parallel(
            EngineType.CONTRADICTION, EngineType.RAG
        ) is True


# =============================================================================
# Unit Tests: Factory Function
# =============================================================================


class TestPlannerFactory:
    """Tests for get_execution_planner factory."""

    def test_factory_returns_planner(self):
        """Factory should return ExecutionPlanner instance."""
        get_execution_planner.cache_clear()
        planner = get_execution_planner()

        assert isinstance(planner, ExecutionPlanner)

    def test_factory_returns_singleton(self):
        """Factory should return the same instance (cached)."""
        get_execution_planner.cache_clear()
        planner1 = get_execution_planner()
        planner2 = get_execution_planner()

        assert planner1 is planner2
