"""Timeline models for date extraction and event management.

Pydantic models for date extraction, event storage, and API responses.
Supports the Timeline Construction Engine for tracking events
extracted from legal documents.

Story 4-1: Date Extraction with Gemini
Story 4-2: Event Classification
"""

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

# =============================================================================
# Event Type Enum (Story 4-2)
# =============================================================================


class EventType(str, Enum):
    """Event types for timeline classification.

    Raw dates are initially stored as RAW_DATE, then classified
    into specific event types by the EventClassifier.
    """

    FILING = "filing"
    NOTICE = "notice"
    HEARING = "hearing"
    ORDER = "order"
    TRANSACTION = "transaction"
    DOCUMENT = "document"
    DEADLINE = "deadline"
    UNCLASSIFIED = "unclassified"
    RAW_DATE = "raw_date"


# =============================================================================
# Event Classification Models (Story 4-2)
# =============================================================================


class SecondaryTypeScore(BaseModel):
    """Secondary event type with confidence score."""

    type: EventType
    confidence: float = Field(ge=0.0, le=1.0)


class EventClassificationResult(BaseModel):
    """Result from classifying a single event.

    Contains the primary classification and metadata about
    how the classification was determined.
    """

    event_id: str = Field(..., description="Event UUID that was classified")
    event_type: EventType = Field(..., description="Classified event type")
    classification_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score for classification"
    )
    secondary_types: list[SecondaryTypeScore] = Field(
        default_factory=list, description="Alternative classifications with scores"
    )
    keywords_matched: list[str] = Field(
        default_factory=list, description="Keywords that matched for classification"
    )
    classification_reasoning: str | None = Field(
        None, description="LLM explanation for the classification"
    )


class ClassifiedEvent(BaseModel):
    """A fully classified timeline event.

    Extends RawEvent with classification data. Used for API responses
    after events have been classified.
    """

    id: str = Field(..., description="Event UUID")
    matter_id: str = Field(..., description="Matter UUID")
    document_id: str | None = Field(None, description="Source document UUID")
    event_date: date = Field(..., description="Event date")
    event_date_precision: Literal["day", "month", "year", "approximate"] = Field(
        default="day", description="Date precision level"
    )
    event_date_text: str | None = Field(
        None, description="Original date text from document"
    )
    event_type: EventType = Field(..., description="Classified event type")
    description: str = Field(..., description="Context text surrounding the date")
    classification_confidence: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Classification confidence"
    )
    source_page: int | None = Field(None, description="Source page number")
    source_bbox_ids: list[str] = Field(
        default_factory=list, description="Bounding box UUIDs"
    )
    verified: bool = Field(
        default=False, description="Whether event has been manually verified"
    )
    is_manual: bool = Field(default=False, description="Whether manually created")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


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


# =============================================================================
# Event Classification API Models (Story 4-2)
# =============================================================================


class EventClassificationListItem(BaseModel):
    """Event item for classified events list responses."""

    id: str = Field(..., description="Event UUID")
    event_date: date = Field(..., description="Event date")
    event_date_precision: str = Field(..., description="Date precision")
    event_date_text: str | None = Field(None, description="Original date text")
    event_type: str = Field(..., description="Classified event type")
    description: str = Field(..., description="Context text")
    classification_confidence: float = Field(
        ..., description="Classification confidence"
    )
    document_id: str | None = Field(None, description="Source document UUID")
    source_page: int | None = Field(None, description="Source page number")
    verified: bool = Field(default=False, description="Whether verified")


class ClassifiedEventsListResponse(BaseModel):
    """API response for classified events list endpoint.

    GET /api/matters/{matter_id}/timeline/events
    """

    data: list[EventClassificationListItem]
    meta: PaginationMeta


class UnclassifiedEventItem(BaseModel):
    """Event item for unclassified events list responses.

    Includes suggested types for manual classification.
    """

    id: str = Field(..., description="Event UUID")
    event_date: date = Field(..., description="Event date")
    event_type: str = Field(..., description="Current event type (unclassified)")
    description: str = Field(..., description="Context text")
    classification_confidence: float = Field(..., description="Confidence score")
    suggested_types: list[SecondaryTypeScore] = Field(
        default_factory=list, description="Suggested event types for manual selection"
    )
    document_id: str | None = Field(None, description="Source document UUID")


