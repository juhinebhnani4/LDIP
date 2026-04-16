"""Admin Pipeline API routes for manual task triggering and pipeline management.

Provides admin-only endpoints for:
- Triggering any pipeline task manually
- Retrying failed tasks
- Resetting document status
- Viewing pipeline status
- Reprocessing stuck documents
- Worker starvation diagnostics (jobs overview, bottleneck stats, error patterns)

All endpoints require admin access (configured via ADMIN_EMAILS env var).
"""

import asyncio
from enum import Enum

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field

from app.api.deps import require_admin_access
from app.core.rate_limit import ADMIN_RATE_LIMIT, limiter
from app.models.auth import AuthenticatedUser
from app.services.supabase.client import get_service_client

router = APIRouter(prefix="/admin/pipeline", tags=["admin-pipeline"])
logger = structlog.get_logger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class PipelineTask(str, Enum):
    """Available pipeline tasks that can be triggered manually."""

    # Document processing tasks
    PROCESS_DOCUMENT = "process_document"
    VALIDATE_OCR = "validate_ocr"
    CALCULATE_CONFIDENCE = "calculate_confidence"
    CHUNK_DOCUMENT = "chunk_document"
    EMBED_CHUNKS = "embed_chunks"
    EXTRACT_ENTITIES = "extract_entities"
    RESOLVE_ALIASES = "resolve_aliases"
    EXTRACT_CITATIONS = "extract_citations"
    LINK_BBOXES = "link_chunks_to_bboxes"  # Decoupled bbox linking

    # Engine tasks
    EXTRACT_DATES = "extract_dates_from_document"
    CLASSIFY_EVENTS = "classify_events_for_document"
    LINK_ENTITIES = "link_entities_after_extraction"

    # Chunked document tasks
    PROCESS_CHUNKED = "process_document_chunked"
    FINALIZE_CHUNKED = "finalize_chunked_document"
    RETRY_FAILED_CHUNKS = "retry_failed_chunks"


# Task name to Celery task mapping
TASK_MAPPING = {
    PipelineTask.PROCESS_DOCUMENT: "app.workers.tasks.document_tasks.process_document",
    PipelineTask.VALIDATE_OCR: "app.workers.tasks.document_tasks.validate_ocr",
    PipelineTask.CALCULATE_CONFIDENCE: "app.workers.tasks.document_tasks.calculate_confidence",
    PipelineTask.CHUNK_DOCUMENT: "app.workers.tasks.document_tasks.chunk_document",
    PipelineTask.EMBED_CHUNKS: "app.workers.tasks.document_tasks.embed_chunks",
    PipelineTask.EXTRACT_ENTITIES: "app.workers.tasks.document_tasks.extract_entities",
    PipelineTask.RESOLVE_ALIASES: "app.workers.tasks.document_tasks.resolve_aliases",
    PipelineTask.EXTRACT_CITATIONS: "app.workers.tasks.document_tasks.extract_citations",
    PipelineTask.LINK_BBOXES: "app.workers.tasks.document_tasks.link_chunks_to_bboxes_task",
    PipelineTask.EXTRACT_DATES: "app.workers.tasks.engine_tasks.extract_dates_from_document",
    PipelineTask.CLASSIFY_EVENTS: "app.workers.tasks.engine_tasks.classify_events_for_document",
    PipelineTask.LINK_ENTITIES: "app.workers.tasks.engine_tasks.link_entities_after_extraction",
    PipelineTask.PROCESS_CHUNKED: "app.workers.tasks.chunked_document_tasks.process_document_chunked",
    PipelineTask.FINALIZE_CHUNKED: "app.workers.tasks.chunked_document_tasks.finalize_chunked_document",
    PipelineTask.RETRY_FAILED_CHUNKS: "app.workers.tasks.chunked_document_tasks.retry_failed_chunks",
}


# =============================================================================
# Request/Response Models
# =============================================================================


class TriggerTaskRequest(BaseModel):
    """Request body for triggering a task."""

    force: bool = Field(
        default=False,
        description="Skip status validation checks",
    )
    prev_status: str | None = Field(
        default=None,
        description="Override prev_result status for task chain simulation",
    )


class TriggerTaskResponse(BaseModel):
    """Response for task trigger request."""

    success: bool
    message: str
    document_id: str
    task_name: str
    celery_task_id: str | None = None


