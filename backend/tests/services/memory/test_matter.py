"""Tests for Matter Memory Repository.

Story 7-2: Session TTL and Context Restoration
Story 7-3: Matter Memory PostgreSQL JSONB Storage
Tasks 7.2, 7.6: Test session archival and matter isolation.
Tasks 5.2-5.7: Test query history, timeline cache, entity graph, and staleness.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.models.memory import (
    ArchivedSession,
    CachedEntity,
    EntityGraphCache,
    EntityRelationship,
    QueryHistory,
    QueryHistoryEntry,
    SessionEntityMention,
    SessionMessage,
    TimelineCache,
    TimelineCacheEntry,
)
from app.services.memory.matter import (
    ARCHIVED_SESSION_TYPE,
    ENTITY_GRAPH_TYPE,
    QUERY_HISTORY_TYPE,
    TIMELINE_CACHE_TYPE,
    MatterMemoryRepository,
    get_matter_memory_repository,
    is_cache_stale,
    reset_matter_memory_repository,
)


# Valid UUIDs for testing
MATTER_ID = "12345678-1234-1234-1234-123456789abc"
USER_ID = "abcdefab-abcd-abcd-abcd-abcdefabcdef"
MATTER_ID_2 = "87654321-4321-4321-4321-987654321fed"
USER_ID_2 = "fedcbafe-fedc-fedc-fedc-fedcbafedcba"


@pytest.fixture
def mock_supabase() -> MagicMock:
    """Create a mock Supabase client for testing."""
    mock = MagicMock()

    # Setup default response chain for insert
    mock.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "test-record-id"}
    ]

    # Setup default response chain for get_latest (3 eq calls: matter_id, memory_type, user_id)
    mock.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = (
        []
    )

    # Setup default response chain for get_archived_sessions (variable eq calls)
    mock.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value.data = (
        []
    )
    # With user_id filter
    mock.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value.data = (
        []
    )

    return mock


@pytest.fixture
def matter_repo(mock_supabase: MagicMock) -> MatterMemoryRepository:
    """Create a matter memory repository with mock Supabase."""
    reset_matter_memory_repository()
    return MatterMemoryRepository(mock_supabase)


@pytest.fixture
def sample_archived_session() -> ArchivedSession:
    """Create a sample archived session for testing."""
    return ArchivedSession(
        session_id="session-123",
        matter_id=MATTER_ID,
        user_id=USER_ID,
        created_at="2026-01-14T10:00:00Z",
        archived_at="2026-01-14T18:00:00Z",
        last_activity="2026-01-14T17:55:00Z",
        entities_mentioned={
            "e1": SessionEntityMention(
                entity_id="e1",
                entity_name="John Smith",
                entity_type="person",
                aliases=["John", "J. Smith"],
                mention_count=5,
                last_mentioned="2026-01-14T17:50:00Z",
            )
        },
        last_messages=[
            SessionMessage(
                role="user",
                content="Tell me about John Smith",
                timestamp="2026-01-14T17:50:00Z",
                entity_refs=["e1"],
            ),
            SessionMessage(
                role="assistant",
                content="John Smith is the plaintiff in this case...",
                timestamp="2026-01-14T17:51:00Z",
                entity_refs=["e1"],
            ),
        ],
        total_query_count=10,
        total_messages=20,
        ttl_extended_count=3,
        archival_reason="manual_end",
    )


class TestSaveArchivedSession:
    """Tests for save_archived_session (Task 7.2)."""

    @pytest.mark.asyncio
    async def test_save_archived_session_basic(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
        sample_archived_session: ArchivedSession,
    ) -> None:
        """Should save archived session to PostgreSQL."""
        record_id = await matter_repo.save_archived_session(sample_archived_session)

        assert record_id == "test-record-id"
        mock_supabase.table.assert_called_with("matter_memory")

    @pytest.mark.asyncio
    async def test_save_archived_session_correct_data(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
        sample_archived_session: ArchivedSession,
    ) -> None:
        """Should save with correct memory_type and data."""
        await matter_repo.save_archived_session(sample_archived_session)

        insert_call = mock_supabase.table.return_value.insert
        insert_call.assert_called_once()

        call_args = insert_call.call_args[0][0]
        assert call_args["matter_id"] == MATTER_ID
        assert call_args["memory_type"] == ARCHIVED_SESSION_TYPE
        assert call_args["data"]["session_id"] == "session-123"
        assert call_args["data"]["user_id"] == USER_ID

    @pytest.mark.asyncio
    async def test_save_archived_session_preserves_entities(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
        sample_archived_session: ArchivedSession,
    ) -> None:
        """Should preserve entity mentions in saved data."""
        await matter_repo.save_archived_session(sample_archived_session)

        call_args = mock_supabase.table.return_value.insert.call_args[0][0]
        entities = call_args["data"]["entities_mentioned"]

        assert "e1" in entities
        assert entities["e1"]["entity_name"] == "John Smith"
        assert entities["e1"]["mention_count"] == 5


class TestGetLatestArchivedSession:
    """Tests for get_latest_archived_session (Task 7.3)."""

    @pytest.mark.asyncio
    async def test_get_latest_archived_session_found(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
        sample_archived_session: ArchivedSession,
    ) -> None:
        """Should return latest archived session when found."""
        # Setup mock to return archived session data (3 eq calls: matter_id, memory_type, user_id)
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {"data": sample_archived_session.model_dump(mode="json")}
        ]

        result = await matter_repo.get_latest_archived_session(MATTER_ID, USER_ID)

        assert result is not None
        assert result.session_id == "session-123"
        assert result.user_id == USER_ID
        assert "e1" in result.entities_mentioned

    @pytest.mark.asyncio
    async def test_get_latest_archived_session_not_found(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Should return None when no archived session exists."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = (
            []
        )

        result = await matter_repo.get_latest_archived_session(MATTER_ID, USER_ID)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_latest_archived_session_queries_with_user_filter(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
        sample_archived_session: ArchivedSession,
    ) -> None:
        """Should filter by user_id in SQL query (defense-in-depth)."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {"data": sample_archived_session.model_dump(mode="json")}
        ]

        await matter_repo.get_latest_archived_session(MATTER_ID, USER_ID)

        # Verify all 3 eq calls were made (matter_id, memory_type, user_id filter)
        eq_calls = mock_supabase.table.return_value.select.return_value.eq.call_args_list
        # First eq call should be matter_id
        assert eq_calls[0][0] == ("matter_id", MATTER_ID)


