"""Tests for memory models.

Story 7-1: Session Memory Redis Storage
Story 7-3: Matter Memory PostgreSQL JSONB Storage
Task 6.1: Unit tests for SessionMessage, SessionEntityMention, SessionContext models
Task 5.1: Unit tests for QueryHistoryEntry, QueryHistory, TimelineCache, EntityGraphCache
"""

import pytest
from pydantic import ValidationError

from app.models.memory import (
    CachedEntity,
    EntityGraphCache,
    EntityRelationship,
    QueryHistory,
    QueryHistoryEntry,
    SessionContext,
    SessionEntityMention,
    SessionMessage,
    TimelineCache,
    TimelineCacheEntry,
)


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


# =============================================================================
# Story 7-3: Matter Memory Model Tests
# =============================================================================


class TestQueryHistoryEntry:
    """Tests for QueryHistoryEntry model (Story 7-3: Task 5.1)."""

    def test_query_history_entry_creation(self) -> None:
        """QueryHistoryEntry should have required fields."""
        entry = QueryHistoryEntry(
            query_id="query-123",
            query_text="What is the timeline?",
            asked_by="user-456",
            asked_at="2026-01-14T10:00:00Z",
        )
        assert entry.query_id == "query-123"
        assert entry.query_text == "What is the timeline?"
        assert entry.verified is False  # Default
        assert entry.engines_used == []  # Default
        assert entry.confidence is None  # Default

    def test_query_history_entry_with_all_fields(self) -> None:
        """QueryHistoryEntry should store all optional fields."""
        entry = QueryHistoryEntry(
            query_id="query-123",
            query_text="What is the timeline?",
            normalized_query="timeline",
            asked_by="user-456",
            asked_at="2026-01-14T10:00:00Z",
            response_summary="Timeline shows events from 2020-2025",
            engines_used=["timeline", "citation"],
            confidence=85.5,
            verified=True,
            verified_by="attorney-789",
            verified_at="2026-01-14T11:00:00Z",
            tokens_used=1500,
            cost_usd=0.045,
        )
        assert entry.normalized_query == "timeline"
        assert entry.verified is True
        assert entry.verified_by == "attorney-789"
        assert entry.tokens_used == 1500
        assert entry.cost_usd == 0.045

    def test_query_history_entry_confidence_range(self) -> None:
        """Confidence should be between 0 and 100."""
        # Valid confidence
        entry = QueryHistoryEntry(
            query_id="q1",
            query_text="test",
            asked_by="u1",
            asked_at="2026-01-14T10:00:00Z",
            confidence=50.0,
        )
        assert entry.confidence == 50.0

        # Invalid confidence - too high
        with pytest.raises(ValidationError):
            QueryHistoryEntry(
                query_id="q1",
                query_text="test",
                asked_by="u1",
                asked_at="2026-01-14T10:00:00Z",
                confidence=101.0,
            )

        # Invalid confidence - negative
        with pytest.raises(ValidationError):
            QueryHistoryEntry(
                query_id="q1",
                query_text="test",
                asked_by="u1",
                asked_at="2026-01-14T10:00:00Z",
                confidence=-1.0,
            )

    def test_query_history_entry_tokens_minimum(self) -> None:
        """Tokens used should be non-negative."""
        with pytest.raises(ValidationError):
            QueryHistoryEntry(
                query_id="q1",
                query_text="test",
                asked_by="u1",
                asked_at="2026-01-14T10:00:00Z",
                tokens_used=-1,
            )

    def test_query_history_entry_serialization(self) -> None:
        """QueryHistoryEntry should serialize correctly."""
        entry = QueryHistoryEntry(
            query_id="query-123",
            query_text="Test query",
            asked_by="user-456",
            asked_at="2026-01-14T10:00:00Z",
            engines_used=["timeline"],
        )
        json_str = entry.model_dump_json()
        restored = QueryHistoryEntry.model_validate_json(json_str)

        assert restored.query_id == entry.query_id
        assert restored.query_text == entry.query_text
        assert restored.engines_used == ["timeline"]


