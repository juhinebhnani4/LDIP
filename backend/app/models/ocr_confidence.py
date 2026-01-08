"""OCR confidence result models for quality assessment.

Models for calculating and representing OCR confidence metrics
at document and page level for quality assessment display.
"""

from pydantic import BaseModel, Field


class PageConfidence(BaseModel):
    """Confidence metrics for a single page."""

    page_number: int = Field(..., ge=1, description="Page number (1-indexed)")
    confidence: float = Field(..., ge=0, le=1, description="Average confidence for the page")
    word_count: int = Field(..., ge=0, description="Number of words/bounding boxes on this page")


class OCRConfidenceResult(BaseModel):
    """Complete OCR confidence result for a document.

    Contains overall confidence metrics and per-page breakdown
    for quality assessment display.
    """

    document_id: str = Field(..., description="Document UUID")
    overall_confidence: float | None = Field(
        None, ge=0, le=1,
        description="Average OCR confidence across all words"
    )
    page_confidences: list[PageConfidence] = Field(
        default_factory=list,
        description="Per-page confidence breakdown"
    )
    quality_status: str | None = Field(
        None,
        description="Quality level: 'good' (>85%), 'fair' (70-85%), 'poor' (<70%)"
    )
    total_words: int = Field(
        default=0, ge=0,
        description="Total word count across all pages"
    )


class OCRQualityResponse(BaseModel):
    """API response for OCR quality endpoint."""

    data: OCRConfidenceResult
