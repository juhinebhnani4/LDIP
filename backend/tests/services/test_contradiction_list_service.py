"""Tests for Contradiction List Service.

Story 14.2: Contradictions List API Endpoint

Test Categories:
- Service initialization
- Query building
- Filtering
- Pagination
- Sorting
- Entity grouping
- Error handling
"""

from unittest.mock import MagicMock, patch

import pytest

from app.models.contradiction import ContradictionType, SeverityLevel
from app.services.contradiction_list_service import (
    ContradictionListService,
    ContradictionListServiceError,
    get_contradiction_list_service,
)


@pytest.fixture
def mock_supabase_client():
    """Create mock Supabase client."""
    return MagicMock()


@pytest.fixture
def service(mock_supabase_client):
    """Create service with mocked Supabase client."""
    service = ContradictionListService()
    service._supabase_client = mock_supabase_client
    return service


@pytest.fixture
def mock_contradiction_data():
    """Create mock contradiction data from database."""
    return [
        {
            "id": "contradiction-1",
            "entity_id": "entity-123",
            "contradiction_type": "amount_mismatch",
            "severity": "high",
            "explanation": "Amount conflict detected",
            "confidence": 0.95,
            "evidence": {"value_a": "500000", "value_b": "800000"},
            "created_at": "2026-01-15T10:00:00Z",
            "statement_a_id": "chunk-1",
            "statement_b_id": "chunk-2",
            "identity_nodes": {
                "id": "entity-123",
                "canonical_name": "Nirav Jobalia",
            },
        },
        {
            "id": "contradiction-2",
            "entity_id": "entity-456",
            "contradiction_type": "date_mismatch",
            "severity": "medium",
            "explanation": "Date conflict detected",
            "confidence": 0.88,
            "evidence": {"value_a": "2024-01-15", "value_b": "2024-06-15"},
            "created_at": "2026-01-15T09:00:00Z",
            "statement_a_id": "chunk-3",
            "statement_b_id": "chunk-4",
            "identity_nodes": {
                "id": "entity-456",
                "canonical_name": "John Smith",
            },
        },
    ]


@pytest.fixture
def mock_chunk_data():
    """Create mock chunk data."""
    return {
        "chunk-1": {
            "id": "chunk-1",
            "content": "The loan amount was Rs. 5 lakhs.",
            "page_number": 5,
            "document_id": "doc-1",
            "documents": {"id": "doc-1", "filename": "Contract.pdf"},
        },
        "chunk-2": {
            "id": "chunk-2",
            "content": "The loan amount was Rs. 8 lakhs.",
            "page_number": 12,
            "document_id": "doc-2",
            "documents": {"id": "doc-2", "filename": "Agreement.pdf"},
        },
    }


# =============================================================================
# Initialization Tests
# =============================================================================


class TestServiceInitialization:
    """Tests for service initialization."""

    def test_service_creates_without_client(self):
        """Service should initialize without Supabase client."""
        service = ContradictionListService()
        assert service._supabase_client is None

    def test_singleton_returns_same_instance(self):
        """get_contradiction_list_service should return singleton."""
        # Clear the cache first
        get_contradiction_list_service.cache_clear()

        service1 = get_contradiction_list_service()
        service2 = get_contradiction_list_service()

        assert service1 is service2

    def test_supabase_property_raises_if_not_configured(self):
        """supabase property should raise if not configured."""
        with patch(
            "app.services.contradiction_list_service.get_supabase_client",
            return_value=None,
        ):
            service = ContradictionListService()

            with pytest.raises(ContradictionListServiceError) as exc_info:
                _ = service.supabase

            assert exc_info.value.code == "SUPABASE_NOT_CONFIGURED"


# =============================================================================
# Query Tests
# =============================================================================


