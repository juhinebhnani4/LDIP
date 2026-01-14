"""Memory models for session and conversation context.

Story 7-1: Session Memory Redis Storage
Story 7-2: Session TTL and Context Restoration
Story 7-3: Matter Memory PostgreSQL JSONB Storage
Story 7-4: Key Findings and Research Notes
Story 7-5: Query Cache Redis Storage

These models define the structure of session data stored in Redis
for conversation context persistence. Part of the Three-Layer Memory System.

Layer 1: Session Memory (this module) - Conversation context during user session
Layer 2: Matter Memory (Story 7-3, 7-4) - Persistent findings, entity graph, key findings, research notes
Layer 3: Query Cache (Story 7-5) - LLM response caching with 1-hour TTL
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Story 7-4: Finding Type Enum
# =============================================================================

# Finding types aligned with engine outputs (Story 7-4: Task 1.4)
#
# Design Note (Code Review Issue #2):
#   Using Literal instead of Enum is intentional for:
#   1. Performance: No enum overhead in JSONB serialization
#   2. Simplicity: Direct string comparison in DB queries
#   3. Pydantic v2: Native Literal support with automatic validation
#   Runtime validation occurs via Pydantic - invalid types raise ValidationError
#   with message: "Input should be 'citation_verified', 'citation_mismatch', ..."
FindingType = Literal[
    "citation_verified",  # Citation Engine: verified citation
    "citation_mismatch",  # Citation Engine: misquoted/wrong section
    "contradiction",  # Contradiction Engine: statement conflict
    "timeline_anomaly",  # Timeline Engine: date gap/sequence issue
    "entity_link",  # MIG: entity relationship finding
    "custom",  # User-defined finding
]


# =============================================================================
# Constants (Story 7-2)
# =============================================================================

MAX_ARCHIVED_MESSAGES = 10  # Maximum messages to store in archived session


class SessionMessage(BaseModel):
    """A single message in the session conversation.

    Story 7-1: Tracks individual messages for context.
    Messages are stored in a sliding window (max 20).
    """

    role: Literal["user", "assistant"] = Field(description="Message role")
    content: str = Field(description="Message content text")
    timestamp: str = Field(description="ISO8601 timestamp when sent")
    entity_refs: list[str] = Field(
        default_factory=list,
        description="Entity IDs mentioned in this message",
    )


class SessionEntityMention(BaseModel):
    """Tracked entity mention for pronoun resolution.

    Story 7-1: Enables "he", "she", "they", "it" resolution
    by tracking which entities were mentioned in the conversation.

    Note: Named SessionEntityMention to avoid collision with
    EntityMention in app.models.entity which is a DB model.
    """

    entity_id: str = Field(description="Entity UUID from MIG")
    entity_name: str = Field(description="Primary entity name")
    entity_type: str = Field(
        default="unknown",
        description="Entity type: person, organization, location, etc.",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Known aliases for this entity",
    )
    mention_count: int = Field(default=1, ge=1, description="Times mentioned")
    last_mentioned: str = Field(description="ISO8601 timestamp of last mention")


class SessionContext(BaseModel):
    """Complete session context stored in Redis.

    Story 7-1: Main session data structure for Redis persistence.
    Story 7-2: Extended with TTL tracking and archival fields.

    Stored with 7-day TTL, auto-extended on access (max 30 days).

    Key format: session:{matter_id}:{user_id}:context
    """

    # Session identification
    session_id: str = Field(description="Unique session UUID")
    matter_id: str = Field(description="Matter UUID for isolation")
    user_id: str = Field(description="User UUID who owns this session")

    # Timestamps
    created_at: str = Field(description="ISO8601 session creation time")
    last_activity: str = Field(description="ISO8601 last activity time")

    # Conversation context
    messages: list[SessionMessage] = Field(
        default_factory=list,
        max_length=20,
        description="Recent messages (max 20, sliding window)",
    )

    # Entity tracking for pronoun resolution
    entities_mentioned: dict[str, SessionEntityMention] = Field(
        default_factory=dict,
        description="Map of entity_id -> SessionEntityMention for context",
    )

    # Session metadata
    query_count: int = Field(default=0, ge=0, description="Queries in this session")
    ttl_extended_count: int = Field(
        default=0,
        ge=0,
        description="Times TTL was auto-extended",
    )

    # Story 7-2: TTL tracking and archival fields
    max_ttl_reached: bool = Field(
        default=False,
        description="True when 30-day max lifetime reached (no more extensions)",
    )
    total_lifetime_days: int = Field(
        default=0,
        ge=0,
        description="Cumulative session age in days",
    )
    archived_at: str | None = Field(
        default=None,
        description="ISO8601 timestamp when session was archived to Matter Memory",
    )


# =============================================================================
# Story 7-2: Archived Session Model
# =============================================================================


class ArchivedSession(BaseModel):
    """Archived session for Matter Memory storage.

    Story 7-2: Persists session context after expiry/end.
    Enables context restoration when user returns to matter.

    Stored in PostgreSQL matter_memory table with memory_type='archived_session'.
    """

    # Original session info
    session_id: str = Field(description="Original session UUID")
    matter_id: str = Field(description="Matter UUID for querying")
    user_id: str = Field(description="User UUID who owned this session")

    # Timestamps
    created_at: str = Field(description="Original session creation time")
    archived_at: str = Field(description="When session was archived")
    last_activity: str = Field(description="Last activity before archival")

    # Preserved context for restoration
    entities_mentioned: dict[str, SessionEntityMention] = Field(
        default_factory=dict,
        description="Entity mentions for pronoun resolution restoration",
    )

    # Last messages (subset for restoration)
    last_messages: list[SessionMessage] = Field(
        default_factory=list,
        max_length=MAX_ARCHIVED_MESSAGES,
        description=f"Last {MAX_ARCHIVED_MESSAGES} messages for context restoration",
    )

    # Session stats
    total_query_count: int = Field(default=0, ge=0, description="Total queries in session")
    total_messages: int = Field(default=0, ge=0, description="Total messages in session")
    ttl_extended_count: int = Field(default=0, ge=0, description="Times TTL was extended")

    # Archival metadata
    archival_reason: Literal["expired", "manual_end", "logout"] = Field(
        description="Why session was archived"
    )


# =============================================================================
# Story 7-3: Matter Memory Models (Query History, Timeline Cache, Entity Graph)
# =============================================================================


class QueryHistoryEntry(BaseModel):
    """Single query record in matter query history.

    Story 7-3: Forensic audit trail entry for matter-level query logging.
    Stored append-only for audit integrity.
    """

    query_id: str = Field(description="Unique query UUID")
    query_text: str = Field(description="Original query text")
    normalized_query: str | None = Field(
        default=None,
        description="Normalized query for cache matching",
    )
    asked_by: str = Field(description="User UUID who asked")
    asked_at: str = Field(description="ISO8601 timestamp")

    # Response metadata
    response_summary: str = Field(
        default="",
        description="Brief summary of the response",
    )
    engines_used: list[str] = Field(
        default_factory=list,
        description="Engines that processed this query",
    )
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Overall response confidence 0-100",
    )

    # Verification status
    verified: bool = Field(
        default=False,
        description="Attorney verified the response",
    )
    verified_by: str | None = Field(default=None, description="Verifier user UUID")
    verified_at: str | None = Field(default=None, description="Verification timestamp")

    # Cost tracking
    tokens_used: int | None = Field(default=None, ge=0, description="Total tokens consumed")
    cost_usd: float | None = Field(default=None, ge=0, description="Total cost in USD")


class QueryHistory(BaseModel):
    """Matter query history container.

    Story 7-3: Append-only forensic audit log for all queries on a matter.
    Stored as JSONB in matter_memory table with memory_type='query_history'.
    """

    entries: list[QueryHistoryEntry] = Field(
        default_factory=list,
        description="Query history entries (newest last)",
    )

    @field_validator("entries", mode="before")
    @classmethod
    def validate_entries(cls, v: list | None) -> list:
        """Ensure entries is always a list."""
        return v or []


class TimelineCacheEntry(BaseModel):
    """Single event in cached timeline.

    Story 7-3: Simplified event for timeline cache storage.
    """

    event_id: str = Field(description="Event UUID")
    event_date: str = Field(description="ISO8601 event date")
    event_type: str = Field(description="Event classification")
    description: str = Field(description="Event description")
    entities: list[str] = Field(
        default_factory=list,
        description="Entity IDs involved",
    )
    document_id: str | None = Field(default=None, description="Source document")
    confidence: float | None = Field(default=None, ge=0, le=100)


class TimelineCache(BaseModel):
    """Cached timeline for matter.

    Story 7-3: Pre-built timeline for instant re-queries.
    Stored as JSONB in matter_memory table with memory_type='timeline_cache'.
    Invalidated when new documents are uploaded.
    """

    cached_at: str = Field(description="ISO8601 cache creation time")
    last_document_upload: str | None = Field(
        default=None,
        description="Last doc upload time for staleness check",
    )
    version: int = Field(default=1, ge=1, description="Cache version")
    events: list[TimelineCacheEntry] = Field(
        default_factory=list,
        description="Timeline events sorted by date",
    )
    date_range_start: str | None = Field(default=None, description="Earliest event date")
    date_range_end: str | None = Field(default=None, description="Latest event date")
    event_count: int = Field(default=0, ge=0, description="Total events in timeline")

    @field_validator("events", mode="before")
    @classmethod
    def validate_events(cls, v: list | None) -> list:
        """Ensure events is always a list."""
        return v or []


class EntityRelationship(BaseModel):
    """Relationship between entities in cache.

    Story 7-3: Cached MIG relationship for entity graph.
    """

    source_id: str = Field(description="Source entity ID")
    target_id: str = Field(description="Target entity ID")
    relationship_type: str = Field(description="Relationship type")
    confidence: float | None = Field(default=None, ge=0, le=1)


class CachedEntity(BaseModel):
    """Entity in cached entity graph.

    Story 7-3: Simplified entity for cache storage.
    """

    entity_id: str = Field(description="Entity UUID")
    canonical_name: str = Field(description="Primary entity name")
    entity_type: str = Field(description="Entity type: PERSON, ORG, etc.")
    aliases: list[str] = Field(default_factory=list, description="Known aliases")
    mention_count: int = Field(default=0, ge=0, description="Total mentions")


class EntityGraphCache(BaseModel):
    """Cached entity graph for matter.

    Story 7-3: Pre-built MIG relationships for instant queries.
    Stored as JSONB in matter_memory table with memory_type='entity_graph'.
    Invalidated when new documents are uploaded.
    """

    cached_at: str = Field(description="ISO8601 cache creation time")
    last_document_upload: str | None = Field(
        default=None,
        description="Last doc upload time for staleness check",
    )
    version: int = Field(default=1, ge=1, description="Cache version")
    entities: dict[str, CachedEntity] = Field(
        default_factory=dict,
        description="Map of entity_id -> CachedEntity",
    )
    relationships: list[EntityRelationship] = Field(
        default_factory=list,
        description="Entity relationships",
    )
    entity_count: int = Field(default=0, ge=0, description="Total entities")
    relationship_count: int = Field(default=0, ge=0, description="Total relationships")

    @field_validator("entities", mode="before")
    @classmethod
    def validate_entities(cls, v: dict | None) -> dict:
        """Ensure entities is always a dict."""
        return v or {}

    @field_validator("relationships", mode="before")
    @classmethod
    def validate_relationships(cls, v: list | None) -> list:
        """Ensure relationships is always a list."""
        return v or []


# =============================================================================
# Story 7-4: Key Findings Models (Task 1)
# =============================================================================


class FindingEvidence(BaseModel):
    """Evidence supporting a finding.

    Story 7-4: Task 1.1 - Links finding to source documents.
    """

    document_id: str = Field(description="Source document UUID")
    page: int = Field(ge=1, description="Page number (1-indexed)")
    bbox_ids: list[str] = Field(
        default_factory=list,
        description="Bounding box IDs for highlighting",
    )
    text_excerpt: str = Field(
        default="",
        description="Quoted text excerpt from document",
    )
    confidence: float = Field(
        default=100.0,
        ge=0,
        le=100,
        description="Confidence in this evidence 0-100",
    )


class KeyFinding(BaseModel):
    """Attorney-verified finding stored in Matter Memory.

    Story 7-4: Task 1.2 - AC #1 - Persistent finding with evidence linkage.
    Part of the verification workflow (ADR-004).
    """

    finding_id: str = Field(description="Unique finding UUID")
    finding_type: FindingType = Field(description="Type of finding")
    description: str = Field(description="Finding description")

    # Evidence linkage
    evidence: list[FindingEvidence] = Field(
        default_factory=list,
        description="Supporting evidence from documents",
    )

    # Verification status (ADR-004: Tiered verification)
    verified_by: str | None = Field(default=None, description="Verifier user UUID")
    verified_at: str | None = Field(default=None, description="Verification timestamp")

    # Metadata
    notes: str = Field(default="", description="Attorney notes on this finding")
    confidence: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Overall finding confidence 0-100",
    )

    # Timestamps
    created_at: str = Field(description="ISO8601 creation timestamp")
    created_by: str = Field(description="Creator user UUID")
    updated_at: str | None = Field(default=None, description="Last update timestamp")

    # Source engine (for traceability)
    source_engine: str | None = Field(
        default=None,
        description="Engine that generated this finding (if automated)",
    )
    source_query_id: str | None = Field(
        default=None,
        description="Query that generated this finding (links to query_history)",
    )


class KeyFindings(BaseModel):
    """Container for matter key findings.

    Story 7-4: Task 1.3 - Stored as JSONB in matter_memory with memory_type='key_findings'.
    Uses append-only semantics.
    """

    findings: list[KeyFinding] = Field(
        default_factory=list,
        description="Key findings (append-only, newest last)",
    )

    @field_validator("findings", mode="before")
    @classmethod
    def validate_findings(cls, v: list | None) -> list:
        """Ensure findings is always a list."""
        return v or []


# =============================================================================
# Story 7-4: Research Notes Models (Task 2)
# =============================================================================


class ResearchNote(BaseModel):
    """Attorney research note stored in Matter Memory.

    Story 7-4: Task 2.1 - AC #2 - Personal notes with markdown support.
    """

    note_id: str = Field(description="Unique note UUID")
    created_by: str = Field(description="Creator user UUID")
    created_at: str = Field(description="ISO8601 creation timestamp")
    updated_at: str | None = Field(default=None, description="Last update timestamp")

    # Note content
    title: str = Field(description="Note title")
    content: str = Field(default="", description="Note content (markdown supported)")

    # Organization
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for categorization",
    )
    linked_findings: list[str] = Field(
        default_factory=list,
        description="Finding IDs this note references",
    )


class ResearchNotes(BaseModel):
    """Container for matter research notes.

    Story 7-4: Task 2.2 - Stored as JSONB in matter_memory with memory_type='research_notes'.
    """

    notes: list[ResearchNote] = Field(
        default_factory=list,
        description="Research notes",
    )

    @field_validator("notes", mode="before")
    @classmethod
    def validate_notes(cls, v: list | None) -> list:
        """Ensure notes is always a list."""
        return v or []


# =============================================================================
# Story 7-5: Query Cache Models (Task 1)
# =============================================================================


class CachedQueryResult(BaseModel):
    """Cached query result stored in Redis.

    Story 7-5: AC #1 - Results cached at cache:query:{matter_id}:{query_hash}
    AC #2 - Cached results returned in ~10ms
    AC #3 - 1-hour TTL with automatic expiration

    Part of Layer 3 (Query Cache) in the Three-Layer Memory System.
    """

    # Query identification
    query_hash: str = Field(description="SHA256 hash of normalized query (64 hex chars)")
    matter_id: str = Field(description="Matter UUID for isolation")
    original_query: str = Field(description="Original user query before normalization")
    normalized_query: str = Field(description="Normalized query used for hashing")

    # Timing
    cached_at: str = Field(description="ISO8601 timestamp when result was cached")
    expires_at: str = Field(description="ISO8601 timestamp when cache entry expires")

    # Response data
    result_summary: str = Field(
        default="",
        description="Brief summary of the query result",
    )
    engine_used: str | None = Field(
        default=None,
        description="Engine that processed the query",
    )
    findings_count: int = Field(
        default=0,
        ge=0,
        description="Number of findings in the result",
    )
    confidence: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Overall confidence score 0-100",
    )

    # Full response payload
    response_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Complete response payload for cache hit",
    )

    # Metadata
    cache_version: int = Field(
        default=1,
        ge=1,
        description="Cache schema version for migration support",
    )
