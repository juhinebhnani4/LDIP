# LDIP Architecture Audit - Remediation Todos

**Generated**: 2026-01-17
**Audit By**: Winston (Architect Agent)
**Severity Legend**: 🔴 HIGH | 🟡 MEDIUM | 🟠 LOW

---

## Priority 1: Security - Celery Worker Matter Isolation 🔴

### 1.1 Add matter_id validation to all Celery tasks

**Problem**: Worker tasks receive only `document_id` and don't validate matter ownership. Service role bypasses RLS, creating a security hole.

**Files to modify**:
- `backend/app/workers/tasks/document_tasks.py`
- `backend/app/workers/tasks/` (any other task files)

**Acceptance Criteria**:
- [ ] All Celery tasks that operate on matter-scoped data accept `matter_id` as required parameter
- [ ] Tasks validate document belongs to specified matter BEFORE processing
- [ ] Tasks fail fast with clear error if validation fails
- [ ] Validation uses single query (not two separate queries)
- [ ] Audit log entry created for validation failures

**Edge Cases to Handle**:
- [ ] Document deleted between task enqueue and execution → graceful failure with specific error code
- [ ] Matter deleted but document orphaned → validation must catch this
- [ ] Race condition: document moved to different matter during processing → validation at start AND before final write
- [ ] Null/empty matter_id passed → reject with 400-level error, not 500
- [ ] Invalid UUID format for matter_id → reject before DB query
- [ ] Task retry: validation must pass on every retry, not just first attempt

**Implementation Pattern**:
```python
@celery_app.task(bind=True, max_retries=3)
def process_document(self, matter_id: str, document_id: str):
    # 1. Validate UUID formats first (no DB hit)
    if not is_valid_uuid(matter_id) or not is_valid_uuid(document_id):
        raise ValueError(f"Invalid UUID format: matter_id={matter_id}, document_id={document_id}")

    # 2. Single query validates ownership AND fetches document
    doc = db.table('documents').select('*')\
        .eq('id', document_id)\
        .eq('matter_id', matter_id)\
        .single()\
        .execute()

    if not doc.data:
        logger.warning("document_matter_validation_failed",
                      document_id=document_id,
                      matter_id=matter_id)
        raise DocumentNotFoundError(f"Document {document_id} not found in matter {matter_id}")

    # 3. Proceed with processing...
```

**Testing Requirements**:
- [ ] Unit test: valid matter_id + document_id → processes successfully
- [ ] Unit test: valid matter_id + wrong document_id → fails with DocumentNotFoundError
- [ ] Unit test: invalid UUID format → fails before DB query
- [ ] Unit test: document exists but different matter → fails validation
- [ ] Integration test: enqueue task with mismatched IDs → task fails, job marked failed
- [ ] Security test: attempt to access document from other tenant's matter → blocked

---

### 1.2 Audit all task enqueue sites

**Problem**: When tasks are enqueued, they must include matter_id. Need to find all `.delay()` and `.apply_async()` calls.

**Files to audit**:
- `backend/app/api/routes/documents.py` (likely primary)
- `backend/app/api/routes/matters.py`
- `backend/app/services/` (any service that enqueues tasks)

**Acceptance Criteria**:
- [ ] All task enqueue calls include matter_id as first positional argument
- [ ] Matter_id is sourced from validated context (not user input directly)
- [ ] No task enqueue uses only document_id

**Edge Cases**:
- [ ] Batch operations: each document in batch must have matter_id validated
- [ ] Re-processing existing document: matter_id must be fetched from DB, not assumed
- [ ] Webhook-triggered processing: validate matter_id from webhook payload against DB

---

## Priority 2: API Contract Standardization 🔴

### 2.1 Audit current API response patterns

**Problem**: Mix of snake_case and camelCase responses with transformers scattered across frontend.

**Files to audit**:
- [ ] `backend/app/api/routes/*.py` - check each route's `response_model_by_alias` setting
- [ ] `backend/app/models/*.py` - check Field alias definitions
- [ ] `frontend/src/lib/api/*.ts` - inventory all transformer functions
- [ ] `frontend/src/types/*.ts` - check type definitions match backend

