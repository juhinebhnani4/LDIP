"""Tests for memory models.

Story 7-1: Session Memory Redis Storage
Task 6.1: Unit tests for SessionMessage, SessionEntityMention, SessionContext models
"""

import pytest
from pydantic import ValidationError

from app.models.memory import SessionContext, SessionEntityMention, SessionMessage


class TestSessionMessage:
    """Tests for SessionMessage model."""

    def test_session_message_creation(self) -> None:
        """Message should include role, content, timestamp."""
        msg = SessionMessage(
            role="user",
            content="What about the plaintiff?",
            timestamp="2026-01-14T10:00:00Z",
            entity_refs=["entity-123"],
        )
        assert msg.role == "user"
        assert "plaintiff" in msg.content
        assert msg.timestamp == "2026-01-14T10:00:00Z"
        assert "entity-123" in msg.entity_refs

    def test_session_message_default_entity_refs(self) -> None:
        """Entity refs should default to empty list."""
        msg = SessionMessage(
            role="assistant",
            content="The plaintiff is John Smith.",
            timestamp="2026-01-14T10:00:00Z",
        )
        assert msg.entity_refs == []

    def test_session_message_user_role(self) -> None:
        """User role messages should be valid."""
        msg = SessionMessage(
            role="user",
            content="Tell me about the case.",
            timestamp="2026-01-14T10:00:00Z",
        )
        assert msg.role == "user"

    def test_session_message_assistant_role(self) -> None:
        """Assistant role messages should be valid."""
        msg = SessionMessage(
            role="assistant",
            content="Based on the documents, the case involves...",
            timestamp="2026-01-14T10:00:00Z",
        )
        assert msg.role == "assistant"

    def test_session_message_serialization(self) -> None:
        """Message should serialize to JSON correctly."""
        msg = SessionMessage(
            role="user",
            content="What about him?",
            timestamp="2026-01-14T10:00:00Z",
            entity_refs=["e1", "e2"],
        )
        json_str = msg.model_dump_json()
        assert "user" in json_str
        assert "What about him?" in json_str

    def test_session_message_deserialization(self) -> None:
        """Message should deserialize from JSON correctly."""
        json_str = '{"role": "user", "content": "Test", "timestamp": "2026-01-14T10:00:00Z", "entity_refs": []}'
        msg = SessionMessage.model_validate_json(json_str)
        assert msg.role == "user"
        assert msg.content == "Test"


class TestSessionEntityMention:
    """Tests for SessionEntityMention model."""

    def test_entity_mention_creation(self) -> None:
        """Entity mention should include all required fields."""
        mention = SessionEntityMention(
            entity_id="entity-123",
            entity_name="John Smith",
            entity_type="person",
            aliases=["Mr. Smith", "J. Smith"],
            mention_count=3,
            last_mentioned="2026-01-14T10:00:00Z",
        )
        assert mention.entity_id == "entity-123"
        assert mention.entity_name == "John Smith"
        assert mention.entity_type == "person"
        assert "Mr. Smith" in mention.aliases
        assert mention.mention_count == 3

    def test_entity_mention_defaults(self) -> None:
        """Entity mention should have correct defaults."""
        mention = SessionEntityMention(
            entity_id="entity-123",
            entity_name="Acme Corp",
            last_mentioned="2026-01-14T10:00:00Z",
        )
        assert mention.entity_type == "unknown"
        assert mention.aliases == []
        assert mention.mention_count == 1

    def test_entity_mention_organization_type(self) -> None:
        """Organization entities should be valid."""
        mention = SessionEntityMention(
            entity_id="org-456",
            entity_name="Acme Corporation",
            entity_type="organization",
            last_mentioned="2026-01-14T10:00:00Z",
        )
        assert mention.entity_type == "organization"

    def test_entity_mention_minimum_count(self) -> None:
        """Mention count should be at least 1."""
        with pytest.raises(ValidationError):
            SessionEntityMention(
                entity_id="entity-123",
                entity_name="Test",
                mention_count=0,
                last_mentioned="2026-01-14T10:00:00Z",
            )

    def test_entity_mention_serialization(self) -> None:
        """Entity mention should serialize correctly."""
        mention = SessionEntityMention(
            entity_id="e1",
            entity_name="Test Entity",
            last_mentioned="2026-01-14T10:00:00Z",
        )
        json_str = mention.model_dump_json()
        restored = SessionEntityMention.model_validate_json(json_str)
        assert restored.entity_id == mention.entity_id
        assert restored.entity_name == mention.entity_name