class TestGetArchivedSessions:
    """Tests for get_archived_sessions (Task 7.4)."""

    @pytest.mark.asyncio
    async def test_get_archived_sessions_with_pagination(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
        sample_archived_session: ArchivedSession,
    ) -> None:
        """Should return list with pagination."""
        # With user_id filter, there are 3 eq calls: matter_id, memory_type, user_id
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value.data = [
            {"data": sample_archived_session.model_dump(mode="json")}
        ]

        result = await matter_repo.get_archived_sessions(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            limit=10,
            offset=0,
        )

        assert len(result) == 1
        assert result[0].session_id == "session-123"

    @pytest.mark.asyncio
    async def test_get_archived_sessions_empty(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Should return empty list when no sessions."""
        # Without user_id filter, there are 2 eq calls: matter_id, memory_type
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value.data = (
            []
        )

        result = await matter_repo.get_archived_sessions(MATTER_ID)

        assert result == []


class TestMatterIsolation:
    """Tests for matter isolation (Task 7.6)."""

    @pytest.mark.asyncio
    async def test_archived_session_matter_isolation(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Archived sessions should be filtered by matter_id."""
        await matter_repo.get_latest_archived_session(MATTER_ID, USER_ID)

        # Verify query filters by matter_id
        eq_calls = mock_supabase.table.return_value.select.return_value.eq.call_args_list
        assert any(call[0] == ("matter_id", MATTER_ID) for call in eq_calls)

    @pytest.mark.asyncio
    async def test_save_includes_matter_id(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
        sample_archived_session: ArchivedSession,
    ) -> None:
        """Save should include matter_id for RLS."""
        await matter_repo.save_archived_session(sample_archived_session)

        call_args = mock_supabase.table.return_value.insert.call_args[0][0]
        assert call_args["matter_id"] == MATTER_ID


class TestServiceFactory:
    """Tests for factory functions."""

    def teardown_method(self) -> None:
        """Reset singleton after each test."""
        reset_matter_memory_repository()

    def test_get_matter_memory_repository_singleton(self) -> None:
        """Factory should return same instance."""
        reset_matter_memory_repository()

        repo1 = get_matter_memory_repository()
        repo2 = get_matter_memory_repository()

        assert repo1 is repo2

    def test_get_matter_memory_repository_with_client(self) -> None:
        """Factory should accept custom Supabase client."""
        reset_matter_memory_repository()
        mock_supabase = MagicMock()

        repo = get_matter_memory_repository(mock_supabase)

        assert repo._supabase is mock_supabase

    def test_reset_matter_memory_repository(self) -> None:
        """Reset should clear the singleton."""
        get_matter_memory_repository()
        reset_matter_memory_repository()

        repo = get_matter_memory_repository()
        assert repo is not None


# =============================================================================
# Story 7-3: Query History Tests (Task 5.2, 5.4)
# =============================================================================


class TestQueryHistoryMethods:
    """Tests for query history repository methods (Story 7-3: Task 5.2)."""

    @pytest.mark.asyncio
    async def test_get_query_history_empty(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Should return empty history when none exists."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = (
            None
        )

        history = await matter_repo.get_query_history(MATTER_ID)

        assert history.entries == []

    @pytest.mark.asyncio
    async def test_get_query_history_with_entries(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Should return query history entries."""
        entries_data = [
            {
                "query_id": "q1",
                "query_text": "First query",
                "asked_by": USER_ID,
                "asked_at": "2026-01-14T10:00:00Z",
                "verified": False,
            },
            {
                "query_id": "q2",
                "query_text": "Second query",
                "asked_by": USER_ID,
                "asked_at": "2026-01-14T11:00:00Z",
                "verified": True,
            },
        ]
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "data": {"entries": entries_data}
        }

        history = await matter_repo.get_query_history(MATTER_ID)

        assert len(history.entries) == 2
        assert history.entries[0].query_id == "q1"
        assert history.entries[1].query_id == "q2"

    @pytest.mark.asyncio
    async def test_get_query_history_respects_limit(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Should respect limit parameter."""
        entries_data = [{"query_id": f"q{i}", "query_text": f"Query {i}", "asked_by": "u1", "asked_at": "2026-01-14T10:00:00Z"} for i in range(10)]
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "data": {"entries": entries_data}
        }

        history = await matter_repo.get_query_history(MATTER_ID, limit=5)

        # Should return last 5 entries (newest)
        assert len(history.entries) == 5

    @pytest.mark.asyncio
    async def test_append_query_uses_db_function(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Should use append_to_matter_memory DB function (Task 5.4)."""
        entry = QueryHistoryEntry(
            query_id="query-123",
            query_text="What is the timeline?",
            asked_by=USER_ID,
            asked_at="2026-01-14T10:00:00Z",
        )

        mock_supabase.rpc.return_value.execute.return_value.data = "record-id"

        await matter_repo.append_query(MATTER_ID, entry)

        # Verify DB function was called with correct params
        mock_supabase.rpc.assert_called_once()
        call_args = mock_supabase.rpc.call_args
        assert call_args[0][0] == "append_to_matter_memory"
        assert call_args[0][1]["p_matter_id"] == MATTER_ID
        assert call_args[0][1]["p_memory_type"] == QUERY_HISTORY_TYPE
        assert call_args[0][1]["p_key"] == "entries"


# =============================================================================
# Story 7-3: Timeline Cache Tests (Task 5.2, 5.5)
# =============================================================================


class TestTimelineCacheMethods:
    """Tests for timeline cache repository methods (Story 7-3: Task 5.2)."""

    @pytest.mark.asyncio
    async def test_get_timeline_cache_not_found(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Should return None when no cache exists."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = (
            None
        )

        cache = await matter_repo.get_timeline_cache(MATTER_ID)

        assert cache is None

    @pytest.mark.asyncio
    async def test_get_timeline_cache_found(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Should return timeline cache when exists."""
        cache_data = {
            "cached_at": "2026-01-14T10:00:00Z",
            "events": [
                {
                    "event_id": "evt-1",
                    "event_date": "2025-01-01",
                    "event_type": "filing",
                    "description": "Initial filing",
                }
            ],
            "event_count": 1,
        }
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "data": cache_data
        }

        cache = await matter_repo.get_timeline_cache(MATTER_ID)

        assert cache is not None
        assert cache.event_count == 1
        assert len(cache.events) == 1
        assert cache.events[0].event_id == "evt-1"

    @pytest.mark.asyncio
    async def test_set_timeline_cache_uses_upsert(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Should use upsert_matter_memory DB function."""
        cache = TimelineCache(
            cached_at="2026-01-14T10:00:00Z",
            events=[],
            event_count=0,
        )

        mock_supabase.rpc.return_value.execute.return_value.data = "record-id"

        await matter_repo.set_timeline_cache(MATTER_ID, cache)

        mock_supabase.rpc.assert_called_once()
        call_args = mock_supabase.rpc.call_args
        assert call_args[0][0] == "upsert_matter_memory"
        assert call_args[0][1]["p_matter_id"] == MATTER_ID
        assert call_args[0][1]["p_memory_type"] == TIMELINE_CACHE_TYPE

    @pytest.mark.asyncio
    async def test_invalidate_timeline_cache_deletes(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Should delete timeline cache (Task 5.5)."""
        mock_supabase.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"id": "record-id"}
        ]

        deleted = await matter_repo.invalidate_timeline_cache(MATTER_ID)

        assert deleted is True
        mock_supabase.table.return_value.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_timeline_cache_not_found(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Should return False when nothing to delete."""
        mock_supabase.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = (
            []
        )

        deleted = await matter_repo.invalidate_timeline_cache(MATTER_ID)

        assert deleted is False


# =============================================================================
# Story 7-3: Entity Graph Cache Tests (Task 5.2)
# =============================================================================


class TestEntityGraphCacheMethods:
    """Tests for entity graph cache repository methods (Story 7-3: Task 5.2)."""

    @pytest.mark.asyncio
    async def test_get_entity_graph_cache_not_found(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Should return None when no cache exists."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = (
            None
        )

        cache = await matter_repo.get_entity_graph_cache(MATTER_ID)

        assert cache is None

    @pytest.mark.asyncio
    async def test_get_entity_graph_cache_found(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Should return entity graph cache when exists."""
        cache_data = {
            "cached_at": "2026-01-14T10:00:00Z",
            "entities": {
                "e1": {
                    "entity_id": "e1",
                    "canonical_name": "John Smith",
                    "entity_type": "PERSON",
                }
            },
            "relationships": [
                {
                    "source_id": "e1",
                    "target_id": "e2",
                    "relationship_type": "KNOWS",
                }
            ],
            "entity_count": 1,
            "relationship_count": 1,
        }
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "data": cache_data
        }

        cache = await matter_repo.get_entity_graph_cache(MATTER_ID)

        assert cache is not None
        assert "e1" in cache.entities
        assert cache.entities["e1"].canonical_name == "John Smith"
        assert len(cache.relationships) == 1

    @pytest.mark.asyncio
    async def test_set_entity_graph_cache_uses_upsert(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Should use upsert_matter_memory DB function."""
        cache = EntityGraphCache(
            cached_at="2026-01-14T10:00:00Z",
            entities={},
            relationships=[],
            entity_count=0,
            relationship_count=0,
        )

        mock_supabase.rpc.return_value.execute.return_value.data = "record-id"

        await matter_repo.set_entity_graph_cache(MATTER_ID, cache)

        mock_supabase.rpc.assert_called_once()
        call_args = mock_supabase.rpc.call_args
        assert call_args[0][0] == "upsert_matter_memory"
        assert call_args[0][1]["p_memory_type"] == ENTITY_GRAPH_TYPE

    @pytest.mark.asyncio
    async def test_invalidate_entity_graph_cache_deletes(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Should delete entity graph cache."""
        mock_supabase.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {"id": "record-id"}
        ]

        deleted = await matter_repo.invalidate_entity_graph_cache(MATTER_ID)

        assert deleted is True


