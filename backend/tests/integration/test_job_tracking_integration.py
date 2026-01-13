"""Integration tests for Job Tracking pipeline.

Story 2c-3: Background Job Status Tracking and Retry

Tests the complete job lifecycle from creation through processing stages,
including failure and retry scenarios with partial progress preservation.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.job import (
    JobQueueStats,
    JobStageHistory,
    JobStatus,
    JobType,
    ProcessingJob,
    ProcessingJobCreate,
    ProcessingJobUpdate,
    StageStatus,
)
from app.services.job_tracking import (
    JobTrackingService,
    PartialProgressTracker,
    StageProgress,
    TimeEstimator,
    create_progress_tracker,
)


class TestJobLifecycleIntegration:
    """Integration tests for complete job lifecycle."""

    @pytest.fixture
    def mock_supabase_client(self):
        """Create a mock Supabase client with in-memory storage."""
        client = MagicMock()

        # In-memory storage for jobs and stages
        jobs_storage: dict[str, dict] = {}
        stages_storage: list[dict] = []

        def mock_table(name: str):
            table = MagicMock()

            if name == "processing_jobs":
                # Insert
                def mock_insert(data):
                    result = MagicMock()
                    job_id = str(uuid4())
                    job_data = {
                        "id": job_id,
                        **data,
                        "status": data.get("status", "QUEUED"),
                        "created_at": datetime.utcnow().isoformat(),
                        "updated_at": datetime.utcnow().isoformat(),
                    }
                    jobs_storage[job_id] = job_data
                    result.execute.return_value = MagicMock(data=[job_data])
                    return result

                # Select
                def mock_select(*args):
                    query = MagicMock()
                    query._filters = {}

                    def mock_eq(field, value):
                        query._filters[field] = value
                        return query

                    def mock_limit(n):
                        return query

                    def mock_order(*args, **kwargs):
                        return query

                    def mock_execute():
                        result = MagicMock()
                        # Filter jobs
                        matching = []
                        for job in jobs_storage.values():
                            match = True
                            for field, value in query._filters.items():
                                if job.get(field) != value:
                                    match = False
                                    break
                            if match:
                                matching.append(job)
                        result.data = matching
                        return result

                    query.eq = mock_eq
                    query.limit = mock_limit
                    query.order = mock_order
                    query.execute = mock_execute
                    return query

                # Update
                def mock_update(data):
                    result = MagicMock()

                    def mock_eq(field, value):
                        if field == "id" and value in jobs_storage:
                            jobs_storage[value].update(data)
                            jobs_storage[value]["updated_at"] = datetime.utcnow().isoformat()
                            result.execute.return_value = MagicMock(data=[jobs_storage[value]])
                        else:
                            result.execute.return_value = MagicMock(data=[])
                        return result

                    result.eq = mock_eq
                    return result

                table.insert = mock_insert
                table.select = mock_select
                table.update = mock_update

            elif name == "job_stage_history":
                def mock_insert(data):
                    result = MagicMock()
                    stage_id = str(uuid4())
                    stage_data = {
                        "id": stage_id,
                        **data,
                        "created_at": datetime.utcnow().isoformat(),
                    }
                    stages_storage.append(stage_data)
                    result.execute.return_value = MagicMock(data=[stage_data])
                    return result

                def mock_select(*args):
                    query = MagicMock()
                    query._job_id = None

                    def mock_eq(field, value):
                        if field == "job_id":
                            query._job_id = value
                        return query

                    def mock_order(*args, **kwargs):
                        result = MagicMock()
                        matching = [s for s in stages_storage if s.get("job_id") == query._job_id]
                        result.execute.return_value = MagicMock(data=matching)
                        return result

                    def mock_limit(n):
                        result = MagicMock()
                        matching = [s for s in stages_storage if s.get("job_id") == query._job_id]
                        result.execute.return_value = MagicMock(data=matching[-1:] if matching else [])
                        return result

                    query.eq = mock_eq
                    query.order = mock_order
                    query.limit = mock_limit
                    return query

                def mock_update(data):
                    result = MagicMock()

                    def mock_eq(field, value):
                        for stage in stages_storage:
                            if stage.get(field) == value:
                                stage.update(data)
                                result.execute.return_value = MagicMock(data=[stage])
                                return result
                        result.execute.return_value = MagicMock(data=[])
                        return result

                    result.eq = mock_eq
                    return result

                table.insert = mock_insert
                table.select = mock_select
                table.update = mock_update

            return table

        client.table = mock_table
        client._jobs = jobs_storage
        client._stages = stages_storage

        return client

    @pytest.fixture
    def job_tracker(self, mock_supabase_client):
        """Create a JobTrackingService with mocked client."""
        with patch("app.services.job_tracking.tracker.get_supabase_client") as mock_get:
            mock_get.return_value = mock_supabase_client
            tracker = JobTrackingService()
            tracker._client = mock_supabase_client
            yield tracker

    @pytest.mark.asyncio
    async def test_full_job_lifecycle_success(self, job_tracker, mock_supabase_client):
        """Test complete job lifecycle: create -> process stages -> complete."""
        matter_id = str(uuid4())
        document_id = str(uuid4())

        # Step 1: Create job
        job = await job_tracker.create_job(
            matter_id=matter_id,
            document_id=document_id,
            job_type=JobType.DOCUMENT_PROCESSING,
        )

        assert job is not None
        assert job.status == JobStatus.QUEUED
        assert job.matter_id == matter_id
        assert job.document_id == document_id

        job_id = job.id

        # Step 2: Start OCR stage
        await job_tracker.record_stage_start(job_id, "ocr")
        await job_tracker.update_job_status(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            stage="ocr",
            progress_pct=0,
        )

        job = await job_tracker.get_job(job_id)
        assert job.status == JobStatus.PROCESSING
        assert job.current_stage == "ocr"

        # Step 3: Complete OCR stage
        await job_tracker.record_stage_complete(job_id, "ocr", {"page_count": 10})

        # Step 4: Process remaining stages
        stages = ["validation", "confidence", "chunking", "embedding", "entity_extraction", "alias_resolution"]

        for i, stage in enumerate(stages):
            await job_tracker.record_stage_start(job_id, stage)
            progress = int(((i + 2) / 7) * 100)  # +2 because OCR is done
            await job_tracker.update_job_status(
                job_id=job_id,
                status=JobStatus.PROCESSING,
                stage=stage,
                progress_pct=progress,
            )
            await job_tracker.record_stage_complete(job_id, stage)

        # Step 5: Mark job completed
        await job_tracker.update_job_status(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            progress_pct=100,
        )

        # Verify final state
        job = await job_tracker.get_job(job_id)
        assert job.status == JobStatus.COMPLETED
        assert job.progress_pct == 100

        # Verify stage history
        stages = await job_tracker.get_stage_history(job_id)
        assert len(stages) == 7  # All 7 stages

    @pytest.mark.asyncio
    async def test_job_failure_and_retry_flow(self, job_tracker, mock_supabase_client):
        """Test job failure, status update, and manual retry."""
        matter_id = str(uuid4())
        document_id = str(uuid4())

        # Create and start processing
        job = await job_tracker.create_job(
            matter_id=matter_id,
            document_id=document_id,
            job_type=JobType.DOCUMENT_PROCESSING,
        )
        job_id = job.id

        # Start OCR
        await job_tracker.record_stage_start(job_id, "ocr")
        await job_tracker.update_job_status(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            stage="ocr",
        )

        # Simulate failure
        await job_tracker.record_stage_failure(job_id, "ocr", "OCR API timeout")
        await job_tracker.increment_retry_count(job_id)

        # Check retry count
        job = await job_tracker.get_job(job_id)
        assert job.retry_count == 1

        # Simulate max retries exceeded -> mark as FAILED
        await job_tracker.update_job_status(
            job_id=job_id,
            status=JobStatus.FAILED,
            error_message="Max retries exceeded",
            error_code="MAX_RETRIES_EXCEEDED",
        )

        job = await job_tracker.get_job(job_id)
        assert job.status == JobStatus.FAILED
        assert job.error_message == "Max retries exceeded"

        # Manual retry
        retried_job = await job_tracker.retry_job(job_id, matter_id)
        assert retried_job is not None
        assert retried_job.status == JobStatus.QUEUED
        assert retried_job.retry_count == 2  # Incremented

    @pytest.mark.asyncio
    async def test_job_cancel_flow(self, job_tracker, mock_supabase_client):
        """Test cancelling a queued or processing job."""
        matter_id = str(uuid4())
        document_id = str(uuid4())

        # Create job
        job = await job_tracker.create_job(
            matter_id=matter_id,
            document_id=document_id,
            job_type=JobType.DOCUMENT_PROCESSING,
        )
        job_id = job.id

        # Cancel while QUEUED
        cancelled_job = await job_tracker.cancel_job(job_id, matter_id)
        assert cancelled_job is not None
        assert cancelled_job.status == JobStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_job_skip_flow(self, job_tracker, mock_supabase_client):
        """Test skipping a failed job."""
        matter_id = str(uuid4())
        document_id = str(uuid4())

        # Create and fail job
        job = await job_tracker.create_job(
            matter_id=matter_id,
            document_id=document_id,
            job_type=JobType.DOCUMENT_PROCESSING,
        )
        job_id = job.id

        await job_tracker.update_job_status(
            job_id=job_id,
            status=JobStatus.FAILED,
            error_message="Processing failed",
        )

        # Skip the failed job
        skipped_job = await job_tracker.skip_job(job_id, matter_id)
        assert skipped_job is not None
        assert skipped_job.status == JobStatus.SKIPPED


class TestPartialProgressIntegration:
    """Integration tests for partial progress preservation."""

    @pytest.fixture
    def mock_job_with_metadata(self):
        """Create a mock job with partial progress metadata."""
        return MagicMock(
            id="job-123",
            matter_id="matter-456",
            metadata={
                "partial_progress": {
                    "embedding": {
                        "stage_name": "embedding",
                        "total_items": 100,
                        "processed_items": [f"chunk-{i}" for i in range(50)],
                        "failed_items": {"chunk-99": "API error"},
                        "last_item_id": "chunk-49",
                        "started_at": "2026-01-12T10:00:00",
                    }
                }
            }
        )

    def test_resume_from_partial_progress(self, mock_job_with_metadata):
        """Test resuming processing from saved partial progress."""
        with patch("app.services.job_tracking.partial_progress.get_job_tracking_service") as mock_get:
            mock_tracker = MagicMock()
            mock_tracker.get_job = AsyncMock(return_value=mock_job_with_metadata)
            mock_get.return_value = mock_tracker

            with patch("asyncio.new_event_loop") as mock_loop:
                mock_event_loop = MagicMock()
                mock_event_loop.run_until_complete.return_value = mock_job_with_metadata
                mock_loop.return_value = mock_event_loop

                # Create tracker and load progress
                tracker = PartialProgressTracker(
                    job_id="job-123",
                    matter_id="matter-456",
                    job_tracker=mock_tracker,
                )

                progress = tracker.get_or_create_stage("embedding")

                # Verify progress was loaded
                assert len(progress.processed_items) == 50
                assert progress.total_items == 100
                assert "chunk-0" in progress.processed_items
                assert "chunk-49" in progress.processed_items
                assert progress.progress_pct == 50

    def test_partial_progress_skip_processed_items(self):
        """Test that processed items are correctly skipped on retry."""
        progress = StageProgress(stage_name="embedding")
        progress.total_items = 100

        # Mark first 50 as processed
        for i in range(50):
            progress.mark_processed(f"chunk-{i}")

        # Simulate retry with all 100 chunks
        all_chunks = [f"chunk-{i}" for i in range(100)]
        remaining = progress.get_remaining_items(all_chunks)

        # Should only have chunks 50-99
        assert len(remaining) == 50
        assert "chunk-0" not in remaining
        assert "chunk-49" not in remaining
        assert "chunk-50" in remaining
        assert "chunk-99" in remaining


class TestTimeEstimatorIntegration:
    """Integration tests for time estimation."""

    def test_estimates_realistic_document_time(self):
        """Test time estimation for a realistic document."""
        estimator = TimeEstimator()

        # 50-page document
        estimate = estimator.estimate_total_document_time(page_count=50)

        # Should be reasonable (between 1 minute and 10 minutes)
        assert estimate > timedelta(minutes=1)
        assert estimate < timedelta(minutes=10)

    def test_remaining_time_decreases_through_stages(self):
        """Test that remaining time decreases as stages complete."""
        estimator = TimeEstimator()

        stages = ["ocr", "validation", "chunking", "embedding", "entity_extraction"]
        remaining_times = []

        for stage in stages:
            remaining = estimator.estimate_remaining_time(
                current_stage=stage,
                page_count=50,
            )
            remaining_times.append(remaining)

        # Each stage should have less remaining time than previous
        for i in range(1, len(remaining_times)):
            assert remaining_times[i] < remaining_times[i - 1]

    def test_progress_percentage_increases_through_stages(self):
        """Test that progress percentage increases through stages."""
        estimator = TimeEstimator()

        stages = ["ocr", "validation", "chunking", "embedding", "entity_extraction", "alias_resolution"]
        progress_values = []

        for stage in stages:
            progress = estimator.estimate_stage_progress(stage, 0.5)  # 50% through each stage
            progress_values.append(progress)

        # Progress should generally increase (allowing for mid-stage dips)
        assert progress_values[-1] > progress_values[0]

        # Final stage should be near completion
        assert progress_values[-1] > 90


class TestMatterIsolationIntegration:
    """Integration tests for matter isolation in job tracking."""

    @pytest.fixture
    def mock_client_with_matters(self):
        """Create mock client with jobs from multiple matters."""
        client = MagicMock()

        matter1_id = str(uuid4())
        matter2_id = str(uuid4())

        jobs = [
            {
                "id": str(uuid4()),
                "matter_id": matter1_id,
                "document_id": str(uuid4()),
                "job_type": "DOCUMENT_PROCESSING",
                "status": "COMPLETED",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            },
            {
                "id": str(uuid4()),
                "matter_id": matter1_id,
                "document_id": str(uuid4()),
                "job_type": "DOCUMENT_PROCESSING",
                "status": "PROCESSING",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            },
            {
                "id": str(uuid4()),
                "matter_id": matter2_id,
                "document_id": str(uuid4()),
                "job_type": "DOCUMENT_PROCESSING",
                "status": "QUEUED",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            },
        ]

        def mock_table(name):
            table = MagicMock()

            def mock_select(*args):
                query = MagicMock()
                query._matter_id = None

                def mock_eq(field, value):
                    if field == "matter_id":
                        query._matter_id = value
                    return query

                def mock_order(*args, **kwargs):
                    return query

                def mock_limit(n):
                    return query

                def mock_execute():
                    result = MagicMock()
                    if query._matter_id:
                        result.data = [j for j in jobs if j["matter_id"] == query._matter_id]
                    else:
                        result.data = jobs
                    return result

                query.eq = mock_eq
                query.order = mock_order
                query.limit = mock_limit
                query.execute = mock_execute
                return query

            table.select = mock_select
            return table

        client.table = mock_table
        client._matter1_id = matter1_id
        client._matter2_id = matter2_id

        return client

    @pytest.mark.asyncio
    async def test_list_jobs_isolated_by_matter(self, mock_client_with_matters):
        """Test that job listing is isolated by matter_id."""
        with patch("app.services.job_tracking.tracker.get_supabase_client") as mock_get:
            mock_get.return_value = mock_client_with_matters

            tracker = JobTrackingService()
            tracker._client = mock_client_with_matters

            # List jobs for matter 1
            jobs = await tracker.list_jobs_for_matter(
                matter_id=mock_client_with_matters._matter1_id
            )

            # Should only see matter 1's jobs
            assert len(jobs) == 2
            for job in jobs:
                assert job.matter_id == mock_client_with_matters._matter1_id

    @pytest.mark.asyncio
    async def test_get_job_validates_matter_id(self, mock_client_with_matters):
        """Test that get_job with matter_id validation works."""
        with patch("app.services.job_tracking.tracker.get_supabase_client") as mock_get:
            mock_get.return_value = mock_client_with_matters

            tracker = JobTrackingService()
            tracker._client = mock_client_with_matters

            # Try to get a job with wrong matter_id
            # The mock will return empty when matter_id filter doesn't match
            job = await tracker.get_job(
                job_id="some-job-id",
                matter_id="wrong-matter-id"
            )

            # Should return None (no match)
            assert job is None


class TestQueueStatsIntegration:
    """Integration tests for queue statistics."""

    def test_stats_count_all_statuses(self):
        """Test that queue stats counts all job statuses correctly."""
        stats = JobQueueStats(
            queued=5,
            processing=2,
            completed=100,
            failed=3,
            cancelled=1,
            skipped=2,
            avg_processing_time_ms=125000,
        )

        assert stats.queued == 5
        assert stats.processing == 2
        assert stats.completed == 100
        assert stats.failed == 3
        assert stats.cancelled == 1
        assert stats.skipped == 2

        # Total should be sum of all
        total = (
            stats.queued + stats.processing + stats.completed +
            stats.failed + stats.cancelled + stats.skipped
        )
        assert total == 113