class UnclassifiedEventsResponse(BaseModel):
    """API response for unclassified events endpoint.

    GET /api/matters/{matter_id}/timeline/unclassified
    """

    data: list[UnclassifiedEventItem]
    meta: PaginationMeta


class ClassificationJobData(BaseModel):
    """Job data for event classification."""

    job_id: str = Field(..., description="Job UUID for progress tracking")
    status: str = Field(default="queued", description="Job status")
    events_to_classify: int = Field(..., description="Number of events to classify")


class ClassificationJobResponse(BaseModel):
    """API response for classification job trigger.

    POST /api/matters/{matter_id}/timeline/classify
    """

    data: ClassificationJobData


class ManualClassificationRequest(BaseModel):
    """Request body for manual event classification.

    PATCH /api/matters/{matter_id}/timeline/events/{event_id}
    """

    event_type: EventType = Field(..., description="New event type")


class ManualClassificationResponse(BaseModel):
    """Response for manual classification update."""

    data: ClassifiedEvent


# =============================================================================
# Entity Linking API Models (Story 4-3)
# =============================================================================


class EntityReference(BaseModel):
    """Lightweight entity reference for timeline events."""

    entity_id: str = Field(..., description="Entity UUID")
    canonical_name: str = Field(..., description="Entity canonical name")
    entity_type: str = Field(..., description="Entity type (PERSON, ORG, etc.)")
    role: str | None = Field(None, description="Entity role in matter")


class TimelineEventWithEntities(BaseModel):
    """Timeline event enriched with entity information."""

    id: str = Field(..., description="Event UUID")
    event_date: date = Field(..., description="Event date")
    event_date_precision: str = Field(..., description="Date precision")
    event_date_text: str | None = Field(None, description="Original date text")
    event_type: str = Field(..., description="Event type")
    description: str = Field(..., description="Event description")
    document_id: str | None = Field(None, description="Source document UUID")
    source_page: int | None = Field(None, description="Source page number")
    confidence: float = Field(..., description="Classification confidence")
    entities: list[EntityReference] = Field(
        default_factory=list, description="Linked entities"
    )
    is_ambiguous: bool = Field(default=False, description="Whether date is ambiguous")
    is_verified: bool = Field(default=False, description="Whether manually verified")
    is_manual: bool = Field(default=False, description="Whether manually created")


class TimelineWithEntitiesResponse(BaseModel):
    """API response for timeline with entity information.

    GET /api/matters/{matter_id}/timeline/full
    """

    data: list[TimelineEventWithEntities]
    meta: PaginationMeta


class TimelineStatisticsData(BaseModel):
    """Statistics about a matter's timeline."""

    total_events: int = Field(..., description="Total number of events")
    events_by_type: dict[str, int] = Field(
        default_factory=dict, description="Event count by type"
    )
    entities_involved: int = Field(..., description="Number of unique entities")
    date_range_start: date | None = Field(None, description="Earliest event date")
    date_range_end: date | None = Field(None, description="Latest event date")
    events_with_entities: int = Field(..., description="Events with entity links")
    events_without_entities: int = Field(..., description="Events without entity links")
    verified_events: int = Field(..., description="Manually verified events")


class TimelineStatisticsResponse(BaseModel):
    """API response for timeline statistics.

    GET /api/matters/{matter_id}/timeline/stats
    """

    data: TimelineStatisticsData


class EntityLinkingJobData(BaseModel):
    """Job data for entity linking."""

    job_id: str = Field(..., description="Job UUID for progress tracking")
    status: str = Field(default="queued", description="Job status")
    events_to_process: int = Field(..., description="Number of events to process")


class EntityLinkingJobResponse(BaseModel):
    """API response for entity linking job trigger.

    POST /api/matters/{matter_id}/timeline/link-entities
    """

    data: EntityLinkingJobData


class EntityTimelineRequest(BaseModel):
    """Request for entity-focused timeline view."""

    entity_id: str = Field(..., description="Entity UUID to focus on")


