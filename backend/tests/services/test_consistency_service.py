"""Tests for Consistency Service.

Story 5.4: Cross-Engine Consistency Checking

Test Categories:
- Date normalization and matching
- Name similarity matching
- Issue creation and deduplication
- Issue retrieval and filtering
- Issue status updates
- Summary counts
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models.consistency_issue import (
    ConsistencyIssue,
    ConsistencyIssueCreate,
    ConsistencyIssueSummary,
    EngineType,
    IssueSeverity,
    IssueStatus,
    IssueType,
)
from app.services.consistency_service import (
    ConsistencyService,
    ConsistencyCheckResult,
    normalize_date,
    dates_match,
    names_similar,
    get_consistency_service,
    reset_consistency_service,
    DATE_TOLERANCE_DAYS,
    FUZZY_NAME_THRESHOLD,
)


@pytest.fixture
def mock_supabase_client():
    """Create mock Supabase client."""
    client = MagicMock()
    return client


@pytest.fixture
def consistency_service(mock_supabase_client):
    """Create consistency service with mock client."""
    service = ConsistencyService(client=mock_supabase_client)
    return service


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton between tests."""
    reset_consistency_service()
    yield
    reset_consistency_service()


# =============================================================================
# Date Normalization Tests
# =============================================================================


class TestNormalizeDate:
    """Test date string normalization."""

    def test_normalizes_iso_format(self) -> None:
        """Should normalize YYYY-MM-DD format."""
        result = normalize_date("2024-03-15")
        assert result is not None
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15

    def test_normalizes_us_format(self) -> None:
        """Should normalize MM/DD/YYYY format."""
        result = normalize_date("03/15/2024")
        assert result is not None
        assert result.month == 3
        assert result.day == 15

    def test_normalizes_uk_format(self) -> None:
        """Should normalize DD/MM/YYYY format."""
        result = normalize_date("15/03/2024")
        assert result is not None
        # Could be parsed as either format, so just check it parses
        assert result is not None

    def test_normalizes_iso_with_time(self) -> None:
        """Should normalize ISO format with time."""
        result = normalize_date("2024-03-15T10:30:00")
        assert result is not None
        assert result.year == 2024

    def test_normalizes_written_format(self) -> None:
        """Should normalize written date format."""
        result = normalize_date("15 March 2024")
        assert result is not None
        assert result.year == 2024

    def test_returns_none_for_invalid(self) -> None:
        """Should return None for invalid date."""
        result = normalize_date("not a date")
        assert result is None

    def test_returns_none_for_empty(self) -> None:
        """Should return None for empty string."""
        result = normalize_date("")
        assert result is None

    def test_returns_none_for_none(self) -> None:
        """Should return None for None input."""
        result = normalize_date(None)
        assert result is None


# =============================================================================
# Date Matching Tests
# =============================================================================


class TestDatesMatch:
    """Test date comparison with tolerance."""

    def test_exact_match(self) -> None:
        """Should match identical dates."""
        assert dates_match("2024-03-15", "2024-03-15") is True

    def test_within_tolerance(self) -> None:
        """Should match dates within tolerance."""
        assert dates_match("2024-03-15", "2024-03-17", tolerance_days=7) is True

    def test_outside_tolerance(self) -> None:
        """Should not match dates outside tolerance."""
        assert dates_match("2024-03-15", "2024-03-30", tolerance_days=7) is False

    def test_matches_when_one_none(self) -> None:
        """Should match when one date is None (can't compare)."""
        assert dates_match(None, "2024-03-15") is True
        assert dates_match("2024-03-15", None) is True

    def test_matches_when_both_none(self) -> None:
        """Should match when both dates are None."""
        assert dates_match(None, None) is True

    def test_matches_invalid_date(self) -> None:
        """Should match when one date is invalid (can't compare)."""
        assert dates_match("invalid", "2024-03-15") is True


# =============================================================================
# Name Similarity Tests
# =============================================================================


