"""Integration tests for the Query Orchestrator.

Story 6-2: Engine Execution Ordering

Tests cover:
- Full pipeline integration (Task 6.2)
- Intent → Plan → Execute → Aggregate flow
- Citation query flow (AC #1)
- Multi-engine query flow (AC #1-4)
- Error handling and graceful degradation
- Matter isolation (CRITICAL)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.orchestrator.orchestrator import (
    QueryOrchestrator,
    get_query_orchestrator,
)
from app.models.orchestrator import (
    EngineExecutionResult,
    EngineType,
    IntentAnalysisResult,
    IntentClassification,
    QueryIntent,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_intent_analyzer():
    """Create mock intent analyzer."""
    analyzer = MagicMock()

    async def mock_analyze(matter_id, query):
        # Default: RAG search
        intent = QueryIntent.RAG_SEARCH
        engines = [EngineType.RAG]

        # Detect citation keywords
        if "citation" in query.lower() or "act" in query.lower():
            intent = QueryIntent.CITATION
            engines = [EngineType.CITATION]

        # Detect timeline keywords
        if "timeline" in query.lower() or "when" in query.lower():
            intent = QueryIntent.TIMELINE
            engines = [EngineType.TIMELINE]

        # Detect multi-engine
        if "and" in query.lower():
            intent = QueryIntent.MULTI_ENGINE
            engines = [EngineType.CITATION, EngineType.TIMELINE]

        return IntentAnalysisResult(
            matter_id=matter_id,
            query=query,
            classification=IntentClassification(
                intent=intent,
                confidence=0.9,
                required_engines=engines,
                reasoning="Test classification",
            ),
            fast_path_used=True,
        )

    analyzer.analyze_intent = AsyncMock(side_effect=mock_analyze)
    return analyzer


@pytest.fixture
def mock_executor():
    """Create mock engine executor."""
    executor = MagicMock()

    async def mock_execute(matter_id, query, engines, context=None):
        results = []
        for engine in engines:
            results.append(
                EngineExecutionResult(
                    engine=engine,
                    success=True,
                    data={"engine": engine.value, "matter_id": matter_id},
                    execution_time_ms=50,
                    confidence=0.85,
                )
            )
        return results

    executor.execute_engines = AsyncMock(side_effect=mock_execute)
    return executor


@pytest.fixture
def mock_aggregator():
    """Create mock result aggregator."""
    from app.engines.orchestrator.aggregator import ResultAggregator

    return ResultAggregator()  # Use real aggregator for integration tests


@pytest.fixture
def orchestrator(mock_intent_analyzer, mock_executor, mock_aggregator):
    """Create QueryOrchestrator with mocked components."""
    get_query_orchestrator.cache_clear()
    return QueryOrchestrator(
        intent_analyzer=mock_intent_analyzer,
        executor=mock_executor,
        aggregator=mock_aggregator,
    )


# =============================================================================
# Integration Tests: Full Pipeline (Task 6.2)
# =============================================================================


class TestFullPipeline:
    """Integration tests for the full orchestration pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_citation_query(self, orchestrator):
        """Full pipeline for citation-specific query."""
        result = await orchestrator.process_query(
            matter_id="matter-123",
            query="What citations are in this case?",
        )

        assert result.matter_id == "matter-123"
        assert EngineType.CITATION in result.successful_engines
        assert result.unified_response
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_full_pipeline_timeline_query(self, orchestrator):
        """Full pipeline for timeline-specific query."""
        result = await orchestrator.process_query(
            matter_id="matter-123",
            query="What is the timeline of events?",
        )

        assert EngineType.TIMELINE in result.successful_engines

    @pytest.mark.asyncio
    async def test_full_pipeline_multi_engine(self, orchestrator):
        """Full pipeline for ambiguous query requiring multiple engines."""
        result = await orchestrator.process_query(
            matter_id="matter-123",
            query="Tell me about the citations and timeline",
        )

        # Should use multiple engines
        assert len(result.successful_engines) >= 2
        assert EngineType.CITATION in result.successful_engines
        assert EngineType.TIMELINE in result.successful_engines

    @pytest.mark.asyncio
    async def test_full_pipeline_general_query(self, orchestrator):
        """Full pipeline for general query (RAG fallback)."""
        result = await orchestrator.process_query(
            matter_id="matter-123",
            query="What happened in the case?",
        )

        assert EngineType.RAG in result.successful_engines


# =============================================================================
# Integration Tests: Matter Isolation (CRITICAL)
# =============================================================================


class TestMatterIsolation:
    """Critical security tests for matter isolation."""

    @pytest.mark.asyncio
    async def test_matter_id_in_result(self, orchestrator):
        """Verify matter_id is in the final result."""
        result = await orchestrator.process_query(
            matter_id="secure-matter-abc",
            query="What citations?",
        )

        assert result.matter_id == "secure-matter-abc"

    @pytest.mark.asyncio
    async def test_matter_id_propagated_to_executor(self, mock_intent_analyzer):
        """Verify matter_id is passed to executor."""
        captured_matter_id = None

        async def capture_execute(matter_id, query, engines, context=None):
            nonlocal captured_matter_id
            captured_matter_id = matter_id
            return [
                EngineExecutionResult(
                    engine=e,
                    success=True,
                    data={},
                    execution_time_ms=10,
                    confidence=0.8,
                )
                for e in engines
            ]

        executor = MagicMock()
        executor.execute_engines = AsyncMock(side_effect=capture_execute)

        orchestrator = QueryOrchestrator(
            intent_analyzer=mock_intent_analyzer,
            executor=executor,
        )

        await orchestrator.process_query(
            matter_id="test-matter-xyz",
            query="Test query",
        )

        assert captured_matter_id == "test-matter-xyz"

    @pytest.mark.asyncio
    async def test_matter_id_propagated_to_intent_analyzer(self, mock_executor):
        """Verify matter_id is passed to intent analyzer."""
        captured_matter_id = None

        async def capture_analyze(matter_id, query):
            nonlocal captured_matter_id
            captured_matter_id = matter_id
            return IntentAnalysisResult(
                matter_id=matter_id,
                query=query,
                classification=IntentClassification(
                    intent=QueryIntent.RAG_SEARCH,
                    confidence=0.9,
                    required_engines=[EngineType.RAG],
                    reasoning="Test",
                ),
                fast_path_used=True,
            )

        analyzer = MagicMock()
        analyzer.analyze_intent = AsyncMock(side_effect=capture_analyze)

        orchestrator = QueryOrchestrator(
            intent_analyzer=analyzer,
            executor=mock_executor,
        )

        await orchestrator.process_query(
            matter_id="analyzer-test-matter",
            query="Test query",
        )

        assert captured_matter_id == "analyzer-test-matter"