class ResetStatusRequest(BaseModel):
    """Request body for resetting document status."""

    new_status: str = Field(
        ...,
        description="New status to set (e.g., 'ocr_complete', 'processing', 'pending')",
    )
    clear_error: bool = Field(
        default=True,
        description="Clear any error message/code",
    )


class ResetStatusResponse(BaseModel):
    """Response for status reset request."""

    success: bool
    message: str
    document_id: str
    old_status: str
    new_status: str


class PipelineStageInfo(BaseModel):
    """Information about a pipeline stage."""

    stage: str
    status: str
    completed: bool
    error: str | None = None
    data_available: bool = False


class PipelineStatusResponse(BaseModel):
    """Response for pipeline status request."""

    document_id: str
    document_status: str
    matter_id: str
    stages: list[PipelineStageInfo]
    chunks_count: int = 0
    entities_count: int = 0
    has_extracted_text: bool = False
    has_embeddings: bool = False


class RetryFailedResponse(BaseModel):
    """Response for retry failed tasks request."""

    success: bool
    message: str
    document_id: str
    tasks_triggered: list[str]


class StuckDocumentInfo(BaseModel):
    """Information about a stuck document."""

    document_id: str
    document_name: str
    status: str
    updated_at: str
    hours_stuck: float


class ReprocessStuckResponse(BaseModel):
    """Response for reprocessing stuck documents."""

    success: bool
    matter_id: str
    documents_found: int
    documents_reprocessed: int
    stuck_documents: list[StuckDocumentInfo]
    errors: list[str]


# =============================================================================
# Helper Functions
# =============================================================================


async def _get_document(document_id: str) -> dict:
    """Get document by ID with validation."""
    client = get_service_client()
    response = (
        client.table("documents")
        .select("id, filename, status, matter_id, extracted_text, ocr_error, updated_at")
        .eq("id", document_id)
        .single()
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": f"Document {document_id} not found",
                    "details": {},
                }
            },
        )

    return response.data


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/documents/{document_id}/trigger/{task_name}",
    response_model=TriggerTaskResponse,
    summary="Trigger a pipeline task manually",
    description="Trigger any pipeline task for a specific document. Admin only.",
)
async def trigger_task(
    document_id: str = Path(..., description="Document UUID"),
    task_name: PipelineTask = Path(..., description="Task to trigger"),
    request: TriggerTaskRequest | None = None,
    admin: AuthenticatedUser = Depends(require_admin_access),
) -> TriggerTaskResponse:
    """Trigger a pipeline task manually for a document."""
    from app.workers.celery import celery_app

    # Validate document exists
    doc = await _get_document(document_id)

    # Get the Celery task
    celery_task_name = TASK_MAPPING.get(task_name)
    if not celery_task_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_TASK",
                    "message": f"Unknown task: {task_name}",
                    "details": {"available_tasks": [t.value for t in PipelineTask]},
                }
            },
        )

    # Build task arguments
    force = request.force if request else False
    prev_status = request.prev_status if request else None

    # Prepare prev_result for task chain simulation
    prev_result = {
        "document_id": document_id,
        "status": prev_status or doc["status"],
    }

    logger.info(
        "admin_trigger_task",
        admin_id=admin.id,
        admin_email=admin.email,
        document_id=document_id,
        task_name=task_name.value,
        force=force,
        prev_status=prev_status,
    )

    try:
        # Send the task to Celery
        task = celery_app.send_task(
            celery_task_name,
            kwargs={
                "prev_result": prev_result,
                "document_id": document_id,
                "force": force,
            },
        )

        return TriggerTaskResponse(
            success=True,
            message=f"Task {task_name.value} triggered successfully",
            document_id=document_id,
            task_name=task_name.value,
            celery_task_id=task.id,
        )

    except Exception as e:
        logger.error(
            "admin_trigger_task_failed",
            document_id=document_id,
            task_name=task_name.value,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "TASK_TRIGGER_FAILED",
                    "message": f"Failed to trigger task: {e!s}",
                    "details": {},
                }
            },
        ) from e