# =============================================================================
# Story 7-3: Cache Staleness Tests (Task 5.7)
# =============================================================================


class TestCacheStaleness:
    """Tests for cache staleness detection (Story 7-3: Task 5.7)."""

    def test_cache_stale_when_no_cache_timestamp(self) -> None:
        """Should be stale when cache timestamp is None."""
        assert is_cache_stale(None, "2026-01-14T10:00:00Z") is True

    def test_cache_not_stale_when_no_doc_upload(self) -> None:
        """Should not be stale when no docs uploaded."""
        assert is_cache_stale("2026-01-14T10:00:00Z", None) is False

    def test_cache_stale_when_doc_uploaded_after_cache(self) -> None:
        """Should be stale when doc uploaded after cache created."""
        cache_time = "2026-01-14T10:00:00Z"
        upload_time = "2026-01-14T11:00:00Z"
        assert is_cache_stale(cache_time, upload_time) is True

    def test_cache_not_stale_when_doc_uploaded_before_cache(self) -> None:
        """Should not be stale when cache created after last upload."""
        cache_time = "2026-01-14T11:00:00Z"
        upload_time = "2026-01-14T10:00:00Z"
        assert is_cache_stale(cache_time, upload_time) is False

    def test_cache_stale_with_timezone_z_suffix(self) -> None:
        """Should handle Z suffix in timestamps."""
        cache_time = "2026-01-14T10:00:00Z"
        upload_time = "2026-01-14T12:00:00Z"
        assert is_cache_stale(cache_time, upload_time) is True

    def test_cache_not_stale_same_time(self) -> None:
        """Should not be stale when timestamps are equal."""
        same_time = "2026-01-14T10:00:00Z"
        assert is_cache_stale(same_time, same_time) is False


