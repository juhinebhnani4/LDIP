"""Admin Pipeline API routes for manual task triggering and pipeline management.

Provides admin-only endpoints for:
- Triggering any pipeline task manually
- Retrying failed tasks
- Resetting document status
- Viewing pipeline status
- Reprocessing stuck documents

All endpoints require admin access (configured via ADMIN_EMAILS env var).
"""

from enum import Enum

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from app.api.deps import require_admin_access
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
        .select("id, name, status, matter_id, extracted_text, error_message, updated_at")
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
        client.table("identity_nodes")
        .select("id", count="exact")
        .eq("source_document_id", document_id)
        .execute()
    )
    entities_count = entities_resp.count or 0

    # Build task list based on what's missing
    if doc_status in ("failed", "error", "ocr_failed"):
        # Full reprocess
        celery_app.send_task(
            TASK_MAPPING[PipelineTask.PROCESS_DOCUMENT],
            kwargs={"document_id": document_id},
        )
        tasks_triggered.append("process_document")

    elif has_text and chunks_count == 0:
        # Has text but no chunks - run chunking
        celery_app.send_task(
            TASK_MAPPING[PipelineTask.CHUNK_DOCUMENT],
            kwargs={
                "document_id": document_id,
                "prev_result": {"document_id": document_id, "status": "ocr_complete"},
                "force": True,
            },
        )
        tasks_triggered.append("chunk_document")

    elif chunks_count > 0 and entities_count == 0:
        # Has chunks but no entities - run entity extraction
        celery_app.send_task(
            TASK_MAPPING[PipelineTask.EXTRACT_ENTITIES],
            kwargs={
                "document_id": document_id,
                "prev_result": {"document_id": document_id, "status": "chunking_complete"},
                "force": True,
            },
        )
        tasks_triggered.append("extract_entities")

    if not tasks_triggered:
        return RetryFailedResponse(
            success=True,
            message="No failed tasks detected - document appears complete",
            document_id=document_id,
            tasks_triggered=[],
        )

    return RetryFailedResponse(
        success=True,
        message=f"Triggered {len(tasks_triggered)} task(s) for retry",
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
        client.table("identity_nodes")
        .select("id", count="exact")
        .eq("source_document_id", document_id)
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
