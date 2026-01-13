"""Timeline Cache Service for Matter Memory.

Provides caching for timeline data using Redis to improve performance
for repeated timeline queries. Uses matter-level keys with timeline prefix.

Story 4-3: Events Table + MIG Integration
"""

import json
from dataclasses import asdict
from datetime import date, datetime
from functools import lru_cache
from typing import Any

import structlog

from app.core.config import get_settings
from app.engines.timeline.timeline_builder import (
    ConstructedTimeline,
    EntityReference,
    EntityTimelineView,
    TimelineEvent,
    TimelineSegment,
    TimelineStatistics,
)
from app.models.entity import EntityType
from app.models.timeline import EventType
from app.services.memory import matter_key

logger = structlog.get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Cache TTL for timeline data (1 hour - refreshed on new events)
TIMELINE_CACHE_TTL = 60 * 60

# Cache key suffixes
CACHE_SUFFIX_TIMELINE = "timeline"
CACHE_SUFFIX_STATS = "timeline_stats"
CACHE_SUFFIX_ENTITY_VIEW = "timeline_entity"


# =============================================================================
# JSON Serialization Helpers
# =============================================================================


class TimelineCacheEncoder(json.JSONEncoder):
    """JSON encoder for timeline cache data."""

    def default(self, obj: Any) -> Any:
        # datetime must be checked before date (datetime is a subclass of date)
        if isinstance(obj, datetime):
            return {"__datetime__": obj.isoformat()}
        if isinstance(obj, date):
            return {"__date__": obj.isoformat()}
        if isinstance(obj, EventType):
            return {"__event_type__": obj.value}
        if isinstance(obj, EntityType):
            return {"__entity_type__": obj.value}
        return super().default(obj)


def timeline_decoder(obj: dict) -> Any:
    """JSON decoder hook for timeline cache data."""
    if "__date__" in obj:
        return date.fromisoformat(obj["__date__"])
    if "__datetime__" in obj:
        return datetime.fromisoformat(obj["__datetime__"])
    if "__event_type__" in obj:
        try:
            return EventType(obj["__event_type__"])
        except ValueError:
            return EventType.UNCLASSIFIED
    if "__entity_type__" in obj:
        try:
            return EntityType(obj["__entity_type__"])
        except ValueError:
            return EntityType.PERSON
    return obj


def _serialize_timeline(timeline: ConstructedTimeline) -> str:
    """Serialize a ConstructedTimeline to JSON string."""
    data = {
        "matter_id": timeline.matter_id,
        "events": [_event_to_dict(e) for e in timeline.events],
        "segments": [_segment_to_dict(s) for s in timeline.segments],
        "entity_views": [_entity_view_to_dict(v) for v in timeline.entity_views],
        "statistics": _stats_to_dict(timeline.statistics),
        "generated_at": timeline.generated_at,
        "page": timeline.page,
        "per_page": timeline.per_page,
        "total_events": timeline.total_events,
        "total_pages": timeline.total_pages,
    }
    return json.dumps(data, cls=TimelineCacheEncoder)


def _deserialize_timeline(json_str: str) -> ConstructedTimeline:
    """Deserialize a JSON string to ConstructedTimeline."""
    data = json.loads(json_str, object_hook=timeline_decoder)

    return ConstructedTimeline(
        matter_id=data["matter_id"],
        events=[_dict_to_event(e) for e in data["events"]],
        segments=[_dict_to_segment(s) for s in data["segments"]],
        entity_views=[_dict_to_entity_view(v) for v in data["entity_views"]],
        statistics=_dict_to_stats(data["statistics"]),
        generated_at=data["generated_at"],
        page=data["page"],
        per_page=data["per_page"],
        total_events=data["total_events"],
        total_pages=data["total_pages"],
    )


def _event_to_dict(event: TimelineEvent) -> dict:
    """Convert TimelineEvent to dict."""
    return {
        "event_id": event.event_id,
        "event_date": event.event_date,
        "event_date_precision": event.event_date_precision,
        "event_date_text": event.event_date_text,
        "event_type": event.event_type,
        "description": event.description,
        "document_id": event.document_id,
        "document_name": event.document_name,
        "source_page": event.source_page,
        "confidence": event.confidence,
        "entities": [_entity_ref_to_dict(e) for e in event.entities],
        "is_ambiguous": event.is_ambiguous,
        "is_verified": event.is_verified,
    }