class TestNamesSimilar:
    """Test fuzzy name matching."""

    def test_exact_match(self) -> None:
        """Should match identical names."""
        assert names_similar("John Smith", "John Smith") is True

    def test_case_insensitive(self) -> None:
        """Should be case insensitive."""
        assert names_similar("John Smith", "john smith") is True

    def test_whitespace_normalized(self) -> None:
        """Should normalize whitespace."""
        assert names_similar("  John Smith  ", "John Smith") is True

    def test_similar_names_match(self) -> None:
        """Should match similar names above threshold."""
        with patch("app.core.fuzzy_match.get_similarity_ratio") as mock_ratio:
            mock_ratio.return_value = 0.90
            assert names_similar("John Smith", "Jon Smith") is True

    def test_dissimilar_names_no_match(self) -> None:
        """Should not match dissimilar names."""
        with patch("app.core.fuzzy_match.get_similarity_ratio") as mock_ratio:
            mock_ratio.return_value = 0.50
            assert names_similar("John Smith", "Jane Doe") is False

    def test_containment_fallback(self) -> None:
        """Should match if one name contains the other."""
        with patch("app.core.fuzzy_match.get_similarity_ratio") as mock_ratio:
            mock_ratio.side_effect = Exception("Fuzzy match error")
            # Fallback to containment check
            assert names_similar("Smith", "John Smith") is True


# =============================================================================
# Check Matter Consistency Tests
# =============================================================================


class TestCheckMatterConsistency:
    """Test full consistency check operation."""

    @pytest.mark.asyncio
    async def test_returns_check_result(
        self, consistency_service, mock_supabase_client
    ) -> None:
        """Should return ConsistencyCheckResult."""
        # Mock no data to find
        mock_result = MagicMock()
        mock_result.data = []
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.not_.return_value.is_.return_value.execute.return_value = mock_result
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        result = await consistency_service.check_matter_consistency("matter-123")

        assert isinstance(result, ConsistencyCheckResult)
        assert result.duration_ms >= 0
        assert len(result.engines_checked) == 3  # Default all engines

    @pytest.mark.asyncio
    async def test_checks_specified_engines_only(
        self, consistency_service, mock_supabase_client
    ) -> None:
        """Should only check specified engines."""
        mock_result = MagicMock()
        mock_result.data = []
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        result = await consistency_service.check_matter_consistency(
            "matter-123",
            engines=["timeline"],
        )

        assert result.engines_checked == ["timeline"]


# =============================================================================
# Issue Creation Tests
# =============================================================================


class TestCreateIssueIfNew:
    """Test issue creation with deduplication."""

    @pytest.mark.asyncio
    async def test_creates_new_issue(
        self, consistency_service, mock_supabase_client
    ) -> None:
        """Should create issue when not existing."""
        # Mock no existing issue
        mock_existing = MagicMock()
        mock_existing.data = []
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = mock_existing

        # Mock insert
        mock_insert = MagicMock()
        mock_supabase_client.table.return_value.insert.return_value.execute.return_value = mock_insert

        issue = ConsistencyIssueCreate(
            matter_id="matter-123",
            issue_type=IssueType.DATE_MISMATCH,
            source_engine=EngineType.TIMELINE,
            source_id="event-1",
            source_value="2024-03-15",
            conflicting_engine=EngineType.ENTITY,
            conflicting_id="mention-1",
            conflicting_value="2024-03-20",
            description="Date mismatch found",
        )

        created = await consistency_service._create_issue_if_new(issue)

        assert created is True

    @pytest.mark.asyncio
    async def test_skips_existing_issue(
        self, consistency_service, mock_supabase_client
    ) -> None:
        """Should not create duplicate issue."""
        # Mock existing issue found
        mock_existing = MagicMock()
        mock_existing.data = [{"id": "existing-issue-id"}]
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = mock_existing

        issue = ConsistencyIssueCreate(
            matter_id="matter-123",
            issue_type=IssueType.DATE_MISMATCH,
            source_engine=EngineType.TIMELINE,
            source_id="event-1",
            conflicting_engine=EngineType.ENTITY,
            conflicting_id="mention-1",
            description="Date mismatch found",
        )

        created = await consistency_service._create_issue_if_new(issue)

        assert created is False
        mock_supabase_client.table.return_value.insert.assert_not_called()


