"""Tests for Matter Memory Service.

Story 7-3: Matter Memory PostgreSQL JSONB Storage
Task 5.3: Unit tests for MatterMemoryService facade methods.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.memory import (
    CachedEntity,
    EntityGraphCache,
    EntityRelationship,
    QueryHistory,
    QueryHistoryEntry,
    TimelineCache,
    TimelineCacheEntry,
)
from app.services.memory.matter_service import (
    MatterMemoryService,
    get_matter_memory_service,
    reset_matter_memory_service,
)


# Valid UUIDs for testing
MATTER_ID = "12345678-1234-1234-1234-123456789abc"
USER_ID = "abcdefab-abcd-abcd-abcd-abcdefabcdef"


@pytest.fixture
def mock_repository() -> MagicMock:
    """Create a mock MatterMemoryRepository."""
    mock = MagicMock()

    # Setup async mock methods
    mock.append_query = AsyncMock(return_value="record-id")
    mock.get_query_history = AsyncMock(return_value=QueryHistory(entries=[]))
    mock.get_timeline_cache = AsyncMock(return_value=None)
    mock.set_timeline_cache = AsyncMock(return_value="record-id")
    mock.invalidate_timeline_cache = AsyncMock(return_value=True)
    mock.get_entity_graph_cache = AsyncMock(return_value=None)
    mock.set_entity_graph_cache = AsyncMock(return_value="record-id")
    mock.invalidate_entity_graph_cache = AsyncMock(return_value=True)
    mock.set_memory = AsyncMock(return_value="record-id")

    return mock


@pytest.fixture
def service(mock_repository: MagicMock) -> MatterMemoryService:
    """Create a MatterMemoryService with mock repository."""
    reset_matter_memory_service()
    return MatterMemoryService(mock_repository)


class TestLogQuery:
    """Tests for log_query method (Story 7-3: Task 5.3)."""

    @pytest.mark.asyncio
    async def test_log_query_basic(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should log query with required fields."""
        result = await service.log_query(
            matter_id=MATTER_ID,
            query_id="query-123",
            query_text="What is the timeline?",
            asked_by=USER_ID,
        )

        assert result == "record-id"
        mock_repository.append_query.assert_called_once()

        call_args = mock_repository.append_query.call_args
        assert call_args[0][0] == MATTER_ID
        entry = call_args[0][1]
        assert entry.query_id == "query-123"
        assert entry.query_text == "What is the timeline?"
        assert entry.asked_by == USER_ID

    @pytest.mark.asyncio
    async def test_log_query_with_optional_fields(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should log query with all optional fields."""
        result = await service.log_query(
            matter_id=MATTER_ID,
            query_id="query-123",
            query_text="What is the timeline?",
            asked_by=USER_ID,
            normalized_query="timeline",
            response_summary="Events from 2020-2025",
            engines_used=["timeline", "citation"],
            confidence=85.0,
            tokens_used=1500,
            cost_usd=0.045,
        )

        call_args = mock_repository.append_query.call_args
        entry = call_args[0][1]
        assert entry.normalized_query == "timeline"
        assert entry.engines_used == ["timeline", "citation"]
        assert entry.confidence == 85.0
        assert entry.tokens_used == 1500
        assert entry.cost_usd == 0.045


class TestGetQueryHistory:
    """Tests for get_query_history method."""

    @pytest.mark.asyncio
    async def test_get_query_history_delegates(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should delegate to repository."""
        mock_repository.get_query_history.return_value = QueryHistory(
            entries=[
                QueryHistoryEntry(
                    query_id="q1",
                    query_text="Test",
                    asked_by=USER_ID,
                    asked_at="2026-01-14T10:00:00Z",
                )
            ]
        )

        history = await service.get_query_history(MATTER_ID, limit=50)

        mock_repository.get_query_history.assert_called_once_with(MATTER_ID, 50)
        assert len(history.entries) == 1


class TestMarkQueryVerified:
    """Tests for mark_query_verified method."""

    @pytest.mark.asyncio
    async def test_mark_query_verified_success(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should mark query as verified."""
        mock_repository.get_query_history.return_value = QueryHistory(
            entries=[
                QueryHistoryEntry(
                    query_id="query-123",
                    query_text="Test",
                    asked_by=USER_ID,
                    asked_at="2026-01-14T10:00:00Z",
                    verified=False,
                )
            ]
        )

        result = await service.mark_query_verified(
            matter_id=MATTER_ID,
            query_id="query-123",
            verified_by="attorney-456",
        )

        assert result is True
        mock_repository.set_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_query_verified_not_found(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should return False when query not found."""
        mock_repository.get_query_history.return_value = QueryHistory(entries=[])

        result = await service.mark_query_verified(
            matter_id=MATTER_ID,
            query_id="nonexistent",
            verified_by="attorney-456",
        )

        assert result is False
        mock_repository.set_memory.assert_not_called()


class TestGetOrBuildTimeline:
    """Tests for get_or_build_timeline method."""

    @pytest.mark.asyncio
    async def test_cache_hit(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should return cached timeline when valid."""
        cached = TimelineCache(
            cached_at="2026-01-14T10:00:00Z",
            events=[],
            event_count=0,
        )
        mock_repository.get_timeline_cache.return_value = cached

        # No docs uploaded after cache = not stale
        result = await service.get_or_build_timeline(
            matter_id=MATTER_ID,
            last_document_upload=None,
        )

        assert result is cached
        mock_repository.set_timeline_cache.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_no_builder(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should return None when no cache and no builder."""
        mock_repository.get_timeline_cache.return_value = None

        result = await service.get_or_build_timeline(MATTER_ID)

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_stale_rebuilds(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should rebuild when cache is stale."""
        # Stale cache
        stale_cache = TimelineCache(
            cached_at="2026-01-14T10:00:00Z",
            events=[],
            event_count=0,
            version=1,
        )
        mock_repository.get_timeline_cache.return_value = stale_cache

        # Builder function
        async def builder(matter_id: str) -> list[TimelineCacheEntry]:
            return [
                TimelineCacheEntry(
                    event_id="evt-1",
                    event_date="2025-01-01",
                    event_type="filing",
                    description="New filing",
                )
            ]

        # Doc uploaded after cache = stale
        result = await service.get_or_build_timeline(
            matter_id=MATTER_ID,
            last_document_upload="2026-01-14T12:00:00Z",
            builder_fn=builder,
        )

        assert result is not None
        assert result.event_count == 1
        assert result.version == 2  # Incremented
        mock_repository.set_timeline_cache.assert_called_once()


class TestSetTimelineCache:
    """Tests for set_timeline_cache method."""

    @pytest.mark.asyncio
    async def test_set_timeline_cache_creates(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should create new timeline cache."""
        events = [
            TimelineCacheEntry(
                event_id="evt-1",
                event_date="2025-01-01",
                event_type="filing",
                description="Filing",
            ),
            TimelineCacheEntry(
                event_id="evt-2",
                event_date="2025-06-15",
                event_type="hearing",
                description="Hearing",
            ),
        ]

        cache = await service.set_timeline_cache(
            matter_id=MATTER_ID,
            events=events,
            last_document_upload="2026-01-14T10:00:00Z",
        )

        assert cache.event_count == 2
        assert cache.version == 1  # First version
        # Events should be sorted
        assert cache.events[0].event_date == "2025-01-01"
        assert cache.events[1].event_date == "2025-06-15"


class TestGetOrBuildEntityGraph:
    """Tests for get_or_build_entity_graph method."""

    @pytest.mark.asyncio
    async def test_cache_hit(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should return cached entity graph when valid."""
        cached = EntityGraphCache(
            cached_at="2026-01-14T10:00:00Z",
            entities={},
            relationships=[],
            entity_count=0,
            relationship_count=0,
        )
        mock_repository.get_entity_graph_cache.return_value = cached

        result = await service.get_or_build_entity_graph(
            matter_id=MATTER_ID,
            last_document_upload=None,
        )

        assert result is cached
        mock_repository.set_entity_graph_cache.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_no_builder(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should return None when no cache and no builder."""
        mock_repository.get_entity_graph_cache.return_value = None

        result = await service.get_or_build_entity_graph(MATTER_ID)

        assert result is None


class TestSetEntityGraphCache:
    """Tests for set_entity_graph_cache method."""

    @pytest.mark.asyncio
    async def test_set_entity_graph_cache_creates(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should create new entity graph cache."""
        entities = {
            "e1": CachedEntity(
                entity_id="e1",
                canonical_name="John Smith",
                entity_type="PERSON",
            )
        }
        relationships = [
            EntityRelationship(
                source_id="e1",
                target_id="e2",
                relationship_type="KNOWS",
            )
        ]

        cache = await service.set_entity_graph_cache(
            matter_id=MATTER_ID,
            entities=entities,
            relationships=relationships,
            last_document_upload="2026-01-14T10:00:00Z",
        )

        assert cache.entity_count == 1
        assert cache.relationship_count == 1
        assert "e1" in cache.entities


class TestInvalidateMatterCaches:
    """Tests for invalidate_matter_caches method."""

    @pytest.mark.asyncio
    async def test_invalidates_both_caches(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should invalidate timeline and entity graph caches."""
        result = await service.invalidate_matter_caches(MATTER_ID)

        assert result["timeline_cache"] is True
        assert result["entity_graph_cache"] is True
        mock_repository.invalidate_timeline_cache.assert_called_once_with(MATTER_ID)
        mock_repository.invalidate_entity_graph_cache.assert_called_once_with(MATTER_ID)


class TestStalenessChecks:
    """Tests for is_timeline_stale and is_entity_graph_stale methods."""

    @pytest.mark.asyncio
    async def test_is_timeline_stale_no_cache(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should return True when no cache exists."""
        mock_repository.get_timeline_cache.return_value = None

        stale = await service.is_timeline_stale(MATTER_ID, "2026-01-14T10:00:00Z")

        assert stale is True

    @pytest.mark.asyncio
    async def test_is_timeline_stale_with_cache(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should check staleness when cache exists."""
        mock_repository.get_timeline_cache.return_value = TimelineCache(
            cached_at="2026-01-14T10:00:00Z",
            events=[],
            event_count=0,
        )

        # Doc uploaded after cache = stale
        stale = await service.is_timeline_stale(MATTER_ID, "2026-01-14T12:00:00Z")

        assert stale is True

    @pytest.mark.asyncio
    async def test_is_entity_graph_stale_no_cache(
        self,
        service: MatterMemoryService,
        mock_repository: MagicMock,
    ) -> None:
        """Should return True when no cache exists."""
        mock_repository.get_entity_graph_cache.return_value = None

        stale = await service.is_entity_graph_stale(MATTER_ID, "2026-01-14T10:00:00Z")

        assert stale is True


class TestServiceFactory:
    """Tests for factory functions."""

    def teardown_method(self) -> None:
        """Reset singleton after each test."""
        reset_matter_memory_service()

    def test_get_matter_memory_service_singleton(self) -> None:
        """Factory should return same instance."""
        reset_matter_memory_service()

        with patch(
            "app.services.memory.matter_service.get_matter_memory_repository"
        ) as mock:
            mock.return_value = MagicMock()

            service1 = get_matter_memory_service()
            service2 = get_matter_memory_service()

            assert service1 is service2

    def test_get_matter_memory_service_with_repository(self) -> None:
        """Factory should accept custom repository."""
        reset_matter_memory_service()
        mock_repo = MagicMock()

        service = get_matter_memory_service(mock_repo)

        assert service._repository is mock_repo

    def test_reset_matter_memory_service(self) -> None:
        """Reset should clear the singleton."""
        with patch(
            "app.services.memory.matter_service.get_matter_memory_repository"
        ) as mock:
            mock.return_value = MagicMock()

            get_matter_memory_service()
            reset_matter_memory_service()

            service = get_matter_memory_service()
            assert service is not None
