# Story 7.5: Implement Query Cache

Status: review

## Story

As an **attorney**,
I want **repeated queries to return instantly**,
So that **I don't wait for expensive LLM calls on identical questions**.

## Acceptance Criteria

1. **Given** I ask a query
   **When** the query is processed
   **Then** results are cached at cache:query:{matter_id}:{query_hash}
   **And** query_hash is SHA256 of normalized query text

2. **Given** I ask the same query again
   **When** cache is checked
   **Then** cached results are returned in ~10ms
   **And** no LLM calls are made

3. **Given** cache entry is 1 hour old
   **When** TTL expires
   **Then** the entry is automatically deleted
   **And** next query runs fresh

4. **Given** I upload a new document
   **When** upload completes
   **Then** all cache entries for the matter are invalidated (pattern: cache:query:{matterId}:*)
   **And** queries run fresh with new document content

## Tasks / Subtasks

- [x] Task 1: Create Query Cache Models (AC: #1, #2)
  - [x] 1.1: Create `CachedQueryResult` model with query_hash, matter_id, original_query, normalized_query, cached_at, expires_at, result_summary, engine_used, findings_count, confidence
  - [x] 1.2: Create `QueryNormalizer` utility class with `normalize()` and `hash()` methods
  - [x] 1.3: Add models to `backend/app/models/memory.py` (extend existing)

- [x] Task 2: Create QueryCacheRepository for Redis CRUD (AC: #1-3)
  - [x] 2.1: Create `backend/app/services/memory/query_cache.py`
  - [x] 2.2: Implement `get_cached_result()` method - retrieve by query hash
  - [x] 2.3: Implement `set_cached_result()` method - store with 1-hour TTL
  - [x] 2.4: Implement `delete_cached_result()` method - remove single entry
  - [x] 2.5: Implement `invalidate_matter_cache()` method - delete all cache:query:{matter_id}:* keys

- [x] Task 3: Implement Query Normalization (AC: #1)
  - [x] 3.1: Implement case normalization (lowercase)
  - [x] 3.2: Implement whitespace normalization (collapse multiple spaces, trim)
  - [x] 3.3: Implement punctuation stripping (remove non-essential punctuation)
  - [x] 3.4: Implement SHA256 hashing of normalized query
  - [x] 3.5: Add hash validation per `redis_keys.py` pattern (32-64 hex chars)

- [x] Task 4: Create QueryCacheService with High-Level Methods (AC: #1-4)
  - [x] 4.1: Create `backend/app/services/memory/query_cache_service.py`
  - [x] 4.2: Implement `check_cache()` - returns cached result or None
  - [x] 4.3: Implement `cache_result()` - normalize, hash, and store result
  - [x] 4.4: Implement `invalidate_on_document_upload()` - hook for upload pipeline
  - [x] 4.5: Implement `get_cache_stats()` - for monitoring (hit rate, size)

- [x] Task 5: Write Comprehensive Tests (AC: #1-4)
  - [x] 5.1: Unit tests for QueryNormalizer (various input formats)
  - [x] 5.2: Unit tests for QueryCacheRepository methods (mock Redis)
  - [x] 5.3: Unit tests for QueryCacheService high-level methods
  - [x] 5.4: Test cache hit scenario (same query returns cached)
  - [x] 5.5: Test cache miss scenario (new query not cached)
  - [x] 5.6: Test TTL expiry (1-hour expiration)
  - [x] 5.7: Test matter isolation (CRITICAL - cache:query:matter_A:* isolated from matter_B)
  - [x] 5.8: Test bulk invalidation (all matter cache cleared on upload)

- [x] Task 6: Update Module Exports (AC: #1-4)
  - [x] 6.1: Export new models from `models/memory.py`
  - [x] 6.2: Export QueryCacheRepository from `services/memory/query_cache.py`
  - [x] 6.3: Export QueryCacheService from `services/memory/query_cache_service.py`
  - [x] 6.4: Update `services/memory/__init__.py` with all new exports

## Dev Notes

### Architecture Compliance

This story implements **Query Cache (Layer 3)** - completing the **Three-Layer Memory System** (Epic 7):

```
SESSION MEMORY (7-1) -> TTL & ARCHIVAL (7-2) -> MATTER MEMORY (7-3) -> KEY FINDINGS (7-4) -> QUERY CACHE (7-5) <--
```

Query Cache satisfies:
- **FR7**: Query Cache (Layer 3) - Redis cache with key format `cache:query:{matter_id}:{query_hash}`
- **NFR1**: <10s query response - cached queries return in ~10ms
- **NFR32**: Performance optimization - avoid redundant LLM calls
- **Architecture Decision**: 1-hour TTL with invalidation on document upload

### Critical Implementation Details

1. **Redis Key Infrastructure Already Exists**

   From `backend/app/services/memory/redis_keys.py`:
   ```python
   # Key function already implemented
   def cache_key(matter_id: str, query_hash: str) -> str:
       """Generate a query cache Redis key with matter isolation.

       Returns: cache:query:{matter_id}:{query_hash}
       """
       _validate_uuid(matter_id, "matter_id")
       # query_hash validated as 32-64 char hex string
       if not re.match(r"^[a-f0-9]{32,64}$", query_hash, re.IGNORECASE):
           raise ValueError("query_hash must be a valid hex hash (32-64 characters)")
       return f"cache:query:{matter_id}:{query_hash}"

   # Pattern function for bulk invalidation
   def cache_pattern(matter_id: str) -> str:
       """Generate Redis SCAN pattern for cache keys.

       Returns: cache:query:{matter_id}:*
       """
       return f"cache:query:{matter_id}:*"

   # TTL constant already defined
   CACHE_TTL = 60 * 60  # 1 hour in seconds
   ```

2. **Redis Client Singleton Available**

   From `backend/app/services/memory/redis_client.py`:
   ```python
   async def get_redis_client() -> Any:
       """Get or create async Redis client.
       Returns Upstash Redis for production or redis-py for local.
       """

   # Usage pattern:
   redis = await get_redis_client()
   await redis.setex(key, ttl_seconds, value)
   await redis.get(key)
   await redis.delete(key)
   ```

3. **Follow Session Memory Service Pattern**

   From `backend/app/services/memory/session.py`:
   ```python
   class SessionMemoryService:
       def __init__(self, redis_client: Any = None) -> None:
           self._redis = redis_client  # Inject for testing

       async def _ensure_client(self) -> None:
           if self._redis is None:
               self._redis = await get_redis_client()

   # Factory pattern:
   _session_memory_service: SessionMemoryService | None = None

   def get_session_memory_service(redis_client: Any = None) -> SessionMemoryService:
       global _session_memory_service
       if _session_memory_service is None:
           _session_memory_service = SessionMemoryService(redis_client)
       return _session_memory_service
   ```

4. **Query Normalization Pattern**

   Reference from `backend/app/services/rag/embedder.py`:
   ```python
   import hashlib

   def _hash_text(self, text: str) -> str:
       """Generate SHA256 hash of text for cache key."""
       return hashlib.sha256(text.encode("utf-8")).hexdigest()
       # Returns: 64-character lowercase hex string
   ```

   For query normalization, implement:
   ```python
   import hashlib
   import re

   class QueryNormalizer:
       """Normalize queries for consistent cache key generation.

       Story 7-5: AC #1 - query_hash is SHA256 of normalized query text.
       """

       def normalize(self, query: str) -> str:
           """Normalize query for consistent hashing.

           Steps:
           1. Lowercase
           2. Collapse whitespace
           3. Strip leading/trailing whitespace
           4. Remove non-essential punctuation
           """
           normalized = query.lower()
           normalized = re.sub(r'\s+', ' ', normalized)  # Collapse whitespace
           normalized = normalized.strip()
           # Keep alphanumeric, basic punctuation for semantic meaning
           normalized = re.sub(r'[^\w\s\?\.\,\'\"\-]', '', normalized)
           return normalized

       def hash(self, query: str) -> str:
           """Generate SHA256 hash of normalized query."""
           normalized = self.normalize(query)
           return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
   ```

5. **Cached Result Data Model**

   Add to `backend/app/models/memory.py`:
   ```python
   class CachedQueryResult(BaseModel):
       """Cached query result stored in Redis.

       Story 7-5: AC #1 - Results cached at cache:query:{matter_id}:{query_hash}
       """

       query_hash: str = Field(description="SHA256 hash of normalized query")
       matter_id: str = Field(description="Matter UUID for isolation")
       original_query: str = Field(description="Original user query")
       normalized_query: str = Field(description="Normalized query used for hashing")

       # Timing
       cached_at: str = Field(description="ISO8601 cache timestamp")
       expires_at: str = Field(description="ISO8601 expiration timestamp")

       # Response data
       result_summary: str = Field(description="Summary of query result")
       engine_used: str | None = Field(default=None, description="Engine that processed query")
       findings_count: int = Field(default=0, description="Number of findings in result")
       confidence: float = Field(default=0.0, ge=0, le=100, description="Overall confidence")

       # Full response payload
       response_data: dict[str, Any] = Field(
           default_factory=dict,
           description="Complete response payload for cache hit"
       )

       # Metadata
       cache_version: int = Field(default=1, description="Cache schema version")
   ```

6. **Bulk Invalidation Pattern**

   For document upload invalidation (AC #4):
   ```python
   async def invalidate_matter_cache(self, matter_id: str) -> int:
       """Delete all cache entries for a matter.

       Story 7-5: AC #4 - Invalidate on document upload.
       Uses SCAN to find and delete all matching keys.

       Returns:
           Number of keys deleted.
       """
       await self._ensure_client()

       pattern = cache_pattern(matter_id)  # "cache:query:{matter_id}:*"
       deleted_count = 0

       # Use SCAN for safe iteration (doesn't block like KEYS)
       cursor = 0
       while True:
           cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
           if keys:
               await self._redis.delete(*keys)
               deleted_count += len(keys)
           if cursor == 0:
               break

       logger.info(
           "matter_cache_invalidated",
           matter_id=matter_id,
           keys_deleted=deleted_count,
       )

       return deleted_count
   ```

### Existing Code to Reuse (DO NOT REINVENT)

| Component | Location | Purpose |
|-----------|----------|---------|
| `cache_key()` | `app/services/memory/redis_keys.py` | Generate cache key |
| `cache_pattern()` | `app/services/memory/redis_keys.py` | Generate SCAN pattern |
| `CACHE_TTL` | `app/services/memory/redis_keys.py` | 1-hour TTL constant |
| `get_redis_client()` | `app/services/memory/redis_client.py` | Async Redis client |
| `validate_key_access()` | `app/services/memory/redis_keys.py` | Defense-in-depth validation |
| `SessionMemoryService` | `app/services/memory/session.py` | Pattern for Redis service |
| Hash pattern | `app/services/rag/embedder.py` | SHA256 hashing |
| structlog | All modules | Structured logging |

### Previous Story (7-4) Learnings

From Story 7-4 implementation and code review:

1. **Error Handling**: Wrap all Redis operations in try/except with structured logging
2. **Defense-in-Depth**: Validate keys with `validate_key_access()` before operations
3. **Async Interface**: All Redis operations must be awaited
4. **Singleton Pattern**: Use factory function with optional injection
5. **Constants**: Extract magic strings as module-level constants

### File Structure

Create new query cache service:

```
backend/app/
├── models/
│   └── memory.py                     # Add CachedQueryResult model
├── services/
│   └── memory/
│       ├── __init__.py               # Update exports
│       ├── query_cache.py            # NEW: QueryCacheRepository
│       ├── query_cache_service.py    # NEW: QueryCacheService
│       └── query_normalizer.py       # NEW: QueryNormalizer utility
└── tests/
    └── services/
        └── memory/
            ├── test_query_cache.py           # NEW: Repository tests
            ├── test_query_cache_service.py   # NEW: Service tests
            └── test_query_normalizer.py      # NEW: Normalizer tests
```

### Testing Requirements

Per project-context.md:
- Backend: `tests/services/memory/` directory
- Use pytest-asyncio for async tests
- Mock Redis client for unit tests
- **Include matter isolation test (CRITICAL)**

**Minimum Test Cases:**

```python
# test_query_normalizer.py

def test_normalize_lowercase():
    """Should convert to lowercase."""
    normalizer = QueryNormalizer()
    assert normalizer.normalize("What is SARFAESI?") == "what is sarfaesi?"


def test_normalize_whitespace():
    """Should collapse multiple whitespace."""
    normalizer = QueryNormalizer()
    assert normalizer.normalize("what   is    sarfaesi?") == "what is sarfaesi?"


def test_hash_consistency():
    """Same query should produce same hash."""
    normalizer = QueryNormalizer()
    hash1 = normalizer.hash("What is SARFAESI?")
    hash2 = normalizer.hash("what is sarfaesi?")  # Different case
    assert hash1 == hash2  # Should be same after normalization


def test_hash_is_sha256():
    """Hash should be 64-char hex string."""
    normalizer = QueryNormalizer()
    hash_val = normalizer.hash("test query")
    assert len(hash_val) == 64
    assert all(c in "0123456789abcdef" for c in hash_val)


# test_query_cache.py

@pytest.mark.asyncio
async def test_cache_set_and_get(mock_redis):
    """Should store and retrieve cached results."""
    repo = QueryCacheRepository(mock_redis)

    result = CachedQueryResult(
        query_hash="abc123...",
        matter_id="matter-1",
        original_query="What is SARFAESI?",
        normalized_query="what is sarfaesi?",
        cached_at="2026-01-14T10:00:00Z",
        expires_at="2026-01-14T11:00:00Z",
        result_summary="SARFAESI is...",
        response_data={"answer": "..."},
    )

    await repo.set_cached_result(result)

    mock_redis.setex.assert_called_once()
    call_args = mock_redis.setex.call_args
    assert call_args[0][1] == 3600  # CACHE_TTL


@pytest.mark.asyncio
async def test_matter_isolation(mock_redis):
    """Cache should be isolated by matter."""
    repo = QueryCacheRepository(mock_redis)

    # Set up mock to track keys
    stored_keys = []
    async def track_set(key, ttl, value):
        stored_keys.append(key)
    mock_redis.setex.side_effect = track_set

    await repo.set_cached_result(result_matter_a)
    await repo.set_cached_result(result_matter_b)

    # Keys should include different matter IDs
    assert "cache:query:matter-A:" in stored_keys[0]
    assert "cache:query:matter-B:" in stored_keys[1]


@pytest.mark.asyncio
async def test_bulk_invalidation(mock_redis):
    """Should delete all cache entries for a matter."""
    repo = QueryCacheRepository(mock_redis)

    # Mock SCAN returning keys
    mock_redis.scan.return_value = (0, [
        "cache:query:matter-1:hash1",
        "cache:query:matter-1:hash2",
    ])
    mock_redis.delete.return_value = 2

    count = await repo.invalidate_matter_cache("matter-1")

    assert count == 2
    mock_redis.scan.assert_called_with(0, match="cache:query:matter-1:*", count=100)
```

### Git Intelligence

Recent commit patterns:
- `feat(memory): implement Story 7-4 Key Findings and Research Notes`
- `fix(review): code review fixes for Story 7-4`

Use: `feat(memory): implement query cache Redis storage (Story 7-5)`

### Performance Considerations

1. **Cache Hit Performance**: Target ~10ms for cached results (vs 3-5 seconds fresh)
2. **SCAN vs KEYS**: Use SCAN for bulk invalidation (non-blocking)
3. **TTL Management**: Redis handles expiry automatically, no manual cleanup needed
4. **Serialization**: Use Pydantic `model_dump_json()` for efficient serialization

### Security Considerations

1. **Matter Isolation**: `cache_key()` enforces matter_id in key (Layer 3 of 4-layer isolation)
2. **Input Validation**: `cache_key()` validates UUID format and hash format
3. **Defense-in-Depth**: Use `validate_key_access()` before returning cached data
4. **No Sensitive Data**: Cache stores query results, not raw documents

### Environment Variables

No new environment variables needed - uses existing:
- `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` (production)
- `REDIS_URL` (local development, default: `redis://localhost:6379/0`)

### Integration Points

1. **Query Orchestrator (Epic 6)**: Check cache before engine execution, cache results after
2. **Document Upload (Epic 2A)**: Call `invalidate_matter_cache()` on upload completion
3. **Session Memory (Epic 7-1/7-2)**: Shares Redis client and key infrastructure
4. **Audit Trail (Story 6-3)**: Log cache hits/misses for observability

### Dependencies

This story depends on:
- **Story 7-1**: Session Memory Redis Storage (COMPLETED) - Created Redis client singleton
- **Story 7-2**: Session TTL and Context Restoration (COMPLETED) - Established TTL patterns
- **Story 6-1**: Query Intent Analysis (COMPLETED) - Query classification for cache key

### Project Structure Notes

- Create new `query_cache.py` repository file
- Create new `query_cache_service.py` service file
- Create new `query_normalizer.py` utility file
- Extend `models/memory.py` with CachedQueryResult
- Tests in `tests/services/memory/`
- **No migrations needed** - pure Redis implementation

### References

- [Project Context](_bmad-output/project-context.md) - Naming conventions, testing rules
- [Architecture: Memory](_bmad-output/architecture.md#memory-system-coverage) - 3-layer memory system spec
- [Epic 7 Definition](_bmad-output/project-planning-artifacts/epics.md) - Story requirements
- [Story 7-1](./7-1-session-memory-redis.md) - Redis client pattern (CRITICAL - follow same patterns)
- [Redis Keys Module](backend/app/services/memory/redis_keys.py) - Key generation and validation
- [FR7 Requirement](_bmad-output/project-planning-artifacts/epics.md) - Query Cache specification

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 78 new tests pass (32 normalizer + 27 repository + 19 service)
- Full memory test suite: 241 tests pass
- No regressions detected

### Completion Notes List

1. **Task 1 Complete**: Created `CachedQueryResult` model in `memory.py` with all required fields (query_hash, matter_id, original_query, normalized_query, cached_at, expires_at, result_summary, engine_used, findings_count, confidence, response_data, cache_version)

2. **Task 2 Complete**: Created `QueryCacheRepository` in `query_cache.py` with:
   - `get_cached_result()` - retrieve by matter_id + query_hash
   - `set_cached_result()` - store with 1-hour TTL (CACHE_TTL)
   - `delete_cached_result()` - remove single entry
   - `invalidate_matter_cache()` - bulk delete using SCAN pattern
   - `get_cache_stats()` - monitoring support

3. **Task 3 Complete**: Created `QueryNormalizer` in `query_normalizer.py` with:
   - `normalize()` - lowercase, collapse whitespace, trim, strip special chars
   - `hash()` - SHA256 of normalized query (64-char hex)
   - `normalize_and_hash()` - convenience method returning both

4. **Task 4 Complete**: Created `QueryCacheService` in `query_cache_service.py` with:
   - `check_cache()` - normalize query and check cache
   - `cache_result()` - normalize, hash, and store with timestamps
   - `invalidate_on_document_upload()` - bulk invalidation hook
   - `get_cache_stats()` - monitoring interface
   - `delete_cached_query()` - targeted deletion

5. **Task 5 Complete**: 78 comprehensive tests across 3 test files:
   - `test_query_normalizer.py` - 32 tests for normalization and hashing
   - `test_query_cache.py` - 27 tests for repository operations
   - `test_query_cache_service.py` - 19 tests for service layer
   - Matter isolation tests included (CRITICAL)
   - TTL expiry tests included
   - Bulk invalidation tests included

6. **Task 6 Complete**: Updated `services/memory/__init__.py` with all exports:
   - CachedQueryResult model
   - QueryNormalizer, get_query_normalizer, reset_query_normalizer
   - QueryCacheRepository, get_query_cache_repository, reset_query_cache_repository
   - QueryCacheService, get_query_cache_service, reset_query_cache_service

### File List

**New Files:**
- backend/app/services/memory/query_normalizer.py
- backend/app/services/memory/query_cache.py
- backend/app/services/memory/query_cache_service.py
- backend/tests/services/memory/test_query_normalizer.py
- backend/tests/services/memory/test_query_cache.py
- backend/tests/services/memory/test_query_cache_service.py

**Modified Files:**
- backend/app/models/memory.py (added CachedQueryResult model)
- backend/app/services/memory/__init__.py (added exports)

### Change Log

- 2026-01-14: Story 7-5 implementation complete - Query Cache for LLM response caching

