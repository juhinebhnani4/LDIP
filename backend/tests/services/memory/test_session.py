"""Tests for Session Memory Service.

Story 7-1: Session Memory Redis Storage
Story 7-2: Session TTL and Context Restoration
Tasks 6.3-6.8: Comprehensive tests for SessionMemoryService
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.models.memory import (
    ArchivedSession,
    SessionContext,
    SessionEntityMention,
    SessionMessage,
)
from app.services.memory.redis_keys import SESSION_TTL
from app.services.memory.session import (
    MAX_SESSION_MESSAGES,
    SessionMemoryService,
    get_session_memory_service,
    reset_session_memory_service,
)


# Valid UUIDs for testing (redis_keys.py validates UUID format)
MATTER_ID = "12345678-1234-1234-1234-123456789abc"
USER_ID = "abcdefab-abcd-abcd-abcd-abcdefabcdef"
MATTER_ID_2 = "87654321-4321-4321-4321-987654321fed"


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client for testing."""
    mock = AsyncMock()
    mock.get.return_value = None
    mock.setex.return_value = True
    mock.delete.return_value = 1
    mock.expire.return_value = True
    return mock


@pytest.fixture
def session_service(mock_redis: AsyncMock) -> SessionMemoryService:
    """Create a session service with mock Redis."""
    reset_session_memory_service()
    return SessionMemoryService(mock_redis)


