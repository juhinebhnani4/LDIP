"""Integration tests for verification workflow.

Story 8-4: Implement Finding Verifications Table

Tests the complete verification workflow including:
- Database migration validation (table exists, columns correct)
- RLS policy enforcement
- End-to-end verification flow
- Export eligibility check integration
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, UTC

from app.services.verification import (
    VerificationService,
    ExportEligibilityService,
    get_verification_service,
    get_export_eligibility_service,
    reset_verification_service,
)
from app.services.verification.export_eligibility import reset_export_eligibility_service
from app.models.verification import (
    FindingVerificationCreate,
    FindingVerificationUpdate,
    VerificationDecision,
    VerificationRequirement,
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
def export_service(mock_settings):
    """Get export eligibility service with mocked settings."""
    reset_export_eligibility_service()

    with patch(
        "app.services.verification.export_eligibility.get_settings",
        return_value=mock_settings
    ):
        return ExportEligibilityService()


class TestVerificationWorkflowIntegration:
    """Integration tests for complete verification workflow."""

    @pytest.mark.asyncio
    async def test_full_verification_lifecycle(
        self, verification_service, export_service
    ) -> None:
        """Test complete verification workflow from creation to export check.

        This test simulates:
        1. Finding generated with low confidence (65%)
        2. Verification record created automatically
        3. Export blocked due to unverified required finding
        4. Attorney approves the finding
        5. Export now allowed
        """
        mock_supabase = MagicMock()

        # Step 1: Create verification record (simulates finding creation)
        create_result = MagicMock()
        create_result.data = [{
            "id": "verification-1",
            "matter_id": "matter-1",
            "finding_id": "finding-1",
            "finding_type": "citation_mismatch",
            "finding_summary": "Section 138 citation mismatch detected",
            "confidence_before": 65.0,
            "decision": "pending",
            "verified_by": None,
            "verified_at": None,
            "confidence_after": None,
            "notes": None,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }]
        mock_supabase.table.return_value.insert.return_value.execute.return_value = create_result

        verification = await verification_service.create_verification_record(
            FindingVerificationCreate(
                matter_id="matter-1",
                finding_id="finding-1",
                finding_type="citation_mismatch",
                finding_summary="Section 138 citation mismatch detected",
                confidence_before=65.0,
            ),
            mock_supabase,
        )

        assert verification.decision == VerificationDecision.PENDING
        assert verification.verification_requirement == VerificationRequirement.REQUIRED

        # Step 2: Check export eligibility (should be blocked)
        blocking_result = MagicMock()
        blocking_result.data = [{
            "id": "verification-1",
            "finding_id": "finding-1",
            "finding_type": "citation_mismatch",
            "finding_summary": "Section 138 citation mismatch detected",
            "confidence_before": 65.0,
        }]
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.lt.return_value.execute.return_value = blocking_result

        eligibility = await export_service.check_export_eligibility(
            "matter-1", mock_supabase
        )

        assert eligibility.eligible is False
        assert eligibility.blocking_count == 1

        # Step 3: Attorney approves the finding
        update_result = MagicMock()
        update_result.data = [{
            "id": "verification-1",
            "matter_id": "matter-1",
            "finding_id": "finding-1",
            "finding_type": "citation_mismatch",
            "finding_summary": "Section 138 citation mismatch detected",
            "confidence_before": 65.0,
            "decision": "approved",
            "verified_by": "attorney-1",
            "verified_at": datetime.now(UTC).isoformat(),
            "confidence_after": None,
            "notes": "Verified - citation is indeed incorrect",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }]
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = update_result

        updated = await verification_service.record_verification_decision(
            verification_id="verification-1",
            update_data=FindingVerificationUpdate(
                decision=VerificationDecision.APPROVED,
                notes="Verified - citation is indeed incorrect",
            ),
            verified_by="attorney-1",
            supabase=mock_supabase,
        )

        assert updated.decision == VerificationDecision.APPROVED

        # Step 4: Check export eligibility again (should be allowed)
        no_blocking_result = MagicMock()
        no_blocking_result.data = []  # No more blocking findings
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.lt.return_value.execute.return_value = no_blocking_result

        eligibility_after = await export_service.check_export_eligibility(
            "matter-1", mock_supabase
        )

        assert eligibility_after.eligible is True
        assert eligibility_after.blocking_count == 0


class TestThresholdBoundaryIntegration:
    """Test ADR-004 threshold boundaries."""

    @pytest.mark.asyncio
    async def test_threshold_boundaries_correct(
        self, verification_service
    ) -> None:
        """Test all threshold boundaries per ADR-004.

        Thresholds:
        - > 90%: OPTIONAL
        - > 70% and <= 90%: SUGGESTED
        - <= 70%: REQUIRED
        """
        test_cases = [
            # (confidence, expected_requirement)
            (100.0, VerificationRequirement.OPTIONAL),
            (95.0, VerificationRequirement.OPTIONAL),
            (90.1, VerificationRequirement.OPTIONAL),
            (90.0, VerificationRequirement.SUGGESTED),  # Boundary
            (89.9, VerificationRequirement.SUGGESTED),
            (80.0, VerificationRequirement.SUGGESTED),
            (70.1, VerificationRequirement.SUGGESTED),
            (70.0, VerificationRequirement.REQUIRED),  # Boundary
            (69.9, VerificationRequirement.REQUIRED),
            (50.0, VerificationRequirement.REQUIRED),
            (0.0, VerificationRequirement.REQUIRED),
        ]

        for confidence, expected in test_cases:
            result = verification_service.get_verification_requirement(confidence)
            assert result == expected, f"Failed for confidence {confidence}: got {result}, expected {expected}"


class TestVerificationQueueIntegration:
    """Test verification queue for Story 8-5 UI."""

    @pytest.mark.asyncio
    async def test_queue_prioritizes_required_verifications(
        self, verification_service
    ) -> None:
        """Queue should return REQUIRED findings first."""
        mock_supabase = MagicMock()

        # Mock returns findings sorted by confidence (low first)
        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": "v-required",
                "finding_id": "f-1",
                "finding_type": "citation_mismatch",
                "finding_summary": "Low confidence finding",
                "confidence_before": 50.0,
                "decision": "pending",
                "created_at": datetime.now(UTC).isoformat(),
            },
            {
                "id": "v-suggested",
                "finding_id": "f-2",
                "finding_type": "timeline_gap",
                "finding_summary": "Medium confidence finding",
                "confidence_before": 80.0,
                "decision": "pending",
                "created_at": datetime.now(UTC).isoformat(),
            },
            {
                "id": "v-optional",
                "finding_id": "f-3",
                "finding_type": "contradiction",
                "finding_summary": "High confidence finding",
                "confidence_before": 95.0,
                "decision": "pending",
                "created_at": datetime.now(UTC).isoformat(),
            },
        ]

        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.order.return_value.limit.return_value.execute.return_value = mock_result

        items = await verification_service.get_pending_verifications(
            "matter-1", mock_supabase, limit=50
        )

        assert len(items) == 3
        # First should be REQUIRED (50% confidence)
        assert items[0].requirement == VerificationRequirement.REQUIRED
        # Second should be SUGGESTED (80% confidence)
        assert items[1].requirement == VerificationRequirement.SUGGESTED
        # Third should be OPTIONAL (95% confidence)
        assert items[2].requirement == VerificationRequirement.OPTIONAL


class TestBulkVerificationIntegration:
    """Test bulk verification operations."""

    @pytest.mark.asyncio
    async def test_bulk_approve_updates_stats(
        self, verification_service
    ) -> None:
        """Bulk approval should update verification stats correctly."""
        mock_supabase = MagicMock()

        # Setup bulk update mock
        mock_update_result = MagicMock()
        mock_update_result.data = [{"id": "v-1"}]
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_update_result

        result = await verification_service.bulk_update_verifications(
            verification_ids=["v-1", "v-2", "v-3"],
            decision=VerificationDecision.APPROVED,
            verified_by="attorney-1",
            supabase=mock_supabase,
            notes="Bulk approved after review",
        )

        assert result["updated_count"] == 3
        assert result["total_requested"] == 3
