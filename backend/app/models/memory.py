"""Memory models for session and conversation context.

Story 7-1: Session Memory Redis Storage

These models define the structure of session data stored in Redis
for conversation context persistence. Part of the Three-Layer Memory System.

Layer 1: Session Memory (this module) - Conversation context during user session
Layer 2: Matter Memory (Story 7-3) - Persistent findings and entity graph
Layer 3: Query Cache (Story 7-5) - LLM response caching
"""

from pydantic import BaseModel, Field


class SessionMessage(BaseModel):
    """A single message in the session conversation.

    Story 7-1: Tracks individual messages for context.
    Messages are stored in a sliding window (max 20).
    """

    role: str = Field(description="Message role: 'user' or 'assistant'")
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
    Stored with 7-day TTL, auto-extended on access.

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