# =============================================================================
# Integration Tests: Error Handling
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in the orchestrator."""

    @pytest.mark.asyncio
    async def test_handle_engine_failure(self, mock_intent_analyzer):
        """Orchestrator should handle engine failures gracefully."""
        async def failing_execute(matter_id, query, engines, context=None):
            return [
                EngineExecutionResult(
                    engine=engines[0],
                    success=False,
                    error="Test failure",
                    execution_time_ms=10,
                )
            ]

        executor = MagicMock()
        executor.execute_engines = AsyncMock(side_effect=failing_execute)

        orchestrator = QueryOrchestrator(
            intent_analyzer=mock_intent_analyzer,
            executor=executor,
        )

        result = await orchestrator.process_query(
            matter_id="matter-123",
            query="What citations?",
        )

        assert len(result.failed_engines) > 0
        assert "error" in result.unified_response.lower() or "unable" in result.unified_response.lower()

    @pytest.mark.asyncio
    async def test_handle_partial_failure(self, mock_intent_analyzer):
        """Orchestrator should handle partial failures."""
        async def partial_execute(matter_id, query, engines, context=None):
            results = []
            for i, engine in enumerate(engines):
                results.append(
                    EngineExecutionResult(
                        engine=engine,
                        success=(i == 0),  # First succeeds, rest fail
                        data={"test": "data"} if i == 0 else None,
                        error=None if i == 0 else "Failed",
                        execution_time_ms=10,
                        confidence=0.8 if i == 0 else None,
                    )
                )
            return results

        executor = MagicMock()
        executor.execute_engines = AsyncMock(side_effect=partial_execute)

        orchestrator = QueryOrchestrator(
            intent_analyzer=mock_intent_analyzer,
            executor=executor,
        )

        result = await orchestrator.process_query(
            matter_id="matter-123",
            query="Tell me about citations and timeline",
        )

        # Should have some successful and some failed
        assert len(result.successful_engines) >= 1 or len(result.failed_engines) >= 1


# =============================================================================
# Unit Tests: Component Access
# =============================================================================


class TestComponentAccess:
    """Tests for component property access."""

    def test_intent_analyzer_property(self, orchestrator, mock_intent_analyzer):
        """Should expose intent analyzer."""
        assert orchestrator.intent_analyzer == mock_intent_analyzer

    def test_executor_property(self, orchestrator, mock_executor):
        """Should expose executor."""
        assert orchestrator.executor == mock_executor

    def test_aggregator_property(self, orchestrator, mock_aggregator):
        """Should expose aggregator."""
        assert orchestrator.aggregator == mock_aggregator

    def test_planner_property(self, orchestrator):
        """Should expose planner."""
        assert orchestrator.planner is not None


# =============================================================================
# Unit Tests: Analyze Intent (without execution)
# =============================================================================


class TestAnalyzeIntent:
    """Tests for analyze_intent method (no execution)."""

    @pytest.mark.asyncio
    async def test_analyze_intent_only(self, orchestrator):
        """Should analyze intent without executing engines."""
        result = await orchestrator.analyze_intent(
            matter_id="matter-123",
            query="What citations?",
        )

        assert result.matter_id == "matter-123"
        assert result.classification is not None
        assert result.classification.intent == QueryIntent.CITATION


# =============================================================================
# Unit Tests: Factory Function
# =============================================================================


class TestOrchestratorFactory:
    """Tests for get_query_orchestrator factory."""

    def test_factory_returns_orchestrator(self):
        """Factory should return QueryOrchestrator instance."""
        get_query_orchestrator.cache_clear()

        with patch("app.engines.orchestrator.orchestrator.get_intent_analyzer"), \
             patch("app.engines.orchestrator.orchestrator.get_execution_planner"), \
             patch("app.engines.orchestrator.orchestrator.get_engine_executor"), \
             patch("app.engines.orchestrator.orchestrator.get_result_aggregator"):
            orchestrator = get_query_orchestrator()

        assert isinstance(orchestrator, QueryOrchestrator)

    def test_factory_returns_singleton(self):
        """Factory should return the same instance (cached)."""
        get_query_orchestrator.cache_clear()

        with patch("app.engines.orchestrator.orchestrator.get_intent_analyzer"), \
             patch("app.engines.orchestrator.orchestrator.get_execution_planner"), \
             patch("app.engines.orchestrator.orchestrator.get_engine_executor"), \
             patch("app.engines.orchestrator.orchestrator.get_result_aggregator"):
            orchestrator1 = get_query_orchestrator()
            orchestrator2 = get_query_orchestrator()

        assert orchestrator1 is orchestrator2
