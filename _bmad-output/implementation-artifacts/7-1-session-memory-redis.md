# Story 7.1: Implement Session Memory Redis Storage

Status: review

## Story

As an **attorney**,
I want **my conversation context maintained during my session**,
So that **I can ask follow-up questions without repeating context**.

## Acceptance Criteria

1. **Given** I start a conversation in a matter
   **When** the session is created
   **Then** a Redis key is created: `session:{matter_id}:{user_id}`
   **And** SessionContext is stored with session_id, matter_id, user_id, created_at, last_activity

2. **Given** I send a message
   **When** the message is processed
   **Then** it is added to the messages array in SessionContext
   **And** last_activity is updated

3. **Given** the messages array grows
   **When** it exceeds 20 messages
   **Then** a sliding window removes the oldest messages
   **And** the most recent 20 are retained

4. **Given** I mention entities in conversation
   **When** tracking runs
   **Then** entities_mentioned map is updated
   **And** pronouns can be resolved to mentioned entities

## Tasks / Subtasks

- [x] Task 1: Create Session Memory Models (AC: #1-4)
  - [x] 1.1: Create `SessionMessage` model with role, content, timestamp, entity_refs
  - [x] 1.2: Create `SessionEntityMention` model with entity_id, entity_name, aliases, mention_count, last_mentioned
  - [x] 1.3: Create `SessionContext` model with session_id, matter_id, user_id, created_at, last_activity, messages, entities_mentioned
  - [x] 1.4: Add models to `backend/app/models/memory.py` (NEW file)

- [x] Task 2: Create Redis Client Wrapper (AC: #1-2)
  - [x] 2.1: Create `backend/app/services/memory/redis_client.py` with async Upstash Redis client
  - [x] 2.2: Implement `get_redis_client()` factory with singleton pattern
  - [x] 2.3: Handle REST-based Upstash Redis (HTTP client, no persistent connections)
  - [x] 2.4: Added fallback to redis-py for local development
  - [x] 2.5: Add environment variable support for REDIS_URL / UPSTASH_REDIS_REST_URL

- [x] Task 3: Create Session Memory Service (AC: #1-4)
  - [x] 3.1: Create `SessionMemoryService` class in `backend/app/services/memory/session.py` (NEW)
  - [x] 3.2: Implement `create_session()` - initialize new session in Redis with 7-day TTL
  - [x] 3.3: Implement `get_session()` - retrieve session context, auto-extend TTL on access
  - [x] 3.4: Implement `add_message()` - add message to session with sliding window (max 20)
  - [x] 3.5: Implement `update_entities()` - track mentioned entities for pronoun resolution
  - [x] 3.6: Implement `get_entities_mentioned()` - retrieve entity map for context
  - [x] 3.7: Implement `end_session()` - clear session from Redis (optional manual cleanup)
  - [x] 3.8: Add `get_session_memory_service()` factory function

- [x] Task 4: Implement Sliding Window Logic (AC: #3)
  - [x] 4.1: Create `_apply_sliding_window()` method to maintain max 20 messages
  - [x] 4.2: Preserve most recent messages when truncating
  - [x] 4.3: Sliding window removes oldest messages automatically
  - [x] 4.4: Log when window slides for debugging

- [x] Task 5: Implement Entity Tracking (AC: #4)
  - [x] 5.1: Entity extraction via `update_entities()` method (caller provides entities)
  - [x] 5.2: Create `resolve_pronoun()` method to map pronouns to recent entities
  - [x] 5.3: Implement recency-weighted entity resolution (most recently mentioned gets priority)
  - [x] 5.4: Handle entity aliases stored in SessionEntityMention

- [x] Task 6: Write Comprehensive Tests (AC: #1-4)
  - [x] 6.1: Unit tests for `SessionMessage`, `SessionEntityMention`, `SessionContext` models (19 tests)
  - [x] 6.2: Unit tests for Redis client wrapper with mocked responses (9 tests)
  - [x] 6.3: Unit tests for `SessionMemoryService` with mock Redis (37 tests)
  - [x] 6.4: Test sliding window behavior (19, 20, 21 messages scenarios)
  - [x] 6.5: Test entity tracking and pronoun resolution
  - [x] 6.6: Test TTL auto-extension on session access
  - [x] 6.7: Test matter isolation (sessions scoped to matter_id + user_id)
  - [x] 6.8: Integration test for full session lifecycle

- [x] Task 7: Update Memory Module Exports (AC: #1-4)
  - [x] 7.1: Export new models from `models/memory.py`
  - [x] 7.2: Export `SessionMemoryService` from `services/memory/__init__.py`
  - [x] 7.3: Export `get_redis_client` from `services/memory/__init__.py`
  - [x] 7.4: Update `models/__init__.py` with memory models

## Dev Notes

### Architecture Compliance

This story implements **Session Memory** - the first layer of the **Three-Layer Memory System** (Epic 7):

```
SESSION MEMORY (7-1) 👈 → TTL & PRONOUN (7-2) → MATTER MEMORY (7-3) → KEY FINDINGS (7-4) → QUERY CACHE (7-5)
```

Session Memory satisfies:
- **FR5**: Context persistence during user session
- **FR6**: Follow-up questions without repeating context
- **NFR31**: Performant session retrieval (Redis in-memory)
- **NFR32**: Session timeout handling (7-day TTL)

### Critical Implementation Details

1. **Session Memory Data Flow**

   ```
   User Message
       ↓
   SessionMemoryService.add_message()
       ↓ Apply sliding window (max 20)
   Redis SETEX with 7-day TTL
       ↓
   SessionMemoryService.update_entities()
       ↓ Extract entity mentions
   Redis HSET entities_mentioned
       ↓
   Orchestrator uses context for follow-up
   ```

2. **Redis Key Structure** (Layer 3 of 4-layer isolation)

   Use existing `redis_keys.py` functions:
   ```python
   from app.services.memory.redis_keys import (
       session_key,      # session:{matter_id}:{user_id}:{key_type}
       SESSION_TTL,      # 7 days = 604800 seconds
       validate_key_access,
   )
   ```

   Key types:
   - `session:{matter_id}:{user_id}:context` - Main SessionContext JSON
   - `session:{matter_id}:{user_id}:messages` - Messages list (optional if in context)
   - `session:{matter_id}:{user_id}:entities` - Entity mention map

3. **Model Definitions** (Task 1)

   Create `backend/app/models/memory.py`:

   ```python
   """Memory models for session and conversation context.

   Story 7-1: Session Memory Redis Storage

   These models define the structure of session data stored in Redis
   for conversation context persistence.
   """

   from datetime import datetime
   from pydantic import BaseModel, Field


   class SessionMessage(BaseModel):
       """A single message in the session conversation.

       Story 7-1: Tracks individual messages for context.
       """

       role: str = Field(description="Message role: 'user' or 'assistant'")
       content: str = Field(description="Message content text")
       timestamp: str = Field(description="ISO8601 timestamp when sent")
       entity_refs: list[str] = Field(
           default_factory=list,
           description="Entity IDs mentioned in this message",
       )


   class EntityMention(BaseModel):
       """Tracked entity mention for pronoun resolution.

       Story 7-1: Enables "he", "she", "they", "it" resolution.
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
           max_length=20,
       )

       # Entity tracking for pronoun resolution
       entities_mentioned: dict[str, EntityMention] = Field(
           default_factory=dict,
           description="Map of entity_id -> EntityMention for context",
       )

       # Session metadata
       query_count: int = Field(default=0, ge=0, description="Queries in this session")
       ttl_extended_count: int = Field(
           default=0, ge=0,
           description="Times TTL was auto-extended",
       )
   ```

4. **Redis Client Implementation** (Task 2)

   Create `backend/app/services/memory/redis_client.py`:

   ```python
   """Async Redis client for session memory.

   Story 7-1: Session Memory Redis Storage

   Uses Upstash Redis (HTTP-based, serverless) for session persistence.
   Falls back to standard redis-py for local development.

   CRITICAL: This is an async client. All operations must be awaited.
   """

   import json
   import os
   from typing import Any

   import structlog

   logger = structlog.get_logger(__name__)

   # Singleton client instance
   _redis_client: Any = None


   async def get_redis_client() -> Any:
       """Get or create async Redis client.

       Returns Upstash Redis client for production or redis-py for local.

       Returns:
           Async Redis client instance.
       """
       global _redis_client

       if _redis_client is not None:
           return _redis_client

       # Check for Upstash environment variables first
       upstash_url = os.getenv("UPSTASH_REDIS_REST_URL")
       upstash_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")

       if upstash_url and upstash_token:
           # Use Upstash Redis (HTTP-based, async)
           try:
               from upstash_redis.asyncio import Redis

               _redis_client = Redis(url=upstash_url, token=upstash_token)
               logger.info("redis_client_initialized", type="upstash", url=upstash_url[:30])
               return _redis_client
           except ImportError:
               logger.warning("upstash_redis_not_installed", fallback="redis-py")

       # Fallback to standard redis-py for local development
       redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

       try:
           import redis.asyncio as redis

           _redis_client = redis.from_url(redis_url, decode_responses=True)
           logger.info("redis_client_initialized", type="redis-py", url=redis_url[:30])
           return _redis_client
       except ImportError:
           logger.error("no_redis_client_available")
           raise RuntimeError("No Redis client available. Install redis or upstash-redis.")


   def reset_redis_client() -> None:
       """Reset Redis client (for testing)."""
       global _redis_client
       _redis_client = None
   ```

5. **SessionMemoryService Implementation** (Task 3)

   Create `backend/app/services/memory/session.py`:

   ```python
   """Session Memory Service for conversation context.

   Story 7-1: Session Memory Redis Storage

   Manages user session context in Redis with:
   - 7-day TTL with auto-extension
   - Sliding window message history (max 20)
   - Entity tracking for pronoun resolution

   CRITICAL: All session data is scoped by matter_id + user_id
   for Layer 3 isolation (Redis key prefix).
   """

   import uuid
   from datetime import datetime, timezone
   from typing import Any

   import structlog

   from app.models.memory import EntityMention, SessionContext, SessionMessage
   from app.services.memory.redis_client import get_redis_client
   from app.services.memory.redis_keys import (
       SESSION_TTL,
       session_key,
       validate_key_access,
   )

   logger = structlog.get_logger(__name__)

   # Maximum messages in sliding window
   MAX_SESSION_MESSAGES = 20


   class SessionMemoryService:
       """Manages session context in Redis.

       Story 7-1: Provides conversation context persistence
       for follow-up questions without repeating context.
       """

       def __init__(self, redis_client: Any = None):
           """Initialize session memory service.

           Args:
               redis_client: Optional Redis client (injected for testing).
           """
           self._redis = redis_client
           self._initialized = False

       async def _ensure_client(self) -> None:
           """Ensure Redis client is initialized."""
           if self._redis is None:
               self._redis = await get_redis_client()
           self._initialized = True

       async def create_session(
           self,
           matter_id: str,
           user_id: str,
       ) -> SessionContext:
           """Create a new session in Redis.

           Args:
               matter_id: Matter UUID for isolation.
               user_id: User UUID who owns this session.

           Returns:
               Newly created SessionContext.
           """
           await self._ensure_client()

           session_id = str(uuid.uuid4())
           now = datetime.now(timezone.utc).isoformat()

           context = SessionContext(
               session_id=session_id,
               matter_id=matter_id,
               user_id=user_id,
               created_at=now,
               last_activity=now,
               messages=[],
               entities_mentioned={},
               query_count=0,
               ttl_extended_count=0,
           )

           # Store in Redis with 7-day TTL
           key = session_key(matter_id, user_id, "context")
           await self._redis.setex(
               key,
               SESSION_TTL,
               context.model_dump_json(),
           )

           logger.info(
               "session_created",
               session_id=session_id,
               matter_id=matter_id,
               user_id=user_id,
               ttl_days=SESSION_TTL // 86400,
           )

           return context

       async def get_session(
           self,
           matter_id: str,
           user_id: str,
           auto_create: bool = True,
           extend_ttl: bool = True,
       ) -> SessionContext | None:
           """Retrieve session context from Redis.

           Args:
               matter_id: Matter UUID.
               user_id: User UUID.
               auto_create: Create new session if not found.
               extend_ttl: Auto-extend TTL on access (sliding expiration).

           Returns:
               SessionContext if found, None otherwise.
           """
           await self._ensure_client()

           key = session_key(matter_id, user_id, "context")

           # Get session data
           data = await self._redis.get(key)

           if data is None:
               if auto_create:
                   logger.info(
                       "session_not_found_creating",
                       matter_id=matter_id,
                       user_id=user_id,
                   )
                   return await self.create_session(matter_id, user_id)
               return None

           # Parse session context
           context = SessionContext.model_validate_json(data)

           # Auto-extend TTL on access (sliding expiration)
           if extend_ttl:
               await self._redis.expire(key, SESSION_TTL)
               context.ttl_extended_count += 1
               context.last_activity = datetime.now(timezone.utc).isoformat()

               # Update stored context
               await self._redis.setex(
                   key,
                   SESSION_TTL,
                   context.model_dump_json(),
               )

               logger.debug(
                   "session_ttl_extended",
                   session_id=context.session_id,
                   matter_id=matter_id,
                   extend_count=context.ttl_extended_count,
               )

           return context

       async def add_message(
           self,
           matter_id: str,
           user_id: str,
           role: str,
           content: str,
           entity_refs: list[str] | None = None,
       ) -> SessionContext:
           """Add a message to session history with sliding window.

           Args:
               matter_id: Matter UUID.
               user_id: User UUID.
               role: Message role ('user' or 'assistant').
               content: Message content.
               entity_refs: Optional entity IDs mentioned.

           Returns:
               Updated SessionContext.
           """
           await self._ensure_client()

           # Get or create session
           context = await self.get_session(matter_id, user_id, auto_create=True)
           if context is None:
               context = await self.create_session(matter_id, user_id)

           # Create message
           message = SessionMessage(
               role=role,
               content=content,
               timestamp=datetime.now(timezone.utc).isoformat(),
               entity_refs=entity_refs or [],
           )

           # Add to messages list
           context.messages.append(message)

           # Apply sliding window (max 20 messages)
           context = self._apply_sliding_window(context)

           # Update activity and query count
           context.last_activity = datetime.now(timezone.utc).isoformat()
           if role == "user":
               context.query_count += 1

           # Save to Redis
           key = session_key(matter_id, user_id, "context")
           await self._redis.setex(
               key,
               SESSION_TTL,
               context.model_dump_json(),
           )

           logger.debug(
               "message_added_to_session",
               session_id=context.session_id,
               role=role,
               message_count=len(context.messages),
               query_count=context.query_count,
           )

           return context

       def _apply_sliding_window(
           self,
           context: SessionContext,
       ) -> SessionContext:
           """Apply sliding window to keep max 20 messages.

           Args:
               context: Session context to modify.

           Returns:
               Modified context with window applied.

           Note:
               This is a local operation on the context object.
               Caller is responsible for persisting changes.
           """
           if len(context.messages) <= MAX_SESSION_MESSAGES:
               return context

           # Remove oldest messages
           removed_count = len(context.messages) - MAX_SESSION_MESSAGES
           context.messages = context.messages[-MAX_SESSION_MESSAGES:]

           logger.info(
               "sliding_window_applied",
               session_id=context.session_id,
               removed_count=removed_count,
               retained_count=len(context.messages),
           )

           return context

       async def update_entities(
           self,
           matter_id: str,
           user_id: str,
           entities: list[dict[str, Any]],
       ) -> SessionContext:
           """Update entity mentions for pronoun resolution.

           Args:
               matter_id: Matter UUID.
               user_id: User UUID.
               entities: List of entity dicts with id, name, type, aliases.

           Returns:
               Updated SessionContext.
           """
           await self._ensure_client()

           context = await self.get_session(matter_id, user_id, auto_create=True)
           if context is None:
               context = await self.create_session(matter_id, user_id)

           now = datetime.now(timezone.utc).isoformat()

           for entity in entities:
               entity_id = entity.get("id", entity.get("entity_id"))
               if not entity_id:
                   continue

               if entity_id in context.entities_mentioned:
                   # Update existing mention
                   mention = context.entities_mentioned[entity_id]
                   mention.mention_count += 1
                   mention.last_mentioned = now
               else:
                   # Add new mention
                   context.entities_mentioned[entity_id] = EntityMention(
                       entity_id=entity_id,
                       entity_name=entity.get("name", entity.get("entity_name", "Unknown")),
                       entity_type=entity.get("type", entity.get("entity_type", "unknown")),
                       aliases=entity.get("aliases", []),
                       mention_count=1,
                       last_mentioned=now,
                   )

           # Save to Redis
           key = session_key(matter_id, user_id, "context")
           await self._redis.setex(
               key,
               SESSION_TTL,
               context.model_dump_json(),
           )

           logger.debug(
               "entities_updated",
               session_id=context.session_id,
               entity_count=len(context.entities_mentioned),
           )

           return context

       async def get_entities_mentioned(
           self,
           matter_id: str,
           user_id: str,
       ) -> dict[str, EntityMention]:
           """Get entities mentioned in session for context.

           Args:
               matter_id: Matter UUID.
               user_id: User UUID.

           Returns:
               Dict of entity_id -> EntityMention.
           """
           context = await self.get_session(matter_id, user_id, auto_create=False)
           if context is None:
               return {}
           return context.entities_mentioned

       async def resolve_pronoun(
           self,
           matter_id: str,
           user_id: str,
           pronoun: str,
       ) -> EntityMention | None:
           """Resolve a pronoun to the most recently mentioned entity.

           Args:
               matter_id: Matter UUID.
               user_id: User UUID.
               pronoun: Pronoun to resolve (he, she, they, it, etc.).

           Returns:
               Most relevant EntityMention or None.
           """
           entities = await self.get_entities_mentioned(matter_id, user_id)
           if not entities:
               return None

           # Filter by pronoun type (gender/plurality)
           pronoun_lower = pronoun.lower()
           candidates: list[EntityMention] = []

           for mention in entities.values():
               entity_type = mention.entity_type.lower()

               # Match pronouns to entity types
               if pronoun_lower in ("he", "him", "his"):
                   if entity_type in ("person", "male", "unknown"):
                       candidates.append(mention)
               elif pronoun_lower in ("she", "her", "hers"):
                   if entity_type in ("person", "female", "unknown"):
                       candidates.append(mention)
               elif pronoun_lower in ("they", "them", "their"):
                   # Can refer to groups or individuals
                   candidates.append(mention)
               elif pronoun_lower in ("it", "its"):
                   if entity_type in ("organization", "thing", "document", "unknown"):
                       candidates.append(mention)
               else:
                   # Unknown pronoun - include all
                   candidates.append(mention)

           if not candidates:
               return None

           # Return most recently mentioned
           return max(candidates, key=lambda m: m.last_mentioned)

       async def end_session(
           self,
           matter_id: str,
           user_id: str,
       ) -> bool:
           """End and clear a session from Redis.

           Args:
               matter_id: Matter UUID.
               user_id: User UUID.

           Returns:
               True if session was deleted, False if not found.

           Note:
               Before clearing, session should be archived to
               Matter Memory (Story 7-2 handles archival).
           """
           await self._ensure_client()

           key = session_key(matter_id, user_id, "context")
           result = await self._redis.delete(key)

           logger.info(
               "session_ended",
               matter_id=matter_id,
               user_id=user_id,
               deleted=result > 0,
           )

           return result > 0


   # Singleton instance
   _session_memory_service: SessionMemoryService | None = None


   def get_session_memory_service(redis_client: Any = None) -> SessionMemoryService:
       """Get or create SessionMemoryService instance.

       Args:
           redis_client: Optional Redis client for injection.

       Returns:
           SessionMemoryService instance.
       """
       global _session_memory_service

       if _session_memory_service is None:
           _session_memory_service = SessionMemoryService(redis_client)
       elif redis_client is not None and _session_memory_service._redis is None:
           _session_memory_service._redis = redis_client

       return _session_memory_service


   def reset_session_memory_service() -> None:
       """Reset singleton (for testing)."""
       global _session_memory_service
       _session_memory_service = None
   ```

6. **Existing Code to Reuse** (CRITICAL - DO NOT REINVENT)

   | Component | Location | Purpose |
   |-----------|----------|---------|
   | `redis_keys.py` | `app/services/memory/redis_keys.py` | Key prefixes and validation (MUST USE) |
   | `SESSION_TTL` | `app/services/memory/redis_keys.py` | 7-day TTL constant (604800 seconds) |
   | `session_key()` | `app/services/memory/redis_keys.py` | Generate session:{matter_id}:{user_id}:{type} |
   | `validate_key_access()` | `app/services/memory/redis_keys.py` | Verify matter isolation |
   | `Settings` | `app/core/config.py` | Redis URL configuration |
   | Factory pattern | All services | `get_*()` functions for DI |
   | structlog | All modules | Structured logging |

### File Structure

Create/extend memory service structure:

```
backend/app/
├── models/
│   ├── __init__.py                   # Update exports
│   └── memory.py                     # Story 7-1 (NEW)
├── services/
│   └── memory/
│       ├── __init__.py               # Update exports for 7-1
│       ├── redis_keys.py             # EXISTS - Key prefix utilities
│       ├── redis_client.py           # Story 7-1 (NEW)
│       └── session.py                # Story 7-1 (NEW)
└── tests/
    ├── models/
    │   └── test_memory_models.py     # Story 7-1 (NEW)
    └── services/
        └── memory/
            ├── test_redis_keys.py    # EXISTS
            ├── test_redis_client.py  # Story 7-1 (NEW)
            └── test_session.py       # Story 7-1 (NEW)
```

### Testing Requirements

Per project-context.md:
- Backend: `tests/services/memory/` directory
- Use pytest-asyncio for async tests
- Mock Redis responses (don't hit real Redis in tests)
- Include matter isolation test (CRITICAL)

**Test Files to Create:**
- `tests/models/test_memory_models.py`
- `tests/services/memory/test_redis_client.py`
- `tests/services/memory/test_session.py`

**Minimum Test Cases:**

```python
# test_memory_models.py
def test_session_message_creation():
    """Message should include role, content, timestamp."""
    msg = SessionMessage(
        role="user",
        content="What about the plaintiff?",
        timestamp="2026-01-14T10:00:00Z",
        entity_refs=["entity-123"],
    )
    assert msg.role == "user"
    assert "plaintiff" in msg.content


def test_session_context_max_messages():
    """Session context should enforce max 20 messages."""
    context = SessionContext(
        session_id="sess-1",
        matter_id="matter-1",
        user_id="user-1",
        created_at="2026-01-14T10:00:00Z",
        last_activity="2026-01-14T10:00:00Z",
    )
    assert len(context.messages) == 0


# test_session.py
@pytest.mark.asyncio
async def test_create_session(mock_redis):
    """Should create session with correct structure."""
    service = SessionMemoryService(mock_redis)

    context = await service.create_session(
        matter_id="matter-123",
        user_id="user-456",
    )

    assert context.session_id
    assert context.matter_id == "matter-123"
    assert context.user_id == "user-456"
    assert len(context.messages) == 0


@pytest.mark.asyncio
async def test_sliding_window_at_20_messages(mock_redis):
    """Window should not slide at exactly 20 messages."""
    service = SessionMemoryService(mock_redis)

    # Add 20 messages
    context = await service.create_session("matter-1", "user-1")
    for i in range(20):
        context = await service.add_message(
            "matter-1", "user-1", "user", f"Message {i}"
        )

    assert len(context.messages) == 20


@pytest.mark.asyncio
async def test_sliding_window_at_21_messages(mock_redis):
    """Window should slide at 21 messages, keeping last 20."""
    service = SessionMemoryService(mock_redis)

    context = await service.create_session("matter-1", "user-1")
    for i in range(21):
        context = await service.add_message(
            "matter-1", "user-1", "user", f"Message {i}"
        )

    assert len(context.messages) == 20
    assert context.messages[0].content == "Message 1"  # Message 0 removed
    assert context.messages[-1].content == "Message 20"


@pytest.mark.asyncio
async def test_entity_tracking_and_resolution(mock_redis):
    """Should track entities and resolve pronouns."""
    service = SessionMemoryService(mock_redis)

    await service.create_session("matter-1", "user-1")
    await service.update_entities("matter-1", "user-1", [
        {"id": "e1", "name": "John Smith", "type": "person"},
        {"id": "e2", "name": "Acme Corp", "type": "organization"},
    ])

    # Resolve pronoun
    mention = await service.resolve_pronoun("matter-1", "user-1", "he")
    assert mention is not None
    assert mention.entity_name == "John Smith"


@pytest.mark.asyncio
async def test_matter_isolation(mock_redis):
    """Sessions should be isolated by matter_id + user_id."""
    service = SessionMemoryService(mock_redis)

    await service.create_session("matter-A", "user-1")
    await service.add_message("matter-A", "user-1", "user", "Matter A message")

    await service.create_session("matter-B", "user-1")
    await service.add_message("matter-B", "user-1", "user", "Matter B message")

    context_a = await service.get_session("matter-A", "user-1")
    context_b = await service.get_session("matter-B", "user-1")

    assert context_a.session_id != context_b.session_id
    assert context_a.messages[0].content == "Matter A message"
    assert context_b.messages[0].content == "Matter B message"


@pytest.mark.asyncio
async def test_ttl_auto_extension(mock_redis):
    """TTL should be extended on session access."""
    service = SessionMemoryService(mock_redis)

    context = await service.create_session("matter-1", "user-1")
    initial_extend_count = context.ttl_extended_count

    # Access session (triggers TTL extension)
    context = await service.get_session("matter-1", "user-1", extend_ttl=True)

    assert context.ttl_extended_count == initial_extend_count + 1
```

### Previous Story (6-3) Learnings

From Story 6-3 implementation:

1. **Factory pattern**: Use `get_*()` functions for dependency injection with global singleton
2. **Structured logging**: Use structlog for all logging with context fields
3. **Non-blocking patterns**: Use async/await consistently
4. **Thread-safe singletons**: Use `threading.Lock()` if needed (not required for async)
5. **Clean models**: Use Pydantic v2 with type hints and Field descriptions
6. **Test coverage**: Include edge cases, security tests, integration tests
7. **Matter isolation**: ALWAYS verify matter_id in all operations (redis_keys.py handles this)
8. **Constants**: Extract magic numbers to named constants (MAX_SESSION_MESSAGES = 20)
9. **Reset functions**: Add `reset_*()` functions for testing

### Git Intelligence

Recent commit pattern:
- `feat(orchestrator): implement audit trail logging (Story 6-3)`
- Pattern: `feat(domain): description (Story X-Y)`
- Code review: `fix(review): address code review issues for Story X-Y`

Use: `feat(memory): implement session memory Redis storage (Story 7-1)`

### Performance Considerations

1. **Upstash Redis**: HTTP-based, serverless, no persistent connections needed
2. **Connection reuse**: Initialize client outside request handler (singleton pattern)
3. **Sliding window**: Local operation, no extra Redis calls
4. **TTL extension**: Combine with data update in single setex call
5. **JSON serialization**: Pydantic `model_dump_json()` is fast and type-safe

### Security Considerations

1. **Matter isolation**: Layer 3 of 4-layer enforcement via redis_keys.py
2. **UUID validation**: redis_keys.py validates all UUIDs before key generation
3. **Key structure**: Fixed format prevents injection (session:{matter}:{user}:{type})
4. **No cross-matter access**: validate_key_access() provides defense-in-depth

### Environment Variables

Required for Upstash Redis (production):
- `UPSTASH_REDIS_REST_URL` - Upstash REST API URL
- `UPSTASH_REDIS_REST_TOKEN` - Upstash auth token

Fallback for local development:
- `REDIS_URL` - Standard Redis URL (default: redis://localhost:6379/0)

### Project Structure Notes

- Models in `models/memory.py` (Pydantic v2)
- Redis client wrapper in `services/memory/redis_client.py`
- Session service in `services/memory/session.py`
- Tests in `tests/services/memory/` and `tests/models/`
- Uses existing `redis_keys.py` for key generation (DO NOT DUPLICATE)

### References

- [Project Context](_bmad-output/project-context.md) - Naming conventions, testing rules
- [Architecture: Memory](../_bmad-output/architecture.md) - 3-layer memory system spec
- [Epic 7 Definition](../_bmad-output/project-planning-artifacts/epics.md) - Story requirements
- [redis_keys.py](backend/app/services/memory/redis_keys.py) - Existing key utilities (MUST USE)
- [Story 6-3](./6-3-audit-trail-logging.md) - Recent patterns and learnings
- [Upstash Redis Python](https://upstash.com/docs/redis/tutorials/python_session) - Session management patterns
- [upstash-redis PyPI](https://pypi.org/project/upstash-redis/) - Async client documentation

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - implementation successful without issues.

### Completion Notes List

- ✅ Implemented SessionMessage, SessionEntityMention, SessionContext models in `backend/app/models/memory.py`
- ✅ Created async Redis client wrapper with Upstash support and redis-py fallback in `backend/app/services/memory/redis_client.py`
- ✅ Implemented SessionMemoryService with all methods:
  - `create_session()` - Creates new session with 7-day TTL (AC #1)
  - `get_session()` - Retrieves session with auto-extend TTL
  - `add_message()` - Adds message with sliding window (AC #2, #3)
  - `update_entities()` - Tracks entity mentions (AC #4)
  - `resolve_pronoun()` - Recency-weighted pronoun resolution (AC #4)
  - `end_session()` - Cleans up session from Redis
- ✅ Sliding window logic maintains max 20 messages (AC #3)
- ✅ Entity tracking enables pronoun resolution (he/she/they/it) (AC #4)
- ✅ 65 tests passing: 19 model tests, 9 redis client tests, 37 service tests
- ✅ Matter isolation verified via redis_keys.py key generation
- ✅ Uses existing redis_keys.py for SESSION_TTL and session_key() - no duplication
- ✅ Factory pattern with `get_session_memory_service()` for DI
- ✅ Reset functions for testing: `reset_redis_client()`, `reset_session_memory_service()`
- ✅ All exports added to `services/memory/__init__.py` and `models/__init__.py`

### File List

**New Files:**
- `backend/app/models/memory.py` - Session memory Pydantic models
- `backend/app/services/memory/redis_client.py` - Async Redis client wrapper
- `backend/app/services/memory/session.py` - SessionMemoryService implementation
- `backend/tests/models/__init__.py` - Model tests package init
- `backend/tests/models/test_memory_models.py` - 19 model unit tests
- `backend/tests/services/memory/__init__.py` - Memory service tests package init
- `backend/tests/services/memory/test_redis_client.py` - 9 Redis client tests
- `backend/tests/services/memory/test_session.py` - 37 service tests

**Modified Files:**
- `backend/app/models/__init__.py` - Added memory model exports
- `backend/app/services/memory/__init__.py` - Added Redis client and session service exports

## Change Log

- 2026-01-14: Story 7-1 implementation complete - Session Memory Redis Storage with 65 passing tests