**Acceptance Criteria**:
- [ ] Document every endpoint and its current response format
- [ ] Identify which transformers exist and which are missing
- [ ] Create migration plan with zero-downtime approach

---

### 2.2 Standardize backend response format

**Decision Required**: Choose ONE approach:
- **Option A (Recommended)**: All routes use `response_model_by_alias=True` → camelCase responses
- **Option B**: All routes return snake_case → frontend handles transformation

**If Option A chosen**:

**Files to modify**:
- `backend/app/api/routes/documents.py`
- `backend/app/api/routes/entities.py`
- `backend/app/api/routes/search.py`
- `backend/app/api/routes/timeline.py`
- `backend/app/api/routes/chat.py`
- (any other route files)

**Acceptance Criteria**:
- [ ] All Pydantic models have camelCase aliases for all fields
- [ ] All routes use `response_model_by_alias=True`
- [ ] No route returns raw dict (must use Pydantic model)
- [ ] OpenAPI schema shows camelCase field names

**Edge Cases**:
- [ ] Nested models: aliases must be defined at every level
- [ ] List responses: items in list must also use aliases
- [ ] Error responses: must also follow camelCase convention
- [ ] Streaming responses (chat): each chunk must use consistent format
- [ ] Pagination metadata: `total_count` vs `totalCount` must be consistent
- [ ] File upload responses: any metadata must follow convention
- [ ] Webhook payloads sent TO external services: may need different format (document separately)

**Testing Requirements**:
- [ ] Contract test for each endpoint verifying camelCase response
- [ ] Snapshot tests for response shapes
- [ ] Frontend integration test: fetch data, verify no transformation needed

---

### 2.3 Remove frontend transformers

**Files to modify**:
- `frontend/src/lib/api/client.ts` - remove `toSnakeCaseManualEvent` and similar
- `frontend/src/lib/api/documents.ts` - remove document transformers
- `frontend/src/lib/api/entities.ts` - remove entity transformers
- `frontend/src/lib/api/search.ts` - remove search transformers
- `frontend/src/lib/api/timeline.ts` - remove timeline transformers

**Acceptance Criteria**:
- [ ] No transformer functions remain in frontend API layer
- [ ] Types directly match API response shape
- [ ] No `as unknown as` type casts for API responses

**Edge Cases**:
- [ ] Backward compatibility: if any external clients use old format, need deprecation period
- [ ] Cached data: localStorage/sessionStorage may have old format → add migration on app load
- [ ] In-flight requests during deployment: may receive mixed formats → frontend should handle both temporarily

---

### 2.4 Generate TypeScript types from OpenAPI

**New tooling to add**:
- [ ] Install `openapi-typescript` or similar generator
- [ ] Add npm script: `npm run generate:types`
- [ ] Configure to output to `frontend/src/types/generated/api.ts`
- [ ] Add pre-commit hook or CI check that types are up-to-date

**Acceptance Criteria**:
- [ ] TypeScript types auto-generated from backend OpenAPI schema
- [ ] No manual type definitions for API responses
- [ ] CI fails if generated types differ from committed types
- [ ] Developer workflow documented in README

**Edge Cases**:
- [ ] Circular references in OpenAPI schema → generator must handle
- [ ] Union types → generator must produce correct TypeScript unions
- [ ] Nullable fields → generator must produce `field: Type | null` not `field?: Type`
- [ ] Date/DateTime fields → generator must use `string` (ISO format) not `Date`

---

## Priority 3: Error Handling Standardization 🔴

### 3.1 Define unified error response schema

**Create new file**: `backend/app/models/errors.py`

**Schema**:
```python
class ErrorDetail(BaseModel):
    code: str  # Machine-readable: "DOCUMENT_NOT_FOUND", "VALIDATION_ERROR"
    message: str  # Human-readable: "Document not found"
    field: Optional[str] = None  # For validation errors
    details: Optional[dict] = None  # Additional context

class ErrorResponse(BaseModel):
    error: ErrorDetail
```

**Acceptance Criteria**:
- [ ] All error responses follow this schema
- [ ] Error codes are documented in enum
- [ ] Error codes are stable (never rename, only add new)

