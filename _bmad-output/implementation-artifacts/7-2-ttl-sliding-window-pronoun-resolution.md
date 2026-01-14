# Story 7.2: Implement Session TTL and Context Restoration

Status: dev-complete

## Story

As an **attorney**,
I want **my session to persist for a week with automatic extension**,
So that **I can continue where I left off**.

## Acceptance Criteria

1. **Given** a session exists
   **When** 7 days pass without activity
   **Then** the session auto-expires
   **And** is archived to Matter Memory before deletion

2. **Given** I am active in a session
   **When** activity occurs
   **Then** the TTL is extended (max 30 days total)
   **And** the session persists

3. **Given** I log out or manually end the session
   **When** the action completes
   **Then** the session is cleared from Redis
   **And** is archived to Matter Memory

4. **Given** a session has expired
   **When** I return to the matter
   **Then** context can be restored from the archived session in Matter Memory
   **And** a new session is created with previous context available

## Tasks / Subtasks

- [x] Task 1: Extend SessionContext Model with TTL Tracking (AC: #1, #2)
  - [x] 1.1: Add `max_ttl_reached: bool` field to SessionContext
  - [x] 1.2: Add `total_lifetime_days: int` field to track cumulative session age
  - [x] 1.3: Add `archived_at: str | None` field for archival timestamp
  - [x] 1.4: Update model in `backend/app/models/memory.py`

- [x] Task 2: Implement TTL Extension with Max Limit (AC: #2)
  - [x] 2.1: Add `MAX_SESSION_LIFETIME` constant (30 days = 2592000 seconds)
  - [x] 2.2: Update `get_session()` to check cumulative lifetime before extending
  - [x] 2.3: Implement `_check_max_lifetime()` helper method
  - [x] 2.4: Log when max lifetime is reached

- [x] Task 3: Create Session Archival Service (AC: #1, #3)
  - [x] 3.1: Create `archive_session()` method in SessionMemoryService
  - [x] 3.2: Implement `ArchivedSession` model for Matter Memory storage
  - [x] 3.3: Store archived session in PostgreSQL `matter_memory` table (JSONB)
  - [x] 3.4: Update `end_session()` to call `archive_session()` before deletion

- [x] Task 4: Implement Context Restoration (AC: #4)
  - [x] 4.1: Create `restore_context()` method in SessionMemoryService
  - [x] 4.2: Query `matter_memory` for most recent archived session
  - [x] 4.3: Create new session with entities_mentioned restored from archive
  - [x] 4.4: Optionally restore last N messages (configurable, default 5)

- [x] Task 5: Implement Redis TTL Expiry Hook (AC: #1)
  - [x] 5.1: Research Redis keyspace notifications for TTL expiry
  - [x] 5.2: Alternative: Implement lazy archival check in `get_session()`
  - [x] 5.3: Lazy pattern implemented in `get_session()` with `restore_from_archive` parameter
  - [x] 5.4: Log archival events with session metadata

- [x] Task 6: Create Matter Memory Repository (AC: #1, #3, #4)
  - [x] 6.1: Create `MatterMemoryRepository` class in `backend/app/services/memory/matter.py`
  - [x] 6.2: Implement `save_archived_session()` method (Supabase JSONB insert)
  - [x] 6.3: Implement `get_latest_archived_session()` method
  - [x] 6.4: Implement `get_archived_sessions()` for listing (with pagination)

- [x] Task 7: Write Comprehensive Tests (AC: #1-4)
  - [x] 7.1: Test TTL extension with max lifetime check
  - [x] 7.2: Test session archival to PostgreSQL
  - [x] 7.3: Test context restoration from archive
  - [x] 7.4: Test end_session with archival
  - [x] 7.5: Test lazy archival on expired session access
  - [x] 7.6: Test matter isolation for archived sessions

- [x] Task 8: Update Memory Module Exports (AC: #1-4)
  - [x] 8.1: Export `ArchivedSession` model
  - [x] 8.2: Export `MatterMemoryRepository`
  - [x] 8.3: Update `services/memory/__init__.py`

## Dev Notes

### Architecture Compliance

This story extends **Session Memory** (Story 7-1) with TTL management and bridges to **Matter Memory** (Story 7-3):

```
SESSION MEMORY (7-1) → TTL & ARCHIVAL (7-2) 👈 → MATTER MEMORY (7-3) → KEY FINDINGS (7-4) → QUERY CACHE (7-5)
```

Story 7-2 satisfies:
- **FR5**: Context persistence across sessions (restoration from archive)
- **NFR32**: Session timeout handling with archival before expiry
- **Architecture Decision**: 3-Layer Memory System with session-to-matter bridging

### Critical Implementation Details

1. **TTL Extension with Max Lifetime**

   From Story 7-1, sessions already have 7-day TTL with auto-extend on access. Story 7-2 adds a **30-day maximum lifetime** to prevent indefinite session persistence:

   ```python
   # Constants in redis_keys.py
   SESSION_TTL = 7 * 24 * 60 * 60       # 7 days - per-access window
   MAX_SESSION_LIFETIME = 30 * 24 * 60 * 60  # 30 days - absolute maximum

   # In SessionMemoryService.get_session()
   async def get_session(..., extend_ttl: bool = True):
       context = await self._get_from_redis(...)

       if extend_ttl and not context.max_ttl_reached:
           # Check if max lifetime reached
           if self._check_max_lifetime(context):
               context.max_ttl_reached = True
               logger.info("session_max_lifetime_reached", session_id=context.session_id)
           else:
               # Extend TTL normally
               await self._redis.setex(key, SESSION_TTL, context.model_dump_json())
               context.ttl_extended_count += 1
   ```

2. **Session Archival Flow**

   ```
   Session Expiry/End
       ↓
   archive_session()
       ↓ Extract archivable data
   ArchivedSession model
       ↓
   MatterMemoryRepository.save_archived_session()
       ↓ INSERT INTO matter_memory
   PostgreSQL JSONB storage
       ↓
   Redis session deleted
   ```

3. **ArchivedSession Model**

   Add to `backend/app/models/memory.py`:

   ```python
   class ArchivedSession(BaseModel):
       """Archived session for Matter Memory storage.

       Story 7-2: Persists session context after expiry/end.
       Enables context restoration when user returns to matter.
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
           max_length=10,
           description="Last 10 messages for context restoration",
       )

       # Session stats
       total_query_count: int = Field(default=0, ge=0)
       total_messages: int = Field(default=0, ge=0)
       ttl_extended_count: int = Field(default=0, ge=0)

       # Archival metadata
       archival_reason: Literal["expired", "manual_end", "logout"] = Field(
           description="Why session was archived"
       )
   ```

4. **Matter Memory Table Schema**

   Story 7-3 will create the full `matter_memory` table, but for archival we need:

   ```sql
   -- Part of Story 7-3, but referenced here for context
   CREATE TABLE IF NOT EXISTS matter_memory (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       matter_id UUID NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
       user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
       memory_type TEXT NOT NULL,  -- 'archived_session', 'query_history', 'timeline_cache', etc.
       data JSONB NOT NULL,
       created_at TIMESTAMPTZ DEFAULT NOW(),
       updated_at TIMESTAMPTZ DEFAULT NOW(),

       -- Indexes for efficient queries
       CONSTRAINT fk_matter FOREIGN KEY (matter_id) REFERENCES matters(id)
   );

   -- RLS policy
   CREATE POLICY "Users access own matter memory"
   ON matter_memory FOR ALL
   USING (
       matter_id IN (
           SELECT matter_id FROM matter_attorneys
           WHERE user_id = auth.uid()
       )
   );

   -- Index for archived session queries
   CREATE INDEX idx_matter_memory_type_matter
   ON matter_memory(matter_id, memory_type)
   WHERE memory_type = 'archived_session';
   ```

   **NOTE**: If matter_memory table doesn't exist yet, coordinate with Story 7-3 or create a minimal version.

5. **Context Restoration Logic**

   ```python
   async def restore_context(
       self,
       matter_id: str,
       user_id: str,
       restore_messages: bool = True,
       message_limit: int = 5,
   ) -> SessionContext | None:
       """Restore context from most recent archived session.

       Story 7-2: AC #4 - Context restoration from Matter Memory.

       Args:
           matter_id: Matter UUID.
           user_id: User UUID.
           restore_messages: Whether to restore last messages.
           message_limit: How many messages to restore (max 10).

       Returns:
           New SessionContext with restored context, or None if no archive.
       """
       # Get latest archived session
       archive = await self._matter_memory.get_latest_archived_session(
           matter_id, user_id
       )

       if archive is None:
           logger.info("no_archived_session_found", matter_id=matter_id, user_id=user_id)
           return None

       # Create new session
       context = await self.create_session(matter_id, user_id)

       # Restore entities (critical for pronoun resolution)
       context.entities_mentioned = archive.entities_mentioned

       # Optionally restore last messages
       if restore_messages and archive.last_messages:
           restored = archive.last_messages[-message_limit:]
           context.messages = restored

       logger.info(
           "context_restored_from_archive",
           session_id=context.session_id,
           original_session_id=archive.session_id,
           entities_restored=len(context.entities_mentioned),
           messages_restored=len(context.messages),
       )

       # Save updated context
       key = session_key(matter_id, user_id, "context")
       await self._redis.setex(key, SESSION_TTL, context.model_dump_json())

       return context
   ```

6. **Lazy Archival Pattern**

   Since Redis keyspace notifications require additional configuration, use lazy archival:

   ```python
   async def get_session(
       self,
       matter_id: str,
       user_id: str,
       auto_create: bool = True,
       extend_ttl: bool = True,
       restore_from_archive: bool = True,  # NEW parameter
   ) -> SessionContext | None:
       """Retrieve session with lazy archival check."""
       await self._ensure_client()

       key = session_key(matter_id, user_id, "context")
       data = await self._redis.get(key)

       if data is None:
           # Session expired or doesn't exist
           if restore_from_archive:
               # Try to restore from archive
               restored = await self.restore_context(matter_id, user_id)
               if restored:
                   return restored

           if auto_create:
               return await self.create_session(matter_id, user_id)
           return None

       # ... rest of existing logic
   ```

### Existing Code to Extend (DO NOT REINVENT)

| Component | Location | Purpose |
|-----------|----------|---------|
| `SessionContext` | `app/models/memory.py` | Add new fields (Story 7-1 foundation) |
| `SessionMemoryService` | `app/services/memory/session.py` | Add archival/restore methods |
| `SESSION_TTL` | `app/services/memory/redis_keys.py` | Add MAX_SESSION_LIFETIME constant |
| `get_supabase_client` | `app/services/supabase/client.py` | For PostgreSQL access |
| Factory pattern | All services | `get_*()` functions for DI |
| structlog | All modules | Structured logging |

### Previous Story (7-1) Learnings

From Story 7-1 code review:

1. **Error Handling**: Wrap all Redis operations in try/except with structured logging
2. **Type Safety**: Use `Literal` types for constrained values (archival_reason)
3. **Defense-in-Depth**: Use `validate_key_access()` for all key operations
4. **Avoid Redundancy**: Pass `extend_ttl=False` to inner calls when handling TTL externally
5. **Model Constraints**: Use Pydantic `max_length` for lists with size limits
6. **Reset Functions**: Add `reset_*()` functions for testing

### File Structure

Extend memory service structure:

```
backend/app/
├── models/
│   └── memory.py                     # Extend with ArchivedSession
├── services/
│   └── memory/
│       ├── __init__.py               # Update exports
│       ├── redis_keys.py             # Add MAX_SESSION_LIFETIME
│       ├── redis_client.py           # Existing (Story 7-1)
│       ├── session.py                # Extend with archival/restore
│       └── matter.py                 # NEW - MatterMemoryRepository
└── tests/
    └── services/
        └── memory/
            ├── test_session.py       # Add archival/restore tests
            └── test_matter.py        # NEW - Matter memory tests
```

### Testing Requirements

Per project-context.md:
- Backend: `tests/services/memory/` directory
- Use pytest-asyncio for async tests
- Mock Supabase client for PostgreSQL tests
- Include matter isolation test (CRITICAL)

**Minimum Test Cases:**

```python
# test_session.py (additions)

@pytest.mark.asyncio
async def test_ttl_extension_respects_max_lifetime(mock_redis):
    """TTL should stop extending after 30 days."""
    service = SessionMemoryService(mock_redis)

    # Create session and simulate 30 days of extensions
    context = await service.create_session("matter-1", "user-1")

    # Mock created_at to be 30 days ago
    old_created_at = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    context.created_at = old_created_at

    # Attempt to extend TTL
    context = await service.get_session("matter-1", "user-1", extend_ttl=True)

    assert context.max_ttl_reached is True


@pytest.mark.asyncio
async def test_archive_session_stores_to_matter_memory(mock_redis, mock_supabase):
    """Session should be archived to PostgreSQL."""
    service = SessionMemoryService(mock_redis)
    matter_repo = MatterMemoryRepository(mock_supabase)
    service._matter_memory = matter_repo

    # Create session with entities
    await service.create_session("matter-1", "user-1")
    await service.update_entities("matter-1", "user-1", [
        {"id": "e1", "name": "John Smith", "type": "person"},
    ])
    await service.add_message("matter-1", "user-1", "user", "What about John?")

    # Archive session
    archive = await service.archive_session("matter-1", "user-1", reason="manual_end")

    assert archive is not None
    assert archive.entities_mentioned["e1"].entity_name == "John Smith"
    assert len(archive.last_messages) == 1


@pytest.mark.asyncio
async def test_restore_context_from_archive(mock_redis, mock_supabase):
    """Context should be restored from archived session."""
    service = SessionMemoryService(mock_redis)

    # Setup mock archived session
    mock_supabase.table().select().execute.return_value.data = [{
        "data": ArchivedSession(
            session_id="old-session",
            matter_id="matter-1",
            user_id="user-1",
            created_at="2026-01-01T00:00:00Z",
            archived_at="2026-01-08T00:00:00Z",
            last_activity="2026-01-08T00:00:00Z",
            entities_mentioned={
                "e1": {
                    "entity_id": "e1",
                    "entity_name": "John Smith",
                    "entity_type": "person",
                    "aliases": [],
                    "mention_count": 3,
                    "last_mentioned": "2026-01-08T00:00:00Z",
                }
            },
            last_messages=[],
            total_query_count=5,
            total_messages=10,
            ttl_extended_count=2,
            archival_reason="expired",
        ).model_dump()
    }]

    # Restore context
    context = await service.restore_context("matter-1", "user-1")

    assert context is not None
    assert "e1" in context.entities_mentioned
    assert context.entities_mentioned["e1"].entity_name == "John Smith"


@pytest.mark.asyncio
async def test_end_session_archives_before_delete(mock_redis, mock_supabase):
    """End session should archive to Matter Memory before deleting from Redis."""
    service = SessionMemoryService(mock_redis)

    await service.create_session("matter-1", "user-1")

    # End session (should archive)
    deleted = await service.end_session("matter-1", "user-1")

    assert deleted is True
    # Verify archival was called (check mock)
    mock_supabase.table().insert.assert_called_once()


@pytest.mark.asyncio
async def test_get_session_restores_from_archive_on_miss(mock_redis, mock_supabase):
    """When session doesn't exist, should try to restore from archive."""
    service = SessionMemoryService(mock_redis)

    # Session doesn't exist in Redis
    mock_redis.get.return_value = None

    # But archived session exists
    mock_supabase.table().select().execute.return_value.data = [
        {"data": {...}}  # archived session data
    ]

    context = await service.get_session(
        "matter-1", "user-1",
        auto_create=False,
        restore_from_archive=True,
    )

    # Should have restored from archive
    assert context is not None
    assert "restored entities present"


@pytest.mark.asyncio
async def test_archived_session_matter_isolation(mock_supabase):
    """Archived sessions should be isolated by matter."""
    repo = MatterMemoryRepository(mock_supabase)

    # Query for matter-A should only return matter-A archives
    await repo.get_latest_archived_session("matter-A", "user-1")

    # Verify query filters by matter_id
    mock_supabase.table().select().eq.assert_called_with("matter_id", "matter-A")
```

### Git Intelligence

Recent commit pattern:
- `feat(memory): implement session memory Redis storage (Story 7-1)`
- Pattern: `feat(domain): description (Story X-Y)`

Use: `feat(memory): implement session TTL and context restoration (Story 7-2)`

### Performance Considerations

1. **Archival is async**: Don't block session end on archival completion
2. **Restoration is lazy**: Only query PostgreSQL when Redis misses
3. **Message limit**: Only restore last 5-10 messages to keep context small
4. **Entity map**: Full restoration since it's critical for pronoun resolution
5. **Index on matter_memory**: Ensure index exists for fast archived session queries

### Security Considerations

1. **Matter isolation**: Archived sessions use RLS on matter_memory table
2. **User isolation**: Archive belongs to specific user, not shared
3. **No sensitive data**: Messages may contain legal content - ensure proper access controls
4. **Audit logging**: Log all archival/restoration events

### Environment Variables

No new environment variables needed - uses existing:
- `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` (Redis)
- `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` (PostgreSQL)

### Dependencies

This story depends on:
- **Story 7-1**: Session Memory Redis Storage (COMPLETED) - Foundation for session operations
- **Story 7-3**: Matter Memory PostgreSQL JSONB (FUTURE) - Full matter_memory table

If matter_memory table doesn't exist yet:
- Option A: Coordinate with Story 7-3 to implement table first
- Option B: Create minimal table schema as part of this story
- **Recommended**: Create the table in this story since archival is the first use case

### Project Structure Notes

- Models in `models/memory.py` (extend existing)
- Session service extension in `services/memory/session.py`
- New Matter Memory repo in `services/memory/matter.py`
- Tests in `tests/services/memory/`
- Migration in `supabase/migrations/` (if creating table)

### References

- [Project Context](_bmad-output/project-context.md) - Naming conventions, testing rules
- [Architecture: Memory](../_bmad-output/architecture.md#memory-system-coverage) - 3-layer memory system spec
- [Epic 7 Definition](../_bmad-output/project-planning-artifacts/epics.md) - Story requirements
- [Story 7-1](./7-1-session-memory-redis.md) - Foundation implementation and patterns
- [redis_keys.py](backend/app/services/memory/redis_keys.py) - Key utilities (add MAX_SESSION_LIFETIME)
- [session.py](backend/app/services/memory/session.py) - Service to extend

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - all tests pass.

### Completion Notes List

1. **All 8 Tasks Completed Successfully**
   - SessionContext model extended with TTL tracking fields
   - TTL extension with 30-day max lifetime implemented
   - Session archival service created with ArchivedSession model
   - Context restoration from archived sessions working
   - Lazy archival pattern via `restore_from_archive` parameter
   - MatterMemoryRepository created for PostgreSQL storage
   - 71 comprehensive tests passing (49 session + 13 matter + 9 redis keys)
   - Module exports updated

2. **Implementation Highlights**
   - Used lazy archival pattern instead of Redis keyspace notifications (simpler, no config needed)
   - Matter isolation preserved through RLS and matter_id filtering
   - Migration added to extend matter_memory.memory_type constraint

3. **Test Results**
   - All 71 tests pass
   - Tests cover: TTL extension, max lifetime, session archival, context restoration, matter isolation

### File List

**Created:**
- `backend/app/services/memory/matter.py` - MatterMemoryRepository for archived sessions
- `backend/tests/services/memory/test_matter.py` - Matter memory repository tests
- `supabase/migrations/20260114000008_add_archived_session_memory_type.sql` - DB migration

**Modified:**
- `backend/app/models/memory.py` - Added ArchivedSession model, MAX_ARCHIVED_MESSAGES constant, extended SessionContext
- `backend/app/services/memory/session.py` - Added archive_session(), restore_context(), updated get_session() and end_session()
- `backend/app/services/memory/redis_keys.py` - Added MAX_SESSION_LIFETIME constant
- `backend/app/services/memory/__init__.py` - Updated exports
- `backend/tests/services/memory/test_session.py` - Added Story 7-2 tests

