"""Processing job models for background job tracking."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JobType(str, Enum):
    """Type of processing job.

    Types:
    - DOCUMENT_PROCESSING: Full document pipeline (OCR through entity extraction)
    - OCR: Optical character recognition stage
    - VALIDATION: OCR validation and correction stage
    - CHUNKING: Parent-child chunk creation stage
    - EMBEDDING: Vector embedding generation stage
    - ENTITY_EXTRACTION: MIG entity extraction stage
    - ALIAS_RESOLUTION: Entity alias resolution stage
    - DATE_EXTRACTION: Timeline date extraction stage (Story 4-1)
    - EVENT_CLASSIFICATION: Timeline event classification stage (Story 4-2)
    - ENTITY_LINKING: Timeline event to MIG entity linking stage (Story 4-3)
    """

    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    OCR = "OCR"
    VALIDATION = "VALIDATION"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    ENTITY_EXTRACTION = "ENTITY_EXTRACTION"
    ALIAS_RESOLUTION = "ALIAS_RESOLUTION"
    DATE_EXTRACTION = "DATE_EXTRACTION"
    EVENT_CLASSIFICATION = "EVENT_CLASSIFICATION"
    ENTITY_LINKING = "ENTITY_LINKING"


class JobStatus(str, Enum):
    """Processing job status.

    States:
    - QUEUED: Job created, waiting in queue
    - PROCESSING: Job actively being processed
    - COMPLETED: Job completed successfully
    - FAILED: Job failed after all retries exhausted
    - CANCELLED: Job cancelled by user or system
    - SKIPPED: Job skipped by user (failed job that won't be retried)
    """

    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class StageStatus(str, Enum):
    """Individual stage status within a job.

    States:
    - PENDING: Stage not yet started
    - IN_PROGRESS: Stage currently executing
    - COMPLETED: Stage completed successfully
    - FAILED: Stage failed
    - SKIPPED: Stage skipped (due to previous failure or manual skip)
    """

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class JobStageHistory(BaseModel):
    """Stage-level tracking for a processing job."""

    id: str = Field(..., description="Stage history UUID")
    job_id: str = Field(..., description="Parent job UUID")
    stage_name: str = Field(..., description="Stage name: ocr, validation, chunking, etc.")
    status: StageStatus = Field(
        default=StageStatus.PENDING,
        description="Stage status"
    )
    started_at: datetime | None = Field(None, description="When stage started")
    completed_at: datetime | None = Field(None, description="When stage completed")
    error_message: str | None = Field(None, description="Error message if failed")
    metadata: dict = Field(
        default_factory=dict,
        description="Stage-specific metadata"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


class ProcessingJobBase(BaseModel):
    """Base processing job properties."""

    matter_id: str = Field(..., description="Matter UUID this job belongs to")
    document_id: str | None = Field(None, description="Document UUID (null for matter-level jobs)")
    job_type: JobType = Field(..., description="Type of processing job")


class ProcessingJobCreate(ProcessingJobBase):
    """Model for creating a new processing job."""

    celery_task_id: str | None = Field(None, description="Celery task ID for correlation")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    metadata: dict = Field(
        default_factory=dict,
        description="Initial job metadata"
    )


class ProcessingJobUpdate(BaseModel):
    """Model for updating a processing job."""

    status: JobStatus | None = Field(None, description="New status")
    current_stage: str | None = Field(None, description="Current processing stage")
    completed_stages: int | None = Field(None, ge=0, description="Number of completed stages")
    progress_pct: int | None = Field(None, ge=0, le=100, description="Progress percentage")
    estimated_completion: datetime | None = Field(None, description="Estimated completion time")
    error_message: str | None = Field(None, description="Error message if failed")
    error_code: str | None = Field(None, description="Machine-readable error code")
    retry_count: int | None = Field(None, ge=0, description="Current retry count")
    started_at: datetime | None = Field(None, description="Processing start time")
    completed_at: datetime | None = Field(None, description="Processing completion time")
    metadata: dict | None = Field(None, description="Updated metadata")


class ProcessingJob(ProcessingJobBase):
    """Complete processing job model returned from API."""

    id: str = Field(..., description="Job UUID")
    status: JobStatus = Field(
        default=JobStatus.QUEUED,
        description="Current job status"
    )
    celery_task_id: str | None = Field(None, description="Celery task ID for correlation")

    # Progress tracking
    current_stage: str | None = Field(None, description="Current processing stage name")
    total_stages: int = Field(default=7, description="Total stages in pipeline")
    completed_stages: int = Field(default=0, description="Completed stages count")
    progress_pct: int = Field(
        default=0,
        ge=0, le=100,
        description="Overall progress percentage"
    )
    estimated_completion: datetime | None = Field(
        None,
        description="Estimated completion timestamp"
    )

    # Error handling
    error_message: str | None = Field(None, description="Error message if failed")
    error_code: str | None = Field(None, description="Machine-readable error code")
    retry_count: int = Field(default=0, ge=0, description="Number of retries attempted")
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")

    # Metadata for partial progress
    metadata: dict = Field(
        default_factory=dict,
        description="Job metadata (completed_pages, chunks_created, etc.)"
    )

    # Timestamps
    started_at: datetime | None = Field(None, description="When processing started")
    completed_at: datetime | None = Field(None, description="When processing completed")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class ProcessingJobWithHistory(ProcessingJob):
    """Processing job with stage history included."""

    stage_history: list[JobStageHistory] = Field(
        default_factory=list,
        description="Stage-level history records"
    )


class JobQueueStats(BaseModel):
    """Queue statistics for a matter's processing jobs."""

    queued: int = Field(default=0, ge=0, description="Jobs in queue")
    processing: int = Field(default=0, ge=0, description="Jobs currently processing")
    completed: int = Field(default=0, ge=0, description="Completed jobs")
    failed: int = Field(default=0, ge=0, description="Failed jobs")
    cancelled: int = Field(default=0, ge=0, description="Cancelled jobs")
    skipped: int = Field(default=0, ge=0, description="Skipped jobs")
    avg_processing_time_ms: int = Field(
        default=0, ge=0,
        description="Average processing time in milliseconds"
    )


class JobListItem(BaseModel):
    """Simplified job item for list responses."""

    id: str = Field(..., description="Job UUID")
    matter_id: str = Field(..., description="Matter UUID")
    document_id: str | None = Field(None, description="Document UUID")
    job_type: JobType = Field(..., description="Type of processing job")
    status: JobStatus = Field(..., description="Current job status")
    current_stage: str | None = Field(None, description="Current stage name")
    progress_pct: int = Field(default=0, description="Progress percentage")
    estimated_completion: datetime | None = Field(None, description="Estimated completion")
    retry_count: int = Field(default=0, description="Retry attempts")
    error_message: str | None = Field(None, description="Error if failed")
    created_at: datetime = Field(..., description="When job was created")


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, le=100, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


# API Response Models (following { data } or { error } format)

class JobResponse(BaseModel):
    """API response wrapper for a single job."""

    data: ProcessingJob


class JobDetailResponse(BaseModel):
    """API response wrapper for job with stage history."""

    data: ProcessingJobWithHistory


class JobsListResponse(BaseModel):
    """API response for paginated job list."""

    data: list[JobListItem]
    meta: PaginationMeta


class JobStatsResponse(BaseModel):
    """API response for queue statistics."""

    data: JobQueueStats


class JobErrorDetail(BaseModel):
    """Structured error detail for job operations."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict = Field(
        default_factory=dict,
        description="Additional error context"
    )


class JobErrorResponse(BaseModel):
    """API error response for job operations."""

    error: JobErrorDetail


# =============================================================================
# API Response Models for routes/jobs.py
# =============================================================================


class JobListResponse(BaseModel):
    """Response for list of jobs."""

    jobs: list[ProcessingJob] = Field(default_factory=list, description="List of jobs")
    total: int = Field(default=0, ge=0, description="Total number of jobs")
    limit: int = Field(default=50, ge=1, description="Page limit")
    offset: int = Field(default=0, ge=0, description="Page offset")


class ProcessingJobResponse(BaseModel):
    """Response for single job with stage history."""

    job: ProcessingJob = Field(..., description="The processing job")
    stages: list[JobStageHistory] = Field(
        default_factory=list, description="Stage history"
    )