---

### 3.2 Implement global exception handler

**File to modify**: `backend/app/main.py`

**Acceptance Criteria**:
- [ ] `@app.exception_handler(Exception)` catches all unhandled exceptions
- [ ] Returns 500 with structured error response
- [ ] Logs full traceback to Axiom
- [ ] Does NOT expose internal details to client
- [ ] Correlation ID included in error response

**Edge Cases**:
- [ ] Pydantic ValidationError → return 422 with field-level errors
- [ ] HTTPException → pass through with structured format
- [ ] asyncio.CancelledError → handle gracefully (request cancelled)
- [ ] Database connection error → return 503 Service Unavailable
- [ ] Redis connection error → degrade gracefully if possible
- [ ] Out of memory → let process crash (K8s/Railway will restart)

**Handler Priority** (order matters):
1. HTTPException → structured 4xx/5xx response
2. RequestValidationError → structured 422 response
3. Custom service exceptions → map to appropriate HTTP status
4. Exception → generic 500 response

---

### 3.3 Standardize service layer exceptions

**Files to modify**:
- `backend/app/services/matter_service.py` (has pattern to copy)
- `backend/app/services/document_service.py`
- `backend/app/services/timeline_service.py`
- `backend/app/services/entity_service.py`
- (all other services)

**Create**: `backend/app/services/exceptions.py`

```python
class ServiceError(Exception):
    """Base class for service-layer exceptions."""
    code: str = "SERVICE_ERROR"
    status_code: int = 500

    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)

class NotFoundError(ServiceError):
    code = "NOT_FOUND"
    status_code = 404

class ValidationError(ServiceError):
    code = "VALIDATION_ERROR"
    status_code = 400

class AuthorizationError(ServiceError):
    code = "FORBIDDEN"
    status_code = 403

class ConflictError(ServiceError):
    code = "CONFLICT"
    status_code = 409

class ExternalServiceError(ServiceError):
    code = "EXTERNAL_SERVICE_ERROR"
    status_code = 502
```

