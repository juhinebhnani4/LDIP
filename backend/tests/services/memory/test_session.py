"""Tests for Session Memory Service.

Story 7-1: Session Memory Redis Storage
Tasks 6.3-6.8: Comprehensive tests for SessionMemoryService
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.models.memory import SessionContext, SessionEntityMention, SessionMessage
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
        mock_redis.expire.assert_called_once()

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
        """Sliding window should preserve most recent messages."""
        messages = [
            SessionMessage(
                role="user",
                content=f"Message {i}",
                timestamp=f"2026-01-14T10:{i:02d}:00Z",
            )
            for i in range(25)
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
            content="Message 25",
        )

        # 25 + 1 = 26, should slide to 20
        assert len(context.messages) == 20
        # Messages 0-5 should be removed, 6-25 retained
        assert context.messages[0].content == "Message 6"
        assert context.messages[-1].content == "Message 25"


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

        # 6. End session
        result = await session_service.end_session(MATTER_ID, USER_ID)
        assert result is True
        assert len(stored_data) == 0