# =============================================================================
# Get Issues Tests
# =============================================================================


class TestGetIssuesForMatter:
    """Test issue retrieval."""

    @pytest.mark.asyncio
    async def test_returns_issues(
        self, consistency_service, mock_supabase_client
    ) -> None:
        """Should return list of ConsistencyIssue."""
        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": "issue-1",
                "matter_id": "matter-123",
                "issue_type": "date_mismatch",
                "severity": "warning",
                "source_engine": "timeline",
                "source_id": "event-1",
                "source_value": "2024-03-15",
                "conflicting_engine": "entity",
                "conflicting_id": "mention-1",
                "conflicting_value": "2024-03-20",
                "description": "Date mismatch",
                "document_id": None,
                "document_name": None,
                "status": "open",
                "resolved_by": None,
                "resolved_at": None,
                "resolution_notes": None,
                "detected_at": "2024-03-20T10:00:00Z",
                "created_at": "2024-03-20T10:00:00Z",
                "updated_at": "2024-03-20T10:00:00Z",
                "metadata": {},
            }
        ]
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.offset.return_value.execute.return_value = mock_result

        issues = await consistency_service.get_issues_for_matter("matter-123")

        assert len(issues) == 1
        assert isinstance(issues[0], ConsistencyIssue)
        assert issues[0].issue_type == IssueType.DATE_MISMATCH

    @pytest.mark.asyncio
    async def test_applies_status_filter(
        self, consistency_service, mock_supabase_client
    ) -> None:
        """Should filter by status when specified."""
        mock_result = MagicMock()
        mock_result.data = []
        mock_chain = MagicMock()
        mock_chain.eq.return_value = mock_chain
        mock_chain.order.return_value = mock_chain
        mock_chain.limit.return_value = mock_chain
        mock_chain.offset.return_value = mock_chain
        mock_chain.execute.return_value = mock_result
        mock_supabase_client.table.return_value.select.return_value = mock_chain

        await consistency_service.get_issues_for_matter(
            "matter-123",
            status="resolved",
        )

        # Verify eq was called with status
        calls = [str(c) for c in mock_chain.eq.call_args_list]
        assert any("status" in str(c) for c in calls)

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_no_data(
        self, consistency_service, mock_supabase_client
    ) -> None:
        """Should return empty list when no issues."""
        mock_result = MagicMock()
        mock_result.data = None
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.offset.return_value.execute.return_value = mock_result

        issues = await consistency_service.get_issues_for_matter("matter-123")

        assert issues == []


# =============================================================================
# Issue Summary Tests
# =============================================================================


class TestGetIssueSummary:
    """Test issue summary retrieval."""

    @pytest.mark.asyncio
    async def test_returns_summary(
        self, consistency_service, mock_supabase_client
    ) -> None:
        """Should return ConsistencyIssueSummary."""
        mock_result = MagicMock()
        mock_result.data = [
            {
                "total_count": 10,
                "open_count": 5,
                "warning_count": 3,
                "error_count": 2,
            }
        ]
        mock_supabase_client.rpc.return_value.execute.return_value = mock_result

        summary = await consistency_service.get_issue_summary("matter-123")

        assert isinstance(summary, ConsistencyIssueSummary)
        assert summary.total_count == 10
        assert summary.open_count == 5
        assert summary.warning_count == 3
        assert summary.error_count == 2

    @pytest.mark.asyncio
    async def test_returns_zeros_on_error(
        self, consistency_service, mock_supabase_client
    ) -> None:
        """Should return zero counts on error."""
        mock_supabase_client.rpc.side_effect = Exception("RPC error")

        summary = await consistency_service.get_issue_summary("matter-123")

        assert summary.total_count == 0
        assert summary.open_count == 0

    @pytest.mark.asyncio
    async def test_returns_zeros_on_empty_result(
        self, consistency_service, mock_supabase_client
    ) -> None:
        """Should return zeros when no data."""
        mock_result = MagicMock()
        mock_result.data = []
        mock_supabase_client.rpc.return_value.execute.return_value = mock_result

        summary = await consistency_service.get_issue_summary("matter-123")

        assert summary.total_count == 0


