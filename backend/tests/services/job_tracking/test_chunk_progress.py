"""Tests for ChunkProgressTracker.

Story 15.3: Integrate Chunk Progress with Job Tracking
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.job import JobStatus
from app.models.ocr_chunk import ChunkProgress
from app.services.job_tracking.chunk_progress import (
    ChunkProgressTracker,
    format_chunk_failure_message,
    get_chunk_progress_tracker,
)


@pytest.fixture
def mock_chunk_service():
    """Create a mock OCRChunkService."""
    service = MagicMock()
    service.get_chunk_progress = AsyncMock()
    return service


@pytest.fixture
def mock_job_tracker():
    """Create a mock JobTrackingService."""
    tracker = MagicMock()
    tracker.update_job_status = AsyncMock()
    return tracker


class TestFormatChunkFailureMessage:
    """Tests for format_chunk_failure_message."""

    def test_formats_failure_with_page_range(self):
        """Format failure message includes page range."""
        result = format_chunk_failure_message(
            chunk_index=4,  # 0-indexed
            page_start=101,
            page_end=125,
            error_message="Document AI timeout",
        )

        assert result == "Chunk 5 (pages 101-125) failed: Document AI timeout"

    def test_formats_first_chunk(self):
        """First chunk (index 0) displays as Chunk 1."""
        result = format_chunk_failure_message(
            chunk_index=0,
            page_start=1,
            page_end=25,
            error_message="Network error",
        )

        assert result == "Chunk 1 (pages 1-25) failed: Network error"

    def test_handles_single_page_chunk(self):
        """Single page chunks format correctly."""
        result = format_chunk_failure_message(
            chunk_index=16,
            page_start=422,
            page_end=422,
            error_message="Invalid PDF",
        )

        assert result == "Chunk 17 (pages 422-422) failed: Invalid PDF"


class TestChunkProgressTracker:
    """Tests for ChunkProgressTracker class."""

    @pytest.mark.asyncio
    async def test_update_chunk_progress_calculates_percentage(
        self,
        mock_chunk_service,
        mock_job_tracker,
    ):
        """Progress percentage is calculated from completed chunks."""
        # Arrange
        mock_chunk_service.get_chunk_progress.return_value = ChunkProgress(
            total=17,
            pending=5,
            processing=1,
            completed=10,
            failed=1,
        )
        tracker = ChunkProgressTracker(
            job_tracker=mock_job_tracker,
            chunk_service=mock_chunk_service,
        )

        # Act
        with patch(
            "app.services.job_tracking.chunk_progress.broadcast_job_progress"
        ) as mock_broadcast:
            result = await tracker.update_chunk_progress(
                job_id="job-123",
                document_id="doc-456",
                matter_id="matter-789",
            )

        # Assert - 10 completed out of 17 = 58%
        mock_job_tracker.update_job_status.assert_called_once()
        call_args = mock_job_tracker.update_job_status.call_args
        assert call_args.kwargs["progress_pct"] == 58
        assert "10/17" in call_args.kwargs["stage"]
        assert call_args.kwargs["status"] == JobStatus.PROCESSING

        # Verify broadcast was called
        mock_broadcast.assert_called_once()
        broadcast_args = mock_broadcast.call_args.kwargs
        assert broadcast_args["progress_pct"] == 58
        assert broadcast_args["job_id"] == "job-123"
        assert broadcast_args["matter_id"] == "matter-789"

        # Verify return value
        assert result.completed == 10
        assert result.total == 17

    @pytest.mark.asyncio
    async def test_update_chunk_progress_handles_zero_total(
        self,
        mock_chunk_service,
        mock_job_tracker,
    ):
        """Zero total chunks results in 0% progress."""
        mock_chunk_service.get_chunk_progress.return_value = ChunkProgress(
            total=0,
            pending=0,
            processing=0,
            completed=0,
            failed=0,
        )
        tracker = ChunkProgressTracker(
            job_tracker=mock_job_tracker,
            chunk_service=mock_chunk_service,
        )

        with patch(
            "app.services.job_tracking.chunk_progress.broadcast_job_progress"
        ):
            await tracker.update_chunk_progress(
                job_id="job-123",
                document_id="doc-456",
                matter_id="matter-789",
            )

        call_args = mock_job_tracker.update_job_status.call_args
        assert call_args.kwargs["progress_pct"] == 0

    @pytest.mark.asyncio
    async def test_update_chunk_progress_100_percent(
        self,
        mock_chunk_service,
        mock_job_tracker,
    ):
        """All chunks completed results in 100% progress."""
        mock_chunk_service.get_chunk_progress.return_value = ChunkProgress(
            total=17,
            pending=0,
            processing=0,
            completed=17,
            failed=0,
        )
        tracker = ChunkProgressTracker(
            job_tracker=mock_job_tracker,
            chunk_service=mock_chunk_service,
        )

        with patch(
            "app.services.job_tracking.chunk_progress.broadcast_job_progress"
        ):
            await tracker.update_chunk_progress(
                job_id="job-123",
                document_id="doc-456",
                matter_id="matter-789",
            )

        call_args = mock_job_tracker.update_job_status.call_args
        assert call_args.kwargs["progress_pct"] == 100
        assert "17/17" in call_args.kwargs["stage"]


class TestStartMergeStage:
    """Tests for start_merge_stage method."""

    @pytest.mark.asyncio
    async def test_start_merge_stage_updates_status(
        self,
        mock_chunk_service,
        mock_job_tracker,
    ):
        """Merge stage updates job with correct stage message."""
        tracker = ChunkProgressTracker(
            job_tracker=mock_job_tracker,
            chunk_service=mock_chunk_service,
        )

        with patch(
            "app.services.job_tracking.chunk_progress.broadcast_job_progress"
        ) as mock_broadcast:
            await tracker.start_merge_stage(
                job_id="job-123",
                document_id="doc-456",
                matter_id="matter-789",
            )

        # Verify job status updated
        mock_job_tracker.update_job_status.assert_called_once()
        call_args = mock_job_tracker.update_job_status.call_args
        assert call_args.kwargs["stage"] == "Merging OCR results"
        assert call_args.kwargs["progress_pct"] == 95
        assert call_args.kwargs["status"] == JobStatus.PROCESSING

        # Verify broadcast
        mock_broadcast.assert_called_once()
        broadcast_args = mock_broadcast.call_args.kwargs
        assert broadcast_args["stage"] == "Merging OCR results"
        assert broadcast_args["progress_pct"] == 95


class TestReportChunkFailure:
    """Tests for report_chunk_failure method."""

    @pytest.mark.asyncio
    async def test_report_chunk_failure_updates_status(
        self,
        mock_chunk_service,
        mock_job_tracker,
    ):
        """Chunk failure reports error with page range context."""
        mock_chunk_service.get_chunk_progress.return_value = ChunkProgress(
            total=17,
            pending=5,
            processing=0,
            completed=10,
            failed=2,
        )
        tracker = ChunkProgressTracker(
            job_tracker=mock_job_tracker,
            chunk_service=mock_chunk_service,
        )

        with patch(
            "app.services.job_tracking.chunk_progress.broadcast_job_progress"
        ):
            await tracker.report_chunk_failure(
                job_id="job-123",
                document_id="doc-456",
                matter_id="matter-789",
                chunk_index=11,
                page_start=276,
                page_end=300,
                error_message="Document AI timeout",
            )

        # Verify job status updated with error
        mock_job_tracker.update_job_status.assert_called_once()
        call_args = mock_job_tracker.update_job_status.call_args

        # Job should still be PROCESSING (not FAILED) to allow retry
        assert call_args.kwargs["status"] == JobStatus.PROCESSING

        # Error message should have formatted failure info
        assert "Chunk 12 (pages 276-300)" in call_args.kwargs["error_message"]
        assert "Document AI timeout" in call_args.kwargs["error_message"]

        # Stage should show failure summary
        assert "failed" in call_args.kwargs["stage"]


class TestGetProgressSummary:
    """Tests for get_progress_summary method."""

    @pytest.mark.asyncio
    async def test_returns_metadata_dict(
        self,
        mock_chunk_service,
        mock_job_tracker,
    ):
        """Progress summary returns dict suitable for job metadata."""
        mock_chunk_service.get_chunk_progress.return_value = ChunkProgress(
            total=17,
            pending=5,
            processing=1,
            completed=10,
            failed=1,
        )
        tracker = ChunkProgressTracker(
            job_tracker=mock_job_tracker,
            chunk_service=mock_chunk_service,
        )

        result = await tracker.get_progress_summary("doc-456")

        assert "chunk_processing" in result
        cp = result["chunk_processing"]
        assert cp["total_chunks"] == 17
        assert cp["completed_chunks"] == 10
        assert cp["failed_chunks"] == 1
        assert cp["pending_chunks"] == 5
        assert cp["processing_chunks"] == 1
        assert cp["progress_pct"] == 58  # 10/17
        assert cp["is_complete"] is False
        assert cp["has_failures"] is True


class TestGetChunkProgressTracker:
    """Tests for get_chunk_progress_tracker factory."""

    def test_returns_singleton(self):
        """Factory returns the same instance."""
        # Clear the cache first
        get_chunk_progress_tracker.cache_clear()

        tracker1 = get_chunk_progress_tracker()
        tracker2 = get_chunk_progress_tracker()

        assert tracker1 is tracker2

    def test_returns_chunk_progress_tracker_instance(self):
        """Factory returns ChunkProgressTracker instance."""
        get_chunk_progress_tracker.cache_clear()

        tracker = get_chunk_progress_tracker()

        assert isinstance(tracker, ChunkProgressTracker)