@router.post(
    "/documents/{document_id}/retry-failed",
    response_model=RetryFailedResponse,
    summary="Retry all failed tasks for a document",
    description="Analyzes document state and retries appropriate failed tasks. Admin only.",
)
async def retry_failed_tasks(
    document_id: str = Path(..., description="Document UUID"),
    admin: AuthenticatedUser = Depends(require_admin_access),
) -> RetryFailedResponse:
    """Retry all failed/stuck tasks for a document."""
    from app.workers.celery import celery_app

    doc = await _get_document(document_id)
    tasks_triggered = []

    logger.info(
        "admin_retry_failed",
        admin_id=admin.id,
        admin_email=admin.email,
        document_id=document_id,
        current_status=doc["status"],
    )

    # Determine which tasks need to be retried based on document state
    doc_status = doc["status"]
    has_text = bool(doc.get("extracted_text"))

    # Get chunk and entity counts
    client = get_service_client()
    chunks_resp = (
        client.table("chunks")
        .select("id", count="exact")
        .eq("document_id", document_id)
        .execute()
    )
    chunks_count = chunks_resp.count or 0

    entities_resp = (
        client.table("entity_mentions")
        .select("id", count="exact")
        .eq("document_id", document_id)
        .execute()
    )
    entities_count = entities_resp.count or 0

    # --- Cleanup before retry ---
    cleanup_actions = []

    async def _cleanup_for_full_reprocess():
        """Delete all downstream data and reset document for full reprocess."""
        nonlocal cleanup_actions
        # 1. Delete OCR chunks
        try:
            client.table("document_ocr_chunks").delete().eq(
                "document_id", document_id
            ).execute()
            cleanup_actions.append("deleted_ocr_chunks")
        except Exception as e:
            logger.warning("retry_cleanup_ocr_chunks_failed", error=str(e))

        # 2. Delete RAG chunks (cascades to embeddings)
        try:
            from app.services.chunk_service import ChunkService
            chunk_svc = ChunkService()
            await chunk_svc.delete_chunks_for_document(document_id)
            cleanup_actions.append("deleted_rag_chunks")
        except Exception as e:
            logger.warning("retry_cleanup_rag_chunks_failed", error=str(e))

        # 3. Reset document status to pending
        try:
            client.table("documents").update({
                "status": "pending",
                "ocr_error": None,
            }).eq("id", document_id).execute()
            cleanup_actions.append("reset_status_to_pending")
        except Exception as e:
            logger.warning("retry_cleanup_reset_status_failed", error=str(e))

        # 4. Mark any PROCESSING jobs as FAILED so they don't block
        try:
            client.table("processing_jobs").update({
                "status": "FAILED",
                "error_message": "Superseded by admin retry",
            }).eq("document_id", document_id).eq(
                "status", "PROCESSING"
            ).execute()
            cleanup_actions.append("failed_stale_jobs")
        except Exception as e:
            logger.warning("retry_cleanup_jobs_failed", error=str(e))

        # 5. Release pipeline lock
        try:
            from app.services.distributed_lock import PipelineLock
            PipelineLock(document_id).release()
            cleanup_actions.append("released_pipeline_lock")
        except Exception as e:
            logger.warning("retry_cleanup_lock_failed", error=str(e))

    # Build task chain based on what's missing.
    # Use create_post_ocr_chain() for multi-step retries so the full pipeline
    # runs (chunk → embed → entities → citations/dates/aliases → mark completed).
    from app.workers.tasks.pipeline_chains import create_post_ocr_chain

    matter_id = doc.get("matter_id")

    if doc_status in ("failed", "error", "ocr_failed"):
        # Full reprocess — clean up everything first
        await _cleanup_for_full_reprocess()

        # Full pipeline: process_document → post-OCR chain
        from app.workers.tasks.document_tasks import process_document
        from celery import chain as celery_chain
        post_ocr = create_post_ocr_chain(
            document_id=document_id,
            matter_id=matter_id or "",
            job_id=None,
        )
        full_chain = celery_chain(
            process_document.s(document_id),
            post_ocr,
        )
        full_chain.apply_async()
        tasks_triggered.append("process_document (full chain)")

    elif doc_status == "ocr_complete" and chunks_count == 0:
        # Stuck in ocr_complete with no chunks — release lock and run full post-OCR chain
        try:
            from app.services.distributed_lock import PipelineLock
            PipelineLock(document_id).release()
            cleanup_actions.append("released_pipeline_lock")
        except Exception as e:
            logger.warning("retry_cleanup_lock_failed", error=str(e))

        post_ocr = create_post_ocr_chain(
            document_id=document_id,
            matter_id=matter_id or "",
            job_id=None,
        )
        post_ocr.apply_async()
        tasks_triggered.append("post_ocr_chain (validate→chunk→embed→entities)")

    elif has_text and chunks_count == 0:
        # Has text but no chunks - run full post-OCR chain
        post_ocr = create_post_ocr_chain(
            document_id=document_id,
            matter_id=matter_id or "",
            job_id=None,
        )
        post_ocr.apply_async()
        tasks_triggered.append("post_ocr_chain (validate→chunk→embed→entities)")

    elif chunks_count > 0 and entities_count == 0:
        # Has chunks but no entities - run from embed onwards
        from app.workers.tasks.document_tasks import embed_chunks, extract_entities
        from celery import chain as celery_chain
        embed_chain = celery_chain(
            embed_chunks.s(
                prev_result={"document_id": document_id, "status": "chunking_complete", "job_id": None},
            ),
            extract_entities.s(),
        )
        embed_chain.apply_async()
        tasks_triggered.append("embed→entities chain")

    if not tasks_triggered:
        return RetryFailedResponse(
            success=True,
            message="No failed tasks detected - document appears complete",
            document_id=document_id,
            tasks_triggered=[],
        )

    logger.info(
        "admin_retry_cleanup_complete",
        document_id=document_id,
        cleanup_actions=cleanup_actions,
        tasks_triggered=tasks_triggered,
    )

    return RetryFailedResponse(
        success=True,
        message=f"Triggered {len(tasks_triggered)} task(s) for retry (cleanup: {', '.join(cleanup_actions) or 'none'})",
        document_id=document_id,
        tasks_triggered=tasks_triggered,
    )


