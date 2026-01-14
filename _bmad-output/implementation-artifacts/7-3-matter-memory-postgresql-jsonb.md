# Story 7.3: Implement Matter Memory PostgreSQL JSONB Storage

Status: review

## Story

As an **attorney**,
I want **matter-level data persisted in the database**,
So that **query history, timelines, and entity graphs are available long-term**.

## Acceptance Criteria

1. **Given** a matter exists
   **When** Matter Memory is accessed
   **Then** the matter_memory table stores JSONB at paths like /matter-{id}/query_history.jsonb

2. **Given** query history is logged
   **When** it is stored
   **Then** /matter-{id}/query_history.jsonb contains append-only query records
   **And** each record has query_id, query_text, asked_by, asked_at, response_summary, verified status

3. **Given** timeline is cached
   **When** /matter-{id}/timeline_cache.jsonb is accessed
   **Then** it contains cached_at, events array, last_document_upload for invalidation

4. **Given** entity graph is cached
   **When** /matter-{id}/entity_graph.jsonb is accessed
   **Then** it contains cached_at, entities map, relationships

## Tasks / Subtasks

- [x] Task 1: Create Matter Memory Models (AC: #1-4)
  - [x] 1.1: Create `QueryHistoryEntry` model with query_id, query_text, asked_by, asked_at, response_summary, verified, engines_used, tokens_used, cost_usd
  - [x] 1.2: Create `QueryHistory` model with entries array and matter_id
  - [x] 1.3: Create `TimelineCache` model with cached_at, events, last_document_upload, version
  - [x] 1.4: Create `EntityGraphCache` model with cached_at, entities map, relationships list
  - [x] 1.5: Add models to `backend/app/models/memory.py` (extend existing)

- [x] Task 2: Extend MatterMemoryRepository with Full CRUD (AC: #1-4)
  - [x] 2.1: Add `get_query_history()` method - retrieve query history for matter
  - [x] 2.2: Add `append_query()` method - add query entry (append-only, uses DB function)
  - [x] 2.3: Add `get_timeline_cache()` method - retrieve cached timeline
  - [x] 2.4: Add `set_timeline_cache()` method - upsert timeline cache
  - [x] 2.5: Add `invalidate_timeline_cache()` method - delete cache (called on doc upload)
  - [x] 2.6: Add `get_entity_graph_cache()` method - retrieve cached entity graph
  - [x] 2.7: Add `set_entity_graph_cache()` method - upsert entity graph cache
  - [x] 2.8: Add `invalidate_entity_graph_cache()` method - delete cache (called on doc upload)
  - [x] 2.9: Add generic `get_memory()` and `set_memory()` methods for flexibility

- [x] Task 3: Create MatterMemoryService Facade (AC: #1-4)
  - [x] 3.1: Create `MatterMemoryService` class in `backend/app/services/memory/matter_service.py` (NEW)
  - [x] 3.2: Implement high-level methods that orchestrate repository + business logic
  - [x] 3.3: Implement `log_query()` - convenience method combining audit + query history
  - [x] 3.4: Implement `get_or_build_timeline()` - check cache, build if stale/missing
  - [x] 3.5: Implement `get_or_build_entity_graph()` - check cache, build if stale/missing
  - [x] 3.6: Add `get_matter_memory_service()` factory function

- [x] Task 4: Implement Cache Invalidation Hooks (AC: #3, #4)
  - [x] 4.1: Create `invalidate_matter_caches()` method - clears timeline + entity_graph
  - [x] 4.2: Document integration point for document upload service
  - [x] 4.3: Add cache staleness detection via `last_document_upload` comparison

- [x] Task 5: Write Comprehensive Tests (AC: #1-4)
  - [x] 5.1: Unit tests for new models (QueryHistoryEntry, QueryHistory, TimelineCache, EntityGraphCache)
  - [x] 5.2: Unit tests for MatterMemoryRepository new methods with mock Supabase
  - [x] 5.3: Unit tests for MatterMemoryService facade methods
  - [x] 5.4: Test append-only semantics for query history
  - [x] 5.5: Test cache invalidation on document upload
  - [x] 5.6: Test matter isolation (RLS verification)
  - [x] 5.7: Test cache staleness detection

- [x] Task 6: Update Module Exports (AC: #1-4)
  - [x] 6.1: Export new models from `models/memory.py`
  - [x] 6.2: Export new methods from MatterMemoryRepository
  - [x] 6.3: Export MatterMemoryService from `services/memory/__init__.py`

## Dev Notes

### Architecture Compliance

This story implements **Matter Memory** - the second layer of the **Three-Layer Memory System** (Epic 7):

```
SESSION MEMORY (7-1) → TTL & ARCHIVAL (7-2) → MATTER MEMORY (7-3) 👈 → KEY FINDINGS (7-4) → QUERY CACHE (7-5)
```

Matter Memory satisfies:
- **FR6**: Matter Memory (Layer 2) - PostgreSQL JSONB storage per matter with query_history, timeline_cache, entity_graph
- **NFR31**: Persistent storage survives session logout/restart
- **Architecture Decision**: 3-Layer Memory System with PostgreSQL for durability

### Critical Implementation Details

1. **Matter Memory Data Types**

   The `matter_memory` table already exists (Story 1-7) with these memory_type values:
   - `query_history` - Append-only query audit log (forensic)
   - `timeline_cache` - Pre-built timeline for fast re-queries
   - `entity_graph` - Cached MIG relationships
   - `key_findings` - Attorney-verified facts (Story 7-4)
   - `research_notes` - Attorney annotations (Story 7-4)
   - `archived_session` - Session archives (Story 7-2, already implemented)

   **NOTE**: Story 7-2 added `archived_session` to the constraint. This story uses existing types.

2. **Existing Infrastructure**

   From Story 7-2, `MatterMemoryRepository` exists with:
   - `save_archived_session()` - Save archived sessions
   - `get_latest_archived_session()` - Retrieve latest archive
   - `get_archived_sessions()` - List archives with pagination

   This story EXTENDS the repository with query_history, timeline_cache, entity_graph methods.

3. **Database Functions Already Available**

   From migration `20260106000005_create_matter_memory_table.sql`:
   ```sql
   -- Upsert full memory entry
   public.upsert_matter_memory(p_matter_id uuid, p_memory_type text, p_data jsonb) → uuid

   -- Append to JSONB array (perfect for query_history)
   public.append_to_matter_memory(p_matter_id uuid, p_memory_type text, p_key text, p_item jsonb) → uuid
   ```

   **USE THESE FUNCTIONS** - they have proper access control and SECURITY DEFINER.

4. **Query History Model**

   Add to `backend/app/models/memory.py`:

   ```python
   class QueryHistoryEntry(BaseModel):
       """Single query record in matter query history.

       Story 7-3: Forensic audit trail entry.
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

       Story 7-3: Append-only forensic audit log.
       """

       entries: list[QueryHistoryEntry] = Field(
           default_factory=list,
           description="Query history entries (newest last)",
       )


   class TimelineCacheEntry(BaseModel):
       """Single event in cached timeline.

       Story 7-3: Simplified event for cache.
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


   class EntityRelationship(BaseModel):
       """Relationship between entities in cache.

       Story 7-3: Cached MIG relationship.
       """

       source_id: str = Field(description="Source entity ID")
       target_id: str = Field(description="Target entity ID")
       relationship_type: str = Field(description="Relationship type")
       confidence: float | None = Field(default=None, ge=0, le=1)


   class CachedEntity(BaseModel):
       """Entity in cached entity graph.

       Story 7-3: Simplified entity for cache.
       """

       entity_id: str = Field(description="Entity UUID")
       canonical_name: str = Field(description="Primary entity name")
       entity_type: str = Field(description="Entity type: PERSON, ORG, etc.")
       aliases: list[str] = Field(default_factory=list, description="Known aliases")
       mention_count: int = Field(default=0, ge=0, description="Total mentions")


   class EntityGraphCache(BaseModel):
       """Cached entity graph for matter.

       Story 7-3: Pre-built MIG relationships for instant queries.
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
   ```

5. **MatterMemoryRepository Extensions**

   Extend `backend/app/services/memory/matter.py`:

   ```python
   # Memory type constants
   QUERY_HISTORY_TYPE = "query_history"
   TIMELINE_CACHE_TYPE = "timeline_cache"
   ENTITY_GRAPH_TYPE = "entity_graph"


   class MatterMemoryRepository:
       # ... existing code ...

       async def get_query_history(
           self,
           matter_id: str,
           limit: int = 100,
       ) -> QueryHistory:
           """Get query history for a matter.

           Story 7-3: AC #2 - Retrieve append-only query records.

           Args:
               matter_id: Matter UUID.
               limit: Maximum entries to return (newest first).

           Returns:
               QueryHistory with entries.
           """
           self._ensure_client()

           try:
               result = (
                   self._supabase.table("matter_memory")
                   .select("data")
                   .eq("matter_id", matter_id)
                   .eq("memory_type", QUERY_HISTORY_TYPE)
                   .single()
                   .execute()
               )
           except Exception as e:
               # No history yet is not an error
               if "No rows" in str(e) or "PGRST116" in str(e):
                   return QueryHistory(entries=[])
               raise

           data = result.data.get("data", {}) if result.data else {}
           entries = data.get("entries", [])

           # Return most recent entries up to limit
           return QueryHistory(entries=entries[-limit:])


       async def append_query(
           self,
           matter_id: str,
           entry: QueryHistoryEntry,
       ) -> str:
           """Append a query entry to history (append-only).

           Story 7-3: AC #2 - Uses DB function for atomic append.

           Args:
               matter_id: Matter UUID.
               entry: Query entry to append.

           Returns:
               Record UUID.
           """
           self._ensure_client()

           try:
               # Use append_to_matter_memory DB function
               result = self._supabase.rpc(
                   "append_to_matter_memory",
                   {
                       "p_matter_id": matter_id,
                       "p_memory_type": QUERY_HISTORY_TYPE,
                       "p_key": "entries",
                       "p_item": entry.model_dump(mode="json"),
                   }
               ).execute()
           except Exception as e:
               logger.error(
                   "append_query_failed",
                   matter_id=matter_id,
                   query_id=entry.query_id,
                   error=str(e),
               )
               raise RuntimeError(f"Failed to append query: {e}") from e

           logger.info(
               "query_appended",
               matter_id=matter_id,
               query_id=entry.query_id,
           )

           return result.data


       async def get_timeline_cache(
           self,
           matter_id: str,
       ) -> TimelineCache | None:
           """Get cached timeline for a matter.

           Story 7-3: AC #3 - Retrieve pre-built timeline.

           Args:
               matter_id: Matter UUID.

           Returns:
               TimelineCache if exists, None otherwise.
           """
           self._ensure_client()

           try:
               result = (
                   self._supabase.table("matter_memory")
                   .select("data")
                   .eq("matter_id", matter_id)
                   .eq("memory_type", TIMELINE_CACHE_TYPE)
                   .single()
                   .execute()
               )
           except Exception as e:
               if "No rows" in str(e) or "PGRST116" in str(e):
                   return None
               raise

           data = result.data.get("data", {}) if result.data else {}

           try:
               return TimelineCache.model_validate(data)
           except ValidationError as e:
               logger.warning(
                   "timeline_cache_validation_failed",
                   matter_id=matter_id,
                   error=str(e),
               )
               return None


       async def set_timeline_cache(
           self,
           matter_id: str,
           cache: TimelineCache,
       ) -> str:
           """Set/update timeline cache for a matter.

           Story 7-3: AC #3 - Store pre-built timeline.

           Args:
               matter_id: Matter UUID.
               cache: Timeline cache to store.

           Returns:
               Record UUID.
           """
           self._ensure_client()

           try:
               result = self._supabase.rpc(
                   "upsert_matter_memory",
                   {
                       "p_matter_id": matter_id,
                       "p_memory_type": TIMELINE_CACHE_TYPE,
                       "p_data": cache.model_dump(mode="json"),
                   }
               ).execute()
           except Exception as e:
               logger.error(
                   "set_timeline_cache_failed",
                   matter_id=matter_id,
                   error=str(e),
               )
               raise RuntimeError(f"Failed to set timeline cache: {e}") from e

           logger.info(
               "timeline_cache_set",
               matter_id=matter_id,
               event_count=cache.event_count,
           )

           return result.data


       async def invalidate_timeline_cache(
           self,
           matter_id: str,
       ) -> bool:
           """Invalidate (delete) timeline cache.

           Story 7-3: Called when new documents uploaded.

           Args:
               matter_id: Matter UUID.

           Returns:
               True if deleted, False if not found.
           """
           self._ensure_client()

           try:
               result = (
                   self._supabase.table("matter_memory")
                   .delete()
                   .eq("matter_id", matter_id)
                   .eq("memory_type", TIMELINE_CACHE_TYPE)
                   .execute()
               )
           except Exception as e:
               logger.error(
                   "invalidate_timeline_cache_failed",
                   matter_id=matter_id,
                   error=str(e),
               )
               raise RuntimeError(f"Failed to invalidate timeline cache: {e}") from e

           deleted = len(result.data) > 0 if result.data else False

           logger.info(
               "timeline_cache_invalidated",
               matter_id=matter_id,
               deleted=deleted,
           )

           return deleted


       # Similar methods for entity_graph_cache...
       # get_entity_graph_cache(), set_entity_graph_cache(), invalidate_entity_graph_cache()
   ```

6. **Cache Staleness Detection**

   ```python
   def is_cache_stale(
       cache_timestamp: str | None,
       last_doc_upload: str | None,
   ) -> bool:
       """Check if cache is stale (doc uploaded after cache created).

       Args:
           cache_timestamp: When cache was created (ISO8601).
           last_doc_upload: When last document was uploaded (ISO8601).

       Returns:
           True if cache is stale (should rebuild), False otherwise.
       """
       if not cache_timestamp:
           return True  # No cache = stale

       if not last_doc_upload:
           return False  # No docs uploaded = not stale

       # Compare timestamps
       from datetime import datetime

       cache_time = datetime.fromisoformat(cache_timestamp.replace("Z", "+00:00"))
       upload_time = datetime.fromisoformat(last_doc_upload.replace("Z", "+00:00"))

       return upload_time > cache_time
   ```

### Existing Code to Reuse (DO NOT REINVENT)

| Component | Location | Purpose |
|-----------|----------|---------|
| `MatterMemoryRepository` | `app/services/memory/matter.py` | Extend with new methods |
| `matter_memory` table | DB migration `20260106000005` | Already has RLS, indexes, functions |
| `upsert_matter_memory()` | DB function | Use for cache upserts |
| `append_to_matter_memory()` | DB function | Use for query history appends |
| `get_supabase_client` | `app/services/supabase/client.py` | DB client |
| Factory pattern | All services | `get_*()` functions |
| structlog | All modules | Structured logging |
| `QueryAuditLogger` | `app/engines/orchestrator/audit.py` | Story 6-3 audit (integration point) |
| `QueryHistoryStore` | `app/engines/orchestrator/query_history.py` | Story 6-3 query history (similar) |

### Previous Story (7-2) Learnings

From Story 7-2 code review:

1. **Error Handling**: Wrap all Supabase operations in try/except with structured logging
2. **Defense-in-Depth**: Use JSONB field filters in addition to RLS
3. **Validation**: Use Pydantic `model_validate()` with fallback to None on ValidationError
4. **Database Functions**: Use existing `upsert_matter_memory()` and `append_to_matter_memory()`
5. **Reset Functions**: Add `reset_*()` functions for testing
6. **Async Interface**: Mark methods async even if Supabase client is sync (future-proofing)

### File Structure

Extend memory service structure:

```
backend/app/
├── models/
│   └── memory.py                     # Extend with new models
├── services/
│   └── memory/
│       ├── __init__.py               # Update exports
│       ├── matter.py                 # Extend MatterMemoryRepository
│       └── matter_service.py         # NEW - MatterMemoryService facade
└── tests/
    ├── models/
    │   └── test_memory_models.py     # Add new model tests
    └── services/
        └── memory/
            ├── test_matter.py        # Add repository tests
            └── test_matter_service.py # NEW - Service tests
```

### Testing Requirements

Per project-context.md:
- Backend: `tests/services/memory/` directory
- Use pytest-asyncio for async tests
- Mock Supabase client for unit tests
- Include matter isolation test (CRITICAL)

**Minimum Test Cases:**

```python
# test_memory_models.py (additions)

def test_query_history_entry_creation():
    """QueryHistoryEntry should have required fields."""
    entry = QueryHistoryEntry(
        query_id="query-123",
        query_text="What is the timeline?",
        asked_by="user-456",
        asked_at="2026-01-14T10:00:00Z",
    )
    assert entry.query_id == "query-123"
    assert entry.verified is False  # Default


def test_timeline_cache_events():
    """TimelineCache should store events."""
    cache = TimelineCache(
        cached_at="2026-01-14T10:00:00Z",
        events=[
            TimelineCacheEntry(
                event_id="evt-1",
                event_date="2025-01-01",
                event_type="filing",
                description="Initial filing",
                entities=["entity-1"],
            )
        ],
        event_count=1,
    )
    assert len(cache.events) == 1
    assert cache.event_count == 1


def test_entity_graph_cache_structure():
    """EntityGraphCache should have entities and relationships."""
    cache = EntityGraphCache(
        cached_at="2026-01-14T10:00:00Z",
        entities={
            "e1": CachedEntity(
                entity_id="e1",
                canonical_name="John Smith",
                entity_type="PERSON",
            )
        },
        relationships=[
            EntityRelationship(
                source_id="e1",
                target_id="e2",
                relationship_type="RELATED_TO",
            )
        ],
        entity_count=1,
        relationship_count=1,
    )
    assert "e1" in cache.entities
    assert len(cache.relationships) == 1


# test_matter.py (additions)

@pytest.mark.asyncio
async def test_append_query_history(mock_supabase):
    """Should append query to history via DB function."""
    repo = MatterMemoryRepository(mock_supabase)

    entry = QueryHistoryEntry(
        query_id="query-123",
        query_text="What is the timeline?",
        asked_by="user-456",
        asked_at="2026-01-14T10:00:00Z",
    )

    mock_supabase.rpc.return_value.execute.return_value.data = "record-id"

    result = await repo.append_query("matter-1", entry)

    # Verify DB function was called correctly
    mock_supabase.rpc.assert_called_once_with(
        "append_to_matter_memory",
        {
            "p_matter_id": "matter-1",
            "p_memory_type": "query_history",
            "p_key": "entries",
            "p_item": entry.model_dump(mode="json"),
        }
    )


@pytest.mark.asyncio
async def test_get_timeline_cache(mock_supabase):
    """Should retrieve timeline cache."""
    repo = MatterMemoryRepository(mock_supabase)

    mock_supabase.table().select().eq().eq().single().execute.return_value.data = {
        "data": {
            "cached_at": "2026-01-14T10:00:00Z",
            "events": [],
            "event_count": 0,
        }
    }

    cache = await repo.get_timeline_cache("matter-1")

    assert cache is not None
    assert cache.event_count == 0


@pytest.mark.asyncio
async def test_timeline_cache_invalidation(mock_supabase):
    """Should delete timeline cache on invalidation."""
    repo = MatterMemoryRepository(mock_supabase)

    mock_supabase.table().delete().eq().eq().execute.return_value.data = [{"id": "x"}]

    deleted = await repo.invalidate_timeline_cache("matter-1")

    assert deleted is True


@pytest.mark.asyncio
async def test_cache_staleness_detection():
    """Cache should be stale if doc uploaded after cache created."""
    from app.services.memory.matter import is_cache_stale

    # Cache created at 10:00, doc uploaded at 11:00 = stale
    assert is_cache_stale(
        cache_timestamp="2026-01-14T10:00:00Z",
        last_doc_upload="2026-01-14T11:00:00Z",
    ) is True

    # Cache created at 11:00, doc uploaded at 10:00 = not stale
    assert is_cache_stale(
        cache_timestamp="2026-01-14T11:00:00Z",
        last_doc_upload="2026-01-14T10:00:00Z",
    ) is False

    # No doc upload = not stale
    assert is_cache_stale(
        cache_timestamp="2026-01-14T10:00:00Z",
        last_doc_upload=None,
    ) is False


@pytest.mark.asyncio
async def test_matter_isolation_query_history(mock_supabase):
    """Query history should be isolated by matter."""
    repo = MatterMemoryRepository(mock_supabase)

    # Get history for matter-A
    await repo.get_query_history("matter-A")

    # Verify matter_id filter was applied
    mock_supabase.table().select().eq.assert_any_call("matter_id", "matter-A")
```

### Git Intelligence

Recent commit pattern:
- `feat(memory): implement session TTL and context restoration (Story 7-2)`
- Pattern: `feat(domain): description (Story X-Y)`

Use: `feat(memory): implement matter memory PostgreSQL JSONB storage (Story 7-3)`

### Performance Considerations

1. **Database Functions**: Use `append_to_matter_memory()` for atomic appends (no read-modify-write)
2. **JSONB Indexes**: GIN index already exists on `data` column for fast queries
3. **Cache Invalidation**: Delete is fast with unique constraint index
4. **Staleness Check**: Compare timestamps in Python, not SQL (simpler)
5. **Pagination**: Query history limit parameter prevents large result sets

### Security Considerations

1. **Matter Isolation**: RLS on `matter_memory` table (Layer 1 of 4-layer isolation)
2. **Access Control**: DB functions use `SECURITY DEFINER` with role checks
3. **Append-Only Query History**: DB function prevents arbitrary updates (forensic integrity)
4. **No Sensitive Data**: Timeline/entity caches are derived from documents (no new PII)

### Environment Variables

No new environment variables needed - uses existing:
- `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` (PostgreSQL)

### Integration Points

1. **Document Upload Service**: Call `invalidate_timeline_cache()` and `invalidate_entity_graph_cache()` after successful upload
2. **Timeline Engine (Epic 4)**: Use `get_timeline_cache()` / `set_timeline_cache()` for caching
3. **Entity Service (Epic 2C)**: Use `get_entity_graph_cache()` / `set_entity_graph_cache()` for MIG caching
4. **Query Orchestrator (Epic 6)**: Use `append_query()` for history (complementary to Story 6-3 audit)

### Dependencies

This story depends on:
- **Story 7-1**: Session Memory Redis Storage (COMPLETED)
- **Story 7-2**: Session TTL and Context Restoration (COMPLETED) - Created `MatterMemoryRepository`
- **Story 1-7**: PostgreSQL RLS Policies (COMPLETED) - Created `matter_memory` table

### Project Structure Notes

- Extend existing `models/memory.py` with new cache models
- Extend existing `services/memory/matter.py` with repository methods
- Create new `services/memory/matter_service.py` for high-level facade
- Tests in `tests/services/memory/` and `tests/models/`
- No new migrations needed - table and functions already exist

### References

- [Project Context](_bmad-output/project-context.md) - Naming conventions, testing rules
- [Architecture: Memory](../_bmad-output/architecture.md#memory-system-coverage) - 3-layer memory system spec
- [Epic 7 Definition](../_bmad-output/project-planning-artifacts/epics.md) - Story requirements
- [Story 7-2](./7-2-ttl-sliding-window-pronoun-resolution.md) - MatterMemoryRepository foundation
- [Migration 20260106000005](supabase/migrations/20260106000005_create_matter_memory_table.sql) - Table schema + DB functions
- [MVP Spec: Matter Memory](../_bmad-output/project-planning-artifacts/MVP-Scope-Definition-v1.0.md#layer-2-matter-memory-postgresql-jsonb) - Full specification

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
