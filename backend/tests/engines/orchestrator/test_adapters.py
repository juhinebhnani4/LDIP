"""Tests for the Engine Adapters.

Story 6-2: Engine Execution Ordering

Tests cover:
- Adapter instantiation (Task 5.1-5.6)
- Engine interface compliance
- Error handling
- Correct parameter passing to underlying engines
- Matter isolation propagation
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.orchestrator.adapters import (
    ADAPTER_REGISTRY,
    RAG_RERANK_TOP_N,
    RAG_SEARCH_LIMIT,
    TIMELINE_DEFAULT_PAGE_SIZE,
    CitationEngineAdapter,
    ContradictionEngineAdapter,
    EngineAdapter,
    RAGEngineAdapter,
    TimelineEngineAdapter,
    get_adapter,
    get_cached_adapter,
)
from app.models.orchestrator import EngineExecutionResult, EngineType


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_citation_discovery():
    """Mock citation discovery service."""
    mock = MagicMock()
    mock.get_discovery_report = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_timeline_builder():
    """Mock timeline builder."""
    from dataclasses import dataclass
    from datetime import date, datetime

    @dataclass
    class MockStatistics:
        total_events: int = 0
        date_range_start: date | None = None
        date_range_end: date | None = None
        events_by_type: dict = None

        def __post_init__(self):
            if self.events_by_type is None:
                self.events_by_type = {}

    @dataclass
    class MockTimeline:
        events: list = None
        statistics: MockStatistics = None

        def __post_init__(self):
            if self.events is None:
                self.events = []
            if self.statistics is None:
                self.statistics = MockStatistics()

    mock = MagicMock()
    mock.build_timeline = AsyncMock(return_value=MockTimeline())
    return mock


@pytest.fixture
def mock_statement_query_engine():
    """Mock statement query engine."""
    from app.models.contradiction import EntityStatements

    mock = MagicMock()
    mock.get_statements_for_entity = AsyncMock(
        return_value=EntityStatements(
            entity_id="entity-123",
            entity_name="Test Entity",
            total_statements=5,
            documents=[],
        )
    )
    return mock


@pytest.fixture
def mock_hybrid_search():
    """Mock hybrid search service."""
    from dataclasses import dataclass

    @dataclass
    class MockSearchResult:
        id: str
        document_id: str
        content: str
        page_number: int | None
        rrf_score: float | None
        relevance_score: float | None

    @dataclass
    class MockSearchResults:
        results: list
        total_candidates: int
        rerank_used: bool

    mock = MagicMock()
    mock.search_with_rerank = AsyncMock(
        return_value=MockSearchResults(
            results=[
                MockSearchResult(
                    id="chunk-1",
                    document_id="doc-123",
                    content="Test content",
                    page_number=1,
                    rrf_score=0.85,
                    relevance_score=0.9,
                )
            ],
            total_candidates=10,
            rerank_used=True,
        )
    )
    return mock


# =============================================================================
# Unit Tests: Adapter Registry
# =============================================================================


class TestAdapterRegistry:
    """Tests for the adapter registry."""

    def test_all_engine_types_have_adapters(self):
        """Every EngineType should have a registered adapter."""
        for engine_type in EngineType:
            assert engine_type in ADAPTER_REGISTRY, (
                f"Missing adapter for {engine_type.value}"
            )

    def test_get_adapter_returns_correct_type(self):
        """get_adapter should return the correct adapter type."""
        adapter = get_adapter(EngineType.CITATION)
        assert isinstance(adapter, CitationEngineAdapter)

        adapter = get_adapter(EngineType.TIMELINE)
        assert isinstance(adapter, TimelineEngineAdapter)

        adapter = get_adapter(EngineType.CONTRADICTION)
        assert isinstance(adapter, ContradictionEngineAdapter)

        adapter = get_adapter(EngineType.RAG)
        assert isinstance(adapter, RAGEngineAdapter)

    def test_get_adapter_invalid_type_raises(self):
        """get_adapter should raise ValueError for unknown engine type."""
        # Create a mock engine type not in registry
        with patch.dict(ADAPTER_REGISTRY, clear=True):
            with pytest.raises(ValueError, match="No adapter registered"):
                get_adapter(EngineType.CITATION)

    def test_get_cached_adapter_returns_same_instance(self):
        """get_cached_adapter should return cached instances."""
        get_cached_adapter.cache_clear()

        adapter1 = get_cached_adapter(EngineType.CITATION)
        adapter2 = get_cached_adapter(EngineType.CITATION)

        assert adapter1 is adapter2


# =============================================================================
# Unit Tests: Citation Engine Adapter
# =============================================================================


class TestCitationEngineAdapter:
    """Tests for CitationEngineAdapter."""

    def test_engine_type_property(self):
        """Should return CITATION engine type."""
        adapter = CitationEngineAdapter()
        assert adapter.engine_type == EngineType.CITATION

    @pytest.mark.asyncio
    async def test_execute_calls_discovery_service(self, mock_citation_discovery):
        """Execute should call the discovery service with correct matter_id."""
        adapter = CitationEngineAdapter()

        with patch.object(adapter, "_get_discovery", return_value=mock_citation_discovery):
            result = await adapter.execute(
                matter_id="matter-123",
                query="What citations?",
            )

        assert result.success
        assert result.engine == EngineType.CITATION
        mock_citation_discovery.get_discovery_report.assert_called_once_with(
            matter_id="matter-123",
            include_available=True,
        )

    @pytest.mark.asyncio
    async def test_execute_handles_error(self):
        """Execute should handle errors gracefully."""
        adapter = CitationEngineAdapter()

        mock_discovery = MagicMock()
        mock_discovery.get_discovery_report = AsyncMock(
            side_effect=Exception("Database error")
        )

        with patch.object(adapter, "_get_discovery", return_value=mock_discovery):
            result = await adapter.execute(
                matter_id="matter-123",
                query="What citations?",
            )

        assert not result.success
        assert "Database error" in result.error
        assert result.engine == EngineType.CITATION


# =============================================================================
# Unit Tests: Timeline Engine Adapter
# =============================================================================


class TestTimelineEngineAdapter:
    """Tests for TimelineEngineAdapter."""

    def test_engine_type_property(self):
        """Should return TIMELINE engine type."""
        adapter = TimelineEngineAdapter()
        assert adapter.engine_type == EngineType.TIMELINE

    @pytest.mark.asyncio
    async def test_execute_calls_builder(self, mock_timeline_builder):
        """Execute should call the timeline builder with correct parameters."""
        adapter = TimelineEngineAdapter()

        with patch.object(adapter, "_get_builder", return_value=mock_timeline_builder):
            result = await adapter.execute(
                matter_id="matter-456",
                query="What's the timeline?",
            )

        assert result.success
        assert result.engine == EngineType.TIMELINE
        mock_timeline_builder.build_timeline.assert_called_once_with(
            matter_id="matter-456",
            include_entities=True,
            page=1,
            per_page=TIMELINE_DEFAULT_PAGE_SIZE,
        )

    @pytest.mark.asyncio
    async def test_execute_handles_error(self):
        """Execute should handle errors gracefully."""
        adapter = TimelineEngineAdapter()

        mock_builder = MagicMock()
        mock_builder.build_timeline = AsyncMock(side_effect=Exception("Timeline error"))

        with patch.object(adapter, "_get_builder", return_value=mock_builder):
            result = await adapter.execute(
                matter_id="matter-123",
                query="What's the timeline?",
            )

        assert not result.success
        assert "Timeline error" in result.error


# =============================================================================
# Unit Tests: Contradiction Engine Adapter
# =============================================================================


class TestContradictionEngineAdapter:
    """Tests for ContradictionEngineAdapter."""

    def test_engine_type_property(self):
        """Should return CONTRADICTION engine type."""
        adapter = ContradictionEngineAdapter()
        assert adapter.engine_type == EngineType.CONTRADICTION

    @pytest.mark.asyncio
    async def test_execute_without_entity_returns_capability_info(self):
        """Execute without entity_id should return capability info."""
        adapter = ContradictionEngineAdapter()

        result = await adapter.execute(
            matter_id="matter-123",
            query="Are there contradictions?",
            context=None,
        )

        assert result.success
        assert result.data["analysis_ready"] is False
        assert "entity" in result.data["message"].lower()

    @pytest.mark.asyncio
    async def test_execute_with_entity_calls_query_engine(
        self, mock_statement_query_engine
    ):
        """Execute with entity_id should call the query engine."""
        adapter = ContradictionEngineAdapter()

        with patch.object(
            adapter, "_get_query_engine", return_value=mock_statement_query_engine
        ):
            result = await adapter.execute(
                matter_id="matter-123",
                query="Check contradictions for John",
                context={"entity_id": "entity-456"},
            )

        assert result.success
        assert result.data["analysis_ready"] is True
        assert result.data["entity_id"] == "entity-456"

        # Verify correct method was called with correct parameter order
        mock_statement_query_engine.get_statements_for_entity.assert_called_once_with(
            entity_id="entity-456",
            matter_id="matter-123",
        )

    @pytest.mark.asyncio
    async def test_execute_handles_error(self):
        """Execute should handle errors gracefully."""
        adapter = ContradictionEngineAdapter()

        mock_engine = MagicMock()
        mock_engine.get_statements_for_entity = AsyncMock(
            side_effect=Exception("Query failed")
        )

        with patch.object(adapter, "_get_query_engine", return_value=mock_engine):
            result = await adapter.execute(
                matter_id="matter-123",
                query="Check contradictions",
                context={"entity_id": "entity-456"},
            )

        assert not result.success
        assert "Query failed" in result.error


# =============================================================================
# Unit Tests: RAG Engine Adapter
# =============================================================================


class TestRAGEngineAdapter:
    """Tests for RAGEngineAdapter."""

    def test_engine_type_property(self):
        """Should return RAG engine type."""
        adapter = RAGEngineAdapter()
        assert adapter.engine_type == EngineType.RAG

    @pytest.mark.asyncio
    async def test_execute_calls_hybrid_search(self, mock_hybrid_search):
        """Execute should call hybrid search with correct parameters."""
        adapter = RAGEngineAdapter()

        with patch.object(adapter, "_get_search", return_value=mock_hybrid_search):
            result = await adapter.execute(
                matter_id="matter-789",
                query="Search for something",
            )

        assert result.success
        assert result.engine == EngineType.RAG
        mock_hybrid_search.search_with_rerank.assert_called_once_with(
            matter_id="matter-789",
            query="Search for something",
            limit=RAG_SEARCH_LIMIT,
            top_n=RAG_RERANK_TOP_N,
        )

    @pytest.mark.asyncio
    async def test_execute_handles_error(self):
        """Execute should handle errors gracefully."""
        adapter = RAGEngineAdapter()

        mock_search = MagicMock()
        mock_search.search_with_rerank = AsyncMock(side_effect=Exception("Search error"))

        with patch.object(adapter, "_get_search", return_value=mock_search):
            result = await adapter.execute(
                matter_id="matter-123",
                query="Search query",
            )

        assert not result.success
        assert "Search error" in result.error


# =============================================================================
# Unit Tests: Base Adapter Helper Methods
# =============================================================================


class TestAdapterHelperMethods:
    """Tests for base adapter helper methods."""

    def test_create_success_result(self):
        """_create_success_result should create proper success result."""
        adapter = CitationEngineAdapter()

        result = adapter._create_success_result(
            data={"test": "data"},
            execution_time_ms=100,
            confidence=0.95,
        )

        assert result.success is True
        assert result.engine == EngineType.CITATION
        assert result.data == {"test": "data"}
        assert result.execution_time_ms == 100
        assert result.confidence == 0.95
        assert result.error is None

    def test_create_error_result(self):
        """_create_error_result should create proper error result."""
        adapter = TimelineEngineAdapter()

        result = adapter._create_error_result(
            error="Something went wrong",
            execution_time_ms=50,
        )

        assert result.success is False
        assert result.engine == EngineType.TIMELINE
        assert result.error == "Something went wrong"
        assert result.execution_time_ms == 50
        assert result.data is None


# =============================================================================
# Unit Tests: Matter Isolation
# =============================================================================


class TestMatterIsolation:
    """Critical security tests for matter isolation in adapters."""

    @pytest.mark.asyncio
    async def test_citation_adapter_propagates_matter_id(self, mock_citation_discovery):
        """Citation adapter should propagate matter_id to underlying service."""
        adapter = CitationEngineAdapter()

        with patch.object(adapter, "_get_discovery", return_value=mock_citation_discovery):
            await adapter.execute(matter_id="secure-matter", query="Test")

        call_args = mock_citation_discovery.get_discovery_report.call_args
        assert call_args.kwargs["matter_id"] == "secure-matter"

    @pytest.mark.asyncio
    async def test_timeline_adapter_propagates_matter_id(self, mock_timeline_builder):
        """Timeline adapter should propagate matter_id to underlying service."""
        adapter = TimelineEngineAdapter()

        with patch.object(adapter, "_get_builder", return_value=mock_timeline_builder):
            await adapter.execute(matter_id="secure-matter", query="Test")

        call_args = mock_timeline_builder.build_timeline.call_args
        assert call_args.kwargs["matter_id"] == "secure-matter"

    @pytest.mark.asyncio
    async def test_contradiction_adapter_propagates_matter_id(
        self, mock_statement_query_engine
    ):
        """Contradiction adapter should propagate matter_id to underlying service."""
        adapter = ContradictionEngineAdapter()

        with patch.object(
            adapter, "_get_query_engine", return_value=mock_statement_query_engine
        ):
            await adapter.execute(
                matter_id="secure-matter",
                query="Test",
                context={"entity_id": "entity-123"},
            )

        call_args = mock_statement_query_engine.get_statements_for_entity.call_args
        assert call_args.kwargs["matter_id"] == "secure-matter"

    @pytest.mark.asyncio
    async def test_rag_adapter_propagates_matter_id(self, mock_hybrid_search):
        """RAG adapter should propagate matter_id to underlying service."""
        adapter = RAGEngineAdapter()

        with patch.object(adapter, "_get_search", return_value=mock_hybrid_search):
            await adapter.execute(matter_id="secure-matter", query="Test")

        call_args = mock_hybrid_search.search_with_rerank.call_args
        assert call_args.kwargs["matter_id"] == "secure-matter"


# =============================================================================
# Unit Tests: Constants
# =============================================================================


class TestConstants:
    """Tests for adapter constants."""

    def test_rag_search_limit_is_positive(self):
        """RAG_SEARCH_LIMIT should be a positive integer."""
        assert isinstance(RAG_SEARCH_LIMIT, int)
        assert RAG_SEARCH_LIMIT > 0

    def test_rag_rerank_top_n_is_positive(self):
        """RAG_RERANK_TOP_N should be a positive integer."""
        assert isinstance(RAG_RERANK_TOP_N, int)
        assert RAG_RERANK_TOP_N > 0

    def test_rag_rerank_top_n_less_than_limit(self):
        """RAG_RERANK_TOP_N should be <= RAG_SEARCH_LIMIT."""
        assert RAG_RERANK_TOP_N <= RAG_SEARCH_LIMIT

    def test_timeline_page_size_is_positive(self):
        """TIMELINE_DEFAULT_PAGE_SIZE should be a positive integer."""
        assert isinstance(TIMELINE_DEFAULT_PAGE_SIZE, int)
        assert TIMELINE_DEFAULT_PAGE_SIZE > 0
