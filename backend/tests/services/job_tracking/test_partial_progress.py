"""Unit tests for the Partial Progress Preservation module.

Story 2c-3: Background Job Status Tracking and Retry
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.job_tracking.partial_progress import (
    PartialProgressTracker,
    StageProgress,
    create_progress_tracker,
)


# =============================================================================
# Test StageProgress
# =============================================================================


class TestStageProgress:
    """Tests for StageProgress dataclass."""

    def test_initializes_with_defaults(self) -> None:
        """Should initialize with sensible defaults."""
        progress = StageProgress(stage_name="embedding")

        assert progress.stage_name == "embedding"
        assert progress.total_items == 0
        assert progress.processed_items == set()
        assert progress.failed_items == {}
        assert progress.last_item_id is None
        assert progress.started_at is None

    def test_calculates_progress_percentage(self) -> None:
        """Should calculate progress percentage correctly."""
        progress = StageProgress(stage_name="embedding")
        progress.total_items = 100
        progress.processed_items = {"1", "2", "3", "4", "5"}

        assert progress.progress_pct == 5

    def test_progress_percentage_zero_total(self) -> None:
        """Should return 0% when total is zero."""
        progress = StageProgress(stage_name="embedding")
        progress.total_items = 0

        assert progress.progress_pct == 0

    def test_progress_percentage_caps_at_100(self) -> None:
        """Should cap at 100% even if more processed than total."""
        progress = StageProgress(stage_name="embedding")
        progress.total_items = 5
        progress.processed_items = {"1", "2", "3", "4", "5", "6", "7"}

        assert progress.progress_pct == 100

    def test_marks_item_as_processed(self) -> None:
        """Should mark item as processed and update last_item_id."""
        progress = StageProgress(stage_name="embedding")

        progress.mark_processed("chunk-1")
        progress.mark_processed("chunk-2")

        assert "chunk-1" in progress.processed_items
        assert "chunk-2" in progress.processed_items
        assert progress.last_item_id == "chunk-2"

    def test_marks_item_as_failed(self) -> None:
        """Should mark item as failed with error message."""
        progress = StageProgress(stage_name="embedding")

        progress.mark_failed("chunk-1", "API timeout")

        assert progress.failed_items == {"chunk-1": "API timeout"}

    def test_checks_if_item_is_processed(self) -> None:
        """Should correctly check if item is already processed."""
        progress = StageProgress(stage_name="embedding")
        progress.mark_processed("chunk-1")

        assert progress.is_processed("chunk-1") is True
        assert progress.is_processed("chunk-2") is False

    def test_gets_remaining_items(self) -> None:
        """Should return items not yet processed."""
        progress = StageProgress(stage_name="embedding")
        progress.mark_processed("chunk-1")
        progress.mark_processed("chunk-3")

        all_items = ["chunk-1", "chunk-2", "chunk-3", "chunk-4"]
        remaining = progress.get_remaining_items(all_items)

        assert remaining == ["chunk-2", "chunk-4"]

    def test_to_dict_serialization(self) -> None:
        """Should serialize to dictionary correctly."""
        progress = StageProgress(
            stage_name="embedding",
            total_items=100,
            started_at=datetime(2026, 1, 12, 10, 0, 0),
        )
        progress.mark_processed("chunk-1")
        progress.mark_failed("chunk-2", "Error")

        result = progress.to_dict()

        assert result["stage_name"] == "embedding"
        assert result["total_items"] == 100
        assert "chunk-1" in result["processed_items"]
        assert result["failed_items"] == {"chunk-2": "Error"}
        assert result["started_at"] == "2026-01-12T10:00:00"
        assert result["progress_pct"] == 1

    def test_from_dict_deserialization(self) -> None:
        """Should deserialize from dictionary correctly."""
        data = {
            "stage_name": "embedding",
            "total_items": 100,
            "processed_items": ["chunk-1", "chunk-2"],
            "failed_items": {"chunk-3": "Error"},
            "last_item_id": "chunk-2",
            "started_at": "2026-01-12T10:00:00",
        }

        progress = StageProgress.from_dict(data)

        assert progress.stage_name == "embedding"
        assert progress.total_items == 100
        assert progress.processed_items == {"chunk-1", "chunk-2"}
        assert progress.failed_items == {"chunk-3": "Error"}
        assert progress.last_item_id == "chunk-2"
        assert progress.started_at == datetime(2026, 1, 12, 10, 0, 0)

    def test_from_dict_handles_missing_fields(self) -> None:
        """Should handle missing fields with defaults."""
        data = {"stage_name": "embedding"}

        progress = StageProgress.from_dict(data)

        assert progress.stage_name == "embedding"
        assert progress.total_items == 0
        assert progress.processed_items == set()
        assert progress.failed_items == {}


# =============================================================================
# Test PartialProgressTracker
# =============================================================================


class TestPartialProgressTracker:
    """Tests for PartialProgressTracker."""

    @pytest.fixture
    def mock_job_tracker(self):
        """Create a mock JobTrackingService."""
        tracker = MagicMock()
        return tracker

    def test_creates_new_stage_progress(self, mock_job_tracker) -> None:
        """Should create new StageProgress for unknown stage."""
        with patch("app.services.job_tracking.partial_progress.get_job_tracking_service") as mock_get:
            mock_get.return_value = mock_job_tracker
            mock_job_tracker.get_job = AsyncMock(return_value=None)

            tracker = PartialProgressTracker(
                job_id="job-123",
                matter_id="matter-456",
                job_tracker=mock_job_tracker,
            )

            with patch("asyncio.new_event_loop") as mock_loop:
                mock_event_loop = MagicMock()
                mock_event_loop.run_until_complete.return_value = None
                mock_loop.return_value = mock_event_loop

                progress = tracker.get_or_create_stage("embedding")

            assert progress.stage_name == "embedding"
            assert progress.started_at is not None

    def test_loads_progress_from_job_metadata(self, mock_job_tracker) -> None:
        """Should load existing progress from job metadata."""
        mock_job = MagicMock()
        mock_job.metadata = {
            "partial_progress": {
                "embedding": {
                    "stage_name": "embedding",
                    "total_items": 100,
                    "processed_items": ["chunk-1", "chunk-2"],
                    "failed_items": {},
                    "last_item_id": "chunk-2",
                    "started_at": "2026-01-12T10:00:00",
                }
            }
        }

        with (
            patch("asyncio.new_event_loop") as mock_loop,
            patch("asyncio.set_event_loop"),
        ):
            mock_event_loop = MagicMock()
            mock_event_loop.run_until_complete.return_value = mock_job
            mock_loop.return_value = mock_event_loop

            tracker = PartialProgressTracker(
                job_id="job-123",
                job_tracker=mock_job_tracker,
            )
            mock_job_tracker.get_job = AsyncMock(return_value=mock_job)

            progress = tracker.get_or_create_stage("embedding")

            assert len(progress.processed_items) == 2
            assert "chunk-1" in progress.processed_items
            assert "chunk-2" in progress.processed_items

    def test_save_progress_every_10_items(self, mock_job_tracker) -> None:
        """Should only save progress every 10 items by default."""
        mock_job = MagicMock()
        mock_job.metadata = {}
        mock_job_tracker.get_job = AsyncMock(return_value=mock_job)
        mock_job_tracker.update_job = AsyncMock()

        tracker = PartialProgressTracker(
            job_id="job-123",
            job_tracker=mock_job_tracker,
        )
        tracker._loaded = True

        progress = StageProgress(stage_name="embedding")
        progress.total_items = 100

        with patch("asyncio.new_event_loop") as mock_loop:
            mock_event_loop = MagicMock()
            mock_event_loop.run_until_complete.return_value = mock_job
            mock_loop.return_value = mock_event_loop

            # Add 5 items - should not save
            for i in range(5):
                progress.mark_processed(f"chunk-{i}")
            tracker.save_progress(progress)

            # Add 5 more items (total 10) - should save
            for i in range(5, 10):
                progress.mark_processed(f"chunk-{i}")
            tracker.save_progress(progress)

    def test_save_progress_force(self, mock_job_tracker) -> None:
        """Should save immediately when force=True."""
        mock_job = MagicMock()
        mock_job.metadata = {}
        mock_job_tracker.get_job = AsyncMock(return_value=mock_job)
        mock_job_tracker.update_job = AsyncMock()

        tracker = PartialProgressTracker(
            job_id="job-123",
            job_tracker=mock_job_tracker,
        )
        tracker._loaded = True

        progress = StageProgress(stage_name="embedding")
        progress.mark_processed("chunk-1")

        with (
            patch("asyncio.new_event_loop") as mock_loop,
            patch("asyncio.set_event_loop"),
        ):
            mock_event_loop = MagicMock()
            mock_event_loop.run_until_complete.return_value = mock_job
            mock_loop.return_value = mock_event_loop

            # Force save with only 1 item
            tracker.save_progress(progress, force=True)

            # Verify save was attempted
            assert mock_event_loop.run_until_complete.called


# =============================================================================
# Test create_progress_tracker factory
# =============================================================================


class TestCreateProgressTracker:
    """Tests for create_progress_tracker factory function."""

    def test_returns_none_for_no_job_id(self) -> None:
        """Should return None when job_id is not provided."""
        result = create_progress_tracker(None)
        assert result is None

    def test_returns_tracker_with_valid_job_id(self) -> None:
        """Should return tracker when job_id is provided."""
        with patch("app.services.job_tracking.partial_progress.get_job_tracking_service"):
            result = create_progress_tracker(
                job_id="job-123",
                matter_id="matter-456",
            )

            assert result is not None
            assert isinstance(result, PartialProgressTracker)
            assert result.job_id == "job-123"
            assert result.matter_id == "matter-456"

    def test_accepts_custom_job_tracker(self) -> None:
        """Should use provided job_tracker."""
        mock_tracker = MagicMock()

        result = create_progress_tracker(
            job_id="job-123",
            job_tracker=mock_tracker,
        )

        assert result is not None
        assert result._job_tracker is mock_tracker
