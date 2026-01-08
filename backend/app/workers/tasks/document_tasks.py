"""Celery tasks related to document processing.

Implements OCR processing using Google Document AI with retry logic
and proper status updates. Includes Gemini-based OCR validation.
"""

import structlog
from celery.exceptions import MaxRetriesExceededError

from app.models.document import DocumentStatus
from app.models.ocr_validation import CorrectionType, ValidationStatus
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
from app.services.ocr.confidence_calculator import (
    ConfidenceCalculatorError,
    update_document_confidence,
)
from app.services.ocr.gemini_validator import (
    GeminiOCRValidator,
    GeminiValidatorError,
    get_gemini_validator,
)
from app.services.ocr.human_review_service import (
    HumanReviewService,
    HumanReviewServiceError,
    get_human_review_service,
)
from app.services.ocr.pattern_corrector import apply_pattern_corrections
from app.services.ocr.validation_extractor import (
    ValidationExtractor,
    ValidationExtractorError,
    get_validation_extractor,
)
from app.services.pubsub_service import broadcast_document_status
from app.services.storage_service import StorageError, StorageService, get_storage_service
from app.workers.celery import celery_app

logger = structlog.get_logger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAYS = [30, 60, 120]  # Exponential backoff: 30s, 60s, 120s

# PDF magic bytes signature
PDF_MAGIC_BYTES = b"%PDF-"


def _validate_pdf_content(content: bytes, document_id: str) -> None:
    """Validate that content appears to be a PDF file.

    Args:
        content: File content bytes.
        document_id: Document ID for logging.

    Raises:
        OCRServiceError: If content is not a valid PDF.
    """
    if not content.startswith(PDF_MAGIC_BYTES):
        logger.error(
            "document_invalid_pdf",
            document_id=document_id,
            first_bytes=content[:20].hex() if content else "empty",
        )
        raise OCRServiceError(
            message="File does not appear to be a valid PDF",
            code="INVALID_PDF_FORMAT",
            is_retryable=False,
        )


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

        # Validate PDF format before sending to OCR
        _validate_pdf_content(pdf_content, document_id)

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


