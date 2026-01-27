"""Tests for export eligibility service.

Story 8-4: Implement Finding Verifications Table (Task 8)

Test Categories:
- Export eligibility check
- Blocking findings detection
- Fail-safe behavior on errors
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.verification.export_eligibility import (
    ExportEligibilityService,
    get_export_eligibility_service,
    reset_export_eligibility_service,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.verification_export_block_below = 70.0
    return settings


@pytest.fixture
def export_service(mock_settings):
    """Get export eligibility service with mocked settings."""
    reset_export_eligibility_service()

    with patch(
        "app.services.verification.export_eligibility.get_settings",
        return_value=mock_settings
    ):
        return ExportEligibilityService()


@pytest.fixture
def mock_supabase():
    """Create mock Supabase client."""
    return MagicMock()


class TestExportEligibilityCheck:
    """Test export eligibility determination."""

    @pytest.mark.asyncio
    async def test_eligible_when_no_blocking_findings(
        self, export_service, mock_supabase
    ) -> None:
        """Export should be eligible when no blocking findings."""
        mock_result = MagicMock()
        mock_result.data = []  # No blocking findings

        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.lte.return_value.execute.return_value = mock_result

        result = await export_service.check_export_eligibility(
            matter_id="test-matter-id",
            supabase=mock_supabase,
        )

        assert result.eligible is True
        assert result.blocking_count == 0
        assert len(result.blocking_findings) == 0
        assert "allowed" in result.message.lower()

    @pytest.mark.asyncio
    async def test_blocked_when_low_confidence_pending(
        self, export_service, mock_supabase
    ) -> None:
        """Export should be blocked when low confidence findings are pending."""
        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": "verification-1",
                "finding_id": "finding-1",
                "finding_type": "citation_mismatch",
                "finding_summary": "Section 138 citation issue",
                "confidence_before": 65.0,
            },
            {
                "id": "verification-2",
                "finding_id": "finding-2",
                "finding_type": "timeline_gap",
                "finding_summary": "Missing timeline events",
                "confidence_before": 50.0,
            },
        ]

        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.lte.return_value.execute.return_value = mock_result

        result = await export_service.check_export_eligibility(
            matter_id="test-matter-id",
            supabase=mock_supabase,
        )

        assert result.eligible is False
        assert result.blocking_count == 2
        assert len(result.blocking_findings) == 2
        assert "blocked" in result.message.lower()

    @pytest.mark.asyncio
    async def test_returns_blocking_finding_details(
        self, export_service, mock_supabase
    ) -> None:
        """Should return details of blocking findings."""
        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": "verification-1",
                "finding_id": "finding-1",
                "finding_type": "citation_mismatch",
                "finding_summary": "Section 138 citation issue",
                "confidence_before": 65.0,
            },
        ]

        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.lte.return_value.execute.return_value = mock_result

        result = await export_service.check_export_eligibility(
            matter_id="test-matter-id",
            supabase=mock_supabase,
        )

        assert len(result.blocking_findings) == 1
        blocking = result.blocking_findings[0]
        assert blocking.verification_id == "verification-1"
        assert blocking.finding_id == "finding-1"
        assert blocking.finding_type == "citation_mismatch"
        assert blocking.confidence == 65.0


class TestCourtReadyMode:
    """Test court-ready (required) verification mode - Story 3.2."""

    @pytest.mark.asyncio
    async def test_court_ready_blocks_all_pending_findings(
        self, export_service, mock_supabase
    ) -> None:
        """Court-ready mode should block export when ANY findings are pending."""
        # Mock matter with required verification mode
        mock_matter_result = MagicMock()
        mock_matter_result.data = [{"verification_mode": "required"}]

        # Mock findings - high confidence but still pending
        mock_blocking_result = MagicMock()
        mock_blocking_result.data = [
            {
                "id": "verification-1",
                "finding_id": "finding-1",
                "finding_type": "citation_mismatch",
                "finding_summary": "High confidence finding",
                "confidence_before": 95.0,  # Would NOT block in advisory mode
            },
        ]

        # Set up the mock chain for court-ready mode
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_matter_result
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_blocking_result

        result = await export_service.check_export_eligibility(
            matter_id="test-matter-id",
            supabase=mock_supabase,
        )

        assert result.eligible is False
        assert result.verification_mode == "required"
        assert result.blocking_count == 1
        assert "court-ready" in result.message.lower()

    @pytest.mark.asyncio
    async def test_court_ready_allows_when_all_verified(
        self, export_service, mock_supabase
    ) -> None:
        """Court-ready mode should allow export when all findings are verified."""
        # Mock matter with required verification mode
        mock_matter_result = MagicMock()
        mock_matter_result.data = [{"verification_mode": "required"}]

        # Mock no pending findings
        mock_blocking_result = MagicMock()
        mock_blocking_result.data = []

        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_matter_result
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_blocking_result

        result = await export_service.check_export_eligibility(
            matter_id="test-matter-id",
            supabase=mock_supabase,
        )

        assert result.eligible is True
        assert result.verification_mode == "required"
        assert result.blocking_count == 0
        assert "court-ready" in result.message.lower()

    @pytest.mark.asyncio
    async def test_court_ready_no_warnings_category(
        self, export_service, mock_supabase
    ) -> None:
        """Court-ready mode should not have warning findings category."""
        # Mock matter with required verification mode
        mock_matter_result = MagicMock()
        mock_matter_result.data = [{"verification_mode": "required"}]

        # No pending findings
        mock_blocking_result = MagicMock()
        mock_blocking_result.data = []

        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_matter_result
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_blocking_result

        result = await export_service.check_export_eligibility(
            matter_id="test-matter-id",
            supabase=mock_supabase,
        )

        # In court-ready mode, warnings list should always be empty
        assert result.warning_count == 0
        assert len(result.warning_findings) == 0


class TestFailSafeBehavior:
    """Test fail-safe behavior on errors."""

    @pytest.mark.asyncio
    async def test_blocks_on_database_error(
        self, export_service, mock_supabase
    ) -> None:
        """Export should be blocked on database errors (fail-safe)."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception(
            "Database connection failed"
        )

        result = await export_service.check_export_eligibility(
            matter_id="test-matter-id",
            supabase=mock_supabase,
        )

        # Should fail-safe to blocked
        assert result.eligible is False
        assert "failed" in result.message.lower()

    @pytest.mark.asyncio
    async def test_error_response_includes_verification_mode(
        self, export_service, mock_supabase
    ) -> None:
        """Error response should include verification_mode field (Code Review Fix)."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception(
            "Database error"
        )

        result = await export_service.check_export_eligibility(
            matter_id="test-matter-id",
            supabase=mock_supabase,
        )

        # Should have verification_mode defaulting to advisory
        assert result.verification_mode == "advisory"


class TestGetBlockingFindings:
    """Test getting list of blocking findings."""

    @pytest.mark.asyncio
    async def test_returns_blocking_findings_list(
        self, export_service, mock_supabase
    ) -> None:
        """Should return list of blocking findings."""
        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": "verification-1",
                "finding_id": "finding-1",
                "finding_type": "citation_mismatch",
                "finding_summary": "Issue 1",
                "confidence_before": 60.0,
            },
        ]

        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.lte.return_value.execute.return_value = mock_result

        findings = await export_service.get_blocking_findings(
            matter_id="test-matter-id",
            supabase=mock_supabase,
        )

        assert len(findings) == 1
        assert findings[0].verification_id == "verification-1"


class TestSingletonFactory:
    """Test singleton factory functions."""

    def test_returns_same_instance(self, mock_settings) -> None:
        """get_export_eligibility_service should return same instance."""
        reset_export_eligibility_service()

        with patch(
            "app.services.verification.export_eligibility.get_settings",
            return_value=mock_settings
        ):
            service1 = get_export_eligibility_service()
            service2 = get_export_eligibility_service()

            assert service1 is service2

    def test_reset_clears_singleton(self, mock_settings) -> None:
        """reset_export_eligibility_service should clear singleton."""
        with patch(
            "app.services.verification.export_eligibility.get_settings",
            return_value=mock_settings
        ):
            service1 = get_export_eligibility_service()
            reset_export_eligibility_service()
            service2 = get_export_eligibility_service()

            assert service1 is not service2