@router.post(
    "/documents/{document_id}/reset-status",
    response_model=ResetStatusResponse,
    summary="Reset document status",
    description="Reset a document to a specific status. Admin only.",
)
async def reset_document_status(
    document_id: str = Path(..., description="Document UUID"),
    request: ResetStatusRequest = ...,
    admin: AuthenticatedUser = Depends(require_admin_access),
) -> ResetStatusResponse:
    """Reset document to a specific status."""
    doc = await _get_document(document_id)
    old_status = doc["status"]

    logger.info(
        "admin_reset_status",
        admin_id=admin.id,
        admin_email=admin.email,
        document_id=document_id,
        old_status=old_status,
        new_status=request.new_status,
    )

    # Update document status
    client = get_service_client()
    update_data: dict = {"status": request.new_status}
    if request.clear_error:
        update_data["error_message"] = None
        update_data["error_code"] = None

    client.table("documents").update(update_data).eq("id", document_id).execute()

    return ResetStatusResponse(
        success=True,
        message=f"Document status reset from {old_status} to {request.new_status}",
        document_id=document_id,
        old_status=old_status,
        new_status=request.new_status,
    )


@router.get(
    "/documents/{document_id}/pipeline-status",
    response_model=PipelineStatusResponse,
    summary="Get pipeline status for a document",
    description="Get detailed status of all pipeline stages for a document. Admin only.",
)
async def get_pipeline_status(
    document_id: str = Path(..., description="Document UUID"),
    admin: AuthenticatedUser = Depends(require_admin_access),
) -> PipelineStatusResponse:
    """Get detailed pipeline status for a document."""
    doc = await _get_document(document_id)
    client = get_service_client()

    # Get chunk count and embedding status
    chunks_resp = (
        client.table("chunks")
        .select("id, embedding", count="exact")
        .eq("document_id", document_id)
        .execute()
    )
    chunks_count = chunks_resp.count or 0
    chunks_with_embeddings = sum(1 for c in (chunks_resp.data or []) if c.get("embedding"))

    # Get entity count
    entities_resp = (
        client.table("entity_mentions")
        .select("id", count="exact")
        .eq("document_id", document_id)
        .execute()
    )
    entities_count = entities_resp.count or 0

    # Get OCR chunks count (for chunked processing)
    ocr_chunks_resp = (
        client.table("ocr_chunks")
        .select("id, status", count="exact")
        .eq("document_id", document_id)
        .execute()
    )
    ocr_chunks = ocr_chunks_resp.data or []
    ocr_chunks_completed = sum(1 for c in ocr_chunks if c.get("status") == "completed")

    # Build stage info
    has_text = bool(doc.get("extracted_text"))
    doc_status = doc["status"]

    stages = [
        PipelineStageInfo(
            stage="ocr",
            status="completed" if has_text else doc_status,
            completed=has_text,
            data_available=has_text,
        ),
        PipelineStageInfo(
            stage="chunking",
            status="completed" if chunks_count > 0 else "pending",
            completed=chunks_count > 0,
            data_available=chunks_count > 0,
        ),
        PipelineStageInfo(
            stage="embedding",
            status="completed" if chunks_with_embeddings > 0 else "pending",
            completed=chunks_with_embeddings == chunks_count and chunks_count > 0,
            data_available=chunks_with_embeddings > 0,
        ),
        PipelineStageInfo(
            stage="entity_extraction",
            status="completed" if entities_count > 0 else "pending",
            completed=entities_count > 0,
            data_available=entities_count > 0,
        ),
    ]

    # Add OCR chunks info if applicable
    if ocr_chunks:
        stages.insert(
            0,
            PipelineStageInfo(
                stage="ocr_chunked",
                status=f"{ocr_chunks_completed}/{len(ocr_chunks)} completed",
                completed=ocr_chunks_completed == len(ocr_chunks),
                data_available=ocr_chunks_completed > 0,
            ),
        )

    return PipelineStatusResponse(
        document_id=document_id,
        document_status=doc_status,
        matter_id=doc["matter_id"],
        stages=stages,
        chunks_count=chunks_count,
        entities_count=entities_count,
        has_extracted_text=has_text,
        has_embeddings=chunks_with_embeddings > 0,
    )


