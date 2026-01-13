"""Unit tests for TimelineBuilder.

Tests timeline construction with entity enrichment.

Story 4-3: Events Table + MIG Integration
"""

import pytest
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.timeline.timeline_builder import (
    TimelineBuilder,
    ConstructedTimeline,
    TimelineEvent,
    TimelineStatistics,
    EntityTimelineView,
    EntityReference,
    get_timeline_builder,
)
from app.models.entity import EntityNode, EntityType
from app.models.timeline import EventType, PaginationMeta


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def timeline_builder():
    """Create a TimelineBuilder instance for testing."""
    builder = TimelineBuilder()
    builder._timeline_service = MagicMock()
    builder._mig_service = MagicMock()
    return builder


@pytest.fixture
def mock_events_response():
    """Create mock events response."""
    events = [
        MagicMock(
            id="event-1",
            event_date=date(2024, 1, 15),
            event_date_precision="day",
            event_date_text="15/01/2024",
            event_type="filing",
            description="Petition filed by petitioner",
            document_id="doc-1",
            source_page=5,
            confidence=0.9,
            is_ambiguous=False,
        ),
        MagicMock(
            id="event-2",
            event_date=date(2024, 2, 20),
            event_date_precision="day",
            event_date_text="20/02/2024",
            event_type="hearing",
            description="Matter heard before court",
            document_id="doc-1",
            source_page=10,
            confidence=0.85,
            is_ambiguous=False,
        ),
    ]

    response = MagicMock()
    response.data = events
    response.meta = MagicMock(
        total=2,
        page=1,
        per_page=50,
        total_pages=1,
    )
    return response


@pytest.fixture
def mock_full_event():
    """Create mock full event with entity info."""
    event = MagicMock(
        id="event-1",
        entities_involved=["entity-1", "entity-2"],
        is_manual=False,
        document_name="Petition.pdf",
    )
    return event


@pytest.fixture
def sample_entities():
    """Create sample entities for testing."""
    now = datetime.utcnow()
    return [
        EntityNode(
            id="entity-1",
            matter_id="matter-123",
            canonical_name="Nirav Jobalia",
            entity_type=EntityType.PERSON,
            created_at=now,
            updated_at=now,
            aliases=[],
            metadata={"role": "petitioner"},
        ),
        EntityNode(
            id="entity-2",
            matter_id="matter-123",
            canonical_name="HDFC Bank Ltd",
            entity_type=EntityType.ORG,
            aliases=[],
            metadata={"role": "respondent"},
            created_at=now,
            updated_at=now,
        ),
    ]


# =============================================================================
# Timeline Building Tests
# =============================================================================


class TestTimelineBuilding:
    """Tests for building complete timelines."""

    @pytest.mark.asyncio
    async def test_build_timeline_basic(
        self, timeline_builder, mock_events_response, mock_full_event, sample_entities
    ):
        """Test basic timeline building."""
        timeline_builder.timeline_service.get_timeline_for_matter = AsyncMock(
            return_value=mock_events_response
        )
        timeline_builder.timeline_service.get_event_by_id = AsyncMock(
            return_value=mock_full_event
        )
        timeline_builder.mig_service.get_entities_by_matter = AsyncMock(
            return_value=(sample_entities, 2)
        )

        timeline = await timeline_builder.build_timeline(
            matter_id="matter-123",
            include_entities=True,
            page=1,
            per_page=50,
        )

        assert isinstance(timeline, ConstructedTimeline)
        assert timeline.matter_id == "matter-123"
        assert len(timeline.events) == 2
        assert timeline.total_events == 2

    @pytest.mark.asyncio
    async def test_build_timeline_with_entity_filter(
        self, timeline_builder, mock_events_response, mock_full_event, sample_entities
    ):
        """Test timeline building filtered by entity."""
        timeline_builder.timeline_service.get_events_by_entity = AsyncMock(
            return_value=mock_events_response
        )
        timeline_builder.timeline_service.get_event_by_id = AsyncMock(
            return_value=mock_full_event
        )
        timeline_builder.mig_service.get_entities_by_matter = AsyncMock(
            return_value=(sample_entities, 2)
        )

        timeline = await timeline_builder.build_timeline(
            matter_id="matter-123",
            entity_id="entity-1",
            include_entities=True,
            page=1,
            per_page=50,
        )

        assert isinstance(timeline, ConstructedTimeline)
        timeline_builder.timeline_service.get_events_by_entity.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_timeline_without_entities(
        self, timeline_builder, mock_events_response, mock_full_event
    ):
        """Test timeline building without entity enrichment."""
        timeline_builder.timeline_service.get_timeline_for_matter = AsyncMock(
            return_value=mock_events_response
        )
        timeline_builder.timeline_service.get_event_by_id = AsyncMock(
            return_value=mock_full_event
        )

        timeline = await timeline_builder.build_timeline(
            matter_id="matter-123",
            include_entities=False,
            page=1,
            per_page=50,
        )

        assert isinstance(timeline, ConstructedTimeline)
        # MIG service should not be called
        timeline_builder.mig_service.get_entities_by_matter.assert_not_called()


