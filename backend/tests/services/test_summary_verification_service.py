"""Tests for Summary Verification Service.

Story 14.4: Summary Verification API

Test Categories:
- Verification upsert operations
- Note creation
- Verification queries
- Error handling
"""

import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.summary import (
    SummarySectionTypeEnum,
    SummaryVerificationDecisionEnum,
)
from app.services.summary_verification_service import (
    SummaryVerificationService,
    SummaryVerificationServiceError,
    get_summary_verification_service,
)


@pytest.fixture
def mock_supabase():
    """Create mock Supabase client."""
    mock_client = MagicMock()
    return mock_client


@pytest.fixture
def verification_service_with_mock(mock_supabase) -> SummaryVerificationService:
    """Create verification service with mocked supabase client."""
    service = SummaryVerificationService()
    service._supabase_client = mock_supabase
    return service


# =============================================================================
# Record Verification Tests
# =============================================================================


class TestRecordVerification:
    """Test record_verification method."""

    @pytest.mark.asyncio
    async def test_record_verification_success(
        self, verification_service_with_mock, mock_supabase
    ) -> None:
        """Should record verification successfully."""
        mock_result = MagicMock()
        mock_result.data = [{
            "id": "verification-123",
            "matter_id": "matter-123",
            "section_type": "subject_matter",
            "section_id": "main",
            "decision": "verified",
            "notes": "Approved",
            "verified_by": "user-123",
            "verified_at": "2026-01-16T10:00:00Z",
        }]

        mock_supabase.table.return_value.upsert.return_value.execute.return_value = mock_result

        result = await verification_service_with_mock.record_verification(
            matter_id="matter-123",
            section_type=SummarySectionTypeEnum.SUBJECT_MATTER,
            section_id="main",
            decision=SummaryVerificationDecisionEnum.VERIFIED,
            user_id="user-123",
            notes="Approved",
        )

        assert result.id == "verification-123"
        assert result.decision == SummaryVerificationDecisionEnum.VERIFIED
        assert result.notes == "Approved"

    @pytest.mark.asyncio
    async def test_record_verification_upsert_updates_existing(
        self, verification_service_with_mock, mock_supabase
    ) -> None:
        """Should update existing verification via upsert."""
        mock_result = MagicMock()
        mock_result.data = [{
            "id": "verification-123",
            "matter_id": "matter-123",
            "section_type": "subject_matter",
            "section_id": "main",
            "decision": "flagged",
            "notes": "Needs review",
            "verified_by": "user-456",
            "verified_at": "2026-01-16T11:00:00Z",
        }]

        mock_supabase.table.return_value.upsert.return_value.execute.return_value = mock_result

        result = await verification_service_with_mock.record_verification(
            matter_id="matter-123",
            section_type=SummarySectionTypeEnum.SUBJECT_MATTER,
            section_id="main",
            decision=SummaryVerificationDecisionEnum.FLAGGED,
            user_id="user-456",
            notes="Needs review",
        )

        # Verify upsert was called with on_conflict
        mock_supabase.table.return_value.upsert.assert_called_once()
        assert result.decision == SummaryVerificationDecisionEnum.FLAGGED

    @pytest.mark.asyncio
    async def test_record_verification_handles_error(
        self, verification_service_with_mock, mock_supabase
    ) -> None:
        """Should handle database errors gracefully."""
        mock_supabase.table.return_value.upsert.return_value.execute.side_effect = Exception(
            "Database error"
        )

        with pytest.raises(SummaryVerificationServiceError) as exc_info:
            await verification_service_with_mock.record_verification(
                matter_id="matter-123",
                section_type=SummarySectionTypeEnum.SUBJECT_MATTER,
                section_id="main",
                decision=SummaryVerificationDecisionEnum.VERIFIED,
                user_id="user-123",
            )

        assert exc_info.value.code == "VERIFICATION_FAILED"


# =============================================================================
# Add Note Tests
# =============================================================================


class TestAddNote:
    """Test add_note method."""

    @pytest.mark.asyncio
    async def test_add_note_success(
        self, verification_service_with_mock, mock_supabase
    ) -> None:
        """Should add note successfully."""
        mock_result = MagicMock()
        mock_result.data = [{
            "id": "note-123",
            "matter_id": "matter-123",
            "section_type": "parties",
            "section_id": "entity-123",
            "text": "Need to verify this party",
            "created_by": "user-123",
            "created_at": "2026-01-16T10:00:00Z",
        }]

        mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_result

        result = await verification_service_with_mock.add_note(
            matter_id="matter-123",
            section_type=SummarySectionTypeEnum.PARTIES,
            section_id="entity-123",
            text="Need to verify this party",
            user_id="user-123",
        )

        assert result.id == "note-123"
        assert result.text == "Need to verify this party"

    @pytest.mark.asyncio
    async def test_add_note_strips_whitespace(
        self, verification_service_with_mock, mock_supabase
    ) -> None:
        """Should strip whitespace from note text."""
        mock_result = MagicMock()
        mock_result.data = [{
            "id": "note-123",
            "matter_id": "matter-123",
            "section_type": "parties",
            "section_id": "entity-123",
            "text": "Trimmed note",
            "created_by": "user-123",
            "created_at": "2026-01-16T10:00:00Z",
        }]

        mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_result

        await verification_service_with_mock.add_note(
            matter_id="matter-123",
            section_type=SummarySectionTypeEnum.PARTIES,
            section_id="entity-123",
            text="  Trimmed note  ",
            user_id="user-123",
        )

        # Check that insert was called with stripped text
        call_args = mock_supabase.table.return_value.insert.call_args
        assert call_args[0][0]["text"] == "Trimmed note"


