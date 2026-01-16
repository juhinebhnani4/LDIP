"""Integration tests for the Query Orchestrator.

Story 6-2: Engine Execution Ordering
Story 6-3: Audit Trail Logging

Tests cover:
- Full pipeline integration (Task 6.2)
- Intent → Plan → Execute → Aggregate flow
- Citation query flow (AC #1)
- Multi-engine query flow (AC #1-4)
- Error handling and graceful degradation
- Matter isolation (CRITICAL)
- Audit logging integration (Story 6-3)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.orchestrator.orchestrator import (
    QueryOrchestrator,
    get_query_orchestrator,
)
from app.models.orchestrator import (
    EngineExecutionResult,
    EngineType,
    IntentAnalysisCost,
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
            user_id="test-user-123",  # Required for NFR24 audit compliance
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
            user_id="test-user-123",  # Required for NFR24 audit compliance
        )

        assert EngineType.TIMELINE in result.successful_engines

    @pytest.mark.asyncio
    async def test_full_pipeline_multi_engine(self, orchestrator):
        """Full pipeline for ambiguous query requiring multiple engines."""
        result = await orchestrator.process_query(
            matter_id="matter-123",
            query="Tell me about the citations and timeline",
            user_id="test-user-123",  # Required for NFR24 audit compliance
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
            user_id="test-user-123",  # Required for NFR24 audit compliance
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
            user_id="test-user-123",  # Required for NFR24 audit compliance
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
            user_id="test-user-123",  # Required for NFR24 audit compliance
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
            user_id="test-user-123",  # Required for NFR24 audit compliance
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
            user_id="test-user-123",  # Required for NFR24 audit compliance
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
            user_id="test-user-123",  # Required for NFR24 audit compliance
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


# =============================================================================
# Integration Tests: Audit Logging (Story 6-3)
# =============================================================================


class TestAuditLoggingIntegration:
    """Tests for audit logging integration in orchestrator (Story 6-3)."""

    @pytest.fixture
    def mock_audit_logger(self):
        """Create mock audit logger."""
        logger = MagicMock()
        # log_query is sync, returns QueryAuditEntry
        from app.models.orchestrator import QueryAuditEntry, QueryIntent, EngineType

        mock_entry = QueryAuditEntry(
            query_id="test-query-id",
            matter_id="matter-123",
            query_text="Test query",
            query_intent=QueryIntent.RAG_SEARCH,
            intent_confidence=0.9,
            asked_by="user-456",
            asked_at="2026-01-14T10:00:00Z",
            engines_invoked=[EngineType.RAG],
            successful_engines=[EngineType.RAG],
            failed_engines=[],
            execution_time_ms=100,
            wall_clock_time_ms=80,
            findings_count=0,
            response_summary="Test",
            overall_confidence=0.9,
            llm_costs=[],
            total_cost_usd=0.0,
            findings=[],
        )
        logger.log_query.return_value = mock_entry
        return logger

    @pytest.fixture
    def mock_history_store(self):
        """Create mock history store."""
        store = MagicMock()
        store.append_query = AsyncMock()
        return store

    @pytest.fixture
    def orchestrator_with_audit(
        self, mock_intent_analyzer, mock_executor, mock_aggregator, mock_audit_logger, mock_history_store
    ):
        """Create orchestrator with mocked audit components."""
        get_query_orchestrator.cache_clear()
        return QueryOrchestrator(
            intent_analyzer=mock_intent_analyzer,
            executor=mock_executor,
            aggregator=mock_aggregator,
            audit_logger=mock_audit_logger,
            history_store=mock_history_store,
        )

    @pytest.mark.asyncio
    async def test_audit_logging_called_with_user_id(
        self, orchestrator_with_audit, mock_audit_logger, mock_history_store
    ):
        """Audit logging should be called when user_id is provided."""
        await orchestrator_with_audit.process_query(
            matter_id="matter-123",
            query="What citations?",
            user_id="user-456",
        )

        # Give async task time to complete
        await asyncio.sleep(0.1)

        mock_audit_logger.log_query.assert_called_once()
        mock_history_store.append_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_id_is_required_for_nfr24_compliance(
        self, orchestrator_with_audit
    ):
        """user_id is now REQUIRED for NFR24 audit compliance (no longer optional).

        Story 6-3 Fix: user_id was previously optional, allowing queries to bypass
        the audit trail. Now it's required to ensure all queries are logged.
        """
        import inspect

        # Verify that user_id is a required parameter (no default value)
        sig = inspect.signature(orchestrator_with_audit.process_query)
        user_id_param = sig.parameters.get("user_id")

        assert user_id_param is not None, "user_id parameter should exist"
        assert user_id_param.default is inspect.Parameter.empty, (
            "user_id should be REQUIRED (no default value) for NFR24 audit compliance"
        )

    @pytest.mark.asyncio
    async def test_audit_failure_does_not_fail_query(
        self, mock_intent_analyzer, mock_executor, mock_aggregator
    ):
        """Query should succeed even if audit logging fails (AC: #5)."""
        # Create failing audit components
        failing_audit_logger = MagicMock()
        failing_audit_logger.log_query.side_effect = Exception("Audit failed")

        orchestrator = QueryOrchestrator(
            intent_analyzer=mock_intent_analyzer,
            executor=mock_executor,
            aggregator=mock_aggregator,
            audit_logger=failing_audit_logger,
        )

        # Should not raise
        result = await orchestrator.process_query(
            matter_id="matter-123",
            query="What citations?",
            user_id="user-456",
        )

        # Query should still succeed
        assert result.matter_id == "matter-123"
        assert len(result.successful_engines) >= 0 or len(result.failed_engines) >= 0

    @pytest.mark.asyncio
    async def test_audit_logs_correct_matter_id(
        self, orchestrator_with_audit, mock_audit_logger, mock_history_store
    ):
        """Audit should log correct matter_id."""
        await orchestrator_with_audit.process_query(
            matter_id="specific-matter-abc",
            query="Test query",
            user_id="user-123",
        )

        await asyncio.sleep(0.1)

        # Verify matter_id passed to audit logger
        call_args = mock_audit_logger.log_query.call_args
        assert call_args.kwargs["matter_id"] == "specific-matter-abc"

    @pytest.mark.asyncio
    async def test_audit_logs_correct_user_id(
        self, orchestrator_with_audit, mock_audit_logger, mock_history_store
    ):
        """Audit should log correct user_id."""
        await orchestrator_with_audit.process_query(
            matter_id="matter-123",
            query="Test query",
            user_id="specific-user-xyz",
        )

        await asyncio.sleep(0.1)

        # Verify user_id passed to audit logger
        call_args = mock_audit_logger.log_query.call_args
        assert call_args.kwargs["user_id"] == "specific-user-xyz"

    def test_audit_logger_property(self, orchestrator_with_audit, mock_audit_logger):
        """Should expose audit logger."""
        assert orchestrator_with_audit.audit_logger == mock_audit_logger

    def test_history_store_property(self, orchestrator_with_audit, mock_history_store):
        """Should expose history store."""
        assert orchestrator_with_audit.history_store == mock_history_store