# =============================================================================
# Story 7-3: Matter Isolation Tests (Task 5.6)
# =============================================================================


class TestMatterIsolationStory73:
    """Tests for matter isolation in Story 7-3 methods (Task 5.6)."""

    @pytest.mark.asyncio
    async def test_query_history_isolated_by_matter(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Query history should be filtered by matter_id."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = (
            None
        )

        await matter_repo.get_query_history(MATTER_ID)

        # Verify matter_id filter was applied
        eq_calls = mock_supabase.table.return_value.select.return_value.eq.call_args_list
        assert any(call[0] == ("matter_id", MATTER_ID) for call in eq_calls)

    @pytest.mark.asyncio
    async def test_timeline_cache_isolated_by_matter(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Timeline cache should be filtered by matter_id."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = (
            None
        )

        await matter_repo.get_timeline_cache(MATTER_ID)

        eq_calls = mock_supabase.table.return_value.select.return_value.eq.call_args_list
        assert any(call[0] == ("matter_id", MATTER_ID) for call in eq_calls)

    @pytest.mark.asyncio
    async def test_entity_graph_cache_isolated_by_matter(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Entity graph cache should be filtered by matter_id."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = (
            None
        )

        await matter_repo.get_entity_graph_cache(MATTER_ID)

        eq_calls = mock_supabase.table.return_value.select.return_value.eq.call_args_list
        assert any(call[0] == ("matter_id", MATTER_ID) for call in eq_calls)


