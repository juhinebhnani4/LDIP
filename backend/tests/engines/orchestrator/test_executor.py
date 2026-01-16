"""Tests for the Engine Executor.

Story 6-2: Engine Execution Ordering

Tests cover:
- Parallel engine execution (Task 2.3)
- Single engine execution (Task 2.4)
- Timeout handling (Task 2.4)
- Error handling (graceful degradation)
- Matter isolation (CRITICAL security test)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.orchestrator.executor import (
    ENGINE_TIMEOUT_SECONDS,
    EngineExecutor,
    get_engine_executor,
)
from app.models.orchestrator import (
    EngineExecutionResult,
    EngineType,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_adapter():
    """Create mock adapter that returns success."""
    adapter = MagicMock()
    adapter.engine_type = EngineType.CITATION

    async def mock_execute(matter_id, query, context=None):
        return EngineExecutionResult(
            engine=EngineType.CITATION,
            success=True,
            data={"test": "data"},
            execution_time_ms=50,
            confidence=0.9,
        )

    adapter.execute = AsyncMock(side_effect=mock_execute)
    return adapter


@pytest.fixture
def mock_failing_adapter():
    """Create mock adapter that returns failure."""
    adapter = MagicMock()
    adapter.engine_type = EngineType.TIMELINE

    async def mock_execute(matter_id, query, context=None):
        return EngineExecutionResult(
            engine=EngineType.TIMELINE,
            success=False,
            error="Test error",
            execution_time_ms=30,
        )

    adapter.execute = AsyncMock(side_effect=mock_execute)
    return adapter


@pytest.fixture
def mock_slow_adapter():
    """Create mock adapter that times out."""
    adapter = MagicMock()
    adapter.engine_type = EngineType.RAG

    async def mock_execute(matter_id, query, context=None):
        await asyncio.sleep(ENGINE_TIMEOUT_SECONDS + 1)
        return EngineExecutionResult(
            engine=EngineType.RAG,
            success=True,
            data={},
            execution_time_ms=0,
        )

    adapter.execute = AsyncMock(side_effect=mock_execute)
    return adapter


@pytest.fixture
def mock_adapters(mock_adapter):
    """Patch get_cached_adapter to return mock adapters."""
    adapters = {}

    # Create adapters for each engine type
    for engine_type in EngineType:
        adapter = MagicMock()
        adapter.engine_type = engine_type

        # Create proper async mock - need closure to capture engine_type
        def make_execute_fn(et):
            async def execute_fn(matter_id, query, context=None):
                return EngineExecutionResult(
                    engine=et,
                    success=True,
                    data={"engine": et.value},
                    execution_time_ms=50,
                    confidence=0.85,
                )
            return execute_fn

        adapter.execute = AsyncMock(side_effect=make_execute_fn(engine_type))
        adapters[engine_type] = adapter

    with patch("app.engines.orchestrator.executor.get_cached_adapter") as mock:
        mock.side_effect = lambda et: adapters[et]
        yield adapters


@pytest.fixture
def executor():
    """Create EngineExecutor instance."""
    get_engine_executor.cache_clear()
    return EngineExecutor()


# =============================================================================
# Unit Tests: Parallel Execution (Task 2.3)
# =============================================================================


class TestParallelExecution:
    """Tests for parallel engine execution."""

    @pytest.mark.asyncio
    async def test_execute_parallel_engines(self, executor, mock_adapters):
        """Multiple engines should execute in parallel."""
        results = await executor.execute_engines(
            matter_id="matter-123",
            query="Test query",
            engines=[EngineType.CITATION, EngineType.TIMELINE],
        )

        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_execute_empty_engines(self, executor):
        """Empty engine list returns empty results."""
        results = await executor.execute_engines(
            matter_id="matter-123",
            query="Test query",
            engines=[],
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_execute_single_engine(self, executor, mock_adapters):
        """Single engine execution works correctly."""
        results = await executor.execute_engines(
            matter_id="matter-123",
            query="Test query",
            engines=[EngineType.CITATION],
        )

        assert len(results) == 1
        assert results[0].engine == EngineType.CITATION
        assert results[0].success

    @pytest.mark.asyncio
    async def test_execute_all_four_engines(self, executor, mock_adapters):
        """All four engines can execute in parallel."""
        results = await executor.execute_engines(
            matter_id="matter-123",
            query="Test query",
            engines=[
                EngineType.CITATION,
                EngineType.TIMELINE,
                EngineType.CONTRADICTION,
                EngineType.RAG,
            ],
        )

        assert len(results) == 4
        engines_returned = {r.engine for r in results}
        assert engines_returned == {
            EngineType.CITATION,
            EngineType.TIMELINE,
            EngineType.CONTRADICTION,
            EngineType.RAG,
        }


# =============================================================================
# Unit Tests: Error Handling
# =============================================================================


class TestErrorHandling:
    """Tests for error handling and graceful degradation."""

    @pytest.mark.asyncio
    async def test_execute_with_one_failure(self, executor):
        """If one engine fails, others should still succeed."""
        success_adapter = MagicMock()
        success_adapter.engine_type = EngineType.CITATION
        success_adapter.execute = AsyncMock(return_value=EngineExecutionResult(
            engine=EngineType.CITATION,
            success=True,
            data={"test": "data"},
            execution_time_ms=50,
        ))

        failure_adapter = MagicMock()
        failure_adapter.engine_type = EngineType.TIMELINE
        failure_adapter.execute = AsyncMock(return_value=EngineExecutionResult(
            engine=EngineType.TIMELINE,
            success=False,
            error="Test failure",
            execution_time_ms=30,
        ))

        adapters = {
            EngineType.CITATION: success_adapter,
            EngineType.TIMELINE: failure_adapter,
        }

        with patch("app.engines.orchestrator.executor.get_cached_adapter") as mock:
            mock.side_effect = lambda et: adapters[et]

            results = await executor.execute_engines(
                matter_id="matter-123",
                query="Test query",
                engines=[EngineType.CITATION, EngineType.TIMELINE],
            )

        assert len(results) == 2
        # One success, one failure
        assert sum(1 for r in results if r.success) == 1
        assert sum(1 for r in results if not r.success) == 1

    @pytest.mark.asyncio
    async def test_execute_with_exception(self, executor):
        """Exception in adapter should return error result."""
        exception_adapter = MagicMock()
        exception_adapter.engine_type = EngineType.CITATION
        exception_adapter.execute = AsyncMock(side_effect=Exception("Unexpected error"))

        with patch("app.engines.orchestrator.executor.get_cached_adapter") as mock:
            mock.return_value = exception_adapter

            results = await executor.execute_engines(
                matter_id="matter-123",
                query="Test query",
                engines=[EngineType.CITATION],
            )

        assert len(results) == 1
        assert not results[0].success
        assert "Unexpected error" in results[0].error


# =============================================================================
# Unit Tests: Timeout Handling (Task 2.4)
# =============================================================================


class TestTimeoutHandling:
    """Tests for timeout handling."""

    @pytest.mark.asyncio
    async def test_execute_timeout_handling(self, executor, mock_slow_adapter):
        """Slow engines should timeout gracefully."""
        with patch("app.engines.orchestrator.executor.get_cached_adapter") as mock:
            mock.return_value = mock_slow_adapter

            # Use a shorter timeout for test
            with patch("app.engines.orchestrator.executor.ENGINE_TIMEOUT_SECONDS", 0.1):
                result = await executor._execute_single_engine(
                    matter_id="matter-123",
                    query="Query",
                    engine=EngineType.RAG,
                )

        assert not result.success
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_timeout_doesnt_block_other_engines(self, executor):
        """One timing out engine shouldn't block others."""
        fast_adapter = MagicMock()
        fast_adapter.engine_type = EngineType.CITATION
        fast_adapter.execute = AsyncMock(return_value=EngineExecutionResult(
            engine=EngineType.CITATION,
            success=True,
            data={},
            execution_time_ms=10,
        ))

        async def slow_execute(matter_id, query, context=None):
            await asyncio.sleep(1.0)  # Slow but within timeout
            return EngineExecutionResult(
                engine=EngineType.TIMELINE,
                success=True,
                data={},
                execution_time_ms=1000,
            )

        slow_adapter = MagicMock()
        slow_adapter.engine_type = EngineType.TIMELINE
        slow_adapter.execute = AsyncMock(side_effect=slow_execute)

        adapters = {
            EngineType.CITATION: fast_adapter,
            EngineType.TIMELINE: slow_adapter,
        }

        with patch("app.engines.orchestrator.executor.get_cached_adapter") as mock:
            mock.side_effect = lambda et: adapters[et]

            results = await executor.execute_engines(
                matter_id="matter-123",
                query="Test query",
                engines=[EngineType.CITATION, EngineType.TIMELINE],
            )

        assert len(results) == 2
        # Both should complete
        assert all(r.success for r in results)