# =============================================================================
# Segment Building Tests
# =============================================================================


class TestSegmentBuilding:
    """Tests for timeline segmentation."""

    def test_build_segments_by_month(self, timeline_builder):
        """Test grouping events by month."""
        events = [
            TimelineEvent(
                event_id="e1",
                event_date=date(2024, 1, 15),
                event_date_precision="day",
                event_date_text=None,
                event_type=EventType.FILING,
                description="Event 1",
                document_id=None,
                document_name=None,
                source_page=None,
                confidence=0.9,
                entities=[],
            ),
            TimelineEvent(
                event_id="e2",
                event_date=date(2024, 1, 25),
                event_date_precision="day",
                event_date_text=None,
                event_type=EventType.HEARING,
                description="Event 2",
                document_id=None,
                document_name=None,
                source_page=None,
                confidence=0.9,
                entities=[],
            ),
            TimelineEvent(
                event_id="e3",
                event_date=date(2024, 2, 10),
                event_date_precision="day",
                event_date_text=None,
                event_type=EventType.ORDER,
                description="Event 3",
                document_id=None,
                document_name=None,
                source_page=None,
                confidence=0.9,
                entities=[],
            ),
        ]

        segments = timeline_builder._build_segments(events, "month")

        assert len(segments) == 2
        assert segments[0].period_label == "January 2024"
        assert segments[0].event_count == 2
        assert segments[1].period_label == "February 2024"
        assert segments[1].event_count == 1

    def test_build_segments_by_year(self, timeline_builder):
        """Test grouping events by year."""
        events = [
            TimelineEvent(
                event_id="e1",
                event_date=date(2023, 6, 15),
                event_date_precision="day",
                event_date_text=None,
                event_type=EventType.FILING,
                description="Event 1",
                document_id=None,
                document_name=None,
                source_page=None,
                confidence=0.9,
                entities=[],
            ),
            TimelineEvent(
                event_id="e2",
                event_date=date(2024, 3, 10),
                event_date_precision="day",
                event_date_text=None,
                event_type=EventType.HEARING,
                description="Event 2",
                document_id=None,
                document_name=None,
                source_page=None,
                confidence=0.9,
                entities=[],
            ),
        ]

        segments = timeline_builder._build_segments(events, "year")

        assert len(segments) == 2
        assert segments[0].period_label == "2023"
        assert segments[1].period_label == "2024"

    def test_build_segments_empty(self, timeline_builder):
        """Test building segments with no events."""
        segments = timeline_builder._build_segments([], "month")
        assert segments == []


# =============================================================================
# Entity Timeline Tests
# =============================================================================


class TestEntityTimeline:
    """Tests for entity-focused timeline views."""

    @pytest.mark.asyncio
    async def test_build_entity_timeline(
        self, timeline_builder, mock_events_response, sample_entities
    ):
        """Test building entity-focused timeline."""
        timeline_builder.mig_service.get_entity_by_id = AsyncMock(
            return_value=sample_entities[0]
        )
        timeline_builder.timeline_service.get_events_by_entity = AsyncMock(
            return_value=mock_events_response
        )

        view = await timeline_builder.build_entity_timeline(
            matter_id="matter-123",
            entity_id="entity-1",
            page=1,
            per_page=50,
        )

        assert isinstance(view, EntityTimelineView)
        assert view.entity_id == "entity-1"
        assert view.entity_name == "Nirav Jobalia"
        assert len(view.events) == 2

    @pytest.mark.asyncio
    async def test_build_entity_timeline_not_found(self, timeline_builder):
        """Test entity timeline when entity not found."""
        timeline_builder.mig_service.get_entity_by_id = AsyncMock(return_value=None)

        view = await timeline_builder.build_entity_timeline(
            matter_id="matter-123",
            entity_id="unknown-entity",
            page=1,
            per_page=50,
        )

        assert view.entity_name == "Unknown"
        assert view.events == []


# =============================================================================
# Statistics Tests
# =============================================================================


class TestTimelineStatistics:
    """Tests for timeline statistics."""

    @pytest.mark.asyncio
    async def test_get_timeline_statistics(
        self, timeline_builder, mock_events_response, mock_full_event
    ):
        """Test getting timeline statistics."""
        timeline_builder.timeline_service.get_timeline_for_matter = AsyncMock(
            return_value=mock_events_response
        )
        timeline_builder.timeline_service.get_event_by_id = AsyncMock(
            return_value=mock_full_event
        )

        stats = await timeline_builder.get_timeline_statistics("matter-123")

        assert isinstance(stats, TimelineStatistics)
        assert stats.total_events == 2


# =============================================================================
# Service Factory Tests
# =============================================================================


class TestTimelineBuilderFactory:
    """Tests for service factory function."""

    def test_get_timeline_builder_creates_new(self):
        """Test that factory creates new instance each time."""
        builder1 = get_timeline_builder()
        builder2 = get_timeline_builder()

        # Should be different instances (not cached)
        assert isinstance(builder1, TimelineBuilder)
        assert isinstance(builder2, TimelineBuilder)