class TestSessionCreation:
    """Tests for session creation (AC #1)."""

    @pytest.mark.asyncio
    async def test_create_session_basic(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should create session with correct structure (AC #1)."""
        context = await session_service.create_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
        )

        assert context.session_id is not None
        assert context.matter_id == MATTER_ID
        assert context.user_id == USER_ID
        assert len(context.messages) == 0
        assert context.entities_mentioned == {}
        assert context.query_count == 0
        assert context.ttl_extended_count == 0

    @pytest.mark.asyncio
    async def test_create_session_stores_in_redis(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should store session in Redis with correct TTL."""
        await session_service.create_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
        )

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == SESSION_TTL  # 7-day TTL

    @pytest.mark.asyncio
    async def test_create_session_key_format(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should use correct Redis key format."""
        await session_service.create_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
        )

        call_args = mock_redis.setex.call_args
        key = call_args[0][0]
        assert key == f"session:{MATTER_ID}:{USER_ID}:context"

    @pytest.mark.asyncio
    async def test_create_session_timestamps(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should set created_at and last_activity timestamps."""
        before = datetime.now(timezone.utc).isoformat()
        context = await session_service.create_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
        )
        after = datetime.now(timezone.utc).isoformat()

        assert before <= context.created_at <= after
        assert before <= context.last_activity <= after


class TestSessionRetrieval:
    """Tests for session retrieval."""

    @pytest.mark.asyncio
    async def test_get_session_returns_existing(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should return existing session from Redis."""
        existing_context = SessionContext(
            session_id="existing-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            query_count=5,
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        context = await session_service.get_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
        )

        assert context is not None
        assert context.session_id == "existing-session"
        assert context.query_count == 5

    @pytest.mark.asyncio
    async def test_get_session_auto_creates_when_not_found(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should auto-create session when not found (default behavior)."""
        mock_redis.get.return_value = None

        context = await session_service.get_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            auto_create=True,
        )

        assert context is not None
        assert context.matter_id == MATTER_ID

    @pytest.mark.asyncio
    async def test_get_session_returns_none_without_auto_create(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should return None when not found and auto_create is False."""
        mock_redis.get.return_value = None

        context = await session_service.get_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            auto_create=False,
        )

        assert context is None


class TestTTLExtension:
    """Tests for TTL auto-extension (AC #1)."""

    @pytest.mark.asyncio
    async def test_ttl_auto_extension_on_access(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """TTL should be extended on session access."""
        existing_context = SessionContext(
            session_id="existing-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            ttl_extended_count=0,
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        context = await session_service.get_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            extend_ttl=True,
        )

        assert context is not None
        assert context.ttl_extended_count == 1
        # setex is used to update context with new TTL (more efficient than separate expire)
        assert mock_redis.setex.call_count >= 1

    @pytest.mark.asyncio
    async def test_ttl_not_extended_when_disabled(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """TTL should not be extended when extend_ttl is False."""
        existing_context = SessionContext(
            session_id="existing-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            ttl_extended_count=0,
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        context = await session_service.get_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            extend_ttl=False,
        )

        assert context is not None
        assert context.ttl_extended_count == 0
        mock_redis.expire.assert_not_called()


class TestMessageHandling:
    """Tests for message handling (AC #2)."""

    @pytest.mark.asyncio
    async def test_add_message_to_session(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should add message to session (AC #2)."""
        # First call creates session, subsequent calls get it
        mock_redis.get.return_value = None

        context = await session_service.add_message(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            role="user",
            content="What about the plaintiff?",
        )

        assert len(context.messages) == 1
        assert context.messages[0].role == "user"
        assert context.messages[0].content == "What about the plaintiff?"

    @pytest.mark.asyncio
    async def test_add_message_updates_last_activity(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """last_activity should be updated when message is added."""
        existing_context = SessionContext(
            session_id="existing-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        before = datetime.now(timezone.utc).isoformat()
        context = await session_service.add_message(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            role="user",
            content="Test",
        )

        assert context.last_activity >= before

    @pytest.mark.asyncio
    async def test_add_message_increments_query_count_for_user(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """query_count should increment for user messages."""
        existing_context = SessionContext(
            session_id="existing-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            query_count=5,
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        context = await session_service.add_message(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            role="user",
            content="Test",
        )

        assert context.query_count == 6

    @pytest.mark.asyncio
    async def test_add_message_does_not_increment_query_count_for_assistant(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """query_count should not increment for assistant messages."""
        existing_context = SessionContext(
            session_id="existing-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            query_count=5,
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        context = await session_service.add_message(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            role="assistant",
            content="Response",
        )

        assert context.query_count == 5

    @pytest.mark.asyncio
    async def test_add_message_with_entity_refs(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should store entity refs with message."""
        mock_redis.get.return_value = None

        context = await session_service.add_message(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            role="user",
            content="What about John Smith?",
            entity_refs=["entity-123"],
        )

        assert context.messages[0].entity_refs == ["entity-123"]


class TestSlidingWindow:
    """Tests for sliding window behavior (AC #3)."""

    @pytest.mark.asyncio
    async def test_sliding_window_at_19_messages(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Window should not slide at 19 messages."""
        messages = [
            SessionMessage(
                role="user",
                content=f"Message {i}",
                timestamp=f"2026-01-14T10:{i:02d}:00Z",
            )
            for i in range(19)
        ]
        existing_context = SessionContext(
            session_id="existing-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            messages=messages,
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        context = await session_service.add_message(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            role="user",
            content="Message 19",
        )

        # 19 + 1 = 20, should not slide
        assert len(context.messages) == 20

    @pytest.mark.asyncio
    async def test_sliding_window_at_20_messages(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Window should not slide at exactly 20 messages."""
        messages = [
            SessionMessage(
                role="user",
                content=f"Message {i}",
                timestamp=f"2026-01-14T10:{i:02d}:00Z",
            )
            for i in range(20)
        ]
        existing_context = SessionContext(
            session_id="existing-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            messages=messages,
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        context = await session_service.get_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
        )

        assert context is not None
        assert len(context.messages) == 20

    @pytest.mark.asyncio
    async def test_sliding_window_at_21_messages(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Window should slide at 21 messages, keeping last 20."""
        messages = [
            SessionMessage(
                role="user",
                content=f"Message {i}",
                timestamp=f"2026-01-14T10:{i:02d}:00Z",
            )
            for i in range(20)
        ]
        existing_context = SessionContext(
            session_id="existing-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            messages=messages,
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        context = await session_service.add_message(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            role="user",
            content="Message 20",
        )

        # 20 + 1 = 21, should slide to 20
        assert len(context.messages) == 20
        # Message 0 should be removed
        assert context.messages[0].content == "Message 1"
        assert context.messages[-1].content == "Message 20"

    @pytest.mark.asyncio
    async def test_sliding_window_preserves_recent_messages(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Sliding window should preserve most recent messages when adding many."""
        # Start with max 20 messages (model enforces max_length=20)
        messages = [
            SessionMessage(
                role="user",
                content=f"Message {i}",
                timestamp=f"2026-01-14T10:{i:02d}:00Z",
            )
            for i in range(20)
        ]
        existing_context = SessionContext(
            session_id="existing-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            messages=messages,
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        # Add 5 more messages (would be 25 total, but sliding window keeps 20)
        context = await session_service.add_message(
            MATTER_ID, USER_ID, "user", "Message 20"
        )
        # Update mock to return the new context for subsequent calls
        mock_redis.get.return_value = context.model_dump_json()

        context = await session_service.add_message(
            MATTER_ID, USER_ID, "user", "Message 21"
        )
        mock_redis.get.return_value = context.model_dump_json()

        context = await session_service.add_message(
            MATTER_ID, USER_ID, "user", "Message 22"
        )
        mock_redis.get.return_value = context.model_dump_json()

        context = await session_service.add_message(
            MATTER_ID, USER_ID, "user", "Message 23"
        )
        mock_redis.get.return_value = context.model_dump_json()

        context = await session_service.add_message(
            MATTER_ID, USER_ID, "user", "Message 24"
        )

        # Should have 20 messages (oldest 5 removed)
        assert len(context.messages) == 20
        # Messages 0-4 should be removed, 5-24 retained
        assert context.messages[0].content == "Message 5"
        assert context.messages[-1].content == "Message 24"


class TestEntityTracking:
    """Tests for entity tracking and pronoun resolution (AC #4)."""

    @pytest.mark.asyncio
    async def test_update_entities_adds_new_entities(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should add new entities to tracking."""
        mock_redis.get.return_value = None

        context = await session_service.update_entities(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            entities=[
                {"id": "e1", "name": "John Smith", "type": "person"},
                {"id": "e2", "name": "Acme Corp", "type": "organization"},
            ],
        )

        assert "e1" in context.entities_mentioned
        assert "e2" in context.entities_mentioned
        assert context.entities_mentioned["e1"].entity_name == "John Smith"
        assert context.entities_mentioned["e2"].entity_name == "Acme Corp"

    @pytest.mark.asyncio
    async def test_update_entities_increments_mention_count(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should increment mention count for existing entities."""
        existing_mention = SessionEntityMention(
            entity_id="e1",
            entity_name="John Smith",
            entity_type="person",
            mention_count=2,
            last_mentioned="2026-01-14T10:00:00Z",
        )
        existing_context = SessionContext(
            session_id="existing-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            entities_mentioned={"e1": existing_mention},
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        context = await session_service.update_entities(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            entities=[{"id": "e1", "name": "John Smith", "type": "person"}],
        )

        assert context.entities_mentioned["e1"].mention_count == 3

    @pytest.mark.asyncio
    async def test_update_entities_updates_last_mentioned(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should update last_mentioned timestamp."""
        existing_mention = SessionEntityMention(
            entity_id="e1",
            entity_name="John Smith",
            entity_type="person",
            mention_count=1,
            last_mentioned="2026-01-14T10:00:00Z",
        )
        existing_context = SessionContext(
            session_id="existing-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            entities_mentioned={"e1": existing_mention},
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        before = datetime.now(timezone.utc).isoformat()
        context = await session_service.update_entities(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            entities=[{"id": "e1", "name": "John Smith", "type": "person"}],
        )

        assert context.entities_mentioned["e1"].last_mentioned >= before

    @pytest.mark.asyncio
    async def test_get_entities_mentioned(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should return entities mentioned map."""
        existing_mention = SessionEntityMention(
            entity_id="e1",
            entity_name="John Smith",
            entity_type="person",
            mention_count=1,
            last_mentioned="2026-01-14T10:00:00Z",
        )
        existing_context = SessionContext(
            session_id="existing-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            entities_mentioned={"e1": existing_mention},
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        entities = await session_service.get_entities_mentioned(
            matter_id=MATTER_ID,
            user_id=USER_ID,
        )

        assert "e1" in entities
        assert entities["e1"].entity_name == "John Smith"

    @pytest.mark.asyncio
    async def test_get_entities_mentioned_returns_empty_for_no_session(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should return empty dict when no session exists."""
        mock_redis.get.return_value = None

        entities = await session_service.get_entities_mentioned(
            matter_id=MATTER_ID,
            user_id=USER_ID,
        )

        assert entities == {}


class TestPronounResolution:
    """Tests for pronoun resolution (AC #4)."""

    @pytest.mark.asyncio
    async def test_resolve_pronoun_he_to_person(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should resolve 'he' to person entity."""
        existing_mention = SessionEntityMention(
            entity_id="e1",
            entity_name="John Smith",
            entity_type="person",
            mention_count=1,
            last_mentioned="2026-01-14T10:00:00Z",
        )
        existing_context = SessionContext(
            session_id="existing-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            entities_mentioned={"e1": existing_mention},
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        mention = await session_service.resolve_pronoun(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            pronoun="he",
        )

        assert mention is not None
        assert mention.entity_name == "John Smith"

    @pytest.mark.asyncio
    async def test_resolve_pronoun_it_to_organization(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should resolve 'it' to organization entity."""
        person_mention = SessionEntityMention(
            entity_id="e1",
            entity_name="John Smith",
            entity_type="person",
            mention_count=1,
            last_mentioned="2026-01-14T10:00:00Z",
        )
        org_mention = SessionEntityMention(
            entity_id="e2",
            entity_name="Acme Corp",
            entity_type="organization",
            mention_count=1,
            last_mentioned="2026-01-14T10:01:00Z",
        )
        existing_context = SessionContext(
            session_id="existing-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            entities_mentioned={"e1": person_mention, "e2": org_mention},
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        mention = await session_service.resolve_pronoun(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            pronoun="it",
        )

        assert mention is not None
        assert mention.entity_name == "Acme Corp"

    @pytest.mark.asyncio
    async def test_resolve_pronoun_they_includes_all(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """'they' should consider all entities."""
        person_mention = SessionEntityMention(
            entity_id="e1",
            entity_name="John Smith",
            entity_type="person",
            mention_count=1,
            last_mentioned="2026-01-14T10:00:00Z",
        )
        org_mention = SessionEntityMention(
            entity_id="e2",
            entity_name="Acme Corp",
            entity_type="organization",
            mention_count=1,
            last_mentioned="2026-01-14T10:01:00Z",
        )
        existing_context = SessionContext(
            session_id="existing-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            entities_mentioned={"e1": person_mention, "e2": org_mention},
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        mention = await session_service.resolve_pronoun(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            pronoun="they",
        )

        # Should return most recently mentioned
        assert mention is not None
        assert mention.entity_name == "Acme Corp"

    @pytest.mark.asyncio
    async def test_resolve_pronoun_recency_weighted(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should return most recently mentioned entity."""
        older_mention = SessionEntityMention(
            entity_id="e1",
            entity_name="John Smith",
            entity_type="person",
            mention_count=5,
            last_mentioned="2026-01-14T10:00:00Z",
        )
        newer_mention = SessionEntityMention(
            entity_id="e2",
            entity_name="Jane Doe",
            entity_type="person",
            mention_count=1,
            last_mentioned="2026-01-14T10:05:00Z",
        )
        existing_context = SessionContext(
            session_id="existing-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            entities_mentioned={"e1": older_mention, "e2": newer_mention},
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        mention = await session_service.resolve_pronoun(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            pronoun="she",
        )

        # Jane Doe is more recent despite fewer mentions
        assert mention is not None
        assert mention.entity_name == "Jane Doe"

    @pytest.mark.asyncio
    async def test_resolve_pronoun_returns_none_for_no_match(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should return None when no matching entities."""
        org_mention = SessionEntityMention(
            entity_id="e1",
            entity_name="Acme Corp",
            entity_type="organization",
            mention_count=1,
            last_mentioned="2026-01-14T10:00:00Z",
        )
        existing_context = SessionContext(
            session_id="existing-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            entities_mentioned={"e1": org_mention},
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        mention = await session_service.resolve_pronoun(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            pronoun="he",
        )

        # No person entities, so 'he' has no candidates
        assert mention is None

    @pytest.mark.asyncio
    async def test_resolve_pronoun_returns_none_for_no_session(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should return None when no session exists."""
        mock_redis.get.return_value = None

        mention = await session_service.resolve_pronoun(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            pronoun="he",
        )

        assert mention is None


class TestMatterIsolation:
    """Tests for matter isolation (CRITICAL security test)."""

    @pytest.mark.asyncio
    async def test_matter_isolation_separate_sessions(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Sessions should be isolated by matter_id + user_id."""
        # Session for matter A
        mock_redis.get.return_value = None
        context_a = await session_service.create_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
        )

        # Session for matter B
        context_b = await session_service.create_session(
            matter_id=MATTER_ID_2,
            user_id=USER_ID,
        )

        # Different session IDs
        assert context_a.session_id != context_b.session_id

        # Verify different keys were used
        calls = mock_redis.setex.call_args_list
        assert len(calls) == 2
        key_a = calls[0][0][0]
        key_b = calls[1][0][0]
        assert key_a != key_b
        assert MATTER_ID in key_a
        assert MATTER_ID_2 in key_b

    @pytest.mark.asyncio
    async def test_matter_isolation_messages_not_shared(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Messages from one matter should not appear in another."""
        # Create session for matter A with message
        msg_a = SessionMessage(
            role="user",
            content="Matter A secret message",
            timestamp="2026-01-14T10:00:00Z",
        )
        context_a = SessionContext(
            session_id="session-a",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            messages=[msg_a],
        )

        # Mock get to return context_a for matter A
        mock_redis.get.return_value = context_a.model_dump_json()

        result_a = await session_service.get_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
        )

        assert result_a is not None
        assert len(result_a.messages) == 1
        assert "Matter A" in result_a.messages[0].content

        # Now request matter B - should get new session
        mock_redis.get.return_value = None  # No session for matter B

        result_b = await session_service.get_session(
            matter_id=MATTER_ID_2,
            user_id=USER_ID,
            auto_create=True,
        )

        assert result_b is not None
        assert len(result_b.messages) == 0  # No messages from matter A


class TestSessionEnd:
    """Tests for session ending."""

    @pytest.mark.asyncio
    async def test_end_session_deletes_from_redis(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should delete session from Redis."""
        mock_redis.delete.return_value = 1

        result = await session_service.end_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
        )

        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_end_session_returns_false_for_missing(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Should return False when session doesn't exist."""
        mock_redis.delete.return_value = 0

        result = await session_service.end_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
        )

        assert result is False


class TestServiceFactory:
    """Tests for service factory functions."""

    def teardown_method(self) -> None:
        """Reset singleton after each test."""
        reset_session_memory_service()

    def test_get_session_memory_service_singleton(self) -> None:
        """Factory should return same instance."""
        reset_session_memory_service()

        service1 = get_session_memory_service()
        service2 = get_session_memory_service()

        assert service1 is service2

    def test_get_session_memory_service_with_client(self) -> None:
        """Factory should accept custom Redis client."""
        reset_session_memory_service()
        mock_redis = AsyncMock()

        service = get_session_memory_service(mock_redis)

        assert service._redis is mock_redis

    def test_reset_session_memory_service(self) -> None:
        """Reset should clear the singleton."""
        get_session_memory_service()
        reset_session_memory_service()

        # After reset, should create new instance
        service = get_session_memory_service()
        assert service is not None


class TestIntegrationScenarios:
    """Integration-style tests for full session lifecycle."""

    @pytest.mark.asyncio
    async def test_full_session_lifecycle(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """Test complete session lifecycle: create, messages, entities, end."""
        # Track stored data for verification
        stored_data = {}

        def mock_setex(key: str, ttl: int, data: str) -> bool:
            stored_data[key] = data
            return True

        def mock_get(key: str) -> str | None:
            return stored_data.get(key)

        def mock_delete(key: str) -> int:
            if key in stored_data:
                del stored_data[key]
                return 1
            return 0

        mock_redis.setex.side_effect = mock_setex
        mock_redis.get.side_effect = mock_get
        mock_redis.delete.side_effect = mock_delete

        # 1. Create session
        context = await session_service.create_session(MATTER_ID, USER_ID)
        assert context.session_id is not None
        assert len(stored_data) == 1

        # 2. Add user message
        context = await session_service.add_message(
            MATTER_ID, USER_ID, "user", "Tell me about John Smith"
        )
        assert len(context.messages) == 1
        assert context.query_count == 1

        # 3. Add assistant response
        context = await session_service.add_message(
            MATTER_ID, USER_ID, "assistant", "John Smith is the plaintiff..."
        )
        assert len(context.messages) == 2
        assert context.query_count == 1  # Not incremented for assistant

        # 4. Track entity
        context = await session_service.update_entities(
            MATTER_ID,
            USER_ID,
            [{"id": "e1", "name": "John Smith", "type": "person"}],
        )
        assert "e1" in context.entities_mentioned

        # 5. Resolve pronoun
        mention = await session_service.resolve_pronoun(MATTER_ID, USER_ID, "he")
        assert mention is not None
        assert mention.entity_name == "John Smith"

        # 6. End session (without archival to avoid Supabase mock)
        result = await session_service.end_session(MATTER_ID, USER_ID, archive=False)
        assert result is True
        assert len(stored_data) == 0


# =============================================================================
# Story 7-2: TTL Extension with Max Lifetime
# =============================================================================


class TestMaxLifetimeTTL:
    """Tests for max lifetime TTL check (Story 7-2)."""

    @pytest.mark.asyncio
    async def test_ttl_extension_respects_max_lifetime(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """TTL should stop extending after 30 days (Story 7-2 AC #2)."""
        from datetime import timedelta

        # Create session with created_at 30 days ago
        old_created_at = (
            datetime.now(timezone.utc) - timedelta(days=30)
        ).isoformat()

        existing_context = SessionContext(
            session_id="old-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at=old_created_at,
            last_activity=old_created_at,
            ttl_extended_count=10,
            max_ttl_reached=False,
        )
        mock_redis.get.return_value = existing_context.model_dump_json()
        mock_redis.ttl.return_value = 86400  # 1 day remaining

        # Get session with TTL extension
        context = await session_service.get_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            extend_ttl=True,
            restore_from_archive=False,
        )

        assert context is not None
        assert context.max_ttl_reached is True

    @pytest.mark.asyncio
    async def test_ttl_not_extended_when_max_first_detected(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """TTL should NOT be extended to 7 days when max lifetime first detected."""
        from datetime import timedelta

        # Create session with created_at 30 days ago (just hit max)
        old_created_at = (
            datetime.now(timezone.utc) - timedelta(days=30)
        ).isoformat()

        existing_context = SessionContext(
            session_id="old-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at=old_created_at,
            last_activity=old_created_at,
            ttl_extended_count=10,
            max_ttl_reached=False,  # Not yet marked
        )
        mock_redis.get.return_value = existing_context.model_dump_json()
        mock_redis.ttl.return_value = 172800  # 2 days remaining

        # Get session with TTL extension
        context = await session_service.get_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            extend_ttl=True,
            restore_from_archive=False,
        )

        assert context is not None
        assert context.max_ttl_reached is True

        # Verify setex was called with REMAINING TTL (172800), not SESSION_TTL (7 days)
        setex_calls = mock_redis.setex.call_args_list
        # The last setex call should use remaining TTL, not extend to 7 days
        last_setex_call = setex_calls[-1]
        ttl_used = last_setex_call[0][1]
        assert ttl_used == 172800, f"Expected remaining TTL 172800, got {ttl_used}"

    @pytest.mark.asyncio
    async def test_ttl_extension_works_within_max_lifetime(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """TTL should extend when within 30 days."""
        from datetime import timedelta

        # Create session with created_at 7 days ago
        recent_created_at = (
            datetime.now(timezone.utc) - timedelta(days=7)
        ).isoformat()

        existing_context = SessionContext(
            session_id="recent-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at=recent_created_at,
            last_activity=recent_created_at,
            ttl_extended_count=2,
            max_ttl_reached=False,
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        context = await session_service.get_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            extend_ttl=True,
            restore_from_archive=False,
        )

        assert context is not None
        assert context.max_ttl_reached is False
        assert context.ttl_extended_count == 3  # Incremented

    @pytest.mark.asyncio
    async def test_ttl_not_extended_when_max_reached(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """TTL count should not increment when max_ttl_reached is True."""
        existing_context = SessionContext(
            session_id="maxed-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-01T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            ttl_extended_count=50,
            max_ttl_reached=True,
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        context = await session_service.get_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            extend_ttl=True,
            restore_from_archive=False,
        )

        assert context is not None
        # TTL count should not increment when max already reached
        assert context.ttl_extended_count == 50

    @pytest.mark.asyncio
    async def test_total_lifetime_days_calculated(
        self, session_service: SessionMemoryService, mock_redis: AsyncMock
    ) -> None:
        """total_lifetime_days should be calculated from created_at."""
        from datetime import timedelta

        # Session created 10 days ago
        created_at = (
            datetime.now(timezone.utc) - timedelta(days=10)
        ).isoformat()

        existing_context = SessionContext(
            session_id="aged-session",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at=created_at,
            last_activity=created_at,
            total_lifetime_days=0,
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        context = await session_service.get_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            extend_ttl=True,
            restore_from_archive=False,
        )

        assert context is not None
        assert context.total_lifetime_days == 10


# =============================================================================
# Story 7-2: Session Archival
# =============================================================================


class TestSessionArchival:
    """Tests for session archival (Story 7-2 AC #1, #3)."""

    @pytest.fixture
    def mock_matter_memory(self) -> AsyncMock:
        """Create a mock MatterMemoryRepository."""
        mock = AsyncMock()
        mock.save_archived_session.return_value = "archive-record-id"
        mock.get_latest_archived_session.return_value = None
        return mock

    @pytest.mark.asyncio
    async def test_archive_session_creates_archive(
        self,
        mock_redis: AsyncMock,
        mock_matter_memory: AsyncMock,
    ) -> None:
        """archive_session should create ArchivedSession object."""
        reset_session_memory_service()
        service = SessionMemoryService(mock_redis, mock_matter_memory)

        # Setup existing session
        existing_context = SessionContext(
            session_id="session-to-archive",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T17:00:00Z",
            query_count=5,
            ttl_extended_count=2,
            messages=[
                SessionMessage(
                    role="user",
                    content="Test message",
                    timestamp="2026-01-14T17:00:00Z",
                )
            ],
            entities_mentioned={
                "e1": SessionEntityMention(
                    entity_id="e1",
                    entity_name="John Smith",
                    entity_type="person",
                    mention_count=3,
                    last_mentioned="2026-01-14T17:00:00Z",
                )
            },
        )
        mock_redis.get.return_value = existing_context.model_dump_json()

        archive = await service.archive_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            reason="manual_end",
        )

        assert archive is not None
        assert archive.session_id == "session-to-archive"
        assert archive.archival_reason == "manual_end"
        assert len(archive.entities_mentioned) == 1
        assert len(archive.last_messages) == 1
        mock_matter_memory.save_archived_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_archive_session_no_session(
        self,
        mock_redis: AsyncMock,
        mock_matter_memory: AsyncMock,
    ) -> None:
        """archive_session should return None if no session exists."""
        reset_session_memory_service()
        service = SessionMemoryService(mock_redis, mock_matter_memory)
        mock_redis.get.return_value = None

        archive = await service.archive_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            reason="expired",
        )

        assert archive is None
        mock_matter_memory.save_archived_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_end_session_archives_before_delete(
        self,
        mock_redis: AsyncMock,
        mock_matter_memory: AsyncMock,
    ) -> None:
        """end_session should archive before deleting (AC #3)."""
        reset_session_memory_service()
        service = SessionMemoryService(mock_redis, mock_matter_memory)

        # Setup existing session
        existing_context = SessionContext(
            session_id="session-to-end",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T17:00:00Z",
        )
        mock_redis.get.return_value = existing_context.model_dump_json()
        mock_redis.delete.return_value = 1

        deleted = await service.end_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            archive=True,
        )

        assert deleted is True
        mock_matter_memory.save_archived_session.assert_called_once()
        mock_redis.delete.assert_called_once()


# =============================================================================
# Story 7-2: Context Restoration
# =============================================================================


class TestContextRestoration:
    """Tests for context restoration (Story 7-2 AC #4)."""

    @pytest.fixture
    def mock_matter_memory_with_archive(self) -> AsyncMock:
        """Create a mock MatterMemoryRepository with archived session."""
        from app.models.memory import ArchivedSession

        mock = AsyncMock()
        mock.save_archived_session.return_value = "archive-record-id"

        archived = ArchivedSession(
            session_id="old-session-123",
            matter_id=MATTER_ID,
            user_id=USER_ID,
            created_at="2026-01-07T10:00:00Z",
            archived_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T09:00:00Z",
            entities_mentioned={
                "e1": SessionEntityMention(
                    entity_id="e1",
                    entity_name="John Smith",
                    entity_type="person",
                    mention_count=5,
                    last_mentioned="2026-01-14T09:00:00Z",
                )
            },
            last_messages=[
                SessionMessage(
                    role="user",
                    content="What about John?",
                    timestamp="2026-01-14T08:55:00Z",
                    entity_refs=["e1"],
                ),
                SessionMessage(
                    role="assistant",
                    content="John Smith is the plaintiff...",
                    timestamp="2026-01-14T09:00:00Z",
                    entity_refs=["e1"],
                ),
            ],
            total_query_count=10,
            total_messages=20,
            ttl_extended_count=5,
            archival_reason="expired",
        )
        mock.get_latest_archived_session.return_value = archived

        return mock

    @pytest.mark.asyncio
    async def test_restore_context_from_archive(
        self,
        mock_redis: AsyncMock,
        mock_matter_memory_with_archive: AsyncMock,
    ) -> None:
        """restore_context should create new session with archived context."""
        reset_session_memory_service()
        service = SessionMemoryService(mock_redis, mock_matter_memory_with_archive)

        # No session in Redis
        mock_redis.get.return_value = None

        context = await service.restore_context(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            restore_messages=True,
            message_limit=5,
        )

        assert context is not None
        # New session ID created
        assert context.session_id != "old-session-123"
        # Entities restored
        assert "e1" in context.entities_mentioned
        assert context.entities_mentioned["e1"].entity_name == "John Smith"
        # Messages restored
        assert len(context.messages) == 2

    @pytest.mark.asyncio
    async def test_restore_context_no_archive(
        self,
        mock_redis: AsyncMock,
    ) -> None:
        """restore_context should return None when no archive exists."""
        mock_matter_memory = AsyncMock()
        mock_matter_memory.get_latest_archived_session.return_value = None

        reset_session_memory_service()
        service = SessionMemoryService(mock_redis, mock_matter_memory)

        context = await service.restore_context(
            matter_id=MATTER_ID,
            user_id=USER_ID,
        )

        assert context is None

    @pytest.mark.asyncio
    async def test_restore_context_respects_message_limit(
        self,
        mock_redis: AsyncMock,
        mock_matter_memory_with_archive: AsyncMock,
    ) -> None:
        """restore_context should limit restored messages."""
        reset_session_memory_service()
        service = SessionMemoryService(mock_redis, mock_matter_memory_with_archive)

        mock_redis.get.return_value = None

        context = await service.restore_context(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            restore_messages=True,
            message_limit=1,
        )

        assert context is not None
        # Only 1 message restored
        assert len(context.messages) == 1

    @pytest.mark.asyncio
    async def test_get_session_restores_from_archive_on_miss(
        self,
        mock_redis: AsyncMock,
        mock_matter_memory_with_archive: AsyncMock,
    ) -> None:
        """get_session should restore from archive when session not found."""
        reset_session_memory_service()
        service = SessionMemoryService(mock_redis, mock_matter_memory_with_archive)

        # Session doesn't exist in Redis
        mock_redis.get.return_value = None

        context = await service.get_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            auto_create=False,
            restore_from_archive=True,
        )

        assert context is not None
        assert "e1" in context.entities_mentioned

    @pytest.mark.asyncio
    async def test_get_session_skips_archive_when_disabled(
        self,
        mock_redis: AsyncMock,
        mock_matter_memory_with_archive: AsyncMock,
    ) -> None:
        """get_session should not restore when restore_from_archive=False."""
        reset_session_memory_service()
        service = SessionMemoryService(mock_redis, mock_matter_memory_with_archive)

        mock_redis.get.return_value = None

        context = await service.get_session(
            matter_id=MATTER_ID,
            user_id=USER_ID,
            auto_create=False,
            restore_from_archive=False,
        )

        assert context is None
        mock_matter_memory_with_archive.get_latest_archived_session.assert_not_called()
