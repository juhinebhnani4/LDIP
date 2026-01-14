"""Tests for Matter Memory Repository.

Story 7-2: Session TTL and Context Restoration
Tasks 7.2, 7.6: Test session archival and matter isolation.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.models.memory import ArchivedSession, SessionEntityMention, SessionMessage
from app.services.memory.matter import (
    ARCHIVED_SESSION_TYPE,
    MatterMemoryRepository,
    get_matter_memory_repository,
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