**Acceptance Criteria**:
- [ ] All services use exceptions from `exceptions.py`
- [ ] No service raises raw `Exception`
- [ ] No service raises `HTTPException` (that's for routes only)
- [ ] Each service has typed exceptions (e.g., `DocumentNotFoundError(NotFoundError)`)

**Edge Cases**:
- [ ] Multiple validation errors → aggregate into single exception with list of issues
- [ ] Partial failure (batch operation) → use `PartialSuccessError` with success/failure lists
- [ ] Retryable vs non-retryable errors → add `is_retryable` property

---

### 3.4 Frontend error handling consolidation

**Files to modify**:
- `frontend/src/lib/api/client.ts` - enhance `ApiError` class
- `frontend/src/stores/` - add error state to Zustand stores
- `frontend/src/components/` - use consistent error display

**Create**: `frontend/src/lib/errors.ts`

**Acceptance Criteria**:
- [ ] Single `handleApiError()` function used everywhere
- [ ] Error state in Zustand stores (not component-local state)
- [ ] Toast notifications use consistent styling
- [ ] Error codes mapped to user-friendly messages
- [ ] Retry logic centralized (not in each component)

**Edge Cases**:
- [ ] Network offline → show "No internet connection" not API error
- [ ] 401 Unauthorized → redirect to login, clear session
- [ ] 403 Forbidden → show "Access denied" with context
- [ ] 429 Rate Limited → show retry countdown
- [ ] 500+ Server Error → show generic message, log to Axiom
- [ ] Request timeout → show "Request timed out, please try again"
- [ ] Response parse error (invalid JSON) → handle gracefully

---

## Priority 4: Memory Layer Coordination 🟡

### 4.1 Document memory layer ownership

**Create**: `docs/architecture/memory-layers.md`

**Content**:
- Which operations write to which cache
- TTL for each layer
- When to invalidate each layer
- Consistency guarantees (eventual vs strong)

**Tables**:

| Operation | Session Cache | Matter Cache | Query Cache |
|-----------|--------------|--------------|-------------|
| Chat message | Write | - | - |
| Document upload | - | Write | Invalidate |
| Timeline extraction | - | Write | Invalidate |
| Entity extraction | - | Write | Invalidate |
| Verification update | - | Write | Invalidate |

---

### 4.2 Implement CacheInvalidationService

**Create**: `backend/app/services/cache/invalidation_service.py`

**Acceptance Criteria**:
- [ ] Single service coordinates all cache invalidation
- [ ] Called after any data mutation
- [ ] Supports selective invalidation (by matter, by document, by entity)
- [ ] Logs all invalidation events for debugging

**Methods**:
```python
class CacheInvalidationService:
    async def invalidate_matter(self, matter_id: str) -> None:
        """Invalidate all caches for a matter."""

    async def invalidate_document(self, matter_id: str, document_id: str) -> None:
        """Invalidate caches affected by document change."""

    async def invalidate_timeline(self, matter_id: str) -> None:
        """Invalidate timeline-related caches."""

    async def invalidate_entities(self, matter_id: str) -> None:
        """Invalidate entity-related caches."""
```

**Edge Cases**:
- [ ] Redis unavailable → log error, don't fail the main operation
- [ ] Partial invalidation failure → retry with exponential backoff
- [ ] Cascade invalidation (document change affects timeline) → handle dependency order
- [ ] Concurrent invalidation requests → idempotent operations

---

### 4.3 Add cache TTL to matter_memory

**Migration required**: Add `expires_at` column to `matter_memory` table

**Acceptance Criteria**:
- [ ] All matter_memory entries have expiration timestamp
- [ ] Background job cleans up expired entries
- [ ] Queries filter out expired entries
- [ ] TTL configurable per memory_type

**Edge Cases**:
- [ ] Clock skew between app servers → use DB server time, not app time
- [ ] Entry updated after creation → extend TTL
- [ ] Query for expired entry → return null, trigger background refresh

---

### 4.4 Implement or remove query cache

**Decision Required**: Is query cache needed for MVP?

**If YES (implement)**:
- Create `backend/app/services/cache/query_cache.py`
- Cache expensive RAG queries
- TTL: 1 hour default
- Key: hash of query + matter_id + filters
- Invalidate on document/entity changes

**If NO (remove from architecture)**:
- Update architecture documentation
- Remove any references to query cache
- Document why it was removed (simplicity for MVP)

---

## Priority 5: Configuration Management 🟡

### 5.1 Add config health check endpoint

**File to modify**: `backend/app/api/routes/health.py` (create if needed)

**Endpoint**: `GET /api/health/config`

**Response**:
```json
{
  "supabase_url_hash": "abc123...",
  "api_version": "1.0.0",
  "feature_flags": {
    "timeline_engine": true,
    "contradiction_engine": true
  },
  "environment": "production"
}
```

**Acceptance Criteria**:
- [ ] Returns hash of critical config values (not the values themselves)
- [ ] Frontend can verify it's talking to correct backend
- [ ] Includes API version for compatibility checking
- [ ] Includes feature flags for UI feature toggling

**Edge Cases**:
- [ ] Config file missing → return 503 with clear error
- [ ] Partial config → return warning in response
- [ ] Sensitive values → NEVER include in response

---

### 5.2 Frontend startup config verification

**File to modify**: `frontend/src/app/layout.tsx` or provider

**Acceptance Criteria**:
- [ ] On app load, fetch `/api/health/config`
- [ ] Verify Supabase URL matches expected
- [ ] If mismatch, show error banner (don't break app)
- [ ] Log config verification result

**Edge Cases**:
- [ ] API unreachable → show "Connecting..." state, retry
- [ ] Config mismatch → show warning but allow usage (graceful degradation)
- [ ] Slow API → don't block app render

---

### 5.3 Centralize worker configuration

**Files to modify**:
- `backend/app/workers/celery.py`
- `backend/app/core/config.py`

**Acceptance Criteria**:
- [ ] Workers load config from same source as API
- [ ] No manual `.env` file loading in workers
- [ ] Google Cloud credentials handled consistently

**Options**:
- **A**: Workers read from Supabase `app_config` table on startup
- **B**: Workers use same environment variables as API (Railway handles this)
- **C**: Shared config file mounted in both containers

**Edge Cases**:
- [ ] Worker starts before config available → retry with backoff
- [ ] Config changes during worker lifetime → support hot reload or require restart
- [ ] Different workers need different config → support worker-type-specific overrides

---

## Priority 6: Security Hardening 🟡

### 6.1 Add MIME type validation to file upload

**File to modify**: `backend/app/api/routes/documents.py`

**Acceptance Criteria**:
- [ ] Validate file MIME type matches extension
- [ ] Whitelist allowed types: PDF, DOCX, TXT
- [ ] Reject with 415 Unsupported Media Type if invalid
- [ ] Log rejected uploads for security audit

**Edge Cases**:
- [ ] MIME type spoofed in header but file is actually different → check magic bytes
- [ ] Zero-byte file → reject
- [ ] Extremely large file → reject before full upload (streaming validation)
- [ ] Encrypted PDF → detect and warn user
- [ ] Corrupted file → attempt to open, reject if fails

**Implementation**:
```python
import magic

ALLOWED_MIME_TYPES = {
    'application/pdf': ['.pdf'],
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    'text/plain': ['.txt'],
}

def validate_file_type(file: UploadFile) -> None:
    # Check magic bytes, not just Content-Type header
    mime = magic.from_buffer(file.file.read(2048), mime=True)
    file.file.seek(0)  # Reset file pointer

    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(415, f"Unsupported file type: {mime}")
```

---

### 6.2 Implement service token rotation

**New process to document**:
- Google Cloud credentials rotation schedule
- Supabase service role key rotation (if possible)
- How to rotate without downtime

**Acceptance Criteria**:
- [ ] Document rotation procedure in `docs/runbooks/`
- [ ] Add monitoring alert for credential age
- [ ] Test rotation procedure in staging

---

### 6.3 Expand security test coverage

**Files to create/modify**:
- `backend/tests/security/test_matter_isolation.py` - expand coverage
- `backend/tests/security/test_file_upload.py` - new
- `backend/tests/security/test_auth_flows.py` - new

**Test Cases to Add**:
- [ ] Cross-tenant document access attempt → blocked
- [ ] Cross-tenant entity access attempt → blocked
- [ ] Cross-tenant timeline access attempt → blocked
- [ ] Invalid JWT → 401 response
- [ ] Expired JWT → 401 response
- [ ] Missing JWT → 401 response
- [ ] Rate limit exceeded → 429 response
- [ ] Malicious file upload → rejected
- [ ] SQL injection attempt → escaped/blocked
- [ ] XSS in user input → sanitized

---

## Priority 7: Technical Debt Cleanup 🟠

### 7.1 Address TODOs in memory services

**Files**:
- `backend/app/services/memory/matter.py`
- `backend/app/services/memory/matter_service.py`
- `backend/app/services/tab_stats_service.py`

**Action**: Either implement the optimization or remove the TODO with justification

---

### 7.2 Document migration strategy

**Create**: `supabase/migrations/README.md`

**Content**:
- How to create new migration
- Naming convention
- How to test migrations locally
- How to rollback (if possible)
- RLS policy verification checklist

---

### 7.3 Run linters with strict rules

**Commands**:
```bash
# Backend
ruff check --fix backend/
mypy backend/app/ --strict

# Frontend
npm run lint -- --max-warnings 0
npx tsc --noEmit
```

**Acceptance Criteria**:
- [ ] Zero linting errors
- [ ] Zero type errors
- [ ] No unused imports
- [ ] No unused variables

---

## Verification Checklist

After completing all items, verify:

- [ ] All Celery tasks validate matter_id
- [ ] All API responses use consistent format (camelCase)
- [ ] All errors return structured response
- [ ] All caches have clear ownership and TTL
- [ ] Config health endpoint works
- [ ] Security tests pass
- [ ] No linting errors
- [ ] Documentation updated

---

## Notes

- Each item should be implemented as a separate PR for easy review
- Write tests BEFORE implementing fixes where possible
- Update architecture documentation after each significant change
- Announce breaking API changes in team channel before deploying