@router.post(
    "/matters/{matter_id}/reprocess-stuck",
    response_model=ReprocessStuckResponse,
    summary="Find and reprocess stuck documents in a matter",
    description="Find documents stuck in processing for > 2 hours and reprocess them. Admin only.",
)
async def reprocess_stuck_documents(
    matter_id: str = Path(..., description="Matter UUID"),
    hours_threshold: float = Query(
        default=2.0,
        ge=0.5,
        le=48.0,
        description="Hours since last update to consider document stuck",
    ),
    admin: AuthenticatedUser = Depends(require_admin_access),
) -> ReprocessStuckResponse:
    """Find and reprocess stuck documents in a matter."""
    from datetime import datetime, timedelta, timezone

    from app.workers.celery import celery_app

    client = get_service_client()

    # Calculate threshold time
    threshold_time = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)

    # Find stuck documents
    response = (
        client.table("documents")
        .select("id, name, status, updated_at")
        .eq("matter_id", matter_id)
        .in_("status", ["processing", "queued", "pending"])
        .lt("updated_at", threshold_time.isoformat())
        .execute()
    )

    stuck_docs = response.data or []
    reprocessed = 0
    errors: list[str] = []

    logger.info(
        "admin_reprocess_stuck",
        admin_id=admin.id,
        admin_email=admin.email,
        matter_id=matter_id,
        hours_threshold=hours_threshold,
        stuck_count=len(stuck_docs),
    )

    stuck_infos = []
    for doc in stuck_docs:
        updated_at = datetime.fromisoformat(doc["updated_at"].replace("Z", "+00:00"))
        hours_stuck = (datetime.now(timezone.utc) - updated_at).total_seconds() / 3600

        stuck_infos.append(
            StuckDocumentInfo(
                document_id=doc["id"],
                document_name=doc["name"],
                status=doc["status"],
                updated_at=doc["updated_at"],
                hours_stuck=round(hours_stuck, 2),
            )
        )

        try:
            # Trigger reprocessing
            celery_app.send_task(
                TASK_MAPPING[PipelineTask.PROCESS_DOCUMENT],
                kwargs={"document_id": doc["id"]},
            )
            reprocessed += 1
        except Exception as e:
            errors.append(f"Failed to reprocess {doc['id']}: {e!s}")

    return ReprocessStuckResponse(
        success=True,
        matter_id=matter_id,
        documents_found=len(stuck_docs),
        documents_reprocessed=reprocessed,
        stuck_documents=stuck_infos,
        errors=errors,
    )


# =============================================================================
# Voyage Embedding Migration
# =============================================================================


class VoyageMigrationRequest(BaseModel):
    """Request body for Voyage embedding backfill."""

    matter_id: str | None = Field(
        default=None,
        description="Optional matter ID to limit scope. If omitted, processes all chunks.",
    )
    batch_size: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Chunks per batch (default 50)",
    )


class VoyageMigrationResponse(BaseModel):
    """Response for Voyage migration trigger."""

    success: bool
    message: str
    celery_task_id: str | None = None