class EntityEventCount(BaseModel):
    """Entity with event count for timeline."""

    entity_id: str = Field(..., description="Entity UUID")
    canonical_name: str = Field(..., description="Entity name")
    entity_type: str = Field(..., description="Entity type")
    event_count: int = Field(..., description="Number of events involving entity")
    first_appearance: date | None = Field(None, description="First event date")
    last_appearance: date | None = Field(None, description="Last event date")


class EntitiesInTimelineResponse(BaseModel):
    """API response for entities involved in timeline.

    GET /api/matters/{matter_id}/timeline/entities
    """

    data: list[EntityEventCount]
    meta: PaginationMeta


# =============================================================================
# Manual Event API Models (Story 10B.5)
# =============================================================================


class ManualEventCreateRequest(BaseModel):
    """Request body for creating a manual timeline event.

    POST /api/matters/{matter_id}/timeline/events

    Story 10B.5: Timeline Filtering and Manual Event Addition
    """

    event_date: date = Field(..., description="Event date")
    event_type: EventType = Field(..., description="Event type")
    title: str = Field(
        ..., min_length=5, max_length=200, description="Event title (used as description)"
    )
    description: str = Field(default="", max_length=2000, description="Additional description")
    entity_ids: list[str] = Field(
        default_factory=list, description="Entity UUIDs to link"
    )
    source_document_id: str | None = Field(
        None, description="Optional source document reference"
    )
    source_page: int | None = Field(None, ge=1, description="Optional source page number")


class ManualEventUpdateRequest(BaseModel):
    """Request body for updating a timeline event.

    PATCH /api/matters/{matter_id}/timeline/events/{event_id}

    For manual events: all fields can be edited.
    For auto-extracted events: only event_type can be edited (classification correction).

    Story 10B.5: Timeline Filtering and Manual Event Addition
    """

    event_date: date | None = Field(None, description="New event date")
    event_type: EventType | None = Field(None, description="New event type")
    title: str | None = Field(
        None, min_length=5, max_length=200, description="New title"
    )
    description: str | None = Field(None, max_length=2000, description="New description")
    entity_ids: list[str] | None = Field(None, description="New entity links")


class ManualEventResponse(BaseModel):
    """Response for manual event operations.

    Story 10B.5: Timeline Filtering and Manual Event Addition
    """

    id: str = Field(..., description="Event UUID")
    event_date: date = Field(..., description="Event date")
    event_date_precision: str = Field(..., description="Date precision")
    event_date_text: str | None = Field(None, description="Original date text")
    event_type: str = Field(..., description="Event type")
    description: str = Field(..., description="Event description")
    document_id: str | None = Field(None, description="Source document UUID")
    source_page: int | None = Field(None, description="Source page number")
    confidence: float = Field(..., description="Confidence score")
    entities: list[EntityReference] = Field(
        default_factory=list, description="Linked entities"
    )
    is_ambiguous: bool = Field(default=False, description="Whether date is ambiguous")
    is_verified: bool = Field(default=False, description="Whether manually verified")
    is_manual: bool = Field(..., description="Whether manually created")
    created_by: str | None = Field(None, description="Creator user ID")
    created_at: datetime | None = Field(None, description="Creation timestamp")


class ManualEventCreateResponse(BaseModel):
    """API response for manual event creation.

    POST /api/matters/{matter_id}/timeline/events
    """

    data: ManualEventResponse


class ManualEventUpdateResponse(BaseModel):
    """API response for manual event update.

    PATCH /api/matters/{matter_id}/timeline/events/{event_id}
    """

    data: ManualEventResponse


class ManualEventDeleteResponse(BaseModel):
    """API response for manual event deletion.

    DELETE /api/matters/{matter_id}/timeline/events/{event_id}
    """

    message: str = Field(default="Event deleted successfully")


class EventVerificationRequest(BaseModel):
    """Request body for setting event verification status.

    PATCH /api/matters/{matter_id}/timeline/events/{event_id}/verify
    """

    is_verified: bool = Field(..., description="Whether event is verified")


# Forward reference resolution
DateExtractionJobResponse.model_rebuild()
ClassifiedEventsListResponse.model_rebuild()
UnclassifiedEventsResponse.model_rebuild()
TimelineWithEntitiesResponse.model_rebuild()
EntitiesInTimelineResponse.model_rebuild()
ManualEventCreateResponse.model_rebuild()
ManualEventUpdateResponse.model_rebuild()
