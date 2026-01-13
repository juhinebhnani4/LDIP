"""Timeline models for date extraction and event management.

Pydantic models for date extraction, event storage, and API responses.
Supports the Timeline Construction Engine for tracking events
extracted from legal documents.

Story 4-1: Date Extraction with Gemini
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


# =============================================================================
# Date Extraction Models
# =============================================================================


class ExtractedDate(BaseModel):
    """Date extracted from document text with context.

    Represents a single date found in a document, including the original
    text, normalized date, surrounding context, and confidence metadata.
    """

    extracted_date: date = Field(..., description="Normalized date in Python date format")
    date_text: str = Field(
        ..., description="Original date text as it appears in document"
    )
    date_precision: Literal["day", "month", "year", "approximate"] = Field(
        ..., description="Precision level of the extracted date"
    )
    context_before: str = Field(
        default="", description="Up to 200 words before the date"
    )
    context_after: str = Field(default="", description="Up to 200 words after the date")
    page_number: int | None = Field(None, description="Page number in source document")
    bbox_ids: list[str] = Field(
        default_factory=list, description="Bounding box UUIDs for highlighting"
    )
    is_ambiguous: bool = Field(
        default=False, description="Whether date format was ambiguous (DD/MM vs MM/DD)"
    )
    ambiguity_reason: str | None = Field(
        None, description="Explanation if date is ambiguous"
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Extraction confidence score",
    )


class DateExtractionResult(BaseModel):
    """Complete result from date extraction process.

    Contains all dates extracted from a document or text chunk,
    along with metadata about the extraction process.
    """

    dates: list[ExtractedDate] = Field(
        default_factory=list, description="List of extracted dates"
    )
    document_id: str = Field(..., description="Source document UUID")
    matter_id: str = Field(..., description="Matter UUID for context")
    total_dates_found: int = Field(
        default=0, description="Total number of dates extracted"
    )
    processing_time_ms: int = Field(
        default=0, description="Processing time in milliseconds"
    )


# =============================================================================
# Event Models (for storing extracted dates)
# =============================================================================


class RawEventBase(BaseModel):
    """Base model for raw timeline events.

    Raw events are dates extracted from documents before classification.
    They have event_type="raw_date" and are later classified in Story 4-2.
    """

    event_date: date = Field(..., description="Event date")
    event_date_precision: Literal["day", "month", "year", "approximate"] = Field(
        default="day", description="Date precision level"
    )
    event_date_text: str | None = Field(
        None, description="Original date text from document"
    )
    description: str = Field(..., description="Context text surrounding the date")
    source_page: int | None = Field(None, description="Source page number")
    source_bbox_ids: list[str] = Field(
        default_factory=list, description="Bounding box UUIDs"
    )
    confidence: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Extraction confidence"
    )


class RawEventCreate(RawEventBase):
    """Model for creating a raw event from date extraction."""

    matter_id: str = Field(..., description="Matter UUID")
    document_id: str | None = Field(None, description="Source document UUID")
    event_type: str = Field(default="raw_date", description="Event type (raw_date)")
    is_ambiguous: bool = Field(default=False, description="Whether date is ambiguous")
    ambiguity_reason: str | None = Field(None, description="Ambiguity explanation")


class RawEvent(RawEventBase):
    """Complete raw event model from database."""

    id: str = Field(..., description="Event UUID")
    matter_id: str = Field(..., description="Matter UUID")
    document_id: str | None = Field(None, description="Source document UUID")
    event_type: str = Field(..., description="Event type")
    entities_involved: list[str] = Field(
        default_factory=list, description="Related entity UUIDs"
    )
    is_manual: bool = Field(default=False, description="Whether manually created")
    created_by: str | None = Field(None, description="Creator user UUID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    # Extended fields for API responses
    document_name: str | None = Field(None, description="Source document name")
    is_ambiguous: bool = Field(default=False, description="Whether date is ambiguous")
    ambiguity_reason: str | None = Field(None, description="Ambiguity explanation")


# =============================================================================
# API Response Models
# =============================================================================


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


class RawDateListItem(BaseModel):
    """Raw date item for list responses."""

    id: str = Field(..., description="Event UUID")
    event_date: date = Field(..., description="Extracted date")
    event_date_precision: str = Field(..., description="Date precision")
    event_date_text: str | None = Field(None, description="Original date text")
    description: str = Field(..., description="Context text")
    document_id: str | None = Field(None, description="Source document UUID")
    source_page: int | None = Field(None, description="Source page number")
    confidence: float = Field(..., description="Extraction confidence")
    is_ambiguous: bool = Field(default=False, description="Whether date is ambiguous")


class RawDatesListResponse(BaseModel):
    """API response for raw dates list endpoint.

    GET /api/matters/{matter_id}/timeline/raw-dates
    """

    data: list[RawDateListItem]
    meta: PaginationMeta


class RawDateDetailResponse(BaseModel):
    """API response for single raw date retrieval.

    GET /api/matters/{matter_id}/timeline/raw-dates/{event_id}
    """

    data: RawEvent


class DateExtractionJobResponse(BaseModel):
    """API response for date extraction job trigger.

    POST /api/matters/{matter_id}/timeline/extract
    """

    data: "DateExtractionJobData"


class DateExtractionJobData(BaseModel):
    """Job data for date extraction."""

    job_id: str = Field(..., description="Job UUID for progress tracking")
    status: str = Field(default="queued", description="Job status")
    documents_to_process: int | None = Field(
        default=None,
        description="Number of documents to process. None for matter-wide extraction "
        "(count determined when task starts).",
    )


# =============================================================================
# Error Models
# =============================================================================


class TimelineErrorDetail(BaseModel):
    """Error detail structure."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict = Field(default_factory=dict, description="Additional error context")


class TimelineErrorResponse(BaseModel):
    """Error response structure."""

    error: TimelineErrorDetail


# Forward reference resolution
DateExtractionJobResponse.model_rebuild()