# =============================================================================
# Update Issue Status Tests
# =============================================================================


class TestUpdateIssueStatus:
    """Test issue status updates."""

    @pytest.mark.asyncio
    async def test_updates_to_resolved(
        self, consistency_service, mock_supabase_client
    ) -> None:
        """Should update status to resolved with user and timestamp."""
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        result = await consistency_service.update_issue_status(
            issue_id="issue-123",
            status=IssueStatus.RESOLVED,
            user_id="user-456",
            resolution_notes="Fixed manually",
        )

        assert result is True
        mock_supabase_client.table.return_value.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_updates_to_dismissed(
        self, consistency_service, mock_supabase_client
    ) -> None:
        """Should update status to dismissed."""
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        result = await consistency_service.update_issue_status(
            issue_id="issue-123",
            status=IssueStatus.DISMISSED,
            user_id="user-456",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_error(
        self, consistency_service, mock_supabase_client
    ) -> None:
        """Should return False on database error."""
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.side_effect = Exception(
            "DB error"
        )

        result = await consistency_service.update_issue_status(
            issue_id="issue-123",
            status=IssueStatus.RESOLVED,
            user_id="user-456",
        )

        assert result is False


# =============================================================================
# Date Extraction Tests
# =============================================================================


class TestExtractDatesFromText:
    """Test date extraction from text."""

    def test_extracts_iso_dates(self, consistency_service) -> None:
        """Should extract YYYY-MM-DD dates."""
        text = "The event occurred on 2024-03-15."
        dates = consistency_service._extract_dates_from_text(text)
        assert "2024-03-15" in dates

    def test_extracts_slash_dates(self, consistency_service) -> None:
        """Should extract slash-separated dates."""
        text = "Dated 03/15/2024 for reference."
        dates = consistency_service._extract_dates_from_text(text)
        assert "03/15/2024" in dates

    def test_extracts_written_dates(self, consistency_service) -> None:
        """Should extract written date formats."""
        text = "On 15 January 2024, the meeting was held."
        dates = consistency_service._extract_dates_from_text(text)
        assert len(dates) > 0

    def test_limits_results(self, consistency_service) -> None:
        """Should limit to 5 dates."""
        text = "Dates: 2024-01-01, 2024-01-02, 2024-01-03, 2024-01-04, 2024-01-05, 2024-01-06, 2024-01-07"
        dates = consistency_service._extract_dates_from_text(text)
        assert len(dates) <= 5


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Test singleton pattern."""

    def test_get_returns_same_instance(self) -> None:
        """Should return same instance on multiple calls."""
        service1 = get_consistency_service()
        service2 = get_consistency_service()
        assert service1 is service2

    def test_reset_clears_instance(self) -> None:
        """Reset should clear the singleton."""
        service1 = get_consistency_service()
        reset_consistency_service()
        service2 = get_consistency_service()
        assert service1 is not service2


# =============================================================================
# Configuration Tests
# =============================================================================


class TestConfiguration:
    """Test configuration values."""

    def test_date_tolerance_reasonable(self) -> None:
        """Date tolerance should be reasonable."""
        assert DATE_TOLERANCE_DAYS >= 1
        assert DATE_TOLERANCE_DAYS <= 30

    def test_fuzzy_threshold_reasonable(self) -> None:
        """Fuzzy threshold should be between 0 and 1."""
        assert 0 < FUZZY_NAME_THRESHOLD < 1
        assert FUZZY_NAME_THRESHOLD >= 0.8  # Should be fairly strict