# =============================================================================
# Get Verifications Tests
# =============================================================================


class TestGetVerifications:
    """Test get_verifications method."""

    @pytest.mark.asyncio
    async def test_get_verifications_all(
        self, verification_service_with_mock, mock_supabase
    ) -> None:
        """Should get all verifications for a matter."""
        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": "v1",
                "matter_id": "matter-123",
                "section_type": "subject_matter",
                "section_id": "main",
                "decision": "verified",
                "notes": None,
                "verified_by": "user-1",
                "verified_at": "2026-01-16T10:00:00Z",
            },
            {
                "id": "v2",
                "matter_id": "matter-123",
                "section_type": "parties",
                "section_id": "entity-1",
                "decision": "flagged",
                "notes": "Needs review",
                "verified_by": "user-2",
                "verified_at": "2026-01-16T11:00:00Z",
            },
        ]

        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_result

        results = await verification_service_with_mock.get_verifications(
            matter_id="matter-123"
        )

        assert len(results) == 2
        assert results[0].id == "v1"
        assert results[1].id == "v2"

    @pytest.mark.asyncio
    async def test_get_verifications_with_filter(
        self, verification_service_with_mock, mock_supabase
    ) -> None:
        """Should filter verifications by section type."""
        mock_result = MagicMock()
        mock_result.data = [{
            "id": "v1",
            "matter_id": "matter-123",
            "section_type": "subject_matter",
            "section_id": "main",
            "decision": "verified",
            "notes": None,
            "verified_by": "user-1",
            "verified_at": "2026-01-16T10:00:00Z",
        }]

        # Mock the chain properly for filtered query
        mock_query = MagicMock()
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.execute.return_value = mock_result
        mock_supabase.table.return_value.select.return_value = mock_query

        results = await verification_service_with_mock.get_verifications(
            matter_id="matter-123",
            section_type=SummarySectionTypeEnum.SUBJECT_MATTER,
        )

        assert len(results) == 1
        assert results[0].section_type == SummarySectionTypeEnum.SUBJECT_MATTER

    @pytest.mark.asyncio
    async def test_get_verifications_returns_empty_on_error(
        self, verification_service_with_mock, mock_supabase
    ) -> None:
        """Should return empty list on error."""
        mock_supabase.table.return_value.select.side_effect = Exception("DB error")

        results = await verification_service_with_mock.get_verifications(
            matter_id="matter-123"
        )

        assert results == []


# =============================================================================
# Check Section Verified Tests
# =============================================================================


class TestCheckSectionVerified:
    """Test check_section_verified method."""

    @pytest.mark.asyncio
    async def test_check_verified_returns_true(
        self, verification_service_with_mock, mock_supabase
    ) -> None:
        """Should return True when section is verified."""
        mock_result = MagicMock()
        mock_result.data = [{"id": "v1"}]

        mock_query = MagicMock()
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value = mock_result
        mock_supabase.table.return_value.select.return_value = mock_query

        result = await verification_service_with_mock.check_section_verified(
            matter_id="matter-123",
            section_type=SummarySectionTypeEnum.SUBJECT_MATTER,
            section_id="main",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_check_verified_returns_false_when_not_found(
        self, verification_service_with_mock, mock_supabase
    ) -> None:
        """Should return False when section is not verified."""
        mock_result = MagicMock()
        mock_result.data = []

        mock_query = MagicMock()
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value = mock_result
        mock_supabase.table.return_value.select.return_value = mock_query

        result = await verification_service_with_mock.check_section_verified(
            matter_id="matter-123",
            section_type=SummarySectionTypeEnum.SUBJECT_MATTER,
            section_id="main",
        )

        assert result is False


# =============================================================================
# Get Notes Tests
# =============================================================================


class TestGetNotes:
    """Test get_notes method."""

    @pytest.mark.asyncio
    async def test_get_notes_all(
        self, verification_service_with_mock, mock_supabase
    ) -> None:
        """Should get all notes for a matter."""
        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": "n1",
                "matter_id": "matter-123",
                "section_type": "parties",
                "section_id": "entity-1",
                "text": "Note 1",
                "created_by": "user-1",
                "created_at": "2026-01-16T10:00:00Z",
            },
            {
                "id": "n2",
                "matter_id": "matter-123",
                "section_type": "subject_matter",
                "section_id": "main",
                "text": "Note 2",
                "created_by": "user-2",
                "created_at": "2026-01-16T11:00:00Z",
            },
        ]

        mock_query = MagicMock()
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_query.execute.return_value = mock_result
        mock_supabase.table.return_value.select.return_value = mock_query

        results = await verification_service_with_mock.get_notes(
            matter_id="matter-123"
        )

        assert len(results) == 2
        assert results[0].id == "n1"
        assert results[1].id == "n2"


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestGetSummaryVerificationService:
    """Test get_summary_verification_service factory."""

    def test_returns_singleton(self) -> None:
        """Should return the same instance on multiple calls."""
        # Clear cache
        get_summary_verification_service.cache_clear()

        service1 = get_summary_verification_service()
        service2 = get_summary_verification_service()

        assert service1 is service2

    def test_returns_service_instance(self) -> None:
        """Should return SummaryVerificationService instance."""
        get_summary_verification_service.cache_clear()

        service = get_summary_verification_service()

        assert isinstance(service, SummaryVerificationService)
