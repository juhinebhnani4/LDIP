"""Tests for Statement Comparison Service.

Story 5-2: Service layer tests for statement comparison.

Tests cover:
- Entity validation (Layer 4 isolation)
- Statement retrieval and comparison orchestration
- Too many statements handling
- Cost tracking aggregation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.contradiction import (
    ComparisonMeta,
    ComparisonResult,
    ContradictionEvidence,
    DocumentStatements,
    EntityComparisons,
    EntityComparisonsResponse,
    EntityStatements,
    EntityStatementsResponse,
    EvidenceType,
    PaginationMeta,
    Statement,
    StatementPairComparison,
)
from app.services.contradiction.comparator import (
    ComparisonServiceError,
    StatementComparisonService,
    TooManyStatementsError,
    get_statement_comparison_service,
)
from app.services.contradiction.statement_query import EntityNotFoundError


# =============================================================================
# Service Tests
# =============================================================================


class TestStatementComparisonService:
    """Tests for StatementComparisonService."""

    @pytest.fixture
    def mock_mig_service(self) -> MagicMock:
        """Create mock MIG service."""
        mock = MagicMock()
        mock.get_entity = AsyncMock(return_value=MagicMock(
            id="entity-123",
            canonical_name="Test Entity",
        ))
        return mock

    @pytest.fixture
    def mock_statement_service(self) -> MagicMock:
        """Create mock statement query service."""
        mock = MagicMock()
        mock.get_entity_statement_count = AsyncMock(return_value=10)
        mock.get_entity_statements = AsyncMock(return_value=EntityStatementsResponse(
            data=EntityStatements(
                entity_id="entity-123",
                entity_name="Test Entity",
                total_statements=10,
                documents=[
                    DocumentStatements(
                        document_id="doc-1",
                        document_name="Contract.pdf",
                        statements=[
                            Statement(
                                entity_id="entity-123",
                                chunk_id=f"chunk-{i}",
                                document_id="doc-1",
                                content=f"Statement {i}",
                                page_number=i,
                            )
                            for i in range(5)
                        ],
                        statement_count=5,
                    ),
                    DocumentStatements(
                        document_id="doc-2",
                        document_name="Statement.pdf",
                        statements=[
                            Statement(
                                entity_id="entity-123",
                                chunk_id=f"chunk-{i+5}",
                                document_id="doc-2",
                                content=f"Statement {i+5}",
                                page_number=i,
                            )
                            for i in range(5)
                        ],
                        statement_count=5,
                    ),
                ],
                aliases_included=[],
            ),
            meta=PaginationMeta(
                total=10,
                page=1,
                per_page=1000,
                total_pages=1,
            ),
        ))
        return mock

    @pytest.fixture
    def mock_comparator(self) -> MagicMock:
        """Create mock statement comparator."""
        from app.engines.contradiction.comparator import ComparisonBatchResult

        mock = MagicMock()
        mock.compare_all_entity_statements = AsyncMock(return_value=ComparisonBatchResult(
            comparisons=[
                StatementPairComparison(
                    statement_a_id="chunk-0",
                    statement_b_id="chunk-5",
                    statement_a_content="Statement 0",
                    statement_b_content="Statement 5",
                    result=ComparisonResult.CONTRADICTION,
                    reasoning="Test reasoning",
                    confidence=0.9,
                    evidence=ContradictionEvidence(
                        type=EvidenceType.AMOUNT_MISMATCH,
                        value_a="500000",
                        value_b="800000",
                    ),
                    document_a_id="doc-1",
                    document_b_id="doc-2",
                    page_a=0,
                    page_b=0,
                ),
                StatementPairComparison(
                    statement_a_id="chunk-1",
                    statement_b_id="chunk-6",
                    statement_a_content="Statement 1",
                    statement_b_content="Statement 6",
                    result=ComparisonResult.CONSISTENT,
                    reasoning="No conflict",
                    confidence=0.85,
                    evidence=ContradictionEvidence(type=EvidenceType.NONE),
                    document_a_id="doc-1",
                    document_b_id="doc-2",
                    page_a=1,
                    page_b=1,
                ),
            ],
            total_input_tokens=1000,
            total_output_tokens=300,
            processing_time_ms=5000,
        ))
        return mock

    @pytest.fixture
    def service(
        self,
        mock_mig_service: MagicMock,
        mock_statement_service: MagicMock,
        mock_comparator: MagicMock,
    ) -> StatementComparisonService:
        """Create service with mocked dependencies."""
        service = StatementComparisonService()
        service._mig_service = mock_mig_service
        service._statement_service = mock_statement_service
        service._comparator = mock_comparator
        return service

    @pytest.mark.asyncio
    async def test_compare_entity_statements_success(
        self,
        service: StatementComparisonService,
    ) -> None:
        """Should return comparison results on success."""
        response = await service.compare_entity_statements(
            entity_id="entity-123",
            matter_id="matter-456",
            max_pairs=50,
        )

        assert isinstance(response, EntityComparisonsResponse)
        assert response.data.entity_id == "entity-123"
        assert response.meta.pairs_compared == 2
        assert response.meta.contradictions_found == 1
        assert response.meta.total_cost_usd > 0

    @pytest.mark.asyncio
    async def test_compare_entity_statements_not_found(
        self,
        service: StatementComparisonService,
        mock_mig_service: MagicMock,
    ) -> None:
        """Should raise EntityNotFoundError when entity not in matter."""
        mock_mig_service.get_entity = AsyncMock(return_value=None)

        with pytest.raises(EntityNotFoundError):
            await service.compare_entity_statements(
                entity_id="nonexistent",
                matter_id="matter-456",
            )

    @pytest.mark.asyncio
    async def test_compare_entity_statements_too_many(
        self,
        service: StatementComparisonService,
        mock_statement_service: MagicMock,
    ) -> None:
        """Should raise TooManyStatementsError for >100 statements."""
        mock_statement_service.get_entity_statement_count = AsyncMock(return_value=150)

        with pytest.raises(TooManyStatementsError) as exc_info:
            await service.compare_entity_statements(
                entity_id="entity-123",
                matter_id="matter-456",
            )

        assert exc_info.value.statement_count == 150
        assert exc_info.value.threshold == 100

    @pytest.mark.asyncio
    async def test_compare_entity_statements_insufficient(
        self,
        service: StatementComparisonService,
        mock_statement_service: MagicMock,
    ) -> None:
        """Should return empty result for <2 statements."""
        mock_statement_service.get_entity_statement_count = AsyncMock(return_value=1)
        mock_statement_service.get_entity_statements = AsyncMock(return_value=EntityStatementsResponse(
            data=EntityStatements(
                entity_id="entity-123",
                entity_name="Test Entity",
                total_statements=1,
                documents=[],
                aliases_included=[],
            ),
            meta=PaginationMeta(total=1, page=1, per_page=1000, total_pages=1),
        ))

        response = await service.compare_entity_statements(
            entity_id="entity-123",
            matter_id="matter-456",
        )

        assert response.meta.pairs_compared == 0
        assert response.meta.contradictions_found == 0
        assert response.meta.total_cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_compare_entity_statements_confidence_filter(
        self,
        service: StatementComparisonService,
    ) -> None:
        """Should filter results by confidence threshold."""
        response = await service.compare_entity_statements(
            entity_id="entity-123",
            matter_id="matter-456",
            confidence_threshold=0.88,  # Higher than the consistent pair's 0.85
        )

        # Only the contradiction (0.9) should pass the filter
        assert len(response.data.comparisons) == 1
        assert response.data.comparisons[0].result == ComparisonResult.CONTRADICTION

    @pytest.mark.asyncio
    async def test_get_estimated_pairs(
        self,
        service: StatementComparisonService,
        mock_statement_service: MagicMock,
    ) -> None:
        """Should calculate estimated pairs correctly."""
        mock_statement_service.get_entity_statement_count = AsyncMock(return_value=10)

        pairs = await service.get_estimated_pairs(
            entity_id="entity-123",
            matter_id="matter-456",
        )

        # N*(N-1)/2 = 10*9/2 = 45
        assert pairs == 45


# =============================================================================
# Factory Tests
# =============================================================================


class TestServiceFactory:
    """Tests for service factory function."""

    def test_singleton_factory(self) -> None:
        """Should return singleton instance."""
        get_statement_comparison_service.cache_clear()

        service1 = get_statement_comparison_service()
        service2 = get_statement_comparison_service()

        assert service1 is service2

        get_statement_comparison_service.cache_clear()