def _dict_to_event(data: dict) -> TimelineEvent:
    """Convert dict to TimelineEvent."""
    return TimelineEvent(
        event_id=data["event_id"],
        event_date=data["event_date"],
        event_date_precision=data["event_date_precision"],
        event_date_text=data.get("event_date_text"),
        event_type=data["event_type"],
        description=data["description"],
        document_id=data.get("document_id"),
        document_name=data.get("document_name"),
        source_page=data.get("source_page"),
        confidence=data.get("confidence", 0.8),
        entities=[_dict_to_entity_ref(e) for e in data.get("entities", [])],
        is_ambiguous=data.get("is_ambiguous", False),
        is_verified=data.get("is_verified", False),
    )


def _entity_ref_to_dict(ref: EntityReference) -> dict:
    """Convert EntityReference to dict."""
    return {
        "entity_id": ref.entity_id,
        "canonical_name": ref.canonical_name,
        "entity_type": ref.entity_type,
        "role": ref.role,
    }


def _dict_to_entity_ref(data: dict) -> EntityReference:
    """Convert dict to EntityReference."""
    return EntityReference(
        entity_id=data["entity_id"],
        canonical_name=data["canonical_name"],
        entity_type=data["entity_type"],
        role=data.get("role"),
    )


def _segment_to_dict(segment: TimelineSegment) -> dict:
    """Convert TimelineSegment to dict."""
    return {
        "period_start": segment.period_start,
        "period_end": segment.period_end,
        "period_label": segment.period_label,
        "events": [_event_to_dict(e) for e in segment.events],
        "event_count": segment.event_count,
    }


def _dict_to_segment(data: dict) -> TimelineSegment:
    """Convert dict to TimelineSegment."""
    return TimelineSegment(
        period_start=data["period_start"],
        period_end=data["period_end"],
        period_label=data["period_label"],
        events=[_dict_to_event(e) for e in data.get("events", [])],
        event_count=data["event_count"],
    )


def _entity_view_to_dict(view: EntityTimelineView) -> dict:
    """Convert EntityTimelineView to dict."""
    return {
        "entity_id": view.entity_id,
        "entity_name": view.entity_name,
        "entity_type": view.entity_type,
        "events": [_event_to_dict(e) for e in view.events],
        "first_appearance": view.first_appearance,
        "last_appearance": view.last_appearance,
        "event_count": view.event_count,
    }


def _dict_to_entity_view(data: dict) -> EntityTimelineView:
    """Convert dict to EntityTimelineView."""
    return EntityTimelineView(
        entity_id=data["entity_id"],
        entity_name=data["entity_name"],
        entity_type=data["entity_type"],
        events=[_dict_to_event(e) for e in data.get("events", [])],
        first_appearance=data.get("first_appearance"),
        last_appearance=data.get("last_appearance"),
        event_count=data["event_count"],
    )


def _stats_to_dict(stats: TimelineStatistics) -> dict:
    """Convert TimelineStatistics to dict."""
    return {
        "total_events": stats.total_events,
        "events_by_type": stats.events_by_type,
        "entities_involved": stats.entities_involved,
        "date_range_start": stats.date_range_start,
        "date_range_end": stats.date_range_end,
        "events_with_entities": stats.events_with_entities,
        "events_without_entities": stats.events_without_entities,
        "verified_events": stats.verified_events,
    }


def _dict_to_stats(data: dict) -> TimelineStatistics:
    """Convert dict to TimelineStatistics."""
    return TimelineStatistics(
        total_events=data["total_events"],
        events_by_type=data["events_by_type"],
        entities_involved=data["entities_involved"],
        date_range_start=data.get("date_range_start"),
        date_range_end=data.get("date_range_end"),
        events_with_entities=data["events_with_entities"],
        events_without_entities=data["events_without_entities"],
        verified_events=data["verified_events"],
    )


# =============================================================================
# Service Implementation
# =============================================================================