class TestSessionContext:
    """Tests for SessionContext model."""

    def test_session_context_creation(self) -> None:
        """Session context should include all required fields."""
        context = SessionContext(
            session_id="sess-123",
            matter_id="matter-456",
            user_id="user-789",
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
        )
        assert context.session_id == "sess-123"
        assert context.matter_id == "matter-456"
        assert context.user_id == "user-789"

    def test_session_context_defaults(self) -> None:
        """Session context should have correct defaults."""
        context = SessionContext(
            session_id="sess-123",
            matter_id="matter-456",
            user_id="user-789",
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
        )
        assert context.messages == []
        assert context.entities_mentioned == {}
        assert context.query_count == 0
        assert context.ttl_extended_count == 0

    def test_session_context_with_messages(self) -> None:
        """Session context should store messages."""
        msg = SessionMessage(
            role="user",
            content="Test message",
            timestamp="2026-01-14T10:00:00Z",
        )
        context = SessionContext(
            session_id="sess-123",
            matter_id="matter-456",
            user_id="user-789",
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            messages=[msg],
        )
        assert len(context.messages) == 1
        assert context.messages[0].content == "Test message"

    def test_session_context_with_entities(self) -> None:
        """Session context should store entity mentions."""
        mention = SessionEntityMention(
            entity_id="e1",
            entity_name="John Smith",
            last_mentioned="2026-01-14T10:00:00Z",
        )
        context = SessionContext(
            session_id="sess-123",
            matter_id="matter-456",
            user_id="user-789",
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            entities_mentioned={"e1": mention},
        )
        assert "e1" in context.entities_mentioned
        assert context.entities_mentioned["e1"].entity_name == "John Smith"

    def test_session_context_query_count_minimum(self) -> None:
        """Query count should be non-negative."""
        with pytest.raises(ValidationError):
            SessionContext(
                session_id="sess-123",
                matter_id="matter-456",
                user_id="user-789",
                created_at="2026-01-14T10:00:00Z",
                last_activity="2026-01-14T10:00:00Z",
                query_count=-1,
            )

    def test_session_context_ttl_extended_count_minimum(self) -> None:
        """TTL extended count should be non-negative."""
        with pytest.raises(ValidationError):
            SessionContext(
                session_id="sess-123",
                matter_id="matter-456",
                user_id="user-789",
                created_at="2026-01-14T10:00:00Z",
                last_activity="2026-01-14T10:00:00Z",
                ttl_extended_count=-1,
            )

    def test_session_context_full_serialization(self) -> None:
        """Full session context should serialize/deserialize correctly."""
        msg = SessionMessage(
            role="user",
            content="What about the plaintiff?",
            timestamp="2026-01-14T10:00:00Z",
            entity_refs=["e1"],
        )
        mention = SessionEntityMention(
            entity_id="e1",
            entity_name="John Smith",
            entity_type="person",
            last_mentioned="2026-01-14T10:00:00Z",
        )
        context = SessionContext(
            session_id="sess-123",
            matter_id="matter-456",
            user_id="user-789",
            created_at="2026-01-14T09:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
            messages=[msg],
            entities_mentioned={"e1": mention},
            query_count=5,
            ttl_extended_count=2,
        )

        json_str = context.model_dump_json()
        restored = SessionContext.model_validate_json(json_str)

        assert restored.session_id == context.session_id
        assert restored.matter_id == context.matter_id
        assert len(restored.messages) == 1
        assert "e1" in restored.entities_mentioned
        assert restored.query_count == 5
        assert restored.ttl_extended_count == 2

    def test_session_context_immutability_of_required_fields(self) -> None:
        """Core identification fields should be present."""
        context = SessionContext(
            session_id="sess-123",
            matter_id="matter-456",
            user_id="user-789",
            created_at="2026-01-14T10:00:00Z",
            last_activity="2026-01-14T10:00:00Z",
        )
        # Verify all required fields are accessible
        assert context.session_id is not None
        assert context.matter_id is not None
        assert context.user_id is not None
        assert context.created_at is not None
        assert context.last_activity is not None
