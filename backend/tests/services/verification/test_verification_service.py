"""Tests for verification service.

Story 8-4: Implement Finding Verifications Table

Test Categories:
- Verification requirement calculation (ADR-004 thresholds)
- Verification record creation
- Verification decision recording
- Queue retrieval
- Statistics calculation
- Bulk operations
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.models.verification import (
    FindingVerificationCreate,
    FindingVerificationUpdate,
    VerificationDecision,
    VerificationRequirement,
)
from app.services.verification.verification_service import (
    VerificationNotFoundError,
    VerificationService,
    VerificationServiceError,
    get_verification_service,
    reset_verification_service,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.verification_threshold_optional = 90.0
    settings.verification_threshold_suggested = 70.0
    settings.verification_export_block_below = 70.0
    return settings


@pytest.fixture
def verification_service(mock_settings):
    """Get verification service with mocked settings."""
    reset_verification_service()

    with patch(
        "app.services.verification.verification_service.get_settings",
        return_value=mock_settings
    ):
        return VerificationService()


@pytest.fixture
def mock_supabase():
    """Create mock Supabase client."""
    return MagicMock()


class TestVerificationRequirementCalculation:
    """Test verification requirement based on confidence thresholds."""

    def test_high_confidence_is_optional(self, verification_service) -> None:
        """Confidence > 90% should return OPTIONAL."""
        result = verification_service.get_verification_requirement(95.0)
        assert result == VerificationRequirement.OPTIONAL

    def test_boundary_90_is_suggested(self, verification_service) -> None:
        """Confidence exactly 90% should return SUGGESTED."""
        result = verification_service.get_verification_requirement(90.0)
        assert result == VerificationRequirement.SUGGESTED

    def test_medium_confidence_is_suggested(self, verification_service) -> None:
        """Confidence 70-90% should return SUGGESTED."""
        result = verification_service.get_verification_requirement(85.0)
        assert result == VerificationRequirement.SUGGESTED

    def test_boundary_70_is_required(self, verification_service) -> None:
        """Confidence exactly 70% should return REQUIRED."""
        result = verification_service.get_verification_requirement(70.0)
        assert result == VerificationRequirement.REQUIRED

    def test_low_confidence_is_required(self, verification_service) -> None:
        """Confidence < 70% should return REQUIRED."""
        result = verification_service.get_verification_requirement(65.0)
        assert result == VerificationRequirement.REQUIRED

    def test_very_low_confidence_is_required(self, verification_service) -> None:
        """Very low confidence should return REQUIRED."""
        result = verification_service.get_verification_requirement(30.0)
        assert result == VerificationRequirement.REQUIRED

    def test_zero_confidence_is_required(self, verification_service) -> None:
        """Zero confidence should return REQUIRED."""
        result = verification_service.get_verification_requirement(0.0)
        assert result == VerificationRequirement.REQUIRED

    def test_max_confidence_is_optional(self, verification_service) -> None:
        """100% confidence should return OPTIONAL."""
        result = verification_service.get_verification_requirement(100.0)
        assert result == VerificationRequirement.OPTIONAL


class TestCreateVerificationRecord:
    """Test verification record creation."""

    @pytest.mark.asyncio
    async def test_creates_record_successfully(
        self, verification_service, mock_supabase
    ) -> None:
        """Should create verification record with correct data."""
        mock_result = MagicMock()
        mock_result.data = [{
            "id": "test-verification-id",
            "matter_id": "test-matter-id",
            "finding_id": "test-finding-id",
            "finding_type": "citation_mismatch",
            "finding_summary": "Test finding summary",
            "confidence_before": 85.0,
            "decision": "pending",
            "verified_by": None,
            "verified_at": None,
            "confidence_after": None,
            "notes": None,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }]

        mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_result

        create_data = FindingVerificationCreate(
            matter_id="test-matter-id",
            finding_id="test-finding-id",
            finding_type="citation_mismatch",
            finding_summary="Test finding summary",
            confidence_before=85.0,
        )

        result = await verification_service.create_verification_record(
            create_data, mock_supabase
        )

        assert result.id == "test-verification-id"
        assert result.decision == VerificationDecision.PENDING
        assert result.verification_requirement == VerificationRequirement.SUGGESTED

    @pytest.mark.asyncio
    async def test_summary_length_enforced_by_model(
        self, verification_service, mock_supabase
    ) -> None:
        """Summary length should be enforced by Pydantic model (max 500 chars)."""
        from pydantic import ValidationError

        # Model should reject summaries > 500 characters
        with pytest.raises(ValidationError) as exc_info:
            FindingVerificationCreate(
                matter_id="test-matter-id",
                finding_id="test-finding-id",
                finding_type="citation_mismatch",
                finding_summary="X" * 501,  # 501 chars - over limit
                confidence_before=85.0,
            )

        assert "finding_summary" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_accepts_max_length_summary(
        self, verification_service, mock_supabase
    ) -> None:
        """Should accept summary at max length (500 chars)."""
        mock_result = MagicMock()
        mock_result.data = [{
            "id": "test-id",
            "matter_id": "test-matter-id",
            "finding_id": "test-finding-id",
            "finding_type": "citation_mismatch",
            "finding_summary": "X" * 500,
            "confidence_before": 85.0,
            "decision": "pending",
            "verified_by": None,
            "verified_at": None,
            "confidence_after": None,
            "notes": None,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }]

        mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_result

        # 500 chars should be accepted
        create_data = FindingVerificationCreate(
            matter_id="test-matter-id",
            finding_id="test-finding-id",
            finding_type="citation_mismatch",
            finding_summary="X" * 500,
            confidence_before=85.0,
        )

        result = await verification_service.create_verification_record(
            create_data, mock_supabase
        )

        assert result is not None


class TestRecordVerificationDecision:
    """Test recording attorney verification decisions."""

    @pytest.mark.asyncio
    async def test_records_approval(
        self, verification_service, mock_supabase
    ) -> None:
        """Should record approval decision."""
        mock_result = MagicMock()
        mock_result.data = [{
            "id": "test-id",
            "matter_id": "test-matter-id",
            "finding_id": "test-finding-id",
            "finding_type": "citation_mismatch",
            "finding_summary": "Test summary",
            "confidence_before": 85.0,
            "decision": "approved",
            "verified_by": "test-user-id",
            "verified_at": datetime.now(UTC).isoformat(),
            "confidence_after": None,
            "notes": "Looks correct",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }]

        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_result

        update_data = FindingVerificationUpdate(
            decision=VerificationDecision.APPROVED,
            notes="Looks correct",
        )

        result = await verification_service.record_verification_decision(
            verification_id="test-id",
            update_data=update_data,
            verified_by="test-user-id",
            supabase=mock_supabase,
        )

        assert result.decision == VerificationDecision.APPROVED
        assert result.notes == "Looks correct"

    @pytest.mark.asyncio
    async def test_records_rejection(
        self, verification_service, mock_supabase
    ) -> None:
        """Should record rejection decision."""
        mock_result = MagicMock()
        mock_result.data = [{
            "id": "test-id",
            "matter_id": "test-matter-id",
            "finding_id": "test-finding-id",
            "finding_type": "citation_mismatch",
            "finding_summary": "Test summary",
            "confidence_before": 85.0,
            "decision": "rejected",
            "verified_by": "test-user-id",
            "verified_at": datetime.now(UTC).isoformat(),
            "confidence_after": None,
            "notes": "False positive - citation is correct",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }]

        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_result

        update_data = FindingVerificationUpdate(
            decision=VerificationDecision.REJECTED,
            notes="False positive - citation is correct",
        )

        result = await verification_service.record_verification_decision(
            verification_id="test-id",
            update_data=update_data,
            verified_by="test-user-id",
            supabase=mock_supabase,
        )

        assert result.decision == VerificationDecision.REJECTED

    @pytest.mark.asyncio
    async def test_records_confidence_adjustment(
        self, verification_service, mock_supabase
    ) -> None:
        """Should record adjusted confidence."""
        mock_result = MagicMock()
        mock_result.data = [{
            "id": "test-id",
            "matter_id": "test-matter-id",
            "finding_id": "test-finding-id",
            "finding_type": "citation_mismatch",
            "finding_summary": "Test summary",
            "confidence_before": 85.0,
            "decision": "approved",
            "verified_by": "test-user-id",
            "verified_at": datetime.now(UTC).isoformat(),
            "confidence_after": 95.0,
            "notes": None,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }]

        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_result

        update_data = FindingVerificationUpdate(
            decision=VerificationDecision.APPROVED,
            confidence_after=95.0,
        )

        result = await verification_service.record_verification_decision(
            verification_id="test-id",
            update_data=update_data,
            verified_by="test-user-id",
            supabase=mock_supabase,
        )

        assert result.confidence_after == 95.0

    @pytest.mark.asyncio
    async def test_raises_not_found_on_missing(
        self, verification_service, mock_supabase
    ) -> None:
        """Should raise VerificationNotFoundError if not found."""
        mock_result = MagicMock()
        mock_result.data = []

        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_result

        update_data = FindingVerificationUpdate(
            decision=VerificationDecision.APPROVED,
        )

        with pytest.raises(VerificationNotFoundError):
            await verification_service.record_verification_decision(
                verification_id="non-existent-id",
                update_data=update_data,
                verified_by="test-user-id",
                supabase=mock_supabase,
            )


class TestGetVerificationStats:
    """Test verification statistics calculation."""

    @pytest.mark.asyncio
    async def test_calculates_stats_correctly(
        self, verification_service, mock_supabase
    ) -> None:
        """Should calculate correct statistics."""
        mock_result = MagicMock()
        mock_result.data = [
            # Low confidence pending (required, blocks export)
            {"decision": "pending", "confidence_before": 65.0},
            # Medium confidence pending (suggested)
            {"decision": "pending", "confidence_before": 80.0},
            # High confidence pending (optional)
            {"decision": "pending", "confidence_before": 95.0},
            # Approved
            {"decision": "approved", "confidence_before": 85.0},
            # Rejected
            {"decision": "rejected", "confidence_before": 75.0},
            # Flagged
            {"decision": "flagged", "confidence_before": 50.0},
        ]

        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        stats = await verification_service.get_verification_stats(
            matter_id="test-matter-id",
            supabase=mock_supabase,
        )

        assert stats.total_verifications == 6
        assert stats.pending_count == 3
        assert stats.approved_count == 1
        assert stats.rejected_count == 1
        assert stats.flagged_count == 1
        assert stats.required_pending == 1  # 65%
        assert stats.suggested_pending == 1  # 80%
        assert stats.optional_pending == 1  # 95%
        assert stats.export_blocked is True  # Has required pending
        assert stats.blocking_count == 1

    @pytest.mark.asyncio
    async def test_export_allowed_when_no_required_pending(
        self, verification_service, mock_supabase
    ) -> None:
        """Export should be allowed when no required verifications pending."""
        mock_result = MagicMock()
        mock_result.data = [
            {"decision": "pending", "confidence_before": 95.0},  # Optional
            {"decision": "approved", "confidence_before": 65.0},  # Was required, now approved
        ]

        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        stats = await verification_service.get_verification_stats(
            matter_id="test-matter-id",
            supabase=mock_supabase,
        )

        assert stats.export_blocked is False
        assert stats.blocking_count == 0


class TestPendingVerifications:
    """Test pending verification queue retrieval."""

    @pytest.mark.asyncio
    async def test_returns_pending_sorted_by_confidence(
        self, verification_service, mock_supabase
    ) -> None:
        """Should return pending verifications sorted by confidence (low first)."""
        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": "id-1",
                "finding_id": "finding-1",
                "finding_type": "citation_mismatch",
                "finding_summary": "Low confidence finding",
                "confidence_before": 50.0,
                "decision": "pending",
                "created_at": datetime.now(UTC).isoformat(),
            },
            {
                "id": "id-2",
                "finding_id": "finding-2",
                "finding_type": "timeline_gap",
                "finding_summary": "High confidence finding",
                "confidence_before": 95.0,
                "decision": "pending",
                "created_at": datetime.now(UTC).isoformat(),
            },
        ]

        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.order.return_value.limit.return_value.execute.return_value = mock_result

        items = await verification_service.get_pending_verifications(
            matter_id="test-matter-id",
            supabase=mock_supabase,
            limit=50,
        )

        assert len(items) == 2
        # First item should be low confidence (REQUIRED tier)
        assert items[0].confidence == 50.0
        assert items[0].requirement == VerificationRequirement.REQUIRED


class TestBulkUpdateVerifications:
    """Test bulk verification operations."""

    @pytest.mark.asyncio
    async def test_bulk_approves_multiple(
        self, verification_service, mock_supabase
    ) -> None:
        """Should bulk approve multiple verifications."""
        mock_result = MagicMock()
        mock_result.data = [{"id": "id-1"}]

        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_result

        result = await verification_service.bulk_update_verifications(
            verification_ids=["id-1", "id-2", "id-3"],
            decision=VerificationDecision.APPROVED,
            verified_by="test-user-id",
            supabase=mock_supabase,
        )

        assert result["updated_count"] == 3
        assert result["failed_ids"] == []

    @pytest.mark.asyncio
    async def test_reports_failed_ids(
        self, verification_service, mock_supabase
    ) -> None:
        """Should report IDs that failed to update."""
        def side_effect(*args, **kwargs):
            result = MagicMock()
            # First call succeeds, second fails
            if mock_supabase.table.return_value.update.call_count == 1:
                result.data = [{"id": "id-1"}]
            else:
                result.data = []  # Not found
            return result

        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.side_effect = side_effect

        result = await verification_service.bulk_update_verifications(
            verification_ids=["id-1", "id-2"],
            decision=VerificationDecision.APPROVED,
            verified_by="test-user-id",
            supabase=mock_supabase,
        )

        assert result["updated_count"] == 1
        assert "id-2" in result["failed_ids"]

    @pytest.mark.asyncio
    async def test_rejects_over_100_items(
        self, verification_service, mock_supabase
    ) -> None:
        """Should reject bulk operations with over 100 items."""
        with pytest.raises(VerificationServiceError) as exc_info:
            await verification_service.bulk_update_verifications(
                verification_ids=[f"id-{i}" for i in range(101)],
                decision=VerificationDecision.APPROVED,
                verified_by="test-user-id",
                supabase=mock_supabase,
            )

        assert exc_info.value.code == "BULK_LIMIT_EXCEEDED"


class TestSingletonFactory:
    """Test singleton factory functions."""

    def test_returns_same_instance(self, mock_settings) -> None:
        """get_verification_service should return same instance."""
        reset_verification_service()

        with patch(
            "app.services.verification.verification_service.get_settings",
            return_value=mock_settings
        ):
            service1 = get_verification_service()
            service2 = get_verification_service()

            assert service1 is service2

    def test_reset_clears_singleton(self, mock_settings) -> None:
        """reset_verification_service should clear singleton."""
        with patch(
            "app.services.verification.verification_service.get_settings",
            return_value=mock_settings
        ):
            service1 = get_verification_service()
            reset_verification_service()
            service2 = get_verification_service()

            assert service1 is not service2