class TimelineCacheService:
    """Service for caching timeline data in Redis.

    Provides matter-level caching for constructed timelines to improve
    performance for repeated queries.

    Cache keys:
    - matter:{matter_id}:timeline:{page}:{per_page} - Full timeline pages
    - matter:{matter_id}:timeline_stats - Timeline statistics
    - matter:{matter_id}:timeline_entity:{entity_id} - Entity-focused views

    Example:
        >>> cache = TimelineCacheService()
        >>> await cache.set_timeline(matter_id, timeline)
        >>> cached = await cache.get_timeline(matter_id, page=1, per_page=50)
    """

    def __init__(self) -> None:
        """Initialize timeline cache service."""
        self._redis = None
        self._settings = get_settings()

    @property
    def redis(self):
        """Get Redis client.

        Returns Redis client if configured, None otherwise.
        Cache operations gracefully degrade to no-op when Redis unavailable.
        """
        if self._redis is None:
            try:
                import redis

                redis_url = self._settings.redis_url
                if redis_url:
                    self._redis = redis.from_url(
                        redis_url, decode_responses=True
                    )
                    # Test connection
                    self._redis.ping()
                    logger.debug("timeline_cache_redis_connected")
                else:
                    logger.debug("timeline_cache_no_redis_url")
                    return None
            except Exception as e:
                logger.warning(
                    "timeline_cache_redis_unavailable",
                    error=str(e),
                )
                return None

        return self._redis

    # =========================================================================
    # Timeline Cache Operations
    # =========================================================================

    async def get_timeline(
        self,
        matter_id: str,
        page: int = 1,
        per_page: int = 50,
    ) -> ConstructedTimeline | None:
        """Get cached timeline for a matter.

        Args:
            matter_id: Matter UUID.
            page: Page number.
            per_page: Items per page.

        Returns:
            ConstructedTimeline if cached, None otherwise.
        """
        if not self.redis:
            return None

        try:
            key = f"{matter_key(matter_id, 'timeline')}:{page}:{per_page}"
            cached = self.redis.get(key)

            if cached:
                logger.debug(
                    "timeline_cache_hit",
                    matter_id=matter_id,
                    page=page,
                )
                return _deserialize_timeline(cached)

            logger.debug(
                "timeline_cache_miss",
                matter_id=matter_id,
                page=page,
            )
            return None

        except Exception as e:
            logger.warning(
                "timeline_cache_get_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return None

    async def set_timeline(
        self,
        matter_id: str,
        timeline: ConstructedTimeline,
        ttl: int = TIMELINE_CACHE_TTL,
    ) -> bool:
        """Cache a timeline for a matter.

        Args:
            matter_id: Matter UUID.
            timeline: ConstructedTimeline to cache.
            ttl: Time to live in seconds.

        Returns:
            True if cached successfully.
        """
        if not self.redis:
            return False

        try:
            key = f"{matter_key(matter_id, 'timeline')}:{timeline.page}:{timeline.per_page}"
            serialized = _serialize_timeline(timeline)
            self.redis.setex(key, ttl, serialized)

            logger.debug(
                "timeline_cache_set",
                matter_id=matter_id,
                page=timeline.page,
                ttl=ttl,
            )
            return True

        except Exception as e:
            logger.warning(
                "timeline_cache_set_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return False

    # =========================================================================
    # Statistics Cache Operations
    # =========================================================================

    async def get_statistics(
        self,
        matter_id: str,
    ) -> TimelineStatistics | None:
        """Get cached timeline statistics.

        Args:
            matter_id: Matter UUID.

        Returns:
            TimelineStatistics if cached, None otherwise.
        """
        if not self.redis:
            return None

        try:
            key = f"{matter_key(matter_id, 'stats')}:timeline"
            cached = self.redis.get(key)

            if cached:
                data = json.loads(cached, object_hook=timeline_decoder)
                return _dict_to_stats(data)

            return None

        except Exception as e:
            logger.warning(
                "timeline_stats_cache_get_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return None

    async def set_statistics(
        self,
        matter_id: str,
        stats: TimelineStatistics,
        ttl: int = TIMELINE_CACHE_TTL,
    ) -> bool:
        """Cache timeline statistics.

        Args:
            matter_id: Matter UUID.
            stats: TimelineStatistics to cache.
            ttl: Time to live in seconds.

        Returns:
            True if cached successfully.
        """
        if not self.redis:
            return False

        try:
            key = f"{matter_key(matter_id, 'stats')}:timeline"
            serialized = json.dumps(_stats_to_dict(stats), cls=TimelineCacheEncoder)
            self.redis.setex(key, ttl, serialized)

            logger.debug(
                "timeline_stats_cache_set",
                matter_id=matter_id,
                ttl=ttl,
            )
            return True

        except Exception as e:
            logger.warning(
                "timeline_stats_cache_set_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return False

    # =========================================================================
    # Entity View Cache Operations
    # =========================================================================

    async def get_entity_view(
        self,
        matter_id: str,
        entity_id: str,
    ) -> EntityTimelineView | None:
        """Get cached entity timeline view.

        Args:
            matter_id: Matter UUID.
            entity_id: Entity UUID.

        Returns:
            EntityTimelineView if cached, None otherwise.
        """
        if not self.redis:
            return None

        try:
            key = f"{matter_key(matter_id, 'timeline')}:entity:{entity_id}"
            cached = self.redis.get(key)

            if cached:
                data = json.loads(cached, object_hook=timeline_decoder)
                return _dict_to_entity_view(data)

            return None

        except Exception as e:
            logger.warning(
                "entity_view_cache_get_failed",
                matter_id=matter_id,
                entity_id=entity_id,
                error=str(e),
            )
            return None

    async def set_entity_view(
        self,
        matter_id: str,
        entity_id: str,
        view: EntityTimelineView,
        ttl: int = TIMELINE_CACHE_TTL,
    ) -> bool:
        """Cache entity timeline view.

        Args:
            matter_id: Matter UUID.
            entity_id: Entity UUID.
            view: EntityTimelineView to cache.
            ttl: Time to live in seconds.

        Returns:
            True if cached successfully.
        """
        if not self.redis:
            return False

        try:
            key = f"{matter_key(matter_id, 'timeline')}:entity:{entity_id}"
            serialized = json.dumps(_entity_view_to_dict(view), cls=TimelineCacheEncoder)
            self.redis.setex(key, ttl, serialized)

            logger.debug(
                "entity_view_cache_set",
                matter_id=matter_id,
                entity_id=entity_id,
                ttl=ttl,
            )
            return True

        except Exception as e:
            logger.warning(
                "entity_view_cache_set_failed",
                matter_id=matter_id,
                entity_id=entity_id,
                error=str(e),
            )
            return False

    # =========================================================================
    # Cache Invalidation
    # =========================================================================

    async def invalidate_timeline(self, matter_id: str) -> int:
        """Invalidate all timeline cache entries for a matter.

        Call this when events are added, updated, or entity links change.

        Args:
            matter_id: Matter UUID.

        Returns:
            Number of cache entries deleted.
        """
        if not self.redis:
            return 0

        try:
            # Use SCAN to find all timeline-related keys
            pattern = f"{matter_key(matter_id, 'timeline')}:*"
            stats_key = f"{matter_key(matter_id, 'stats')}:timeline"

            deleted = 0
            cursor = 0

            # Delete timeline keys
            while True:
                cursor, keys = self.redis.scan(cursor, match=pattern, count=100)
                if keys:
                    deleted += self.redis.delete(*keys)
                if cursor == 0:
                    break

            # Delete stats key
            if self.redis.delete(stats_key):
                deleted += 1

            logger.info(
                "timeline_cache_invalidated",
                matter_id=matter_id,
                keys_deleted=deleted,
            )

            return deleted

        except Exception as e:
            logger.warning(
                "timeline_cache_invalidate_failed",
                matter_id=matter_id,
                error=str(e),
            )
            return 0

    async def invalidate_entity_view(
        self,
        matter_id: str,
        entity_id: str,
    ) -> bool:
        """Invalidate a specific entity view cache entry.

        Args:
            matter_id: Matter UUID.
            entity_id: Entity UUID.

        Returns:
            True if cache entry was deleted.
        """
        if not self.redis:
            return False

        try:
            key = f"{matter_key(matter_id, 'timeline')}:entity:{entity_id}"
            deleted = self.redis.delete(key)

            if deleted:
                logger.debug(
                    "entity_view_cache_invalidated",
                    matter_id=matter_id,
                    entity_id=entity_id,
                )

            return deleted > 0

        except Exception as e:
            logger.warning(
                "entity_view_cache_invalidate_failed",
                matter_id=matter_id,
                entity_id=entity_id,
                error=str(e),
            )
            return False


# =============================================================================
# Service Factory
# =============================================================================


@lru_cache(maxsize=1)
def get_timeline_cache_service() -> TimelineCacheService:
    """Get singleton timeline cache service instance.

    Returns:
        TimelineCacheService instance.
    """
    return TimelineCacheService()