class TestQueryHistory:
    """Tests for QueryHistory model (Story 7-3: Task 5.1)."""

    def test_query_history_creation(self) -> None:
        """QueryHistory should contain entries list."""
        history = QueryHistory(entries=[])
        assert history.entries == []

    def test_query_history_with_entries(self) -> None:
        """QueryHistory should store multiple entries."""
        entries = [
            QueryHistoryEntry(
                query_id="q1",
                query_text="First query",
                asked_by="u1",
                asked_at="2026-01-14T10:00:00Z",
            ),
            QueryHistoryEntry(
                query_id="q2",
                query_text="Second query",
                asked_by="u1",
                asked_at="2026-01-14T11:00:00Z",
            ),
        ]
        history = QueryHistory(entries=entries)

        assert len(history.entries) == 2
        assert history.entries[0].query_id == "q1"
        assert history.entries[1].query_id == "q2"

    def test_query_history_entries_default(self) -> None:
        """QueryHistory entries should default to empty list."""
        history = QueryHistory()
        assert history.entries == []

    def test_query_history_entries_none_coercion(self) -> None:
        """QueryHistory should coerce None entries to empty list."""
        history = QueryHistory.model_validate({"entries": None})
        assert history.entries == []


class TestTimelineCacheEntry:
    """Tests for TimelineCacheEntry model (Story 7-3: Task 5.1)."""

    def test_timeline_cache_entry_creation(self) -> None:
        """TimelineCacheEntry should have required fields."""
        entry = TimelineCacheEntry(
            event_id="evt-1",
            event_date="2025-01-01",
            event_type="filing",
            description="Initial filing submitted",
        )
        assert entry.event_id == "evt-1"
        assert entry.event_date == "2025-01-01"
        assert entry.event_type == "filing"
        assert entry.entities == []  # Default

    def test_timeline_cache_entry_with_entities(self) -> None:
        """TimelineCacheEntry should store entity references."""
        entry = TimelineCacheEntry(
            event_id="evt-1",
            event_date="2025-01-01",
            event_type="meeting",
            description="Meeting between parties",
            entities=["entity-1", "entity-2"],
            document_id="doc-123",
            confidence=90.0,
        )
        assert entry.entities == ["entity-1", "entity-2"]
        assert entry.document_id == "doc-123"
        assert entry.confidence == 90.0


class TestTimelineCache:
    """Tests for TimelineCache model (Story 7-3: Task 5.1)."""

    def test_timeline_cache_creation(self) -> None:
        """TimelineCache should have required fields."""
        cache = TimelineCache(
            cached_at="2026-01-14T10:00:00Z",
        )
        assert cache.cached_at == "2026-01-14T10:00:00Z"
        assert cache.events == []
        assert cache.version == 1
        assert cache.event_count == 0

    def test_timeline_cache_with_events(self) -> None:
        """TimelineCache should store events."""
        events = [
            TimelineCacheEntry(
                event_id="evt-1",
                event_date="2025-01-01",
                event_type="filing",
                description="Initial filing",
            ),
            TimelineCacheEntry(
                event_id="evt-2",
                event_date="2025-06-15",
                event_type="hearing",
                description="First hearing",
            ),
        ]
        cache = TimelineCache(
            cached_at="2026-01-14T10:00:00Z",
            last_document_upload="2026-01-13T15:00:00Z",
            version=2,
            events=events,
            date_range_start="2025-01-01",
            date_range_end="2025-06-15",
            event_count=2,
        )

        assert len(cache.events) == 2
        assert cache.event_count == 2
        assert cache.version == 2
        assert cache.last_document_upload == "2026-01-13T15:00:00Z"
        assert cache.date_range_start == "2025-01-01"
        assert cache.date_range_end == "2025-06-15"

    def test_timeline_cache_events_none_coercion(self) -> None:
        """TimelineCache should coerce None events to empty list."""
        cache = TimelineCache.model_validate(
            {"cached_at": "2026-01-14T10:00:00Z", "events": None}
        )
        assert cache.events == []

    def test_timeline_cache_serialization(self) -> None:
        """TimelineCache should serialize correctly."""
        events = [
            TimelineCacheEntry(
                event_id="evt-1",
                event_date="2025-01-01",
                event_type="filing",
                description="Filing",
            )
        ]
        cache = TimelineCache(
            cached_at="2026-01-14T10:00:00Z",
            events=events,
            event_count=1,
        )

        json_str = cache.model_dump_json()
        restored = TimelineCache.model_validate_json(json_str)

        assert restored.cached_at == cache.cached_at
        assert len(restored.events) == 1
        assert restored.events[0].event_id == "evt-1"