@celery_app.task(
    name="app.workers.tasks.document_tasks.validate_ocr",
    bind=True,
    autoretry_for=(GeminiValidatorError, ValidationExtractorError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=MAX_RETRIES,
    retry_jitter=True,
)  # type: ignore[misc]
def validate_ocr(
    self,  # type: ignore[no-untyped-def]
    prev_result: dict[str, str | int | float | None] | None = None,
    document_id: str | None = None,
    validation_extractor: ValidationExtractor | None = None,
    gemini_validator: GeminiOCRValidator | None = None,
    human_review_service: HumanReviewService | None = None,
    document_service: DocumentService | None = None,
    bounding_box_service: BoundingBoxService | None = None,
) -> dict[str, str | int | float | None]:
    """Validate OCR results using pattern correction and Gemini.

    This task runs after process_document to validate low-confidence words.
    It applies pattern corrections first, then uses Gemini for remaining
    low-confidence words, and queues very low confidence words for human review.

    Args:
        prev_result: Result from previous task in chain (contains document_id).
        document_id: Document UUID (optional, can be in prev_result).
        validation_extractor: Optional ValidationExtractor instance (for testing).
        gemini_validator: Optional GeminiOCRValidator instance (for testing).
        human_review_service: Optional HumanReviewService instance (for testing).
        document_service: Optional DocumentService instance (for testing).
        bounding_box_service: Optional BoundingBoxService instance (for testing).

    Returns:
        Task result with validation summary.

    Raises:
        GeminiValidatorError: If Gemini validation fails (will trigger retry).
        ValidationExtractorError: If extraction fails (will trigger retry).
    """
    # Get document_id from prev_result or parameter
    doc_id = document_id
    if doc_id is None and prev_result:
        doc_id = prev_result.get("document_id")  # type: ignore[assignment]

    if not doc_id:
        logger.error("validate_ocr_no_document_id")
        return {
            "status": "validation_failed",
            "error_code": "NO_DOCUMENT_ID",
            "error_message": "No document_id provided",
        }

    # Check if OCR was successful
    if prev_result and prev_result.get("status") != "ocr_complete":
        logger.info(
            "validate_ocr_skipped_ocr_not_complete",
            document_id=doc_id,
            ocr_status=prev_result.get("status"),
        )
        return {
            "status": "validation_skipped",
            "document_id": doc_id,
            "reason": "OCR not complete",
        }

    # Use injected services or get defaults
    extractor = validation_extractor or get_validation_extractor()
    gemini = gemini_validator or get_gemini_validator()
    human_review = human_review_service or get_human_review_service()
    doc_service = document_service or get_document_service()
    bbox_service = bounding_box_service or get_bounding_box_service()

    logger.info(
        "validate_ocr_task_started",
        document_id=doc_id,
        retry_count=self.request.retries,
    )

    try:
        # Get matter_id for the document
        _, matter_id = doc_service.get_document_for_processing(doc_id)

        # Step 1: Extract low-confidence words
        words_for_gemini, words_for_human = extractor.extract_low_confidence_words(doc_id)

        total_low_confidence = len(words_for_gemini) + len(words_for_human)

        if total_low_confidence == 0:
            # No validation needed - update status and return
            _update_validation_status(doc_service, doc_id, ValidationStatus.VALIDATED)
            logger.info(
                "validate_ocr_no_low_confidence_words",
                document_id=doc_id,
            )
            return {
                "status": "validated",
                "document_id": doc_id,
                "validation_status": "validated",
                "total_validated": 0,
                "pattern_corrections": 0,
                "gemini_corrections": 0,
                "human_review_queued": 0,
            }

        # Step 2: Apply pattern corrections first
        pattern_results, remaining_for_gemini = apply_pattern_corrections(words_for_gemini)

        # Step 3: Validate remaining words with Gemini
        gemini_results = []
        if remaining_for_gemini:
            try:
                gemini_results = gemini.validate_batch_sync(remaining_for_gemini)
            except GeminiValidatorError as e:
                logger.warning(
                    "validate_ocr_gemini_failed",
                    document_id=doc_id,
                    error=str(e),
                )
                # Continue with pattern results only if Gemini fails
                # but re-raise if retryable
                if e.is_retryable:
                    raise

        # Step 4: Queue very low confidence words for human review
        human_review_count = 0
        if words_for_human:
            human_review_count = human_review.add_to_queue(
                document_id=doc_id,
                matter_id=matter_id,
                words=words_for_human,
            )

        # Step 5: Apply corrections to bounding boxes and log
        all_results = pattern_results + gemini_results
        corrections_applied = _apply_validation_results(
            bbox_service=bbox_service,
            doc_service=doc_service,
            document_id=doc_id,
            results=all_results,
        )

        # Step 6: Update document validation status
        final_status = ValidationStatus.VALIDATED
        if human_review_count > 0:
            final_status = ValidationStatus.REQUIRES_HUMAN_REVIEW

        _update_validation_status(doc_service, doc_id, final_status)

        # Count corrections by type
        pattern_count = sum(
            1 for r in all_results
            if r.was_corrected and r.correction_type == CorrectionType.PATTERN
        )
        gemini_count = sum(
            1 for r in all_results
            if r.was_corrected and r.correction_type == CorrectionType.GEMINI
        )

        logger.info(
            "validate_ocr_task_completed",
            document_id=doc_id,
            total_validated=len(all_results),
            pattern_corrections=pattern_count,
            gemini_corrections=gemini_count,
            human_review_queued=human_review_count,
            validation_status=final_status.value,
        )

        # Broadcast validation status
        broadcast_document_status(
            matter_id=matter_id,
            document_id=doc_id,
            status="validation_complete",
            validation_status=final_status.value,
        )

        return {
            "status": "validated",
            "document_id": doc_id,
            "validation_status": final_status.value,
            "total_validated": len(all_results),
            "pattern_corrections": pattern_count,
            "gemini_corrections": gemini_count,
            "human_review_queued": human_review_count,
            "corrections_applied": corrections_applied,
        }

    except (GeminiValidatorError, ValidationExtractorError) as e:
        retry_count = self.request.retries

        logger.warning(
            "validate_ocr_task_retry",
            document_id=doc_id,
            retry_count=retry_count,
            max_retries=MAX_RETRIES,
            error=str(e),
            error_code=getattr(e, "code", "UNKNOWN"),
        )

        if retry_count >= MAX_RETRIES:
            return _handle_validation_failure(doc_service, doc_id, e)

        raise

    except HumanReviewServiceError as e:
        # Human review errors are not critical - log and continue
        logger.warning(
            "validate_ocr_human_review_failed",
            document_id=doc_id,
            error=str(e),
        )
        # Don't fail the whole task for human review issues
        return {
            "status": "validated_with_warnings",
            "document_id": doc_id,
            "warning": "Human review queue failed",
            "error_message": str(e),
        }

    except DocumentServiceError as e:
        logger.error(
            "validate_ocr_document_service_error",
            document_id=doc_id,
            error=str(e),
        )
        return _handle_validation_failure(doc_service, doc_id, e)

    except Exception as e:
        logger.error(
            "validate_ocr_unexpected_error",
            document_id=doc_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return _handle_validation_failure(doc_service, doc_id, e)


def _apply_validation_results(
    bbox_service: BoundingBoxService,
    doc_service: DocumentService,
    document_id: str,
    results: list,
) -> int:
    """Apply validation results to bounding boxes and log corrections.

    Args:
        bbox_service: BoundingBoxService instance.
        doc_service: DocumentService instance.
        document_id: Document UUID.
        results: List of ValidationResult.

    Returns:
        Number of corrections applied.
    """
    from app.services.supabase.client import get_service_client

    client = get_service_client()
    if client is None:
        return 0

    corrections_applied = 0

    for result in results:
        if not result.was_corrected:
            continue

        try:
            # Update bounding box with corrected text
            if result.bbox_id:
                client.table("bounding_boxes").update({
                    "text": result.corrected,
                    "confidence": result.new_confidence,
                }).eq("id", result.bbox_id).execute()

            # Log the correction
            client.table("ocr_validation_log").insert({
                "document_id": document_id,
                "bbox_id": result.bbox_id if result.bbox_id else None,
                "original_text": result.original,
                "corrected_text": result.corrected,
                "old_confidence": result.old_confidence,
                "new_confidence": result.new_confidence,
                "validation_type": result.correction_type.value if result.correction_type else "pattern",
                "reasoning": result.reasoning,
            }).execute()

            corrections_applied += 1

        except Exception as e:
            logger.warning(
                "validate_ocr_apply_result_failed",
                document_id=document_id,
                bbox_id=result.bbox_id,
                error=str(e),
            )

    return corrections_applied


def _update_validation_status(
    doc_service: DocumentService,
    document_id: str,
    status: ValidationStatus,
) -> None:
    """Update document validation status.

    Args:
        doc_service: DocumentService instance.
        document_id: Document UUID.
        status: New validation status.
    """
    from app.services.supabase.client import get_service_client

    client = get_service_client()
    if client is None:
        return

    try:
        client.table("documents").update({
            "validation_status": status.value,
        }).eq("id", document_id).execute()
    except Exception as e:
        logger.warning(
            "validate_ocr_status_update_failed",
            document_id=document_id,
            status=status.value,
            error=str(e),
        )


def _handle_validation_failure(
    doc_service: DocumentService,
    document_id: str,
    error: Exception,
) -> dict[str, str]:
    """Handle validation task failure.

    Args:
        doc_service: DocumentService instance.
        document_id: Document UUID.
        error: The error that caused the failure.

    Returns:
        Task result indicating failure.
    """
    error_code = getattr(error, "code", "VALIDATION_FAILED")
    error_message = str(error)

    logger.error(
        "validate_ocr_task_failed",
        document_id=document_id,
        error=error_message,
        error_code=error_code,
    )

    # Update status to indicate validation is pending (not failed OCR)
    # The document OCR is still valid, just validation couldn't complete
    _update_validation_status(
        doc_service,
        document_id,
        ValidationStatus.PENDING,
    )

    return {
        "status": "validation_failed",
        "document_id": document_id,
        "error_code": error_code,
        "error_message": error_message,
    }


@celery_app.task(
    name="app.workers.tasks.document_tasks.calculate_confidence",
    bind=True,
    autoretry_for=(ConfidenceCalculatorError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=2,
    retry_jitter=True,
)  # type: ignore[misc]
def calculate_confidence(
    self,  # type: ignore[no-untyped-def]
    prev_result: dict[str, str | int | float | None] | None = None,
    document_id: str | None = None,
    document_service: DocumentService | None = None,
) -> dict[str, str | int | float | None]:
    """Calculate and store OCR confidence metrics for a document.

    This task runs after validate_ocr to calculate overall and per-page
    confidence metrics, determine quality status, and update the document.

    Args:
        prev_result: Result from previous task in chain (contains document_id).
        document_id: Document UUID (optional, can be in prev_result).
        document_service: Optional DocumentService instance (for testing).

    Returns:
        Task result with confidence metrics.

    Raises:
        ConfidenceCalculatorError: If calculation fails (will trigger retry).
    """
    # Get document_id from prev_result or parameter
    doc_id = document_id
    if doc_id is None and prev_result:
        doc_id = prev_result.get("document_id")  # type: ignore[assignment]

    if not doc_id:
        logger.error("calculate_confidence_no_document_id")
        return {
            "status": "confidence_failed",
            "error_code": "NO_DOCUMENT_ID",
            "error_message": "No document_id provided",
        }

    # Skip if OCR/validation wasn't successful
    if prev_result:
        prev_status = prev_result.get("status")
        if prev_status not in ("validated", "validated_with_warnings", "validation_skipped"):
            logger.info(
                "calculate_confidence_skipped",
                document_id=doc_id,
                prev_status=prev_status,
            )
            return {
                "status": "confidence_skipped",
                "document_id": doc_id,
                "reason": f"Previous task status: {prev_status}",
            }

    doc_service = document_service or get_document_service()

    logger.info(
        "calculate_confidence_task_started",
        document_id=doc_id,
        retry_count=self.request.retries,
    )

    try:
        # Get matter_id for broadcasting
        _, matter_id = doc_service.get_document_for_processing(doc_id)

        # Calculate and update confidence metrics
        result = update_document_confidence(doc_id)

        logger.info(
            "calculate_confidence_task_completed",
            document_id=doc_id,
            overall_confidence=result.overall_confidence,
            quality_status=result.quality_status,
            total_words=result.total_words,
            page_count=len(result.page_confidences),
        )

        # Broadcast confidence update
        broadcast_document_status(
            matter_id=matter_id,
            document_id=doc_id,
            status="confidence_calculated",
            ocr_confidence=result.overall_confidence,
            quality_status=result.quality_status,
        )

        return {
            "status": "confidence_calculated",
            "document_id": doc_id,
            "overall_confidence": result.overall_confidence,
            "quality_status": result.quality_status,
            "total_words": result.total_words,
            "page_count": len(result.page_confidences),
        }

    except ConfidenceCalculatorError as e:
        retry_count = self.request.retries

        logger.warning(
            "calculate_confidence_task_retry",
            document_id=doc_id,
            retry_count=retry_count,
            max_retries=2,
            error=str(e),
        )

        if retry_count >= 2:
            logger.error(
                "calculate_confidence_task_failed",
                document_id=doc_id,
                error=str(e),
            )
            return {
                "status": "confidence_failed",
                "document_id": doc_id,
                "error_code": "CONFIDENCE_CALCULATION_FAILED",
                "error_message": str(e),
            }

        raise

    except DocumentServiceError as e:
        logger.error(
            "calculate_confidence_document_error",
            document_id=doc_id,
            error=str(e),
        )
        return {
            "status": "confidence_failed",
            "document_id": doc_id,
            "error_code": e.code,
            "error_message": e.message,
        }

    except Exception as e:
        logger.error(
            "calculate_confidence_unexpected_error",
            document_id=doc_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "status": "confidence_failed",
            "document_id": doc_id,
            "error_code": "UNEXPECTED_ERROR",
            "error_message": str(e),
        }
