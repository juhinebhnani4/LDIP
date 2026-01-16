"""Tests for Summary Edit Service.

Story 14.6: Summary Frontend Integration (AC #7)

Test Categories:
- Save edit operations
- Get edit operations
- Delete edit operations
- Error handling
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.models.summary import SummarySectionTypeEnum
from app.services.summary_edit_service import (
    EditNotFoundError,
    EditSaveError,
    SummaryEditService,
    SummaryEditServiceError,
    get_summary_edit_service,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_supabase():
    """Create mock Supabase client."""
    return MagicMock()


@pytest.fixture
def service(mock_supabase):
    """Create service with mocked Supabase."""
    svc = SummaryEditService()
    svc._supabase_client = mock_supabase
    return svc


@pytest.fixture
def sample_edit_row():
    """Create sample edit row from database."""
    return {
        "id": "edit-123",
        "matter_id": "matter-123",
        "section_type": "subject_matter",
        "section_id": "main",
        "original_content": "Original AI-generated content",
        "edited_content": "User-edited content",
        "edited_by": "user-123",
        "edited_at": datetime.now(UTC).isoformat(),
    }


# =============================================================================
# Story 14.6: Save Edit Tests
# =============================================================================


class TestSaveEdit:
    """Test save_edit method."""

    @pytest.mark.asyncio
    async def test_save_edit_success(self, service, mock_supabase, sample_edit_row):
        """Should successfully save edit via upsert."""
        mock_execute = MagicMock()
        mock_execute.data = [sample_edit_row]
        mock_supabase.table.return_value.upsert.return_value.execute.return_value = mock_execute

        result = await service.save_edit(
            matter_id="matter-123",
            section_type=SummarySectionTypeEnum.SUBJECT_MATTER,
            section_id="main",
            content="User-edited content",
            original_content="Original AI-generated content",
            user_id="user-123",
        )

        assert result.id == "edit-123"
        assert result.edited_content == "User-edited content"
        assert result.original_content == "Original AI-generated content"
        mock_supabase.table.assert_called_with("summary_edits")

    @pytest.mark.asyncio
    async def test_save_edit_upsert_updates_existing(self, service, mock_supabase, sample_edit_row):
        """Should update existing edit on conflict."""
        mock_execute = MagicMock()
        mock_execute.data = [sample_edit_row]
        mock_upsert = MagicMock()
        mock_upsert.execute.return_value = mock_execute
        mock_supabase.table.return_value.upsert.return_value = mock_upsert

        await service.save_edit(
            matter_id="matter-123",
            section_type=SummarySectionTypeEnum.SUBJECT_MATTER,
            section_id="main",
            content="Updated content",
            original_content="Original content",
            user_id="user-123",
        )

        # Verify upsert was called with conflict handling
        mock_supabase.table.return_value.upsert.assert_called_once()
        call_kwargs = mock_supabase.table.return_value.upsert.call_args
        assert "on_conflict" in call_kwargs.kwargs

    @pytest.mark.asyncio
    async def test_save_edit_error_handling(self, service, mock_supabase):
        """Should raise EditSaveError on failure."""
        mock_supabase.table.return_value.upsert.return_value.execute.side_effect = Exception(
            "Database error"
        )

        with pytest.raises(EditSaveError) as exc_info:
            await service.save_edit(
                matter_id="matter-123",
                section_type=SummarySectionTypeEnum.SUBJECT_MATTER,
                section_id="main",
                content="Content",
                original_content="Original",
                user_id="user-123",
            )

        assert "Database error" in str(exc_info.value.message)


# =============================================================================
# Story 14.6: Get Edit Tests
# =============================================================================


class TestGetEdit:
    """Test get_edit method."""

    @pytest.mark.asyncio
    async def test_get_edit_success(self, service, mock_supabase, sample_edit_row):
        """Should successfully retrieve edit."""
        mock_execute = MagicMock()
        mock_execute.data = [sample_edit_row]
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_execute

        result = await service.get_edit(
            matter_id="matter-123",
            section_type=SummarySectionTypeEnum.SUBJECT_MATTER,
            section_id="main",
        )

        assert result is not None
        assert result.id == "edit-123"
        assert result.edited_content == "User-edited content"

    @pytest.mark.asyncio
    async def test_get_edit_not_found(self, service, mock_supabase):
        """Should return None when edit not found."""
        mock_execute = MagicMock()
        mock_execute.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = mock_execute

        result = await service.get_edit(
            matter_id="matter-123",
            section_type=SummarySectionTypeEnum.SUBJECT_MATTER,
            section_id="main",
        )

        assert result is None


# =============================================================================
# Story 14.6: Get All Edits Tests
# =============================================================================


class TestGetAllEdits:
    """Test get_all_edits method."""

    @pytest.mark.asyncio
    async def test_get_all_edits_success(self, service, mock_supabase, sample_edit_row):
        """Should successfully retrieve all edits for matter."""
        mock_execute = MagicMock()
        mock_execute.data = [sample_edit_row]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_execute

        result = await service.get_all_edits(matter_id="matter-123")

        assert len(result) == 1
        assert result[0].id == "edit-123"

    @pytest.mark.asyncio
    async def test_get_all_edits_empty(self, service, mock_supabase):
        """Should return empty list when no edits exist."""
        mock_execute = MagicMock()
        mock_execute.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_execute

        result = await service.get_all_edits(matter_id="matter-123")

        assert result == []


# =============================================================================
# Story 14.6: Delete Edit Tests
# =============================================================================


class TestDeleteEdit:
    """Test delete_edit method."""

    @pytest.mark.asyncio
    async def test_delete_edit_success(self, service, mock_supabase, sample_edit_row):
        """Should successfully delete edit."""
        mock_execute = MagicMock()
        mock_execute.data = [sample_edit_row]
        mock_supabase.table.return_value.delete.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = mock_execute

        result = await service.delete_edit(
            matter_id="matter-123",
            section_type=SummarySectionTypeEnum.SUBJECT_MATTER,
            section_id="main",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_edit_not_found(self, service, mock_supabase):
        """Should return False when edit not found."""
        mock_execute = MagicMock()
        mock_execute.data = []
        mock_supabase.table.return_value.delete.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = mock_execute

        result = await service.delete_edit(
            matter_id="matter-123",
            section_type=SummarySectionTypeEnum.SUBJECT_MATTER,
            section_id="main",
        )

        assert result is False


# =============================================================================
# Story 14.6: Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Test get_summary_edit_service factory function."""

    def test_factory_returns_service(self):
        """Should return SummaryEditService instance."""
        # Clear cache first
        get_summary_edit_service.cache_clear()

        service = get_summary_edit_service()

        assert isinstance(service, SummaryEditService)

    def test_factory_returns_singleton(self):
        """Should return same instance on multiple calls (cached)."""
        get_summary_edit_service.cache_clear()

        service1 = get_summary_edit_service()
        service2 = get_summary_edit_service()

        assert service1 is service2


# =============================================================================
# Story 14.6: Exception Tests
# =============================================================================


class TestExceptions:
    """Test exception classes."""

    def test_summary_edit_service_error(self):
        """SummaryEditServiceError should have message, code, and status_code."""
        error = SummaryEditServiceError(
            message="Test error",
            code="TEST_ERROR",
            status_code=400,
        )

        assert error.message == "Test error"
        assert error.code == "TEST_ERROR"
        assert error.status_code == 400

    def test_edit_not_found_error(self):
        """EditNotFoundError should have 404 status."""
        error = EditNotFoundError()

        assert error.code == "EDIT_NOT_FOUND"
        assert error.status_code == 404

    def test_edit_save_error(self):
        """EditSaveError should have 500 status."""
        error = EditSaveError("Save failed")

        assert error.code == "EDIT_SAVE_FAILED"
        assert error.status_code == 500