class TestEntityRelationship:
    """Tests for EntityRelationship model (Story 7-3: Task 5.1)."""

    def test_entity_relationship_creation(self) -> None:
        """EntityRelationship should have required fields."""
        rel = EntityRelationship(
            source_id="e1",
            target_id="e2",
            relationship_type="WORKS_FOR",
        )
        assert rel.source_id == "e1"
        assert rel.target_id == "e2"
        assert rel.relationship_type == "WORKS_FOR"
        assert rel.confidence is None

    def test_entity_relationship_with_confidence(self) -> None:
        """EntityRelationship should store confidence."""
        rel = EntityRelationship(
            source_id="e1",
            target_id="e2",
            relationship_type="RELATED_TO",
            confidence=0.85,
        )
        assert rel.confidence == 0.85

    def test_entity_relationship_confidence_range(self) -> None:
        """EntityRelationship confidence should be 0-1."""
        # Valid
        rel = EntityRelationship(
            source_id="e1",
            target_id="e2",
            relationship_type="RELATED_TO",
            confidence=0.5,
        )
        assert rel.confidence == 0.5

        # Invalid - too high
        with pytest.raises(ValidationError):
            EntityRelationship(
                source_id="e1",
                target_id="e2",
                relationship_type="RELATED_TO",
                confidence=1.5,
            )


class TestCachedEntity:
    """Tests for CachedEntity model (Story 7-3: Task 5.1)."""

    def test_cached_entity_creation(self) -> None:
        """CachedEntity should have required fields."""
        entity = CachedEntity(
            entity_id="e1",
            canonical_name="John Smith",
            entity_type="PERSON",
        )
        assert entity.entity_id == "e1"
        assert entity.canonical_name == "John Smith"
        assert entity.entity_type == "PERSON"
        assert entity.aliases == []
        assert entity.mention_count == 0

    def test_cached_entity_with_aliases(self) -> None:
        """CachedEntity should store aliases."""
        entity = CachedEntity(
            entity_id="e1",
            canonical_name="John Smith",
            entity_type="PERSON",
            aliases=["J. Smith", "John"],
            mention_count=15,
        )
        assert entity.aliases == ["J. Smith", "John"]
        assert entity.mention_count == 15


class TestEntityGraphCache:
    """Tests for EntityGraphCache model (Story 7-3: Task 5.1)."""

    def test_entity_graph_cache_creation(self) -> None:
        """EntityGraphCache should have required fields."""
        cache = EntityGraphCache(cached_at="2026-01-14T10:00:00Z")

        assert cache.cached_at == "2026-01-14T10:00:00Z"
        assert cache.entities == {}
        assert cache.relationships == []
        assert cache.entity_count == 0
        assert cache.relationship_count == 0

    def test_entity_graph_cache_with_data(self) -> None:
        """EntityGraphCache should store entities and relationships."""
        entities = {
            "e1": CachedEntity(
                entity_id="e1",
                canonical_name="John Smith",
                entity_type="PERSON",
            ),
            "e2": CachedEntity(
                entity_id="e2",
                canonical_name="Acme Corp",
                entity_type="ORG",
            ),
        }
        relationships = [
            EntityRelationship(
                source_id="e1",
                target_id="e2",
                relationship_type="WORKS_FOR",
            )
        ]

        cache = EntityGraphCache(
            cached_at="2026-01-14T10:00:00Z",
            last_document_upload="2026-01-13T15:00:00Z",
            version=3,
            entities=entities,
            relationships=relationships,
            entity_count=2,
            relationship_count=1,
        )

        assert "e1" in cache.entities
        assert "e2" in cache.entities
        assert cache.entities["e1"].canonical_name == "John Smith"
        assert len(cache.relationships) == 1
        assert cache.entity_count == 2
        assert cache.relationship_count == 1

    def test_entity_graph_cache_entities_none_coercion(self) -> None:
        """EntityGraphCache should coerce None entities to empty dict."""
        cache = EntityGraphCache.model_validate(
            {"cached_at": "2026-01-14T10:00:00Z", "entities": None}
        )
        assert cache.entities == {}

    def test_entity_graph_cache_relationships_none_coercion(self) -> None:
        """EntityGraphCache should coerce None relationships to empty list."""
        cache = EntityGraphCache.model_validate(
            {"cached_at": "2026-01-14T10:00:00Z", "relationships": None}
        )
        assert cache.relationships == []

    def test_entity_graph_cache_serialization(self) -> None:
        """EntityGraphCache should serialize correctly."""
        entities = {
            "e1": CachedEntity(
                entity_id="e1",
                canonical_name="Test Entity",
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

        cache = EntityGraphCache(
            cached_at="2026-01-14T10:00:00Z",
            entities=entities,
            relationships=relationships,
            entity_count=1,
            relationship_count=1,
        )

        json_str = cache.model_dump_json()
        restored = EntityGraphCache.model_validate_json(json_str)

        assert "e1" in restored.entities
        assert restored.entities["e1"].canonical_name == "Test Entity"
        assert len(restored.relationships) == 1
