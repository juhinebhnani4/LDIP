"""OCR confidence calculator service.

Calculates OCR confidence metrics for documents from bounding box data,
including per-page breakdown and overall quality status determination.
"""

import structlog

from app.core.config import get_settings
from app.models.ocr_confidence import OCRConfidenceResult, PageConfidence
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)


class ConfidenceCalculatorError(Exception):
    """Error during confidence calculation."""


def calculate_document_confidence(document_id: str) -> OCRConfidenceResult:
    """Calculate OCR confidence metrics for a document.

    Queries bounding_boxes table, aggregates confidence per page,
    then calculates overall document confidence.

    Args:
        document_id: UUID of the document to calculate confidence for.

    Returns:
        OCRConfidenceResult with overall confidence, per-page breakdown,
        and quality status determination.

    Raises:
        ConfidenceCalculatorError: If database query fails.
    """
    settings = get_settings()
    supabase = get_supabase_client()

    if not supabase:
        raise ConfidenceCalculatorError("Supabase client not configured")

    logger.info(
        "calculating_document_confidence",
        document_id=document_id,
    )

    try:
        # Get all bounding boxes for document with confidence scores
        response = (
            supabase.table("bounding_boxes")
            .select("page_number, confidence_score")
            .eq("document_id", document_id)
            .execute()
        )
    except Exception as e:
        logger.error(
            "confidence_calculation_db_error",
            document_id=document_id,
            error=str(e),
        )
        raise ConfidenceCalculatorError(f"Database query failed: {e}") from e

    if not response.data:
        logger.info(
            "no_bounding_boxes_found",
            document_id=document_id,
        )
        return OCRConfidenceResult(
            document_id=document_id,
            overall_confidence=None,
            page_confidences=[],
            quality_status=None,
            total_words=0,
        )

    # Group by page and calculate averages
    page_scores: dict[int, list[float]] = {}
    for bbox in response.data:
        page = bbox["page_number"]
        conf = bbox.get("confidence_score")
        if conf is not None:
            if page not in page_scores:
                page_scores[page] = []
            page_scores[page].append(conf)

    if not page_scores:
        # All bounding boxes had null confidence
        return OCRConfidenceResult(
            document_id=document_id,
            overall_confidence=None,
            page_confidences=[],
            quality_status=None,
            total_words=len(response.data),
        )

    # Calculate per-page averages
    page_confidences = [
        PageConfidence(
            page_number=page,
            confidence=sum(scores) / len(scores),
            word_count=len(scores),
        )
        for page, scores in sorted(page_scores.items())
    ]

    # Calculate overall average
    all_scores = [s for scores in page_scores.values() for s in scores]
    overall_confidence = sum(all_scores) / len(all_scores)

    # Determine quality status based on thresholds
    quality_status = _determine_quality_status(overall_confidence, settings)

    logger.info(
        "confidence_calculated",
        document_id=document_id,
        overall_confidence=overall_confidence,
        quality_status=quality_status,
        total_words=len(all_scores),
        page_count=len(page_confidences),
    )

    return OCRConfidenceResult(
        document_id=document_id,
        overall_confidence=overall_confidence,
        page_confidences=page_confidences,
        quality_status=quality_status,
        total_words=len(all_scores),
    )


def _determine_quality_status(confidence: float, settings) -> str:
    """Determine quality status based on confidence thresholds.

    Args:
        confidence: Overall confidence score (0-1).
        settings: Application settings with threshold values.

    Returns:
        Quality status: 'good', 'fair', or 'poor'.
    """
    if confidence >= settings.ocr_quality_good_threshold:
        return "good"
    elif confidence >= settings.ocr_quality_fair_threshold:
        return "fair"
    else:
        return "poor"


def update_document_confidence(document_id: str) -> OCRConfidenceResult:
    """Calculate and update document with OCR confidence metrics.

    Calculates confidence and updates the document record with the results.

    Args:
        document_id: UUID of the document to update.

    Returns:
        OCRConfidenceResult with the calculated metrics.

    Raises:
        ConfidenceCalculatorError: If calculation or update fails.
    """
    supabase = get_supabase_client()

    if not supabase:
        raise ConfidenceCalculatorError("Supabase client not configured")

    # Calculate confidence
    result = calculate_document_confidence(document_id)

    # Prepare update data
    update_data: dict = {
        "ocr_quality_status": result.quality_status,
    }

    # Only update confidence if we have data
    if result.overall_confidence is not None:
        update_data["ocr_confidence"] = result.overall_confidence

    # Store per-page confidences as JSON array
    if result.page_confidences:
        update_data["ocr_confidence_per_page"] = [
            pc.confidence for pc in result.page_confidences
        ]
    else:
        update_data["ocr_confidence_per_page"] = []

    try:
        supabase.table("documents").update(update_data).eq("id", document_id).execute()
        logger.info(
            "document_confidence_updated",
            document_id=document_id,
            quality_status=result.quality_status,
            overall_confidence=result.overall_confidence,
        )
    except Exception as e:
        logger.error(
            "document_confidence_update_failed",
            document_id=document_id,
            error=str(e),
        )
        raise ConfidenceCalculatorError(f"Failed to update document: {e}") from e

    return result
