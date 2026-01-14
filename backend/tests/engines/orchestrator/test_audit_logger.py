"""Tests for the Query Audit Logger.

Story 6-3: Audit Trail Logging (AC: #1-3)

Tests cover:
- Query audit entry creation (AC: #1)
- Findings extraction from engine results (AC: #2)
- LLM cost collection and aggregation (AC: #3)
- Response summary generation
- Edge cases and error handling
"""

import pytest

from app.engines.orchestrator.audit_logger import (
    QueryAuditLogger,
    get_query_audit_logger,
)
from app.models.orchestrator import (
    EngineExecutionResult,
    EngineType,
    IntentAnalysisCost,
    IntentAnalysisResult,
    IntentClassification,
    OrchestratorResult,
    QueryIntent,
    SourceReference,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def audit_logger():
    """Create QueryAuditLogger instance."""
    get_query_audit_logger.cache_clear()
    return QueryAuditLogger()


@pytest.fixture
def mock_intent_result():
    """Create mock intent analysis result with LLM cost."""
    return IntentAnalysisResult(
        matter_id="matter-123",
        query="What citations are in this case?",
        classification=IntentClassification(
            intent=QueryIntent.CITATION,
            confidence=0.95,
            required_engines=[EngineType.CITATION],
            reasoning="Query asks about citations",
        ),
        fast_path_used=False,
        cost=IntentAnalysisCost(
            input_tokens=50,
            output_tokens=30,
            total_cost_usd=0.00007,
            llm_call_made=True,
        ),
    )


@pytest.fixture
def mock_intent_result_fast_path():
    """Create mock intent result using fast path (no LLM cost)."""
    return IntentAnalysisResult(
        matter_id="matter-123",
        query="section 138",
        classification=IntentClassification(
            intent=QueryIntent.CITATION,
            confidence=0.95,
            required_engines=[EngineType.CITATION],
            reasoning="Regex match for section number",
        ),
        fast_path_used=True,
        cost=IntentAnalysisCost(
            input_tokens=0,
            output_tokens=0,
            total_cost_usd=0.0,
            llm_call_made=False,
        ),
    )


@pytest.fixture
def mock_citation_engine_result():
    """Create mock citation engine result."""
    return EngineExecutionResult(
        engine=EngineType.CITATION,
        success=True,
        data={
            "citations": [
                {
                    "act": "NI Act 1881",
                    "section": "138",
                    "confidence": 0.95,
                    "document_id": "doc-123",
                    "document_name": "complaint.pdf",
                },
                {
                    "act": "IPC 1860",
                    "section": "420",
                    "confidence": 0.88,
                    "document_id": "doc-456",
                },
            ],
        },
        execution_time_ms=100,
        confidence=0.92,
    )


@pytest.fixture
def mock_timeline_engine_result():
    """Create mock timeline engine result."""
    return EngineExecutionResult(
        engine=EngineType.TIMELINE,
        success=True,
        data={
            "events": [
                {
                    "date": "2024-01-15",
                    "description": "Complaint filed by plaintiff",
                    "confidence": 0.90,
                    "document_id": "doc-123",
                },
                {
                    "date": "2024-02-20",
                    "description": "First hearing scheduled",
                    "confidence": 0.85,
                },
            ],
        },
        execution_time_ms=150,
        confidence=0.88,
    )


@pytest.fixture
def mock_contradiction_engine_result():
    """Create mock contradiction engine result."""
    return EngineExecutionResult(
        engine=EngineType.CONTRADICTION,
        success=True,
        data={
            "contradictions": [
                {
                    "explanation": "Witness A says event was on Monday, but document B states Tuesday",
                    "confidence": 0.85,
                    "sources": [
                        {"document_id": "doc-001"},
                        {"document_id": "doc-002"},
                    ],
                },
            ],
        },
        execution_time_ms=200,
        confidence=0.85,
    )


@pytest.fixture
def mock_rag_engine_result():
    """Create mock RAG engine result."""
    return EngineExecutionResult(
        engine=EngineType.RAG,
        success=True,
        data={
            "results": [
                {
                    "text": "The defendant claims to have paid the amount...",
                    "score": 0.92,
                    "document_id": "doc-789",
                },
                {
                    "text": "Section 138 of the NI Act provides for...",
                    "score": 0.88,
                    "document_id": "doc-123",
                },
                {
                    "text": "According to the witness statement...",
                    "score": 0.85,
                },
            ],
        },
        execution_time_ms=180,
        confidence=0.90,
    )


@pytest.fixture
def mock_engine_result_with_llm_cost():
    """Create mock engine result with LLM cost tracking."""
    return EngineExecutionResult(
        engine=EngineType.CONTRADICTION,
        success=True,
        data={
            "contradictions": [],
            "llm_cost": {
                "model": "gpt-4",
                "input_tokens": 500,
                "output_tokens": 200,
                "cost_usd": 0.025,
            },
        },
        execution_time_ms=500,
        confidence=0.75,
    )


@pytest.fixture
def mock_failed_engine_result():
    """Create mock failed engine result."""
    return EngineExecutionResult(
        engine=EngineType.RAG,
        success=False,
        error="Database connection failed",
        execution_time_ms=50,
    )


@pytest.fixture
def mock_orchestrator_result(mock_citation_engine_result, mock_timeline_engine_result):
    """Create mock orchestrator result with multiple engines."""
    return OrchestratorResult(
        matter_id="matter-123",
        query="What citations and timeline events are in this case?",
        successful_engines=[EngineType.CITATION, EngineType.TIMELINE],
        failed_engines=[],
        unified_response="Found 2 citations and 2 timeline events. This is a comprehensive response summary that provides details about the legal analysis performed.",
        sources=[
            SourceReference(document_id="doc-123", document_name="complaint.pdf"),
        ],
        confidence=0.90,
        engine_results=[mock_citation_engine_result, mock_timeline_engine_result],
        total_execution_time_ms=250,
        wall_clock_time_ms=180,
    )


@pytest.fixture
def mock_orchestrator_result_with_failures(
    mock_citation_engine_result, mock_failed_engine_result
):
    """Create mock orchestrator result with mixed success/failure."""
    return OrchestratorResult(
        matter_id="matter-456",
        query="Search and analyze",
        successful_engines=[EngineType.CITATION],
        failed_engines=[EngineType.RAG],
        unified_response="Found 2 citations. Note: Some engines encountered errors.",
        sources=[],
        confidence=0.85,
        engine_results=[mock_citation_engine_result, mock_failed_engine_result],
        total_execution_time_ms=150,
        wall_clock_time_ms=100,
    )


# =============================================================================
# Unit Tests: Query Audit Entry Creation (AC: #1)
# =============================================================================


class TestLogQueryCreatesCompleteEntry:
    """Tests for log_query method - creates complete audit entries."""

    def test_creates_entry_with_all_required_fields(
        self, audit_logger, mock_orchestrator_result, mock_intent_result
    ):
        """Audit entry should contain all required fields (AC: #1)."""
        entry = audit_logger.log_query(
            matter_id="matter-123",
            user_id="user-456",
            result=mock_orchestrator_result,
            intent_result=mock_intent_result,
        )

        # Core identification
        assert entry.query_id  # UUID generated
        assert entry.matter_id == "matter-123"

        # Query details
        assert entry.query_text == mock_orchestrator_result.query
        assert entry.query_intent == QueryIntent.CITATION
        assert entry.intent_confidence == 0.95

        # User and timing
        assert entry.asked_by == "user-456"
        assert entry.asked_at  # ISO8601 timestamp

        # Execution details
        assert entry.engines_invoked == [EngineType.CITATION, EngineType.TIMELINE]
        assert entry.successful_engines == [EngineType.CITATION, EngineType.TIMELINE]
        assert entry.failed_engines == []
        assert entry.execution_time_ms == 250
        assert entry.wall_clock_time_ms == 180

        # Results summary
        assert entry.findings_count >= 0
        assert entry.response_summary
        assert entry.overall_confidence == 0.90

    def test_creates_entry_without_intent_result(
        self, audit_logger, mock_orchestrator_result
    ):
        """Should work without intent result (uses defaults)."""
        entry = audit_logger.log_query(
            matter_id="matter-123",
            user_id="user-456",
            result=mock_orchestrator_result,
            intent_result=None,
        )

        assert entry.query_id
        assert entry.query_intent == QueryIntent.RAG_SEARCH  # Default
        assert entry.intent_confidence == 0.0

    def test_creates_entry_with_mixed_success_failure(
        self, audit_logger, mock_orchestrator_result_with_failures, mock_intent_result
    ):
        """Should handle mixed success/failure correctly."""
        entry = audit_logger.log_query(
            matter_id="matter-456",
            user_id="user-789",
            result=mock_orchestrator_result_with_failures,
            intent_result=mock_intent_result,
        )

        assert entry.successful_engines == [EngineType.CITATION]
        assert entry.failed_engines == [EngineType.RAG]
        assert entry.engines_invoked == [EngineType.CITATION, EngineType.RAG]

    def test_generates_unique_query_ids(
        self, audit_logger, mock_orchestrator_result, mock_intent_result
    ):
        """Each call should generate unique query_id."""
        entry1 = audit_logger.log_query(
            matter_id="matter-123",
            user_id="user-456",
            result=mock_orchestrator_result,
            intent_result=mock_intent_result,
        )
        entry2 = audit_logger.log_query(
            matter_id="matter-123",
            user_id="user-456",
            result=mock_orchestrator_result,
            intent_result=mock_intent_result,
        )

        assert entry1.query_id != entry2.query_id


# =============================================================================
# Unit Tests: Findings Extraction (AC: #2)
# =============================================================================


class TestFindingsExtraction:
    """Tests for _extract_findings method."""

    def test_extract_citation_findings(self, audit_logger, mock_citation_engine_result):
        """Should extract citation findings correctly."""
        result = OrchestratorResult(
            matter_id="matter-123",
            query="test",
            successful_engines=[EngineType.CITATION],
            failed_engines=[],
            unified_response="test",
            confidence=0.9,
            engine_results=[mock_citation_engine_result],
            total_execution_time_ms=100,
        )

        findings = audit_logger._extract_findings(result)

        assert len(findings) == 2
        assert all(f.engine == EngineType.CITATION for f in findings)
        assert all(f.finding_type == "citation" for f in findings)
        assert "NI Act 1881 Section 138" in findings[0].summary

    def test_extract_timeline_findings(self, audit_logger, mock_timeline_engine_result):
        """Should extract timeline event findings correctly."""
        result = OrchestratorResult(
            matter_id="matter-123",
            query="test",
            successful_engines=[EngineType.TIMELINE],
            failed_engines=[],
            unified_response="test",
            confidence=0.88,
            engine_results=[mock_timeline_engine_result],
            total_execution_time_ms=150,
        )

        findings = audit_logger._extract_findings(result)

        assert len(findings) == 2
        assert all(f.engine == EngineType.TIMELINE for f in findings)
        assert all(f.finding_type == "timeline_event" for f in findings)
        assert "2024-01-15" in findings[0].summary

    def test_extract_contradiction_findings(
        self, audit_logger, mock_contradiction_engine_result
    ):
        """Should extract contradiction findings correctly."""
        result = OrchestratorResult(
            matter_id="matter-123",
            query="test",
            successful_engines=[EngineType.CONTRADICTION],
            failed_engines=[],
            unified_response="test",
            confidence=0.85,
            engine_results=[mock_contradiction_engine_result],
            total_execution_time_ms=200,
        )

        findings = audit_logger._extract_findings(result)

        assert len(findings) == 1
        assert findings[0].engine == EngineType.CONTRADICTION
        assert findings[0].finding_type == "contradiction"
        assert "Monday" in findings[0].summary

    def test_extract_rag_findings(self, audit_logger, mock_rag_engine_result):
        """Should extract RAG search results (limited to top 5)."""
        result = OrchestratorResult(
            matter_id="matter-123",
            query="test",
            successful_engines=[EngineType.RAG],
            failed_engines=[],
            unified_response="test",
            confidence=0.90,
            engine_results=[mock_rag_engine_result],
            total_execution_time_ms=180,
        )

        findings = audit_logger._extract_findings(result)

        assert len(findings) == 3  # All 3 results
        assert all(f.engine == EngineType.RAG for f in findings)
        assert all(f.finding_type == "search_result" for f in findings)

    def test_extract_findings_from_multiple_engines(
        self,
        audit_logger,
        mock_citation_engine_result,
        mock_timeline_engine_result,
    ):
        """Should extract findings from all successful engines."""
        result = OrchestratorResult(
            matter_id="matter-123",
            query="test",
            successful_engines=[EngineType.CITATION, EngineType.TIMELINE],
            failed_engines=[],
            unified_response="test",
            confidence=0.9,
            engine_results=[mock_citation_engine_result, mock_timeline_engine_result],
            total_execution_time_ms=250,
        )

        findings = audit_logger._extract_findings(result)

        # 2 citations + 2 timeline events
        assert len(findings) == 4
        citation_findings = [f for f in findings if f.engine == EngineType.CITATION]
        timeline_findings = [f for f in findings if f.engine == EngineType.TIMELINE]
        assert len(citation_findings) == 2
        assert len(timeline_findings) == 2

    def test_extract_findings_skips_failed_engines(
        self, audit_logger, mock_citation_engine_result, mock_failed_engine_result
    ):
        """Should skip failed engines when extracting findings."""
        result = OrchestratorResult(
            matter_id="matter-123",
            query="test",
            successful_engines=[EngineType.CITATION],
            failed_engines=[EngineType.RAG],
            unified_response="test",
            confidence=0.85,
            engine_results=[mock_citation_engine_result, mock_failed_engine_result],
            total_execution_time_ms=150,
        )

        findings = audit_logger._extract_findings(result)

        # Only citation findings, not RAG (failed)
        assert len(findings) == 2
        assert all(f.engine == EngineType.CITATION for f in findings)


# =============================================================================
# Unit Tests: LLM Cost Collection (AC: #3)
# =============================================================================


class TestLLMCostCollection:
    """Tests for _collect_llm_costs method."""

    def test_collect_intent_analysis_cost(
        self, audit_logger, mock_orchestrator_result, mock_intent_result
    ):
        """Should collect cost from intent analysis."""
        costs = audit_logger._collect_llm_costs(
            mock_intent_result, mock_orchestrator_result
        )

        assert len(costs) >= 1
        intent_cost = next(
            (c for c in costs if c.purpose == "intent_analysis"), None
        )
        assert intent_cost is not None
        assert intent_cost.model_name == "gpt-3.5-turbo"
        assert intent_cost.input_tokens == 50
        assert intent_cost.output_tokens == 30
        assert intent_cost.cost_usd == 0.00007

    def test_no_cost_for_fast_path(
        self, audit_logger, mock_orchestrator_result, mock_intent_result_fast_path
    ):
        """Should not add cost when fast path used (no LLM call)."""
        costs = audit_logger._collect_llm_costs(
            mock_intent_result_fast_path, mock_orchestrator_result
        )

        # No intent cost because fast_path_used=True and llm_call_made=False
        intent_cost = next(
            (c for c in costs if c.purpose == "intent_analysis"), None
        )
        assert intent_cost is None

    def test_collect_engine_llm_cost(
        self, audit_logger, mock_engine_result_with_llm_cost
    ):
        """Should collect LLM cost from engine results."""
        result = OrchestratorResult(
            matter_id="matter-123",
            query="test",
            successful_engines=[EngineType.CONTRADICTION],
            failed_engines=[],
            unified_response="test",
            confidence=0.75,
            engine_results=[mock_engine_result_with_llm_cost],
            total_execution_time_ms=500,
        )

        costs = audit_logger._collect_llm_costs(None, result)

        assert len(costs) == 1
        assert costs[0].model_name == "gpt-4"
        assert costs[0].purpose == "contradiction_engine"
        assert costs[0].input_tokens == 500
        assert costs[0].output_tokens == 200
        assert costs[0].cost_usd == 0.025

    def test_calculate_total_cost(self, audit_logger, mock_intent_result):
        """Should correctly sum all LLM costs."""
        from app.models.orchestrator import LLMCostEntry

        costs = [
            LLMCostEntry(
                model_name="gpt-3.5-turbo",
                purpose="intent",
                input_tokens=50,
                output_tokens=30,
                cost_usd=0.001,
            ),
            LLMCostEntry(
                model_name="gpt-4",
                purpose="engine",
                input_tokens=500,
                output_tokens=200,
                cost_usd=0.025,
            ),
        ]

        total = audit_logger._calculate_total_cost(costs)

        # Use pytest.approx for floating point comparison
        assert total == pytest.approx(0.026)


# =============================================================================
# Unit Tests: Response Summary Generation
# =============================================================================


class TestResponseSummaryGeneration:
    """Tests for _generate_response_summary method."""

    def test_summary_truncates_long_response(self, audit_logger):
        """Should truncate responses over 500 chars."""
        long_response = "A" * 600
        result = OrchestratorResult(
            matter_id="matter-123",
            query="test",
            successful_engines=[],
            failed_engines=[],
            unified_response=long_response,
            confidence=0.0,
            engine_results=[],
            total_execution_time_ms=0,
        )

        summary = audit_logger._generate_response_summary(result)

        assert len(summary) == 500
        assert summary.endswith("...")

    def test_summary_keeps_short_response(self, audit_logger):
        """Should keep short responses as-is."""
        short_response = "Found 3 citations."
        result = OrchestratorResult(
            matter_id="matter-123",
            query="test",
            successful_engines=[],
            failed_engines=[],
            unified_response=short_response,
            confidence=0.0,
            engine_results=[],
            total_execution_time_ms=0,
        )

        summary = audit_logger._generate_response_summary(result)

        assert summary == short_response


# =============================================================================
# Unit Tests: Factory Function
# =============================================================================


class TestAuditLoggerFactory:
    """Tests for get_query_audit_logger factory."""

    def test_factory_returns_audit_logger(self):
        """Factory should return QueryAuditLogger instance."""
        get_query_audit_logger.cache_clear()
        logger = get_query_audit_logger()

        assert isinstance(logger, QueryAuditLogger)

    def test_factory_returns_singleton(self):
        """Factory should return the same instance (cached)."""
        get_query_audit_logger.cache_clear()
        logger1 = get_query_audit_logger()
        logger2 = get_query_audit_logger()

        assert logger1 is logger2
