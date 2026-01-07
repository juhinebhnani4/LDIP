"""Celery tasks related to document processing.

Implements OCR processing using Google Document AI with retry logic
and proper status updates.
"""

import structlog
from celery.exceptions import MaxRetriesExceededError

from app.models.document import DocumentStatus
from app.services.bounding_box_service import (
    BoundingBoxService,
    get_bounding_box_service,
)
from app.services.document_service import (
    DocumentService,
    DocumentServiceError,
    get_document_service,
)
from app.services.ocr import OCRProcessor, OCRServiceError, get_ocr_processor
from app.services.pubsub_service import broadcast_document_status
from app.services.storage_service import StorageError, StorageService, get_storage_service
from app.workers.celery import celery_app

logger = structlog.get_logger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAYS = [30, 60, 120]  # Exponential backoff: 30s, 60s, 120s


@celery_app.task(
    name="app.workers.tasks.document_tasks.process_document",
    bind=True,
    autoretry_for=(OCRServiceError, StorageError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=MAX_RETRIES,
    retry_jitter=True,
)  # type: ignore[misc]
def process_document(
    self,  # type: ignore[no-untyped-def]
    document_id: str,
    document_service: DocumentService | None = None,
    storage_service: StorageService | None = None,
    ocr_processor: OCRProcessor | None = None,
    bounding_box_service: BoundingBoxService | None = None,
) -> dict[str, str | int | float | None]:
    """Process a document through OCR pipeline.

    Downloads PDF from Supabase Storage, processes with Google Document AI,
    and saves extracted text and bounding boxes.

    Args:
        document_id: Document UUID to process.
        document_service: Optional DocumentService instance (for testing).
        storage_service: Optional StorageService instance (for testing).
        ocr_processor: Optional OCRProcessor instance (for testing).
        bounding_box_service: Optional BoundingBoxService instance (for testing).

    Returns:
        Task result with status, page_count, and processing details.

    Raises:
        OCRServiceError: If OCR processing fails (will trigger retry).
        StorageError: If storage operations fail (will trigger retry).
    """
    # Use injected services or get defaults
    doc_service = document_service or get_document_service()
    store_service = storage_service or get_storage_service()
    ocr = ocr_processor or get_ocr_processor()
    bbox_service = bounding_box_service or get_bounding_box_service()

    logger.info(
        "document_processing_task_started",
        document_id=document_id,
        retry_count=self.request.retries,
    )

    try:
        # Get document info
        storage_path, matter_id = doc_service.get_document_for_processing(document_id)

        # Update status to processing
        doc_service.update_ocr_status(
            document_id=document_id,
            status=DocumentStatus.PROCESSING,
        )

        # Broadcast status change
        broadcast_document_status(
            matter_id=matter_id,
            document_id=document_id,
            status="processing",
        )

        # Download PDF from storage
        logger.info(
            "document_downloading",
            document_id=document_id,
            storage_path=storage_path,
        )
        pdf_content = store_service.download_file(storage_path)

        # Process with OCR
        logger.info(
            "document_ocr_processing",
            document_id=document_id,
            content_size=len(pdf_content),
        )
        ocr_result = ocr.process_document(
            pdf_content=pdf_content,
            document_id=document_id,
        )

        # Save bounding boxes
        logger.info(
            "document_saving_bounding_boxes",
            document_id=document_id,
            bbox_count=len(ocr_result.bounding_boxes),
        )

        # Delete any existing bounding boxes (in case of reprocessing)
        bbox_service.delete_bounding_boxes(document_id)

        # Save new bounding boxes
        saved_bbox_count = bbox_service.save_bounding_boxes(
            document_id=document_id,
            matter_id=matter_id,
            bounding_boxes=ocr_result.bounding_boxes,
        )

        # Calculate average quality score from pages
        avg_quality_score = None
        quality_scores = [
            p.image_quality_score
            for p in ocr_result.pages
            if p.image_quality_score is not None
        ]
        if quality_scores:
            avg_quality_score = sum(quality_scores) / len(quality_scores)

        # Update document with OCR results
        doc_service.update_ocr_status(
            document_id=document_id,
            status=DocumentStatus.OCR_COMPLETE,
            extracted_text=ocr_result.full_text,
            page_count=ocr_result.page_count,
            ocr_confidence=ocr_result.overall_confidence,
            ocr_quality_score=avg_quality_score,
        )

        # Broadcast completion status
        broadcast_document_status(
            matter_id=matter_id,
            document_id=document_id,
            status="ocr_complete",
            page_count=ocr_result.page_count,
            ocr_confidence=ocr_result.overall_confidence,
        )

        logger.info(
            "document_processing_task_completed",
            document_id=document_id,
            page_count=ocr_result.page_count,
            bbox_count=saved_bbox_count,
            processing_time_ms=ocr_result.processing_time_ms,
            overall_confidence=ocr_result.overall_confidence,
        )

        return {
            "status": "ocr_complete",
            "document_id": document_id,
            "page_count": ocr_result.page_count,
            "bbox_count": saved_bbox_count,
            "processing_time_ms": ocr_result.processing_time_ms,
            "overall_confidence": ocr_result.overall_confidence,
        }

    except (OCRServiceError, StorageError) as e:
        # Handle retryable errors
        retry_count = self.request.retries

        logger.warning(
            "document_processing_task_retry",
            document_id=document_id,
            retry_count=retry_count,
            max_retries=MAX_RETRIES,
            error=str(e),
            error_code=getattr(e, "code", "UNKNOWN"),
        )

        # Increment retry count in database
        try:
            doc_service.increment_ocr_retry_count(document_id)
        except DocumentServiceError:
            pass  # Don't fail the retry because of this

        # Check if we've exhausted retries
        # Note: matter_id may not be available if it failed before retrieval
        if retry_count >= MAX_RETRIES:
            _matter_id = None
            try:
                _, _matter_id = doc_service.get_document_for_processing(document_id)
            except Exception:
                pass
            return _handle_max_retries_exceeded(doc_service, document_id, e, _matter_id)

        # Re-raise to trigger retry
        raise

    except MaxRetriesExceededError as e:
        _matter_id = None
        try:
            _, _matter_id = doc_service.get_document_for_processing(document_id)
        except Exception:
            pass
        return _handle_max_retries_exceeded(
            doc_service, document_id, e.__cause__ or e, _matter_id
        )

    except DocumentServiceError as e:
        # Document service errors are not retryable
        logger.error(
            "document_processing_task_failed",
            document_id=document_id,
            error=str(e),
            error_code=e.code,
        )

        try:
            doc_service.update_ocr_status(
                document_id=document_id,
                status=DocumentStatus.OCR_FAILED,
                ocr_error=f"{e.code}: {e.message}",
            )
        except DocumentServiceError:
            pass

        return {
            "status": "ocr_failed",
            "document_id": document_id,
            "error_code": e.code,
            "error_message": e.message,
        }

    except Exception as e:
        # Unexpected errors
        logger.error(
            "document_processing_task_unexpected_error",
            document_id=document_id,
            error=str(e),
            error_type=type(e).__name__,
        )

        try:
            doc_service.update_ocr_status(
                document_id=document_id,
                status=DocumentStatus.OCR_FAILED,
                ocr_error=f"Unexpected error: {e!s}",
            )
        except DocumentServiceError:
            pass

        return {
            "status": "ocr_failed",
            "document_id": document_id,
            "error_code": "UNEXPECTED_ERROR",
            "error_message": str(e),
        }


def _handle_max_retries_exceeded(
    doc_service: DocumentService,
    document_id: str,
    error: Exception,
    matter_id: str | None = None,
) -> dict[str, str]:
    """Handle the case when max retries have been exceeded.

    Args:
        doc_service: DocumentService instance.
        document_id: Document UUID.
        error: The error that caused the failure.
        matter_id: Optional matter UUID for broadcasting.

    Returns:
        Task result indicating failure.
    """
    error_code = getattr(error, "code", "MAX_RETRIES_EXCEEDED")
    error_message = str(error)

    logger.error(
        "document_processing_task_max_retries",
        document_id=document_id,
        error=error_message,
        error_code=error_code,
    )

    try:
        doc_service.update_ocr_status(
            document_id=document_id,
            status=DocumentStatus.OCR_FAILED,
            ocr_error=f"Max retries exceeded ({MAX_RETRIES}): {error_message}",
        )
    except DocumentServiceError as e:
        logger.error(
            "document_processing_task_status_update_failed",
            document_id=document_id,
            error=str(e),
        )

    # Broadcast failure status
    if matter_id:
        broadcast_document_status(
            matter_id=matter_id,
            document_id=document_id,
            status="ocr_failed",
            error_message=f"Max retries exceeded: {error_message}",
        )

    return {
        "status": "ocr_failed",
        "document_id": document_id,
        "error_code": error_code,
        "error_message": f"Max retries exceeded: {error_message}",
    }


@celery_app.task(name="app.workers.tasks.document_tasks.retry_ocr")  # type: ignore[misc]
def retry_ocr(document_id: str) -> dict[str, str]:
    """Manually retry OCR for a failed document.

    Resets retry count and requeues the document for processing.

    Args:
        document_id: Document UUID to retry.

    Returns:
        Task submission result.
    """
    logger.info("document_manual_retry_requested", document_id=document_id)

    doc_service = get_document_service()

    try:
        # Reset the document status to pending
        doc_service.update_ocr_status(
            document_id=document_id,
            status=DocumentStatus.PENDING,
            ocr_error=None,  # Clear previous error
        )

        # Queue for processing
        process_document.delay(document_id)

        logger.info("document_manual_retry_queued", document_id=document_id)

        return {
            "status": "queued",
            "document_id": document_id,
            "message": "Document queued for OCR retry",
        }

    except DocumentServiceError as e:
        logger.error(
            "document_manual_retry_failed",
            document_id=document_id,
            error=str(e),
        )
        return {
            "status": "failed",
            "document_id": document_id,
            "error": e.message,
        }