# =============================================================================
# Unit Tests: Matter Isolation (CRITICAL)
# =============================================================================


class TestMatterIsolation:
    """Tests for matter isolation - CRITICAL security tests."""

    @pytest.mark.asyncio
    async def test_matter_id_propagated_to_adapters(self, executor):
        """Verify matter_id is passed to all engine adapters."""
        captured_matter_ids = []

        async def capture_execute(matter_id, query, context=None):
            captured_matter_ids.append(matter_id)
            return EngineExecutionResult(
                engine=EngineType.CITATION,
                success=True,
                data={},
                execution_time_ms=10,
            )

        adapter = MagicMock()
        adapter.engine_type = EngineType.CITATION
        adapter.execute = AsyncMock(side_effect=capture_execute)

        with patch("app.engines.orchestrator.executor.get_cached_adapter") as mock:
            mock.return_value = adapter

            await executor.execute_engines(
                matter_id="secure-matter-123",
                query="Test query",
                engines=[EngineType.CITATION],
            )

        assert len(captured_matter_ids) == 1
        assert captured_matter_ids[0] == "secure-matter-123"

    @pytest.mark.asyncio
    async def test_matter_id_propagated_to_multiple_engines(self, executor):
        """Verify matter_id is passed to all engines when running multiple."""
        captured_calls = []

        def make_adapter(engine_type):
            async def capture_execute(matter_id, query, context=None):
                captured_calls.append({
                    "engine": engine_type,
                    "matter_id": matter_id,
                })
                return EngineExecutionResult(
                    engine=engine_type,
                    success=True,
                    data={},
                    execution_time_ms=10,
                )

            adapter = MagicMock()
            adapter.engine_type = engine_type
            adapter.execute = AsyncMock(side_effect=capture_execute)
            return adapter

        adapters = {
            EngineType.CITATION: make_adapter(EngineType.CITATION),
            EngineType.TIMELINE: make_adapter(EngineType.TIMELINE),
        }

        with patch("app.engines.orchestrator.executor.get_cached_adapter") as mock:
            mock.side_effect = lambda et: adapters[et]

            await executor.execute_engines(
                matter_id="test-matter-xyz",
                query="Test query",
                engines=[EngineType.CITATION, EngineType.TIMELINE],
            )

        # Both engines should receive the same matter_id
        assert len(captured_calls) == 2
        assert all(c["matter_id"] == "test-matter-xyz" for c in captured_calls)


# =============================================================================
# Unit Tests: Factory Function
# =============================================================================


class TestExecutorFactory:
    """Tests for get_engine_executor factory."""

    def test_factory_returns_executor(self):
        """Factory should return EngineExecutor instance."""
        get_engine_executor.cache_clear()
        executor = get_engine_executor()

        assert isinstance(executor, EngineExecutor)

    def test_factory_returns_singleton(self):
        """Factory should return the same instance (cached)."""
        get_engine_executor.cache_clear()
        executor1 = get_engine_executor()
        executor2 = get_engine_executor()

        assert executor1 is executor2
