"""OCR result models for document processing.

Models for Google Document AI OCR results including pages, bounding boxes,
and processing status.
"""

from enum import Enum

from pydantic import BaseModel, Field


class OCRStatus(str, Enum):
    """OCR processing status.

    States:
    - pending: Awaiting OCR processing
    - processing: OCR in progress
    - ocr_complete: Successfully processed
    - ocr_failed: Processing failed
    """

    PENDING = "pending"
    PROCESSING = "processing"
    OCR_COMPLETE = "ocr_complete"
    OCR_FAILED = "ocr_failed"


class OCRBoundingBox(BaseModel):
    """Bounding box for OCR text positioning.

    Coordinates are percentage-based (0-100) for responsive rendering.
    """

    page: int = Field(..., ge=1, description="Page number (1-indexed)")
    x: float = Field(..., ge=0, le=100, description="X coordinate (percentage)")
    y: float = Field(..., ge=0, le=100, description="Y coordinate (percentage)")
    width: float = Field(..., ge=0, le=100, description="Width (percentage)")
    height: float = Field(..., ge=0, le=100, description="Height (percentage)")
    text: str = Field(..., description="OCR-extracted text content")
    confidence: float | None = Field(
        None, ge=0, le=1, description="OCR confidence score (0-1)"
    )


class OCRPage(BaseModel):
    """OCR result for a single page."""

    page_number: int = Field(..., ge=1, description="Page number (1-indexed)")
    text: str = Field(default="", description="Full extracted text for the page")
    confidence: float | None = Field(
        None, ge=0, le=1, description="Average confidence for the page"
    )
    image_quality_score: float | None = Field(
        None, ge=0, le=1, description="Image quality score from Document AI"
    )


class OCRResult(BaseModel):
    """Complete OCR result for a document."""

    document_id: str = Field(..., description="Document UUID")
    pages: list[OCRPage] = Field(default_factory=list, description="Per-page results")
    bounding_boxes: list[OCRBoundingBox] = Field(
        default_factory=list, description="All bounding boxes"
    )
    full_text: str = Field(default="", description="Full document text")
    overall_confidence: float | None = Field(
        None, ge=0, le=1, description="Average confidence across all pages"
    )
    processing_time_ms: int | None = Field(
        None, ge=0, description="Processing time in milliseconds"
    )
    page_count: int = Field(default=0, ge=0, description="Total number of pages")


class OCRError(BaseModel):
    """OCR error details."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    retry_count: int = Field(default=0, ge=0, description="Number of retry attempts")
    is_retryable: bool = Field(
        default=True, description="Whether the error is retryable"
    )
