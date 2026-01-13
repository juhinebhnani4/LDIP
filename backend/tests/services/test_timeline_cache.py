"""Unit tests for TimelineCacheService.

Tests Redis-based caching for timeline data.

Story 4-3: Events Table + MIG Integration
"""

import pytest
import json
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from app.services.timeline_cache import (
    TimelineCacheService,
    get_timeline_cache_service,
    TIMELINE_CACHE_TTL,
    _serialize_timeline,
    _deserialize_timeline,
)
from app.engines.timeline.timeline_builder import (
    ConstructedTimeline,
    TimelineEvent,
    TimelineStatistics,
    EntityTimelineView,
    EntityReference,
    TimelineSegment,
)
from app.models.entity import EntityType
from app.models.timeline import EventType


# =============================================================================
# Test Constants
# =============================================================================

# Valid UUIDs for testing (redis_keys validates UUID format)
TEST_MATTER_ID = "12345678-1234-1234-1234-123456789012"
TEST_ENTITY_ID = "abcdef01-1234-1234-1234-123456789012"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def cache_service():
    """Create a TimelineCacheService instance for testing."""
    service = TimelineCacheService()
    # Mock Redis client
    service._redis = MagicMock()
    return service


@pytest.fixture
def sample_timeline():
    """Create a sample ConstructedTimeline for testing."""
    events = [
        TimelineEvent(
            event_id="event-1",
            event_date=date(2024, 1, 15),
            event_date_precision="day",
            event_date_text="15/01/2024",
            event_type=EventType.FILING,
            description="Petition filed",
            document_id="doc-1",
            document_name="Petition.pdf",
            source_page=5,
            confidence=0.9,
            entities=[
                EntityReference(
                    entity_id="entity-1",
                    canonical_name="Nirav Jobalia",
                    entity_type=EntityType.PERSON,
                    role="petitioner",
                )
            ],
            is_ambiguous=False,
            is_verified=False,
        ),
    ]

    statistics = TimelineStatistics(
        total_events=1,
        events_by_type={"filing": 1},
        entities_involved=1,
        date_range_start=date(2024, 1, 15),
        date_range_end=date(2024, 1, 15),
        events_with_entities=1,
        events_without_entities=0,
        verified_events=0,
    )

    return ConstructedTimeline(
        matter_id=TEST_MATTER_ID,
        events=events,
        segments=[],
        entity_views=[],
        statistics=statistics,
        generated_at=datetime(2024, 1, 20, 10, 0, 0),
        page=1,
        per_page=50,
        total_events=1,
        total_pages=1,
    )


@pytest.fixture
def sample_statistics():
    """Create sample TimelineStatistics for testing."""
    return TimelineStatistics(
        total_events=10,
        events_by_type={"filing": 3, "hearing": 5, "order": 2},
        entities_involved=5,
        date_range_start=date(2024, 1, 1),
        date_range_end=date(2024, 12, 31),
        events_with_entities=8,
        events_without_entities=2,
        verified_events=3,
    )


@pytest.fixture
def sample_entity_view():
    """Create sample EntityTimelineView for testing."""
    return EntityTimelineView(
        entity_id="entity-1",
        entity_name="Nirav Jobalia",
        entity_type=EntityType.PERSON,
        events=[
            TimelineEvent(
                event_id="event-1",
                event_date=date(2024, 1, 15),
                event_date_precision="day",
                event_date_text=None,
                event_type=EventType.FILING,
                description="Petition filed",
                document_id=None,
                document_name=None,
                source_page=None,
                confidence=0.9,
                entities=[],
                is_ambiguous=False,
                is_verified=False,
            )
        ],
        first_appearance=date(2024, 1, 15),
        last_appearance=date(2024, 1, 15),
        event_count=1,
    )


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialization:
    """Tests for timeline serialization/deserialization."""

    def test_serialize_timeline(self, sample_timeline):
        """Test serializing a timeline to JSON."""
        serialized = _serialize_timeline(sample_timeline)

        assert isinstance(serialized, str)
        data = json.loads(serialized)
        assert data["matter_id"] == TEST_MATTER_ID
        assert len(data["events"]) == 1
        assert data["total_events"] == 1

    def test_deserialize_timeline(self, sample_timeline):
        """Test deserializing a timeline from JSON."""
        serialized = _serialize_timeline(sample_timeline)
        deserialized = _deserialize_timeline(serialized)

        assert isinstance(deserialized, ConstructedTimeline)
        assert deserialized.matter_id == TEST_MATTER_ID
        assert len(deserialized.events) == 1
        assert deserialized.events[0].event_id == "event-1"

    def test_serialize_date_objects(self, sample_timeline):
        """Test that date objects are properly serialized."""
        serialized = _serialize_timeline(sample_timeline)
        data = json.loads(serialized)

        # Check that dates are serialized as ISO format with marker
        event_data = data["events"][0]
        assert "__date__" in str(event_data["event_date"])

    def test_serialize_enum_objects(self, sample_timeline):
        """Test that enum objects are properly serialized."""
        serialized = _serialize_timeline(sample_timeline)
        data = json.loads(serialized)

        # EventType is a str enum, so it serializes to its string value directly
        event_data = data["events"][0]
        # Verify the event type is serialized (either as marker or string value)
        assert event_data["event_type"] == "filing" or "__event_type__" in str(event_data["event_type"])


# =============================================================================
# Timeline Cache Tests
# =============================================================================


