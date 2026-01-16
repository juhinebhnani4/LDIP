"""Timeline Construction Service for building complete timelines.

Aggregates events with entity information to construct comprehensive
timeline views for matters. Supports filtering, entity grouping,
and structured timeline output.

Story 4-3: Events Table + MIG Integration
"""

import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import structlog

from app.models.entity import EntityNode, EntityType
from app.models.timeline import (
    EventType,
)
from app.services.mig.graph import MIGGraphService, get_mig_graph_service
from app.services.timeline_service import TimelineService, get_timeline_service

logger = structlog.get_logger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class EntityReference:
    """Lightweight entity reference for timeline events."""

    entity_id: str
    canonical_name: str
    entity_type: EntityType
    role: str | None = None  # petitioner, respondent, etc.


@dataclass
class TimelineEvent:
    """A single event in the constructed timeline.

    Enriched with entity information and formatted for display.
    """

    event_id: str
    event_date: date
    event_date_precision: str
    event_date_text: str | None
    event_type: EventType
    description: str
    document_id: str | None
    document_name: str | None
    source_page: int | None
    confidence: float
    entities: list[EntityReference] = field(default_factory=list)
    is_ambiguous: bool = False
    is_verified: bool = False


@dataclass
class TimelineSegment:
    """A segment of timeline events grouped by time period."""

    period_start: date
    period_end: date
    period_label: str  # "January 2024", "2024", "Q1 2024"
    events: list[TimelineEvent] = field(default_factory=list)
    event_count: int = 0


@dataclass
class EntityTimelineView:
    """Timeline filtered by entity involvement."""

    entity_id: str
    entity_name: str
    entity_type: EntityType
    events: list[TimelineEvent] = field(default_factory=list)
    first_appearance: date | None = None
    last_appearance: date | None = None
    event_count: int = 0


@dataclass
class TimelineStatistics:
    """Statistics about a constructed timeline."""

    total_events: int
    events_by_type: dict[str, int]
    entities_involved: int
    date_range_start: date | None
    date_range_end: date | None
    events_with_entities: int
    events_without_entities: int
    verified_events: int


@dataclass
class ConstructedTimeline:
    """Complete constructed timeline for a matter.

    Contains all events with entity information and statistics.
    """

    matter_id: str
    events: list[TimelineEvent]
    segments: list[TimelineSegment]
    entity_views: list[EntityTimelineView]
    statistics: TimelineStatistics
    generated_at: datetime
    page: int
    per_page: int
    total_events: int
    total_pages: int


# =============================================================================
# Service Implementation
# =============================================================================