@router.post(
    "/embeddings/migrate-voyage",
    response_model=VoyageMigrationResponse,
    summary="Trigger Voyage embedding backfill",
    description="Backfill Voyage law-2 embeddings for existing chunks. Admin only.",
)
async def trigger_voyage_migration(
    request: VoyageMigrationRequest | None = None,
    admin: AuthenticatedUser = Depends(require_admin_access),
) -> VoyageMigrationResponse:
    """Trigger batch Voyage embedding generation for chunks missing them."""
    from app.workers.celery import celery_app

    matter_id = request.matter_id if request else None
    batch_size = request.batch_size if request else 50

    logger.info(
        "admin_voyage_migration_triggered",
        admin_id=admin.id,
        admin_email=admin.email,
        matter_id=matter_id,
        batch_size=batch_size,
    )

    try:
        task = celery_app.send_task(
            "app.workers.tasks.voyage_embedding_tasks.batch_embed_voyage",
            kwargs={
                "matter_id": matter_id,
                "batch_size": batch_size,
            },
        )

        return VoyageMigrationResponse(
            success=True,
            message=f"Voyage embedding migration triggered{f' for matter {matter_id}' if matter_id else ' for all chunks'}",
            celery_task_id=task.id,
        )

    except Exception as e:
        logger.error(
            "admin_voyage_migration_failed",
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "VOYAGE_MIGRATION_FAILED",
                    "message": f"Failed to trigger Voyage migration: {e!s}",
                    "details": {},
                }
            },
        ) from e


# =============================================================================
# Worker Starvation Diagnostics
# =============================================================================


class JobOverviewItem(BaseModel):
    """A processing job visible across all matters."""

    job_id: str
    matter_id: str
    document_id: str | None
    job_type: str
    status: str
    current_stage: str | None
    progress_pct: int
    retry_count: int
    error_message: str | None
    queue_wait_seconds: float | None = None
    created_at: str
    started_at: str | None
    updated_at: str


class JobsOverviewResponse(BaseModel):
    """Cross-matter jobs overview for admin."""

    jobs: list[JobOverviewItem]
    total_count: int
    queued_count: int
    processing_count: int


class BottleneckStage(BaseModel):
    """Duration stats for a pipeline stage."""

    stage_name: str
    avg_duration_seconds: float
    max_duration_seconds: float
    total_runs: int
    failed_runs: int


class BottleneckStatsResponse(BaseModel):
    """Stage-level bottleneck analysis."""

    stages: list[BottleneckStage]


class ErrorPattern(BaseModel):
    """Grouped error pattern from job stage history."""

    error_message: str
    count: int
    stage_name: str
    last_occurred: str


class ErrorPatternsResponse(BaseModel):
    """Aggregated error patterns."""

    patterns: list[ErrorPattern]
    total_errors: int


class ActiveTaskDetail(BaseModel):
    """A task currently running on a worker."""

    task_name: str
    task_id: str
    worker_name: str
    runtime_seconds: float


class WorkerInfoResponse(BaseModel):
    """Active worker and task information."""

    worker_count: int
    active_tasks: list[ActiveTaskDetail]


@router.get(
    "/worker-info",
    response_model=WorkerInfoResponse,
    summary="Get active worker and task details",
    description="Shows what each worker is currently executing and for how long. Admin only.",
)
@limiter.limit(ADMIN_RATE_LIMIT)
async def get_worker_info(
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin_access),
) -> WorkerInfoResponse:
    """Get active worker details including currently running tasks."""
    from app.services.queue_metrics_service import get_queue_metrics_service

    service = get_queue_metrics_service()
    info = await service.get_active_worker_info()

    tasks = [
        ActiveTaskDetail(
            task_name=t.task_name,
            task_id=t.task_id,
            worker_name=t.worker_name,
            runtime_seconds=t.runtime_seconds,
        )
        for t in info["active_tasks"]
    ]

    return WorkerInfoResponse(
        worker_count=info["worker_count"],
        active_tasks=tasks,
    )