# =============================================================================
# Story 7-3: Generic Memory Methods Tests
# =============================================================================


class TestGenericMemoryMethods:
    """Tests for generic get_memory and set_memory methods."""

    @pytest.mark.asyncio
    async def test_get_memory_returns_data(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Should return raw data dict."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "data": {"custom_key": "custom_value"}
        }

        data = await matter_repo.get_memory(MATTER_ID, "custom_type")

        assert data == {"custom_key": "custom_value"}

    @pytest.mark.asyncio
    async def test_get_memory_returns_none_when_not_found(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Should return None when memory not found."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = (
            None
        )

        data = await matter_repo.get_memory(MATTER_ID, "custom_type")

        assert data is None

    @pytest.mark.asyncio
    async def test_set_memory_uses_upsert(
        self,
        matter_repo: MatterMemoryRepository,
        mock_supabase: MagicMock,
    ) -> None:
        """Should use upsert DB function."""
        mock_supabase.rpc.return_value.execute.return_value.data = "record-id"

        await matter_repo.set_memory(MATTER_ID, "custom_type", {"key": "value"})

        mock_supabase.rpc.assert_called_once()
        call_args = mock_supabase.rpc.call_args
        assert call_args[0][0] == "upsert_matter_memory"
        assert call_args[0][1]["p_memory_type"] == "custom_type"
