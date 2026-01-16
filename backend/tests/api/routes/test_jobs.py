"""Unit tests for job API routes.

Story 2c-3: Background Job Status Tracking and Retry
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.main import app
from app.models.job import (
    JobStageHistory,
    JobStatus,
    JobType,
    ProcessingJob,
    StageStatus,
)
from app.services.job_tracking import (
    JobNotFoundError,
)

# Test JWT secret
TEST_JWT_SECRET = "test-secret-key-for-testing-only-do-not-use-in-production"


def get_test_settings() -> Settings:
    """Create test settings with JWT secret configured."""
    settings = MagicMock(spec=Settings)
    settings.supabase_jwt_secret = TEST_JWT_SECRET
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_anon_key = "test-anon-key"
    settings.is_configured = True
    settings.debug = True
    return settings


def create_test_token(
    user_id: str = "test-user-id",
    email: str = "test@example.com",
) -> str:
    """Create a valid JWT token for testing."""
    payload = {
        "sub": user_id,
        "email": email,
        "role": "authenticated",
        "aud": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iat": datetime.now(UTC),
        "session_id": "test-session",
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def create_mock_job(
    job_id: str | None = None,
    matter_id: str | None = None,
    document_id: str | None = None,
    status: JobStatus = JobStatus.PROCESSING,
    job_type: JobType = JobType.DOCUMENT_PROCESSING,
    current_stage: str = "ocr",
    progress_pct: int = 25,
) -> ProcessingJob:
    """Create a mock ProcessingJob for testing."""
    now = datetime.now(UTC)
    return ProcessingJob(
        id=job_id or str(uuid4()),
        matter_id=matter_id or str(uuid4()),
        document_id=document_id or str(uuid4()),
        job_type=job_type,
        status=status,
        celery_task_id=str(uuid4()),
        current_stage=current_stage,
        total_stages=7,
        completed_stages=1,
        progress_pct=progress_pct,
        estimated_completion=now + timedelta(minutes=5),
        error_message=None,
        error_code=None,
        retry_count=0,
        max_retries=3,
        metadata={},
        started_at=now,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )


def create_mock_stage_history(
    job_id: str,
    stage_name: str = "ocr",
    status: StageStatus = StageStatus.COMPLETED,
) -> JobStageHistory:
    """Create a mock JobStageHistory for testing."""
    now = datetime.now(UTC)
    return JobStageHistory(
        id=str(uuid4()),
        job_id=job_id,
        stage_name=stage_name,
        status=status,
        started_at=now - timedelta(seconds=30),
        completed_at=now if status == StageStatus.COMPLETED else None,
        error_message=None,
        metadata={},
        created_at=now,
    )


class TestGetJobEndpoint:
    """Tests for GET /api/jobs/{job_id} endpoint."""

    @pytest.mark.anyio
    async def test_returns_job_details_on_success(self) -> None:
        """Should return job details when authorized."""
        job_id = str(uuid4())
        matter_id = str(uuid4())
        mock_job = create_mock_job(job_id=job_id, matter_id=matter_id)
        mock_stages = [
            create_mock_stage_history(job_id, "ocr", StageStatus.COMPLETED),
        ]

        mock_tracker = AsyncMock()
        mock_tracker.get_job = AsyncMock(return_value=mock_job)
        mock_tracker.get_stage_history = AsyncMock(return_value=mock_stages)

        app.dependency_overrides[get_settings] = get_test_settings

        try:
            with patch(
                "app.api.routes.jobs.get_job_tracking_service",
                return_value=mock_tracker,
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    response = await client.get(
                        f"/api/jobs/{job_id}",
                        headers={"Authorization": f"Bearer {create_test_token()}"},
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["job"]["id"] == job_id
                assert data["job"]["status"] == "PROCESSING"
                assert len(data["stages"]) == 1
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_returns_404_when_job_not_found(self) -> None:
        """Should return 404 when job doesn't exist."""
        job_id = str(uuid4())

        mock_tracker = AsyncMock()
        mock_tracker.get_job = AsyncMock(side_effect=JobNotFoundError("Job not found"))

        app.dependency_overrides[get_settings] = get_test_settings

        try:
            with patch(
                "app.api.routes.jobs.get_job_tracking_service",
                return_value=mock_tracker,
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    response = await client.get(
                        f"/api/jobs/{job_id}",
                        headers={"Authorization": f"Bearer {create_test_token()}"},
                    )

                assert response.status_code == 404
                data = response.json()
                assert data["detail"]["error"]["code"] == "JOB_NOT_FOUND"
        finally:
            app.dependency_overrides.clear()


class TestRetryJobEndpoint:
    """Tests for POST /api/jobs/{job_id}/retry endpoint."""

    @pytest.mark.anyio
    async def test_retries_failed_job_successfully(self) -> None:
        """Should retry a failed job and return success."""
        job_id = str(uuid4())
        matter_id = str(uuid4())
        mock_job = create_mock_job(
            job_id=job_id, matter_id=matter_id, status=JobStatus.FAILED
        )

        mock_tracker = AsyncMock()
        mock_tracker.get_job = AsyncMock(return_value=mock_job)
        mock_tracker.reset_retry_count = AsyncMock()
        mock_tracker.update_job_status = AsyncMock()

        app.dependency_overrides[get_settings] = get_test_settings

        try:
            with (
                patch(
                    "app.api.routes.jobs.get_job_tracking_service",
                    return_value=mock_tracker,
                ),
                patch("app.api.routes.jobs.process_document") as mock_process,
            ):
                mock_process.delay = MagicMock()

                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    response = await client.post(
                        f"/api/jobs/{job_id}/retry",
                        headers={"Authorization": f"Bearer {create_test_token()}"},
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["new_status"] == "QUEUED"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_rejects_retry_for_non_failed_job(self) -> None:
        """Should reject retry for a job that isn't failed."""
        job_id = str(uuid4())
        matter_id = str(uuid4())
        mock_job = create_mock_job(
            job_id=job_id, matter_id=matter_id, status=JobStatus.PROCESSING
        )

        mock_tracker = AsyncMock()
        mock_tracker.get_job = AsyncMock(return_value=mock_job)

        app.dependency_overrides[get_settings] = get_test_settings

        try:
            with patch(
                "app.api.routes.jobs.get_job_tracking_service",
                return_value=mock_tracker,
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    response = await client.post(
                        f"/api/jobs/{job_id}/retry",
                        headers={"Authorization": f"Bearer {create_test_token()}"},
                    )

                assert response.status_code == 400
                data = response.json()
                assert data["detail"]["error"]["code"] == "INVALID_JOB_STATUS"
        finally:
            app.dependency_overrides.clear()


class TestSkipJobEndpoint:
    """Tests for POST /api/jobs/{job_id}/skip endpoint."""

    @pytest.mark.anyio
    async def test_skips_failed_job_successfully(self) -> None:
        """Should skip a failed job and return success."""
        job_id = str(uuid4())
        matter_id = str(uuid4())
        mock_job = create_mock_job(
            job_id=job_id, matter_id=matter_id, status=JobStatus.FAILED
        )

        mock_tracker = AsyncMock()
        mock_tracker.get_job = AsyncMock(return_value=mock_job)
        mock_tracker.update_job_status = AsyncMock()

        app.dependency_overrides[get_settings] = get_test_settings

        try:
            with patch(
                "app.api.routes.jobs.get_job_tracking_service",
                return_value=mock_tracker,
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    response = await client.post(
                        f"/api/jobs/{job_id}/skip",
                        headers={"Authorization": f"Bearer {create_test_token()}"},
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["new_status"] == "SKIPPED"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_rejects_skip_for_non_failed_job(self) -> None:
        """Should reject skip for a job that isn't failed."""
        job_id = str(uuid4())
        matter_id = str(uuid4())
        mock_job = create_mock_job(
            job_id=job_id, matter_id=matter_id, status=JobStatus.COMPLETED
        )

        mock_tracker = AsyncMock()
        mock_tracker.get_job = AsyncMock(return_value=mock_job)

        app.dependency_overrides[get_settings] = get_test_settings

        try:
            with patch(
                "app.api.routes.jobs.get_job_tracking_service",
                return_value=mock_tracker,
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    response = await client.post(
                        f"/api/jobs/{job_id}/skip",
                        headers={"Authorization": f"Bearer {create_test_token()}"},
                    )

                assert response.status_code == 400
                data = response.json()
                assert data["detail"]["error"]["code"] == "INVALID_JOB_STATUS"
        finally:
            app.dependency_overrides.clear()


class TestCancelJobEndpoint:
    """Tests for POST /api/jobs/{job_id}/cancel endpoint."""

    @pytest.mark.anyio
    async def test_cancels_queued_job_successfully(self) -> None:
        """Should cancel a queued job and return success."""
        job_id = str(uuid4())
        matter_id = str(uuid4())
        mock_job = create_mock_job(
            job_id=job_id, matter_id=matter_id, status=JobStatus.QUEUED
        )

        mock_tracker = AsyncMock()
        mock_tracker.get_job = AsyncMock(return_value=mock_job)
        mock_tracker.update_job_status = AsyncMock()

        app.dependency_overrides[get_settings] = get_test_settings

        try:
            with patch(
                "app.api.routes.jobs.get_job_tracking_service",
                return_value=mock_tracker,
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    response = await client.post(
                        f"/api/jobs/{job_id}/cancel",
                        headers={"Authorization": f"Bearer {create_test_token()}"},
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["new_status"] == "CANCELLED"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_cancels_processing_job_successfully(self) -> None:
        """Should cancel a processing job and return success."""
        job_id = str(uuid4())
        matter_id = str(uuid4())
        mock_job = create_mock_job(
            job_id=job_id, matter_id=matter_id, status=JobStatus.PROCESSING
        )

        mock_tracker = AsyncMock()
        mock_tracker.get_job = AsyncMock(return_value=mock_job)
        mock_tracker.update_job_status = AsyncMock()

        app.dependency_overrides[get_settings] = get_test_settings

        try:
            with patch(
                "app.api.routes.jobs.get_job_tracking_service",
                return_value=mock_tracker,
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    response = await client.post(
                        f"/api/jobs/{job_id}/cancel",
                        headers={"Authorization": f"Bearer {create_test_token()}"},
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["new_status"] == "CANCELLED"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.anyio
    async def test_rejects_cancel_for_completed_job(self) -> None:
        """Should reject cancel for a completed job."""
        job_id = str(uuid4())
        matter_id = str(uuid4())
        mock_job = create_mock_job(
            job_id=job_id, matter_id=matter_id, status=JobStatus.COMPLETED
        )

        mock_tracker = AsyncMock()
        mock_tracker.get_job = AsyncMock(return_value=mock_job)

        app.dependency_overrides[get_settings] = get_test_settings

        try:
            with patch(
                "app.api.routes.jobs.get_job_tracking_service",
                return_value=mock_tracker,
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    response = await client.post(
                        f"/api/jobs/{job_id}/cancel",
                        headers={"Authorization": f"Bearer {create_test_token()}"},
                    )

                assert response.status_code == 400
                data = response.json()
                assert data["detail"]["error"]["code"] == "INVALID_JOB_STATUS"
        finally:
            app.dependency_overrides.clear()


class TestListMatterJobsEndpoint:
    """Tests for GET /api/jobs/matters/{matter_id} endpoint."""

    @pytest.mark.anyio
    async def test_lists_jobs_for_matter(self) -> None:
        """Should list all jobs for a matter."""
        from app.api.deps import get_matter_service

        matter_id = str(uuid4())
        mock_jobs = [
            create_mock_job(matter_id=matter_id, status=JobStatus.PROCESSING),
            create_mock_job(matter_id=matter_id, status=JobStatus.COMPLETED),
        ]

        mock_tracker = AsyncMock()
        mock_tracker.list_jobs_for_matter = AsyncMock(return_value=mock_jobs)

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role_in_matter = AsyncMock(return_value="attorney")

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service

        try:
            with patch(
                "app.api.routes.jobs.get_job_tracking_service",
                return_value=mock_tracker,
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    response = await client.get(
                        f"/api/jobs/matters/{matter_id}",
                        headers={"Authorization": f"Bearer {create_test_token()}"},
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 2
                assert len(data["jobs"]) == 2
        finally:
            app.dependency_overrides.clear()


class TestGetMatterJobStatsEndpoint:
    """Tests for GET /api/jobs/matters/{matter_id}/stats endpoint."""

    @pytest.mark.anyio
    async def test_returns_stats_for_matter(self) -> None:
        """Should return job statistics for a matter."""
        from app.api.deps import get_matter_service

        matter_id = str(uuid4())
        mock_stats = {
            "queued": 2,
            "processing": 1,
            "completed": 10,
            "failed": 1,
            "cancelled": 0,
            "skipped": 0,
            "avg_processing_time_ms": 45000,
        }

        mock_tracker = AsyncMock()
        mock_tracker.get_queue_stats = AsyncMock(return_value=mock_stats)

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role_in_matter = AsyncMock(return_value="attorney")

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service

        try:
            with patch(
                "app.api.routes.jobs.get_job_tracking_service",
                return_value=mock_tracker,
            ):
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    response = await client.get(
                        f"/api/jobs/matters/{matter_id}/stats",
                        headers={"Authorization": f"Bearer {create_test_token()}"},
                    )

                assert response.status_code == 200
                data = response.json()
                assert data["queued"] == 2
                assert data["processing"] == 1
                assert data["completed"] == 10
                assert data["failed"] == 1
        finally:
            app.dependency_overrides.clear()