@router.get(
    "/jobs-overview",
    response_model=JobsOverviewResponse,
    summary="Cross-matter jobs overview",
    description="List all processing jobs across all matters. Shows queue contention. Admin only.",
)
@limiter.limit(ADMIN_RATE_LIMIT)
async def get_jobs_overview(
    request: Request,
    status_filter: str | None = Query(
        default=None,
        description="Filter by status: QUEUED, PROCESSING, FAILED, COMPLETED",
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Max jobs to return"),
    admin: AuthenticatedUser = Depends(require_admin_access),
) -> JobsOverviewResponse:
    """Get cross-matter job overview for diagnosing queue contention."""
    client = get_service_client()

    try:
        # Query processing_jobs across all matters (service client bypasses RLS)
        query = client.table("processing_jobs").select(
            "id, matter_id, document_id, job_type, status, current_stage, "
            "progress_pct, retry_count, error_message, "
            "created_at, started_at, updated_at"
        )

        if status_filter:
            query = query.eq("status", status_filter.upper())

        # Order: QUEUED first (oldest), then PROCESSING, then rest
        result = query.order("created_at", desc=False).limit(limit).execute()

        rows = result.data or []

        # Compute queue wait time: first stage started_at - job created_at
        job_ids = [r["id"] for r in rows if r.get("started_at")]
        wait_times: dict[str, float] = {}
        if job_ids:
            # Get earliest stage start per job
            stage_query = (
                client.table("job_stage_history")
                .select("job_id, started_at")
                .in_("job_id", job_ids)
                .not_.is_("started_at", "null")
                .order("started_at", desc=False)
                .execute()
            )
            # First started_at per job_id
            for row in stage_query.data or []:
                jid = row["job_id"]
                if jid not in wait_times:
                    from datetime import datetime, timezone

                    try:
                        job_created = next(
                            r["created_at"] for r in rows if r["id"] == jid
                        )
                        created_dt = datetime.fromisoformat(
                            job_created.replace("Z", "+00:00")
                        )
                        started_dt = datetime.fromisoformat(
                            row["started_at"].replace("Z", "+00:00")
                        )
                        wait_times[jid] = max(
                            (started_dt - created_dt).total_seconds(), 0
                        )
                    except (StopIteration, ValueError):
                        pass

        jobs = [
            JobOverviewItem(
                job_id=r["id"],
                matter_id=r["matter_id"],
                document_id=r.get("document_id"),
                job_type=r["job_type"],
                status=r["status"],
                current_stage=r.get("current_stage"),
                progress_pct=r.get("progress_pct", 0),
                retry_count=r.get("retry_count", 0),
                error_message=r.get("error_message"),
                queue_wait_seconds=wait_times.get(r["id"]),
                created_at=r["created_at"],
                started_at=r.get("started_at"),
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

        queued = sum(1 for j in jobs if j.status == "QUEUED")
        processing = sum(1 for j in jobs if j.status == "PROCESSING")

        logger.info(
            "admin_jobs_overview",
            admin_id=admin.id,
            total=len(jobs),
            queued=queued,
            processing=processing,
        )

        return JobsOverviewResponse(
            jobs=jobs,
            total_count=len(jobs),
            queued_count=queued,
            processing_count=processing,
        )

    except Exception as e:
        logger.error("admin_jobs_overview_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "JOBS_OVERVIEW_FAILED",
                    "message": "Failed to retrieve jobs overview",
                    "details": {},
                }
            },
        ) from e


@router.get(
    "/bottleneck-stats",
    response_model=BottleneckStatsResponse,
    summary="Pipeline stage bottleneck analysis",
    description="Shows avg/max duration per pipeline stage to identify bottlenecks. Admin only.",
)
@limiter.limit(ADMIN_RATE_LIMIT)
async def get_bottleneck_stats(
    request: Request,
    hours: int = Query(
        default=24, ge=1, le=168, description="Look back period in hours"
    ),
    admin: AuthenticatedUser = Depends(require_admin_access),
) -> BottleneckStatsResponse:
    """Get stage duration analytics to identify pipeline bottlenecks."""
    from datetime import datetime, timedelta, timezone

    client = get_service_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    try:
        # Get completed and failed stages with timing
        result = (
            client.table("job_stage_history")
            .select("stage_name, status, started_at, completed_at")
            .in_("status", ["COMPLETED", "FAILED"])
            .not_.is_("started_at", "null")
            .gte("started_at", cutoff)
            .execute()
        )

        rows = result.data or []

        # Aggregate by stage_name
        stage_stats: dict[str, dict] = {}
        for row in rows:
            name = row["stage_name"]
            if name not in stage_stats:
                stage_stats[name] = {
                    "durations": [],
                    "total": 0,
                    "failed": 0,
                }

            stage_stats[name]["total"] += 1
            if row["status"] == "FAILED":
                stage_stats[name]["failed"] += 1

            if row.get("completed_at") and row.get("started_at"):
                try:
                    started = datetime.fromisoformat(
                        row["started_at"].replace("Z", "+00:00")
                    )
                    completed = datetime.fromisoformat(
                        row["completed_at"].replace("Z", "+00:00")
                    )
                    duration = max((completed - started).total_seconds(), 0)
                    stage_stats[name]["durations"].append(duration)
                except ValueError:
                    pass

        stages = []
        for name, stats in stage_stats.items():
            durations = stats["durations"]
            avg_dur = sum(durations) / len(durations) if durations else 0
            max_dur = max(durations) if durations else 0

            stages.append(
                BottleneckStage(
                    stage_name=name,
                    avg_duration_seconds=round(avg_dur, 1),
                    max_duration_seconds=round(max_dur, 1),
                    total_runs=stats["total"],
                    failed_runs=stats["failed"],
                )
            )

        # Sort by avg duration descending — slowest stage first
        stages.sort(key=lambda s: s.avg_duration_seconds, reverse=True)

        logger.info(
            "admin_bottleneck_stats",
            admin_id=admin.id,
            hours=hours,
            stages_found=len(stages),
        )

        return BottleneckStatsResponse(stages=stages)

    except Exception as e:
        logger.error("admin_bottleneck_stats_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "BOTTLENECK_STATS_FAILED",
                    "message": "Failed to retrieve bottleneck stats",
                    "details": {},
                }
            },
        ) from e