class TestGetAllContradictions:
    """Tests for get_all_contradictions method."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_contradictions(self, service):
        """Should return empty list when no contradictions exist."""
        # Mock count query returning 0
        mock_result = MagicMock()
        mock_result.count = 0

        service._supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            mock_result
        )

        response = await service.get_all_contradictions(
            matter_id="matter-123",
        )

        assert response.data == []
        assert response.meta.total == 0
        assert response.meta.total_pages == 0

    @pytest.mark.asyncio
    async def test_applies_severity_filter(self, service):
        """Should apply severity filter to query."""
        mock_count_result = MagicMock()
        mock_count_result.count = 0

        # Track the query chain
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq1 = MagicMock()
        mock_eq2 = MagicMock()
        mock_eq3 = MagicMock()

        service._supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq1
        mock_eq1.eq.return_value = mock_eq2
        mock_eq2.eq.return_value = mock_eq3
        mock_eq3.execute.return_value = mock_count_result

        await service.get_all_contradictions(
            matter_id="matter-123",
            severity="high",
        )

        # Verify eq was called for severity filter
        mock_eq2.eq.assert_called_with("severity", "high")

    @pytest.mark.asyncio
    async def test_applies_contradiction_type_filter(self, service):
        """Should apply contradiction_type filter to query."""
        mock_count_result = MagicMock()
        mock_count_result.count = 0

        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq1 = MagicMock()
        mock_eq2 = MagicMock()
        mock_eq3 = MagicMock()

        service._supabase_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq1
        mock_eq1.eq.return_value = mock_eq2
        mock_eq2.eq.return_value = mock_eq3
        mock_eq3.execute.return_value = mock_count_result

        await service.get_all_contradictions(
            matter_id="matter-123",
            contradiction_type="date_mismatch",
        )

        mock_eq2.eq.assert_called_with("contradiction_type", "date_mismatch")


# =============================================================================
# Pagination Tests
# =============================================================================


class TestPagination:
    """Tests for pagination logic."""

    @pytest.mark.asyncio
    async def test_calculates_correct_total_pages(self, service):
        """Should calculate total_pages correctly."""
        mock_count_result = MagicMock()
        mock_count_result.count = 45

        mock_query_result = MagicMock()
        mock_query_result.data = []

        # Setup mock chain for count
        mock_table = MagicMock()
        service._supabase_client.table.return_value = mock_table
        mock_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            mock_count_result
        )

        # Setup mock chain for query (more complex)
        mock_table.select.return_value.eq.return_value.eq.return_value.order.return_value.order.return_value.range.return_value.execute.return_value = (
            mock_query_result
        )

        response = await service.get_all_contradictions(
            matter_id="matter-123",
            per_page=20,
        )

        # 45 items with 20 per page = 3 pages
        assert response.meta.total_pages == 3

    @pytest.mark.asyncio
    async def test_clamps_per_page_to_max(self, service):
        """Should clamp per_page to MAX_PAGE_SIZE."""
        mock_count_result = MagicMock()
        mock_count_result.count = 0

        service._supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            mock_count_result
        )

        response = await service.get_all_contradictions(
            matter_id="matter-123",
            per_page=500,  # Exceeds max
        )

        # Should be clamped to 100 (MAX_PAGE_SIZE)
        assert response.meta.per_page == 100


# =============================================================================
# Entity Grouping Tests
# =============================================================================


class TestEntityGrouping:
    """Tests for entity grouping logic."""

    def test_groups_contradictions_by_entity(self, service):
        """Should group contradictions by entity_id."""
        contradictions = [
            {
                "id": "c1",
                "entity_id": "entity-1",
                "entity_name": "Entity One",
                "contradiction_type": "semantic_contradiction",
                "severity": "high",
                "explanation": "Test",
                "confidence": 0.9,
                "evidence": {},
                "created_at": "2026-01-15T10:00:00Z",
                "statement_a": {
                    "chunk_id": "chunk-1",
                    "content": "Test A",
                    "page_number": 1,
                    "document_id": "doc-1",
                    "document_name": "Doc.pdf",
                },
                "statement_b": {
                    "chunk_id": "chunk-2",
                    "content": "Test B",
                    "page_number": 2,
                    "document_id": "doc-2",
                    "document_name": "Doc2.pdf",
                },
            },
            {
                "id": "c2",
                "entity_id": "entity-1",
                "entity_name": "Entity One",
                "contradiction_type": "date_mismatch",
                "severity": "medium",
                "explanation": "Test 2",
                "confidence": 0.8,
                "evidence": {},
                "created_at": "2026-01-15T09:00:00Z",
                "statement_a": {
                    "chunk_id": "chunk-3",
                    "content": "Test C",
                    "page_number": 3,
                    "document_id": "doc-1",
                    "document_name": "Doc.pdf",
                },
                "statement_b": {
                    "chunk_id": "chunk-4",
                    "content": "Test D",
                    "page_number": 4,
                    "document_id": "doc-2",
                    "document_name": "Doc2.pdf",
                },
            },
            {
                "id": "c3",
                "entity_id": "entity-2",
                "entity_name": "Entity Two",
                "contradiction_type": "amount_mismatch",
                "severity": "low",
                "explanation": "Test 3",
                "confidence": 0.7,
                "evidence": {},
                "created_at": "2026-01-15T08:00:00Z",
                "statement_a": {
                    "chunk_id": "chunk-5",
                    "content": "Test E",
                    "page_number": 5,
                    "document_id": "doc-1",
                    "document_name": "Doc.pdf",
                },
                "statement_b": {
                    "chunk_id": "chunk-6",
                    "content": "Test F",
                    "page_number": 6,
                    "document_id": "doc-2",
                    "document_name": "Doc2.pdf",
                },
            },
        ]

        result = service._group_by_entity(contradictions)

        assert len(result) == 2

        # Find entity-1 group
        entity_1_group = next(g for g in result if g.entity_id == "entity-1")
        assert entity_1_group.entity_name == "Entity One"
        assert entity_1_group.count == 2
        assert len(entity_1_group.contradictions) == 2

        # Find entity-2 group
        entity_2_group = next(g for g in result if g.entity_id == "entity-2")
        assert entity_2_group.entity_name == "Entity Two"
        assert entity_2_group.count == 1


# =============================================================================
# Excerpt Truncation Tests
# =============================================================================


class TestExcerptTruncation:
    """Tests for excerpt truncation."""

    def test_truncates_long_excerpts(self, service):
        """Should truncate excerpts longer than MAX_EXCERPT_LENGTH."""
        long_content = "A" * 300

        result = service._truncate_excerpt(long_content)

        assert len(result) == 200
        assert result.endswith("...")

    def test_keeps_short_excerpts(self, service):
        """Should not truncate short excerpts."""
        short_content = "Short content"

        result = service._truncate_excerpt(short_content)

        assert result == short_content


# =============================================================================
# Contradiction Type Parsing Tests
# =============================================================================


class TestContradictionTypeParsing:
    """Tests for contradiction type parsing."""

    def test_builds_item_with_valid_type(self, service):
        """Should parse valid contradiction types."""
        data = {
            "id": "test-id",
            "entity_id": "entity-1",
            "entity_name": "Test",
            "contradiction_type": "semantic_contradiction",
            "severity": "high",
            "explanation": "Test",
            "confidence": 0.9,
            "evidence": {},
            "created_at": "2026-01-15T10:00:00Z",
            "statement_a": {
                "chunk_id": "chunk-1",
                "content": "Test",
                "page_number": 1,
                "document_id": "doc-1",
                "document_name": "Doc.pdf",
            },
            "statement_b": {
                "chunk_id": "chunk-2",
                "content": "Test",
                "page_number": 2,
                "document_id": "doc-2",
                "document_name": "Doc2.pdf",
            },
        }

        item = service._build_contradiction_item(data)

        assert item.contradiction_type == ContradictionType.SEMANTIC_CONTRADICTION

    def test_defaults_to_semantic_for_invalid_type(self, service):
        """Should default to semantic_contradiction for invalid types."""
        data = {
            "id": "test-id",
            "entity_id": "entity-1",
            "entity_name": "Test",
            "contradiction_type": "invalid_type",
            "severity": "medium",
            "explanation": "Test",
            "confidence": 0.9,
            "evidence": {},
            "created_at": "2026-01-15T10:00:00Z",
            "statement_a": {"chunk_id": "c1", "content": "", "document_id": "", "document_name": ""},
            "statement_b": {"chunk_id": "c2", "content": "", "document_id": "", "document_name": ""},
        }

        item = service._build_contradiction_item(data)

        assert item.contradiction_type == ContradictionType.SEMANTIC_CONTRADICTION


# =============================================================================
# Severity Parsing Tests
# =============================================================================


class TestSeverityParsing:
    """Tests for severity parsing."""

    def test_parses_valid_severity(self, service):
        """Should parse valid severity levels."""
        data = {
            "id": "test-id",
            "entity_id": "entity-1",
            "entity_name": "Test",
            "contradiction_type": "semantic_contradiction",
            "severity": "low",
            "explanation": "Test",
            "confidence": 0.9,
            "evidence": {},
            "created_at": "2026-01-15T10:00:00Z",
            "statement_a": {"chunk_id": "c1", "content": "", "document_id": "", "document_name": ""},
            "statement_b": {"chunk_id": "c2", "content": "", "document_id": "", "document_name": ""},
        }

        item = service._build_contradiction_item(data)

        assert item.severity == SeverityLevel.LOW

    def test_defaults_to_medium_for_invalid_severity(self, service):
        """Should default to medium for invalid severity."""
        data = {
            "id": "test-id",
            "entity_id": "entity-1",
            "entity_name": "Test",
            "contradiction_type": "semantic_contradiction",
            "severity": "invalid",
            "explanation": "Test",
            "confidence": 0.9,
            "evidence": {},
            "created_at": "2026-01-15T10:00:00Z",
            "statement_a": {"chunk_id": "c1", "content": "", "document_id": "", "document_name": ""},
            "statement_b": {"chunk_id": "c2", "content": "", "document_id": "", "document_name": ""},
        }

        item = service._build_contradiction_item(data)

        assert item.severity == SeverityLevel.MEDIUM


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_raises_on_count_error(self, service):
        """Should raise ContradictionListServiceError on count failure."""
        service._supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.side_effect = Exception(
            "Database error"
        )

        with pytest.raises(ContradictionListServiceError) as exc_info:
            await service.get_all_contradictions(matter_id="matter-123")

        assert exc_info.value.code == "COUNT_FAILED"
