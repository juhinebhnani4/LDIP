"""Cross-Engine Link Resolution API models.

Gap 5-3: Cross-Engine Correlation Links

Pydantic models for cross-engine link API endpoints.
"""

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Cross-Linked Item Models
# =============================================================================


class CrossLinkedTimelineEventModel(BaseModel):
    """Timeline event with minimal data for cross-engine linking."""

    model_config = ConfigDict(populate_by_name=True)

    event_id: str = Field(..., alias="eventId", description="Timeline event UUID")
    event_date: str = Field(..., alias="eventDate", description="Event date (ISO format)")
    event_type: str = Field(..., alias="eventType", description="Event type classification")
    description: str = Field(..., description="Event description")
    document_id: str | None = Field(
        None, alias="documentId", description="Source document UUID"
    )
    document_name: str | None = Field(
        None, alias="documentName", description="Source document filename"
    )
    source_page: int | None = Field(
        None, alias="sourcePage", description="Source page number"
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")


class CrossLinkedContradictionModel(BaseModel):
    """Contradiction with minimal data for cross-engine linking."""

    model_config = ConfigDict(populate_by_name=True)

    contradiction_id: str = Field(
        ..., alias="contradictionId", description="Contradiction UUID"
    )
    contradiction_type: str = Field(
        ..., alias="contradictionType", description="Type of contradiction"
    )
    severity: str = Field(..., description="Severity level: high, medium, low")
    explanation: str = Field(..., description="Explanation of the contradiction")
    statement_a_excerpt: str = Field(
        ..., alias="statementAExcerpt", description="First statement excerpt"
    )
    statement_b_excerpt: str = Field(
        ..., alias="statementBExcerpt", description="Second statement excerpt"
    )
    document_a_id: str = Field(
        ..., alias="documentAId", description="First document UUID"
    )
    document_a_name: str = Field(
        ..., alias="documentAName", description="First document filename"
    )
    document_b_id: str = Field(
        ..., alias="documentBId", description="Second document UUID"
    )
    document_b_name: str = Field(
        ..., alias="documentBName", description="Second document filename"
    )
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence score")


class CrossLinkedEntityModel(BaseModel):
    """Entity with minimal data for cross-engine linking."""

    model_config = ConfigDict(populate_by_name=True)

    entity_id: str = Field(..., alias="entityId", description="Entity UUID")
    canonical_name: str = Field(
        ..., alias="canonicalName", description="Entity canonical name"
    )
    entity_type: str = Field(..., alias="entityType", description="Entity type")
    aliases: list[str] = Field(default_factory=list, description="Entity aliases")


# =============================================================================
# Response Models
# =============================================================================


class EntityJourneyResponse(BaseModel):
    """Response for entity journey (timeline events for an entity)."""

    model_config = ConfigDict(populate_by_name=True)

    entity_id: str = Field(..., alias="entityId", description="Entity UUID")
    entity_name: str = Field(..., alias="entityName", description="Entity canonical name")
    entity_type: str = Field(..., alias="entityType", description="Entity type")
    events: list[CrossLinkedTimelineEventModel] = Field(
        default_factory=list, description="Timeline events involving this entity"
    )
    total_events: int = Field(
        default=0, alias="totalEvents", description="Total number of events"
    )
    date_range_start: str | None = Field(
        None, alias="dateRangeStart", description="Earliest event date"
    )
    date_range_end: str | None = Field(
        None, alias="dateRangeEnd", description="Latest event date"
    )


class EntityContradictionSummaryResponse(BaseModel):
    """Response for entity contradictions summary."""

    model_config = ConfigDict(populate_by_name=True)

    entity_id: str = Field(..., alias="entityId", description="Entity UUID")
    entity_name: str = Field(..., alias="entityName", description="Entity canonical name")
    contradictions: list[CrossLinkedContradictionModel] = Field(
        default_factory=list, description="Contradictions involving this entity"
    )
    total_contradictions: int = Field(
        default=0, alias="totalContradictions", description="Total contradiction count"
    )
    high_severity_count: int = Field(
        default=0, alias="highSeverityCount", description="High severity count"
    )
    medium_severity_count: int = Field(
        default=0, alias="mediumSeverityCount", description="Medium severity count"
    )
    low_severity_count: int = Field(
        default=0, alias="lowSeverityCount", description="Low severity count"
    )


class TimelineEventContextResponse(BaseModel):
    """Response for timeline event context."""

    model_config = ConfigDict(populate_by_name=True)

    event_id: str = Field(..., alias="eventId", description="Event UUID")
    event_date: str = Field(..., alias="eventDate", description="Event date")
    event_type: str = Field(..., alias="eventType", description="Event type")
    description: str = Field(..., description="Event description")
    document_id: str | None = Field(
        None, alias="documentId", description="Source document UUID"
    )
    document_name: str | None = Field(
        None, alias="documentName", description="Source document filename"
    )
    entities: list[CrossLinkedEntityModel] = Field(
        default_factory=list, description="Entities involved in this event"
    )
    related_contradictions: list[CrossLinkedContradictionModel] = Field(
        default_factory=list,
        alias="relatedContradictions",
        description="Contradictions for entities in this event",
    )


class ContradictionContextResponse(BaseModel):
    """Response for contradiction context."""

    model_config = ConfigDict(populate_by_name=True)

    contradiction_id: str = Field(
        ..., alias="contradictionId", description="Contradiction UUID"
    )
    entity_id: str = Field(..., alias="entityId", description="Entity UUID")
    entity_name: str = Field(..., alias="entityName", description="Entity canonical name")
    contradiction_type: str = Field(
        ..., alias="contradictionType", description="Type of contradiction"
    )
    severity: str = Field(..., description="Severity level")
    explanation: str = Field(..., description="Explanation")
    related_events: list[CrossLinkedTimelineEventModel] = Field(
        default_factory=list,
        alias="relatedEvents",
        description="Timeline events for the same entity",
    )


# =============================================================================
# Error Response Model
# =============================================================================


class CrossEngineErrorDetail(BaseModel):
    """Error detail structure for cross-engine API."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict = Field(default_factory=dict, description="Additional error context")


class CrossEngineErrorResponse(BaseModel):
    """Error response structure for cross-engine API."""

    error: CrossEngineErrorDetail
