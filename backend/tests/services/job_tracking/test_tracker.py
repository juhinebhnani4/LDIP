"""Unit tests for the Job Tracking Service.

Story 2c-3: Background Job Status Tracking and Retry
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.job import (
    JobStatus,
    JobType,
    StageStatus,
)
from app.services.job_tracking.tracker import (
    JobNotFoundError,
    JobTrackingError,
    JobTrackingService,
    get_job_tracking_service,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_supabase_response():
    """Create a mock Supabase response."""
    def _create(data: list[dict] | None = None, count: int | None = None):
        response = MagicMock()
        response.data = data
        response.count = count
        return response
    return _create


@pytest.fixture
def sample_job_row() -> dict[str, Any]:
    """Sample database row for a processing job."""
    return {
        "id": "job-123",
        "matter_id": "matter-456",
        "document_id": "doc-789",
        "job_type": "DOCUMENT_PROCESSING",
        "status": "QUEUED",
        "celery_task_id": "celery-abc",
        "current_stage": None,
        "total_stages": 7,
        "completed_stages": 0,
        "progress_pct": 0,
        "estimated_completion": None,
        "error_message": None,
        "error_code": None,
        "retry_count": 0,
        "max_retries": 3,
        "metadata": {},
        "started_at": None,
        "completed_at": None,
        "created_at": "2026-01-12T10:00:00Z",
        "updated_at": "2026-01-12T10:00:00Z",
    }


@pytest.fixture
def sample_stage_row() -> dict[str, Any]:
    """Sample database row for stage history."""
    return {
        "id": "stage-123",
        "job_id": "job-123",
        "stage_name": "ocr",
        "status": "IN_PROGRESS",
        "started_at": "2026-01-12T10:00:00Z",
        "completed_at": None,
        "error_message": None,
        "metadata": {},
        "created_at": "2026-01-12T10:00:00Z",
    }


@pytest.fixture
def tracker():
    """Create a JobTrackingService with mocked client."""
    with patch("app.services.job_tracking.tracker.get_supabase_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        service = JobTrackingService()
        service._client = mock_client
        yield service


# =============================================================================
# Test ProcessingJob Model Conversion
# =============================================================================


class TestDBRowConversion:
    """Tests for database row to model conversion."""

    def test_converts_job_row_to_processing_job(
        self, tracker: JobTrackingService, sample_job_row: dict
    ) -> None:
        """Should convert database row to ProcessingJob model."""
        job = tracker._db_row_to_processing_job(sample_job_row)

        assert job.id == "job-123"
        assert job.matter_id == "matter-456"
        assert job.document_id == "doc-789"
        assert job.job_type == JobType.DOCUMENT_PROCESSING
        assert job.status == JobStatus.QUEUED
        assert job.celery_task_id == "celery-abc"
        assert job.current_stage is None
        assert job.total_stages == 7
        assert job.completed_stages == 0
        assert job.progress_pct == 0
        assert job.retry_count == 0
        assert job.max_retries == 3
        assert job.metadata == {}

    def test_converts_job_row_with_all_fields(
        self, tracker: JobTrackingService, sample_job_row: dict
    ) -> None:
        """Should handle job row with all optional fields populated."""
        sample_job_row.update({
            "current_stage": "chunking",
            "completed_stages": 3,
            "progress_pct": 42,
            "estimated_completion": "2026-01-12T11:00:00Z",
            "error_message": "Test error",
            "error_code": "TEST_ERROR",
            "started_at": "2026-01-12T10:05:00Z",
        })

        job = tracker._db_row_to_processing_job(sample_job_row)

        assert job.current_stage == "chunking"
        assert job.completed_stages == 3
        assert job.progress_pct == 42
        assert job.estimated_completion is not None
        assert job.error_message == "Test error"
        assert job.error_code == "TEST_ERROR"
        assert job.started_at is not None

    def test_handles_null_values_gracefully(
        self, tracker: JobTrackingService, sample_job_row: dict
    ) -> None:
        """Should handle null values with sensible defaults."""
        sample_job_row.update({
            "total_stages": None,
            "completed_stages": None,
            "progress_pct": None,
            "retry_count": None,
            "max_retries": None,
            "metadata": None,
        })

        job = tracker._db_row_to_processing_job(sample_job_row)

        assert job.total_stages == 7  # Default
        assert job.completed_stages == 0  # Default
        assert job.progress_pct == 0  # Default
        assert job.retry_count == 0  # Default
        assert job.max_retries == 3  # Default
        assert job.metadata == {}  # Default

    def test_converts_stage_row_to_stage_history(
        self, tracker: JobTrackingService, sample_stage_row: dict
    ) -> None:
        """Should convert database row to JobStageHistory model."""
        stage = tracker._db_row_to_stage_history(sample_stage_row)

        assert stage.id == "stage-123"
        assert stage.job_id == "job-123"
        assert stage.stage_name == "ocr"
        assert stage.status == StageStatus.IN_PROGRESS
        assert stage.started_at is not None
        assert stage.completed_at is None
        assert stage.error_message is None
        assert stage.metadata == {}


# =============================================================================
# Test Job Creation
# =============================================================================


class TestJobCreation:
    """Tests for job creation."""

    @pytest.mark.asyncio
    async def test_creates_job_with_required_fields(
        self,
        tracker: JobTrackingService,
        sample_job_row: dict,
        mock_supabase_response,
    ) -> None:
        """Should create job with required fields."""
        # Mock the insert operation
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = mock_supabase_response([sample_job_row])
        tracker._client.table.return_value = mock_table

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda f: f())):
            job = await tracker.create_job(
                matter_id="matter-456",
                job_type=JobType.DOCUMENT_PROCESSING,
            )

        assert job.id == "job-123"
        assert job.matter_id == "matter-456"
        assert job.job_type == JobType.DOCUMENT_PROCESSING
        assert job.status == JobStatus.QUEUED

    @pytest.mark.asyncio
    async def test_creates_job_with_optional_fields(
        self,
        tracker: JobTrackingService,
        sample_job_row: dict,
        mock_supabase_response,
    ) -> None:
        """Should create job with all optional fields."""
        sample_job_row["celery_task_id"] = "celery-xyz"
        sample_job_row["max_retries"] = 5
        sample_job_row["metadata"] = {"custom": "data"}

        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = mock_supabase_response([sample_job_row])
        tracker._client.table.return_value = mock_table

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda f: f())):
            job = await tracker.create_job(
                matter_id="matter-456",
                job_type=JobType.DOCUMENT_PROCESSING,
                document_id="doc-789",
                celery_task_id="celery-xyz",
                max_retries=5,
                metadata={"custom": "data"},
            )

        assert job.celery_task_id == "celery-xyz"
        assert job.max_retries == 5

    @pytest.mark.asyncio
    async def test_raises_error_when_creation_fails(
        self,
        tracker: JobTrackingService,
        mock_supabase_response,
    ) -> None:
        """Should raise JobTrackingError when creation fails."""
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = mock_supabase_response([])
        tracker._client.table.return_value = mock_table

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda f: f())):
            with pytest.raises(JobTrackingError) as exc_info:
                await tracker.create_job(
                    matter_id="matter-456",
                    job_type=JobType.DOCUMENT_PROCESSING,
                )

        assert "Failed to create job" in str(exc_info.value)


# =============================================================================
# Test Job Retrieval
# =============================================================================


class TestJobRetrieval:
    """Tests for job retrieval operations."""

    @pytest.mark.asyncio
    async def test_gets_job_by_id(
        self,
        tracker: JobTrackingService,
        sample_job_row: dict,
        mock_supabase_response,
    ) -> None:
        """Should retrieve job by ID."""
        mock_table = MagicMock()
        mock_query = MagicMock()
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value.execute.return_value = mock_supabase_response([sample_job_row])
        mock_table.select.return_value = mock_query
        tracker._client.table.return_value = mock_table

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda f: f())):
            job = await tracker.get_job("job-123")

        assert job is not None
        assert job.id == "job-123"

    @pytest.mark.asyncio
    async def test_returns_none_when_job_not_found(
        self,
        tracker: JobTrackingService,
        mock_supabase_response,
    ) -> None:
        """Should return None when job not found."""
        mock_table = MagicMock()
        mock_query = MagicMock()
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value.execute.return_value = mock_supabase_response([])
        mock_table.select.return_value = mock_query
        tracker._client.table.return_value = mock_table

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda f: f())):
            job = await tracker.get_job("nonexistent-job")

        assert job is None

    @pytest.mark.asyncio
    async def test_gets_job_with_matter_validation(
        self,
        tracker: JobTrackingService,
        sample_job_row: dict,
        mock_supabase_response,
    ) -> None:
        """Should validate matter_id when provided."""
        mock_table = MagicMock()
        mock_query = MagicMock()
        mock_query.eq.return_value = mock_query
        mock_query.limit.return_value.execute.return_value = mock_supabase_response([sample_job_row])
        mock_table.select.return_value = mock_query
        tracker._client.table.return_value = mock_table

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda f: f())):
            job = await tracker.get_job("job-123", matter_id="matter-456")

        assert job is not None
        # Verify that eq was called twice (for job_id and matter_id)
        assert mock_query.eq.call_count == 2


# =============================================================================
# Test Job Status Updates
# =============================================================================


class TestJobStatusUpdates:
    """Tests for job status updates."""

    @pytest.mark.asyncio
    async def test_updates_job_status(
        self,
        tracker: JobTrackingService,
        sample_job_row: dict,
        mock_supabase_response,
    ) -> None:
        """Should update job status."""
        sample_job_row["status"] = "PROCESSING"
        sample_job_row["current_stage"] = "ocr"
        sample_job_row["progress_pct"] = 15

        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_update.eq.return_value = mock_update
        mock_update.execute.return_value = mock_supabase_response([sample_job_row])
        mock_table.update.return_value = mock_update
        tracker._client.table.return_value = mock_table

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda f: f())):
            job = await tracker.update_job_status(
                job_id="job-123",
                status=JobStatus.PROCESSING,
                stage="ocr",
                progress_pct=15,
            )

        assert job is not None
        assert job.status == JobStatus.PROCESSING
        assert job.current_stage == "ocr"
        assert job.progress_pct == 15

    @pytest.mark.asyncio
    async def test_updates_job_status_with_error(
        self,
        tracker: JobTrackingService,
        sample_job_row: dict,
        mock_supabase_response,
    ) -> None:
        """Should update job with error details."""
        sample_job_row["status"] = "FAILED"
        sample_job_row["error_message"] = "Processing failed"
        sample_job_row["error_code"] = "PROCESSING_ERROR"

        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_update.eq.return_value = mock_update
        mock_update.execute.return_value = mock_supabase_response([sample_job_row])
        mock_table.update.return_value = mock_update
        tracker._client.table.return_value = mock_table

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda f: f())):
            job = await tracker.update_job_status(
                job_id="job-123",
                status=JobStatus.FAILED,
                error_message="Processing failed",
                error_code="PROCESSING_ERROR",
            )

        assert job is not None
        assert job.status == JobStatus.FAILED
        assert job.error_message == "Processing failed"
        assert job.error_code == "PROCESSING_ERROR"


# =============================================================================
# Test Stage History
# =============================================================================


class TestStageHistory:
    """Tests for stage history operations."""

    @pytest.mark.asyncio
    async def test_records_stage_start(
        self,
        tracker: JobTrackingService,
        sample_stage_row: dict,
        mock_supabase_response,
    ) -> None:
        """Should record stage start."""
        mock_table = MagicMock()
        mock_table.insert.return_value.execute.return_value = mock_supabase_response([sample_stage_row])
        tracker._client.table.return_value = mock_table

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda f: f())):
            stage = await tracker.record_stage_start("job-123", "ocr")

        assert stage is not None
        assert stage.job_id == "job-123"
        assert stage.stage_name == "ocr"
        assert stage.status == StageStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_records_stage_complete(
        self,
        tracker: JobTrackingService,
        sample_stage_row: dict,
        mock_supabase_response,
    ) -> None:
        """Should record stage completion."""
        # First query returns in-progress stage
        sample_stage_row["status"] = "IN_PROGRESS"

        # Updated stage after completion
        completed_stage = {**sample_stage_row}
        completed_stage["status"] = "COMPLETED"
        completed_stage["completed_at"] = "2026-01-12T10:05:00Z"

        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.order.return_value = mock_select
        mock_select.limit.return_value.execute.return_value = mock_supabase_response([sample_stage_row])
        mock_table.select.return_value = mock_select

        mock_update = MagicMock()
        mock_update.eq.return_value = mock_update
        mock_update.execute.return_value = mock_supabase_response([completed_stage])
        mock_table.update.return_value = mock_update

        tracker._client.table.return_value = mock_table

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda f: f())):
            stage = await tracker.record_stage_complete("job-123", "ocr")

        assert stage is not None
        assert stage.status == StageStatus.COMPLETED
        assert stage.completed_at is not None

    @pytest.mark.asyncio
    async def test_records_stage_failure(
        self,
        tracker: JobTrackingService,
        sample_stage_row: dict,
        mock_supabase_response,
    ) -> None:
        """Should record stage failure with error message."""
        # First query returns in-progress stage
        sample_stage_row["status"] = "IN_PROGRESS"

        # Updated stage after failure
        failed_stage = {**sample_stage_row}
        failed_stage["status"] = "FAILED"
        failed_stage["error_message"] = "OCR processing failed"
        failed_stage["completed_at"] = "2026-01-12T10:05:00Z"

        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.order.return_value = mock_select
        mock_select.limit.return_value.execute.return_value = mock_supabase_response([sample_stage_row])
        mock_table.select.return_value = mock_select

        mock_update = MagicMock()
        mock_update.eq.return_value = mock_update
        mock_update.execute.return_value = mock_supabase_response([failed_stage])
        mock_table.update.return_value = mock_update

        tracker._client.table.return_value = mock_table

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda f: f())):
            stage = await tracker.record_stage_failure(
                "job-123", "ocr", "OCR processing failed"
            )

        assert stage is not None
        assert stage.status == StageStatus.FAILED
        assert stage.error_message == "OCR processing failed"

    @pytest.mark.asyncio
    async def test_gets_stage_history(
        self,
        tracker: JobTrackingService,
        sample_stage_row: dict,
        mock_supabase_response,
    ) -> None:
        """Should retrieve all stage history for a job."""
        stages = [
            {**sample_stage_row, "stage_name": "ocr", "status": "COMPLETED"},
            {**sample_stage_row, "id": "stage-124", "stage_name": "validation", "status": "COMPLETED"},
            {**sample_stage_row, "id": "stage-125", "stage_name": "chunking", "status": "IN_PROGRESS"},
        ]

        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.order.return_value.execute.return_value = mock_supabase_response(stages)
        mock_table.select.return_value = mock_select
        tracker._client.table.return_value = mock_table

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda f: f())):
            history = await tracker.get_stage_history("job-123")

        assert len(history) == 3
        assert history[0].stage_name == "ocr"
        assert history[1].stage_name == "validation"
        assert history[2].stage_name == "chunking"


# =============================================================================
# Test Retry and Cancel Operations
# =============================================================================


class TestRetryAndCancel:
    """Tests for retry and cancel operations."""

    @pytest.mark.asyncio
    async def test_retries_failed_job(
        self,
        tracker: JobTrackingService,
        sample_job_row: dict,
        mock_supabase_response,
    ) -> None:
        """Should retry a failed job."""
        # Initial job is FAILED
        sample_job_row["status"] = "FAILED"
        sample_job_row["retry_count"] = 1

        # Updated job after retry
        retried_job = {**sample_job_row}
        retried_job["status"] = "QUEUED"
        retried_job["retry_count"] = 2

        mock_table = MagicMock()

        # Mock get_job
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.limit.return_value.execute.return_value = mock_supabase_response([sample_job_row])
        mock_table.select.return_value = mock_select

        # Mock update
        mock_update = MagicMock()
        mock_update.eq.return_value = mock_update
        mock_update.execute.return_value = mock_supabase_response([retried_job])
        mock_table.update.return_value = mock_update

        tracker._client.table.return_value = mock_table

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda f: f())):
            job = await tracker.retry_job("job-123", "matter-456")

        assert job is not None
        assert job.status == JobStatus.QUEUED
        assert job.retry_count == 2

    @pytest.mark.asyncio
    async def test_cannot_retry_non_failed_job(
        self,
        tracker: JobTrackingService,
        sample_job_row: dict,
        mock_supabase_response,
    ) -> None:
        """Should not retry a non-failed job."""
        # Job is PROCESSING, not FAILED
        sample_job_row["status"] = "PROCESSING"

        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.limit.return_value.execute.return_value = mock_supabase_response([sample_job_row])
        mock_table.select.return_value = mock_select
        tracker._client.table.return_value = mock_table

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda f: f())):
            job = await tracker.retry_job("job-123", "matter-456")

        assert job is None

    @pytest.mark.asyncio
    async def test_cancels_queued_job(
        self,
        tracker: JobTrackingService,
        sample_job_row: dict,
        mock_supabase_response,
    ) -> None:
        """Should cancel a queued job."""
        # Initial job is QUEUED
        sample_job_row["status"] = "QUEUED"

        # Updated job after cancel
        cancelled_job = {**sample_job_row}
        cancelled_job["status"] = "CANCELLED"

        mock_table = MagicMock()

        # Mock get_job
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.limit.return_value.execute.return_value = mock_supabase_response([sample_job_row])
        mock_table.select.return_value = mock_select

        # Mock update
        mock_update = MagicMock()
        mock_update.eq.return_value = mock_update
        mock_update.execute.return_value = mock_supabase_response([cancelled_job])
        mock_table.update.return_value = mock_update

        tracker._client.table.return_value = mock_table

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda f: f())):
            job = await tracker.cancel_job("job-123", "matter-456")

        assert job is not None
        assert job.status == JobStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cannot_cancel_completed_job(
        self,
        tracker: JobTrackingService,
        sample_job_row: dict,
        mock_supabase_response,
    ) -> None:
        """Should not cancel a completed job."""
        # Job is COMPLETED
        sample_job_row["status"] = "COMPLETED"

        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.limit.return_value.execute.return_value = mock_supabase_response([sample_job_row])
        mock_table.select.return_value = mock_select
        tracker._client.table.return_value = mock_table

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda f: f())):
            job = await tracker.cancel_job("job-123", "matter-456")

        assert job is None

    @pytest.mark.asyncio
    async def test_skips_failed_job(
        self,
        tracker: JobTrackingService,
        sample_job_row: dict,
        mock_supabase_response,
    ) -> None:
        """Should skip a failed job."""
        # Initial job is FAILED
        sample_job_row["status"] = "FAILED"

        # Updated job after skip
        skipped_job = {**sample_job_row}
        skipped_job["status"] = "SKIPPED"

        mock_table = MagicMock()

        # Mock get_job
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_select
        mock_select.limit.return_value.execute.return_value = mock_supabase_response([sample_job_row])
        mock_table.select.return_value = mock_select

        # Mock update
        mock_update = MagicMock()
        mock_update.eq.return_value = mock_update
        mock_update.execute.return_value = mock_supabase_response([skipped_job])
        mock_table.update.return_value = mock_update

        tracker._client.table.return_value = mock_table

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda f: f())):
            job = await tracker.skip_job("job-123", "matter-456")

        assert job is not None
        assert job.status == JobStatus.SKIPPED


# =============================================================================
# Test Queue Statistics
# =============================================================================


class TestQueueStats:
    """Tests for queue statistics."""

    @pytest.mark.asyncio
    async def test_gets_queue_stats_from_rpc(
        self,
        tracker: JobTrackingService,
        mock_supabase_response,
    ) -> None:
        """Should get queue stats from database function."""
        stats_row = {
            "queued": 5,
            "processing": 2,
            "completed": 100,
            "failed": 3,
            "cancelled": 1,
            "skipped": 2,
            "avg_processing_time_ms": 125000,
        }

        mock_rpc = MagicMock()
        mock_rpc.execute.return_value = mock_supabase_response([stats_row])
        tracker._client.rpc.return_value = mock_rpc

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=lambda f: f())):
            stats = await tracker.get_queue_stats("matter-456")

        assert stats.queued == 5
        assert stats.processing == 2
        assert stats.completed == 100
        assert stats.failed == 3
        assert stats.cancelled == 1
        assert stats.skipped == 2
        assert stats.avg_processing_time_ms == 125000


# =============================================================================
# Test Singleton Pattern
# =============================================================================


class TestServiceFactory:
    """Tests for service factory function."""

    def test_returns_singleton_instance(self) -> None:
        """Should return the same instance on multiple calls."""
        # Clear the cache first
        get_job_tracking_service.cache_clear()

        with patch("app.services.job_tracking.tracker.get_supabase_client") as mock_get_client:
            mock_get_client.return_value = MagicMock()

            service1 = get_job_tracking_service()
            service2 = get_job_tracking_service()

            assert service1 is service2

        # Clear cache after test
        get_job_tracking_service.cache_clear()


# =============================================================================
# Test Error Handling
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_job_tracking_error_has_code(self) -> None:
        """JobTrackingError should have error code."""
        error = JobTrackingError("Test error", code="TEST_CODE")
        assert error.code == "TEST_CODE"
        assert error.message == "Test error"

    def test_job_not_found_error(self) -> None:
        """JobNotFoundError should have correct code."""
        error = JobNotFoundError("Job not found")
        assert error.code == "JOB_NOT_FOUND"
        assert "Job not found" in error.message