class TimelineBuilder:
    """Service for constructing comprehensive timelines.

    Combines events from the timeline service with entity information
    from the MIG to produce enriched timeline views.

    Example:
        >>> builder = TimelineBuilder()
        >>> timeline = await builder.build_timeline(
        ...     matter_id="matter-123",
        ...     include_entities=True,
        ...     group_by="month",
        ... )
    """

    def __init__(self) -> None:
        """Initialize timeline builder."""
        self._timeline_service: TimelineService | None = None
        self._mig_service: MIGGraphService | None = None

    @property
    def timeline_service(self) -> TimelineService:
        """Get timeline service instance."""
        if self._timeline_service is None:
            self._timeline_service = get_timeline_service()
        return self._timeline_service

    @property
    def mig_service(self) -> MIGGraphService:
        """Get MIG service instance."""
        if self._mig_service is None:
            self._mig_service = get_mig_graph_service()
        return self._mig_service

    # =========================================================================
    # Public Methods
    # =========================================================================

    async def build_timeline(
        self,
        matter_id: str,
        event_type: EventType | None = None,
        entity_id: str | None = None,
        include_entities: bool = True,
        include_raw_dates: bool = False,
        group_by: str | None = None,  # "month", "year", "quarter"
        page: int = 1,
        per_page: int = 50,
    ) -> ConstructedTimeline:
        """Build a comprehensive timeline for a matter.

        Args:
            matter_id: Matter UUID.
            event_type: Optional filter by event type.
            entity_id: Optional filter by entity involvement.
            include_entities: If True, enrich events with entity info.
            include_raw_dates: If True, include unclassified raw_date events.
            group_by: Optional grouping period ("month", "year", "quarter").
            page: Page number.
            per_page: Items per page.

        Returns:
            ConstructedTimeline with enriched events.
        """
        start_time = time.time()

        # Determine event type filter
        type_filter = None
        if event_type:
            type_filter = event_type.value
        elif not include_raw_dates:
            type_filter = None  # Will exclude raw_date in query

        # Get events from timeline service
        if entity_id:
            events_response = await self.timeline_service.get_events_by_entity(
                entity_id=entity_id,
                matter_id=matter_id,
                page=page,
                per_page=per_page,
            )
        elif type_filter:
            events_response = await self.timeline_service.get_classified_events(
                matter_id=matter_id,
                event_type=type_filter,
                page=page,
                per_page=per_page,
            )
        else:
            events_response = await self.timeline_service.get_timeline_for_matter(
                matter_id=matter_id,
                event_type=type_filter,
                page=page,
                per_page=per_page,
            )

        # Load entities if requested - use pagination to avoid OOM
        entities_map: dict[str, EntityNode] = {}
        if include_entities:
            entities_map = await self._load_entities_paginated(matter_id)

        # Convert to TimelineEvent objects with entity enrichment
        timeline_events: list[TimelineEvent] = []
        events_with_entities = 0
        events_by_type: dict[str, int] = {}
        all_entity_ids: set[str] = set()

        for event_item in events_response.data:
            # Get full event details for entity_ids
            full_event = await self.timeline_service.get_event_by_id(
                event_id=event_item.id,
                matter_id=matter_id,
            )

            if not full_event:
                continue

            # Track event type statistics
            event_type_str = getattr(event_item, 'event_type', 'raw_date')
            events_by_type[event_type_str] = events_by_type.get(event_type_str, 0) + 1

            # Build entity references
            entity_refs: list[EntityReference] = []
            if include_entities and full_event.entities_involved:
                events_with_entities += 1
                for eid in full_event.entities_involved:
                    all_entity_ids.add(eid)
                    if eid in entities_map:
                        entity = entities_map[eid]
                        # Get role from metadata if available
                        role = entity.metadata.get("role") if entity.metadata else None
                        entity_refs.append(
                            EntityReference(
                                entity_id=entity.id,
                                canonical_name=entity.canonical_name,
                                entity_type=entity.entity_type,
                                role=role,
                            )
                        )

            # Parse event type
            try:
                parsed_type = EventType(event_type_str)
            except ValueError:
                parsed_type = EventType.UNCLASSIFIED

            timeline_events.append(
                TimelineEvent(
                    event_id=event_item.id,
                    event_date=event_item.event_date,
                    event_date_precision=event_item.event_date_precision,
                    event_date_text=event_item.event_date_text,
                    event_type=parsed_type,
                    description=event_item.description,
                    document_id=event_item.document_id,
                    document_name=getattr(full_event, 'document_name', None),
                    source_page=event_item.source_page,
                    confidence=getattr(event_item, 'confidence', 0.8),
                    entities=entity_refs,
                    is_ambiguous=getattr(event_item, 'is_ambiguous', False),
                    is_verified=getattr(full_event, 'is_manual', False),
                )
            )

        # Build segments if grouping requested
        segments = self._build_segments(timeline_events, group_by) if group_by else []

        # Build entity views
        entity_views = self._build_entity_views(
            timeline_events, entities_map, all_entity_ids
        ) if include_entities else []

        # Calculate statistics
        date_range_start = None
        date_range_end = None
        if timeline_events:
            dates = [e.event_date for e in timeline_events]
            date_range_start = min(dates)
            date_range_end = max(dates)

        statistics = TimelineStatistics(
            total_events=events_response.meta.total,
            events_by_type=events_by_type,
            entities_involved=len(all_entity_ids),
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            events_with_entities=events_with_entities,
            events_without_entities=len(timeline_events) - events_with_entities,
            verified_events=sum(1 for e in timeline_events if e.is_verified),
        )

        processing_time = int((time.time() - start_time) * 1000)

        logger.info(
            "timeline_built",
            matter_id=matter_id,
            events_count=len(timeline_events),
            entities_involved=len(all_entity_ids),
            processing_time_ms=processing_time,
        )

        return ConstructedTimeline(
            matter_id=matter_id,
            events=timeline_events,
            segments=segments,
            entity_views=entity_views,
            statistics=statistics,
            generated_at=datetime.now(UTC),
            page=page,
            per_page=per_page,
            total_events=events_response.meta.total,
            total_pages=events_response.meta.total_pages,
        )

    async def build_entity_timeline(
        self,
        matter_id: str,
        entity_id: str,
        page: int = 1,
        per_page: int = 50,
    ) -> EntityTimelineView:
        """Build timeline focused on a specific entity.

        Args:
            matter_id: Matter UUID.
            entity_id: Entity UUID to focus on.
            page: Page number.
            per_page: Items per page.

        Returns:
            EntityTimelineView with events involving the entity.
        """
        # Get entity info
        entity = await self.mig_service.get_entity_by_id(
            entity_id=entity_id,
            matter_id=matter_id,
        )

        if not entity:
            logger.warning(
                "entity_timeline_entity_not_found",
                matter_id=matter_id,
                entity_id=entity_id,
            )
            return EntityTimelineView(
                entity_id=entity_id,
                entity_name="Unknown",
                entity_type=EntityType.PERSON,
                events=[],
                event_count=0,
            )

        # Get events for this entity
        events_response = await self.timeline_service.get_events_by_entity(
            entity_id=entity_id,
            matter_id=matter_id,
            page=page,
            per_page=per_page,
        )

        # Convert to timeline events
        timeline_events: list[TimelineEvent] = []
        for event_item in events_response.data:
            try:
                parsed_type = EventType(getattr(event_item, 'event_type', 'unclassified'))
            except ValueError:
                parsed_type = EventType.UNCLASSIFIED

            timeline_events.append(
                TimelineEvent(
                    event_id=event_item.id,
                    event_date=event_item.event_date,
                    event_date_precision=event_item.event_date_precision,
                    event_date_text=event_item.event_date_text,
                    event_type=parsed_type,
                    description=event_item.description,
                    document_id=event_item.document_id,
                    document_name=None,
                    source_page=event_item.source_page,
                    confidence=getattr(event_item, 'confidence', 0.8),
                    entities=[],  # Don't need entity info for entity-focused view
                    is_ambiguous=getattr(event_item, 'is_ambiguous', False),
                    is_verified=False,
                )
            )

        first_appearance = None
        last_appearance = None
        if timeline_events:
            dates = [e.event_date for e in timeline_events]
            first_appearance = min(dates)
            last_appearance = max(dates)

        return EntityTimelineView(
            entity_id=entity.id,
            entity_name=entity.canonical_name,
            entity_type=entity.entity_type,
            events=timeline_events,
            first_appearance=first_appearance,
            last_appearance=last_appearance,
            event_count=events_response.meta.total,
        )

    async def get_timeline_statistics(
        self,
        matter_id: str,
    ) -> TimelineStatistics:
        """Get statistics about a matter's timeline.

        Args:
            matter_id: Matter UUID.

        Returns:
            TimelineStatistics with aggregate information.
        """
        # Get events using pagination to avoid OOM
        all_events_data = []
        page = 1
        batch_size = 500  # Process in manageable batches

        while True:
            events_response = await self.timeline_service.get_timeline_for_matter(
                matter_id=matter_id,
                page=page,
                per_page=batch_size,
            )
            all_events_data.extend(events_response.data)

            if page >= events_response.meta.total_pages:
                break
            page += 1

        # Use the last response for total count
        all_events = events_response

        events_by_type: dict[str, int] = {}
        all_entity_ids: set[str] = set()
        events_with_entities = 0
        verified_events = 0
        date_range_start = None
        date_range_end = None

        for event_item in all_events_data:
            # Count by type
            event_type = getattr(event_item, 'event_type', 'raw_date')
            events_by_type[event_type] = events_by_type.get(event_type, 0) + 1

            # Get full event for entity info
            full_event = await self.timeline_service.get_event_by_id(
                event_id=event_item.id,
                matter_id=matter_id,
            )

            if full_event:
                if full_event.entities_involved:
                    events_with_entities += 1
                    all_entity_ids.update(full_event.entities_involved)
                if full_event.is_manual:
                    verified_events += 1

        if all_events_data:
            dates = [e.event_date for e in all_events_data]
            date_range_start = min(dates)
            date_range_end = max(dates)

        return TimelineStatistics(
            total_events=all_events.meta.total,
            events_by_type=events_by_type,
            entities_involved=len(all_entity_ids),
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            events_with_entities=events_with_entities,
            events_without_entities=all_events.meta.total - events_with_entities,
            verified_events=verified_events,
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _load_entities_paginated(
        self,
        matter_id: str,
        batch_size: int = 500,
    ) -> dict[str, EntityNode]:
        """Load all entities for a matter using pagination to avoid OOM.

        Args:
            matter_id: Matter UUID.
            batch_size: Number of entities per page (default 500).

        Returns:
            Dict mapping entity_id to EntityNode.
        """
        entities_map: dict[str, EntityNode] = {}
        page = 1

        while True:
            entities, total = await self.mig_service.get_entities_by_matter(
                matter_id=matter_id,
                page=page,
                per_page=batch_size,
            )

            for entity in entities:
                entities_map[entity.id] = entity

            # Check if we've loaded all entities
            if len(entities_map) >= total or not entities:
                break
            page += 1

        logger.debug(
            "entities_loaded_paginated",
            matter_id=matter_id,
            total_entities=len(entities_map),
            pages_loaded=page,
        )

        return entities_map

    def _build_segments(
        self,
        events: list[TimelineEvent],
        group_by: str,
    ) -> list[TimelineSegment]:
        """Group events into time segments.

        Args:
            events: List of timeline events.
            group_by: Grouping period ("month", "year", "quarter").

        Returns:
            List of TimelineSegment objects.
        """
        if not events:
            return []

        segments_map: dict[str, list[TimelineEvent]] = {}

        for event in events:
            key = self._get_period_key(event.event_date, group_by)
            if key not in segments_map:
                segments_map[key] = []
            segments_map[key].append(event)

        segments: list[TimelineSegment] = []
        for key in sorted(segments_map.keys()):
            segment_events = segments_map[key]
            dates = [e.event_date for e in segment_events]

            segments.append(
                TimelineSegment(
                    period_start=min(dates),
                    period_end=max(dates),
                    period_label=self._get_period_label(key, group_by),
                    events=segment_events,
                    event_count=len(segment_events),
                )
            )

        return segments

    def _get_period_key(self, d: date, group_by: str) -> str:
        """Get period key for grouping."""
        if group_by == "year":
            return f"{d.year}"
        elif group_by == "quarter":
            quarter = (d.month - 1) // 3 + 1
            return f"{d.year}-Q{quarter}"
        else:  # month
            return f"{d.year}-{d.month:02d}"

    def _get_period_label(self, key: str, group_by: str) -> str:
        """Get human-readable period label."""
        if group_by == "year":
            return key
        elif group_by == "quarter":
            return key.replace("-", " ")
        else:  # month
            year, month = key.split("-")
            month_names = [
                "", "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]
            return f"{month_names[int(month)]} {year}"

    def _build_entity_views(
        self,
        events: list[TimelineEvent],
        entities_map: dict[str, EntityNode],
        entity_ids: set[str],
    ) -> list[EntityTimelineView]:
        """Build entity-focused views from events.

        Args:
            events: List of timeline events.
            entities_map: Map of entity_id to EntityNode.
            entity_ids: Set of all entity IDs found in events.

        Returns:
            List of EntityTimelineView objects.
        """
        entity_events: dict[str, list[TimelineEvent]] = {eid: [] for eid in entity_ids}

        for event in events:
            for entity_ref in event.entities:
                if entity_ref.entity_id in entity_events:
                    entity_events[entity_ref.entity_id].append(event)

        views: list[EntityTimelineView] = []
        for eid, eid_events in entity_events.items():
            if eid not in entities_map:
                continue

            entity = entities_map[eid]
            first_appearance = None
            last_appearance = None

            if eid_events:
                dates = [e.event_date for e in eid_events]
                first_appearance = min(dates)
                last_appearance = max(dates)

            views.append(
                EntityTimelineView(
                    entity_id=entity.id,
                    entity_name=entity.canonical_name,
                    entity_type=entity.entity_type,
                    events=eid_events,
                    first_appearance=first_appearance,
                    last_appearance=last_appearance,
                    event_count=len(eid_events),
                )
            )

        # Sort by event count descending
        views.sort(key=lambda v: v.event_count, reverse=True)

        return views


# =============================================================================
# Service Factory
# =============================================================================


def get_timeline_builder() -> TimelineBuilder:
    """Get timeline builder instance.

    Note: Not cached as each request may need fresh data.

    Returns:
        TimelineBuilder instance.
    """
    return TimelineBuilder()