class TestTimelineCache:
    """Tests for timeline caching operations."""

    @pytest.mark.asyncio
    async def test_set_timeline(self, cache_service, sample_timeline):
        """Test caching a timeline."""
        result = await cache_service.set_timeline(
            matter_id=TEST_MATTER_ID,
            timeline=sample_timeline,
        )

        assert result is True
        cache_service._redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_timeline_hit(self, cache_service, sample_timeline):
        """Test retrieving a cached timeline."""
        # Mock Redis returning cached data
        serialized = _serialize_timeline(sample_timeline)
        cache_service._redis.get.return_value = serialized

        result = await cache_service.get_timeline(
            matter_id=TEST_MATTER_ID,
            page=1,
            per_page=50,
        )

        assert result is not None
        assert isinstance(result, ConstructedTimeline)
        assert result.matter_id == TEST_MATTER_ID

    @pytest.mark.asyncio
    async def test_get_timeline_miss(self, cache_service):
        """Test cache miss returns None."""
        cache_service._redis.get.return_value = None

        result = await cache_service.get_timeline(
            matter_id=TEST_MATTER_ID,
            page=1,
            per_page=50,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_timeline_no_redis(self):
        """Test graceful handling when Redis unavailable."""
        service = TimelineCacheService()
        service._redis = None

        result = await service.get_timeline(
            matter_id=TEST_MATTER_ID,
            page=1,
            per_page=50,
        )

        assert result is None


# =============================================================================
# Statistics Cache Tests
# =============================================================================


class TestStatisticsCache:
    """Tests for timeline statistics caching."""

    @pytest.mark.asyncio
    async def test_set_statistics(self, cache_service, sample_statistics):
        """Test caching statistics."""
        result = await cache_service.set_statistics(
            matter_id=TEST_MATTER_ID,
            stats=sample_statistics,
        )

        assert result is True
        cache_service._redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_statistics_hit(self, cache_service, sample_statistics):
        """Test retrieving cached statistics."""
        # Create serialized stats manually
        from app.services.timeline_cache import _stats_to_dict, TimelineCacheEncoder

        serialized = json.dumps(
            _stats_to_dict(sample_statistics),
            cls=TimelineCacheEncoder,
        )
        cache_service._redis.get.return_value = serialized

        result = await cache_service.get_statistics(TEST_MATTER_ID)

        assert result is not None
        assert isinstance(result, TimelineStatistics)
        assert result.total_events == 10

    @pytest.mark.asyncio
    async def test_get_statistics_miss(self, cache_service):
        """Test statistics cache miss."""
        cache_service._redis.get.return_value = None

        result = await cache_service.get_statistics(TEST_MATTER_ID)

        assert result is None


# =============================================================================
# Entity View Cache Tests
# =============================================================================


class TestEntityViewCache:
    """Tests for entity view caching."""

    @pytest.mark.asyncio
    async def test_set_entity_view(self, cache_service, sample_entity_view):
        """Test caching entity view."""
        result = await cache_service.set_entity_view(
            matter_id=TEST_MATTER_ID,
            entity_id="entity-1",
            view=sample_entity_view,
        )

        assert result is True
        cache_service._redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_entity_view_hit(self, cache_service, sample_entity_view):
        """Test retrieving cached entity view."""
        from app.services.timeline_cache import (
            _entity_view_to_dict,
            TimelineCacheEncoder,
        )

        serialized = json.dumps(
            _entity_view_to_dict(sample_entity_view),
            cls=TimelineCacheEncoder,
        )
        cache_service._redis.get.return_value = serialized

        result = await cache_service.get_entity_view(
            matter_id=TEST_MATTER_ID,
            entity_id="entity-1",
        )

        assert result is not None
        assert isinstance(result, EntityTimelineView)
        assert result.entity_id == "entity-1"

    @pytest.mark.asyncio
    async def test_get_entity_view_miss(self, cache_service):
        """Test entity view cache miss."""
        cache_service._redis.get.return_value = None

        result = await cache_service.get_entity_view(
            matter_id=TEST_MATTER_ID,
            entity_id="entity-1",
        )

        assert result is None


# =============================================================================
# Cache Invalidation Tests
# =============================================================================


class TestCacheInvalidation:
    """Tests for cache invalidation operations."""

    @pytest.mark.asyncio
    async def test_invalidate_timeline(self, cache_service):
        """Test invalidating all timeline cache entries."""
        # Mock SCAN returning keys
        cache_service._redis.scan.return_value = (0, ["key1", "key2"])
        cache_service._redis.delete.return_value = 2

        deleted = await cache_service.invalidate_timeline(TEST_MATTER_ID)

        assert deleted >= 0
        cache_service._redis.scan.assert_called()

    @pytest.mark.asyncio
    async def test_invalidate_entity_view(self, cache_service):
        """Test invalidating specific entity view."""
        cache_service._redis.delete.return_value = 1

        result = await cache_service.invalidate_entity_view(
            matter_id=TEST_MATTER_ID,
            entity_id=TEST_ENTITY_ID,
        )

        assert result is True
        cache_service._redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_no_redis(self):
        """Test graceful handling of invalidation without Redis."""
        service = TimelineCacheService()
        service._redis = None

        deleted = await service.invalidate_timeline(TEST_MATTER_ID)

        assert deleted == 0


# =============================================================================
# Service Factory Tests
# =============================================================================


class TestCacheServiceFactory:
    """Tests for service factory function."""

    def test_get_timeline_cache_service_singleton(self):
        """Test that factory returns singleton instance."""
        # Clear cache first
        get_timeline_cache_service.cache_clear()

        service1 = get_timeline_cache_service()
        service2 = get_timeline_cache_service()

        assert service1 is service2
        assert isinstance(service1, TimelineCacheService)

        # Clear cache after test
        get_timeline_cache_service.cache_clear()