@router.get(
    "/error-patterns",
    response_model=ErrorPatternsResponse,
    summary="Aggregated error patterns",
    description="Group failed stage errors by message to identify recurring issues. Admin only.",
)
@limiter.limit(ADMIN_RATE_LIMIT)
async def get_error_patterns(
    request: Request,
    hours: int = Query(
        default=24, ge=1, le=168, description="Look back period in hours"
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Max patterns to return"),
    admin: AuthenticatedUser = Depends(require_admin_access),
) -> ErrorPatternsResponse:
    """Get aggregated error patterns from job stage history."""
    from datetime import datetime, timedelta, timezone

    client = get_service_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    try:
        # Source 1: job_stage_history (normal pipeline tasks)
        result = (
            client.table("job_stage_history")
            .select("stage_name, error_message, created_at")
            .eq("status", "FAILED")
            .not_.is_("error_message", "null")
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(500)
            .execute()
        )

        rows = result.data or []

        # Source 2: processing_jobs with errors (chunked processing writes here)
        jobs_result = (
            client.table("processing_jobs")
            .select("current_stage, error_message, updated_at")
            .in_("status", ["FAILED", "PROCESSING"])
            .not_.is_("error_message", "null")
            .gte("updated_at", cutoff)
            .order("updated_at", desc=True)
            .limit(200)
            .execute()
        )

        for job_row in jobs_result.data or []:
            rows.append({
                "stage_name": job_row.get("current_stage") or "chunked_processing",
                "error_message": job_row.get("error_message"),
                "created_at": job_row.get("updated_at"),
            })

        # Group by (truncated error_message, stage_name)
        pattern_map: dict[tuple[str, str], dict] = {}
        for row in rows:
            # Truncate error message to first 200 chars for grouping
            msg = (row.get("error_message") or "")[:200]
            stage = row.get("stage_name", "unknown")
            key = (msg, stage)

            if key not in pattern_map:
                pattern_map[key] = {
                    "error_message": msg,
                    "stage_name": stage,
                    "count": 0,
                    "last_occurred": row.get("created_at", ""),
                }
            pattern_map[key]["count"] += 1

        # Sort by count descending
        patterns = sorted(pattern_map.values(), key=lambda p: p["count"], reverse=True)
        patterns = patterns[:limit]

        return ErrorPatternsResponse(
            patterns=[
                ErrorPattern(
                    error_message=p["error_message"],
                    count=p["count"],
                    stage_name=p["stage_name"],
                    last_occurred=p["last_occurred"],
                )
                for p in patterns
            ],
            total_errors=len(rows),
        )

    except Exception as e:
        logger.error("admin_error_patterns_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "ERROR_PATTERNS_FAILED",
                    "message": "Failed to retrieve error patterns",
                    "details": {},
                }
            },
        ) from e
