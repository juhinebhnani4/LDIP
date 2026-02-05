# Tech-Spec: Epic 8 - Chaos Resilience

**Created:** 2026-01-28
**Status:** Ready for Development
**Epic:** 8 - Chaos Resilience (Phase 7, Week 13-14)
**Gaps Addressed:** #34, #35, #36, #37, #38, #40, #43, #44, #45, #46

---

## Overview

### Problem Statement

LDIP's document processing pipeline lacks resilience against infrastructure failures. Current failure modes include:

1. **Jobs lost on Redis crash** - No persistence before acknowledgment
2. **Batch failures cascade** - One bad document fails entire batch
3. **Worker OOM crashes** - No memory limits, uncontrolled resource usage
4. **Session data loss** - Redis-only sessions with no backup
5. **Retry cost spirals** - No cost controls on retry loops
6. **Priority starvation** - Shared workers across all queues

These gaps were identified through Chaos Monkey testing, Pre-mortem Analysis, and Failure Mode Analysis during elicitation.

### Solution

Implement 10 resilience features across 4 categories:

| Category | Stories | Impact |
|----------|---------|--------|
| **Job Safety** | 8.1, 8.2, 8.3 | Jobs survive crashes, transactions atomic |
| **Resource Control** | 8.4, 8.9 | Memory limits, cost caps |
| **Fallback Systems** | 8.5, 8.7, 8.8 | Session backup, rate limit fallback, search degradation |
| **Operational** | 8.6, 8.10 | Orphan cleanup, priority workers |

### Scope

**In Scope:**
- Per-document pipeline isolation (FR7.1)
- Atomic transaction rollback (FR7.2)
- Job persistence before ack (FR7.3)
- Worker memory limits (FR7.4)
- Session persistence fallback (FR7.5)
- Orphan chunk cleanup enhancement (FR7.6)
- Rate limit fallback mode (FR7.7)
- Search degradation verification (FR7.8)
- Retry cost controls (FR7.9)
- Priority queue worker allocation (FR7.10)

**Out of Scope:**
- Multi-region failover
- Kubernetes auto-scaling
- New queue infrastructure (using existing Redis)
- Frontend resilience features

---

## Context for Development

### Codebase Patterns

**Celery Task Pattern:**
```python
@celery_app.task(
    bind=True,
    autoretry_for=(OCRServiceError, EmbeddingServiceError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=3,
)
def process_document(self, document_id: str) -> dict:
    ...
```

**Job Tracking Pattern:**
```python
# Create job record
job = await tracker.create_job(matter_id, document_id, JobType.DOCUMENT_PROCESSING)

# Update progress
await tracker.update_stage(job.id, "chunking", StageStatus.IN_PROGRESS)
await tracker.update_progress(job.id, progress_pct=50)
```

**Redis Key Pattern:**
```python
# From redis_keys.py - all keys include matter_id
SESSION_KEY = "session:{matter_id}:{user_id}:{key_type}"
CACHE_KEY = "cache:query:{matter_id}:{query_hash}"
```

**Error Handling Pattern:**
```python
try:
    result = await process_stage(...)
except MaxRetriesExceededError:
    await doc_service.update_status(doc_id, DocumentStatus.FAILED)
    raise
```

### Files to Reference

| File | Purpose | Relevance |
|------|---------|-----------|
| `backend/app/workers/celery.py` | Celery config, signals, beat schedule | Memory limits, queue config |
| `backend/app/workers/tasks/document_tasks.py` | Main pipeline tasks | Per-doc isolation |
| `backend/app/services/job_tracking/tracker.py` | Job CRUD operations | Job persistence |
| `backend/app/services/job_recovery.py` | Stale job recovery | Recovery from DB |
| `backend/app/services/memory/redis_client.py` | Redis operations | Session fallback |
| `backend/app/services/memory/redis_keys.py` | Key patterns | Rate limit keys |
| `backend/app/services/rag/hybrid_search.py` | Search with fallbacks | Verify BM25 fallback |
| `backend/app/models/job.py` | Job/Stage models | Schema reference |
| `backend/app/core/config.py` | Settings | New config values |

### Technical Decisions (ADRs from Elicitation)

**ADR-008: Job Persistence Strategy**
- **Decision:** Write job to DB before Redis ack
- **Rationale:** Minimal latency (~5ms), uses existing PostgreSQL, simple recovery

**ADR-009: Session Fallback Strategy**
- **Decision:** Redis primary with async DB backup every 30s
- **Rationale:** Maintains performance, DB backup written async

**ADR-010: Pipeline Isolation Strategy**
- **Decision:** Per-document try/catch with continue-on-error
- **Rationale:** Minimal overhead, batch continues, failed docs logged separately

---

## Implementation Plan

### Story 8.1: Per-Document Pipeline Isolation (FR7.1)

**Task 8.1.1:** Add try/catch wrapper in batch processing
- File: `backend/app/workers/tasks/document_tasks.py`
- Wrap each document in `_process_single_document()` with exception handling
- Log failures individually, continue batch
- Return partial results with success/failure counts

**Task 8.1.2:** Create `BatchProcessingResult` model
- File: `backend/app/models/job.py`
- Fields: `total`, `succeeded`, `failed`, `failed_document_ids`, `errors`

**Task 8.1.3:** Update batch endpoints to return partial results
- File: `backend/app/api/routes/documents.py`
- Return 207 Multi-Status when partial success

**Acceptance Criteria:**
- [ ] Given a batch of 10 documents where doc #5 has a corrupt PDF
- [ ] When the batch processes
- [ ] Then docs 1-4 and 6-10 complete successfully
- [ ] And doc #5 is marked FAILED with error details
- [ ] And the API returns `{"succeeded": 9, "failed": 1, "failed_ids": ["doc5"]}`

---

### Story 8.2: Atomic Transaction Rollback (FR7.2)

**Task 8.2.1:** Create `TransactionManager` service
- File: `backend/app/services/transaction_manager.py`
- Wraps multi-table operations in PostgreSQL transactions
- Tracks operations for rollback

**Task 8.2.2:** Implement cleanup service for failed transactions
- File: `backend/app/services/cleanup_service.py`
- `cleanup_partial_processing(document_id)` - removes orphaned data
- Called on task failure after max retries

**Task 8.2.3:** Add transaction wrapper to entity extraction
- File: `backend/app/workers/tasks/document_tasks.py`
- Entity + mentions + aliases in single transaction
- Rollback all on failure

**Acceptance Criteria:**
- [ ] Given entity extraction creates 5 entities and fails on entity #6
- [ ] When the transaction rolls back
- [ ] Then all 6 entities are removed (not just #6)
- [ ] And no orphaned mentions exist in the database
- [ ] And the document status reflects the failure

---

### Story 8.3: Job Persistence Before Acknowledgment (FR7.3)

**Task 8.3.1:** Modify task dispatch to write DB first
- File: `backend/app/workers/tasks/document_tasks.py`
- Before `task.delay()`, insert into `processing_jobs`
- Store `celery_task_id` after dispatch

**Task 8.3.2:** Add recovery query for orphaned jobs
- File: `backend/app/services/job_recovery.py`
- `recover_from_db()` - find jobs in DB not in Redis
- Re-dispatch to Celery

**Task 8.3.3:** Add startup recovery hook
- File: `backend/app/workers/celery.py`
- On worker ready signal, call `recover_from_db()`

**Acceptance Criteria:**
- [ ] Given a job is dispatched and Redis crashes before worker picks it up
- [ ] When Redis restarts and worker connects
- [ ] Then the job is recovered from PostgreSQL
- [ ] And re-dispatched to Celery queue
- [ ] And processing completes successfully

---

### Story 8.4: Worker Memory Limits (FR7.4)

**Task 8.4.1:** Configure Celery memory limits
- File: `backend/app/workers/celery.py`
- Add `worker_max_memory_per_child = 512 * 1024` (512MB)
- Workers restart after processing task if over limit

**Task 8.4.2:** Add memory monitoring to task execution
- File: `backend/app/workers/tasks/document_tasks.py`
- Log memory usage at task start/end
- Alert if task uses >400MB (80% threshold)

**Task 8.4.3:** Update deployment config
- File: `backend/Procfile` or deployment config
- Add `--max-memory-per-child=524288` to Celery command

**Acceptance Criteria:**
- [ ] Given a worker processes a 200MB PDF
- [ ] When memory exceeds 512MB
- [ ] Then the worker completes current task
- [ ] And restarts with fresh memory
- [ ] And no OOM crash occurs

---

### Story 8.5: Session Persistence Fallback (FR7.5)

**Task 8.5.1:** Create `session_backups` table
- Migration: `backend/supabase/migrations/YYYYMMDD_session_backups.sql`
- Columns: `session_key`, `user_id`, `matter_id`, `data` (JSONB), `updated_at`

**Task 8.5.2:** Add async DB backup to session writes
- File: `backend/app/services/memory/session_service.py`
- After Redis write, queue async DB backup
- Batch writes every 30 seconds

**Task 8.5.3:** Implement fallback read from DB
- File: `backend/app/services/memory/redis_client.py`
- On Redis connection error, read from `session_backups`
- Log fallback usage for monitoring

**Acceptance Criteria:**
- [ ] Given a user has an active session in Redis
- [ ] When Redis becomes unavailable
- [ ] Then session data is retrieved from PostgreSQL backup
- [ ] And the user continues working without re-login
- [ ] And a warning is logged about Redis fallback

---

### Story 8.6: Orphan Chunk Cleanup (FR7.6)

**Task 8.6.1:** Enhance orphan detection query
- File: `backend/app/workers/tasks/maintenance_tasks.py`
- Find chunks where `document_id` references deleted/non-existent document
- Find chunks older than 24h with no parent chunk

**Task 8.6.2:** Add cleanup metrics
- Log: chunks_cleaned, embeddings_removed, storage_freed
- Add to admin dashboard metrics

**Task 8.6.3:** Schedule cleanup job
- File: `backend/app/workers/celery.py`
- Run `cleanup_orphan_chunks` every 1 hour (already exists, verify coverage)

**Acceptance Criteria:**
- [ ] Given a worker crashed during chunking leaving 50 orphan chunks
- [ ] When the hourly cleanup job runs
- [ ] Then all 50 orphan chunks are deleted
- [ ] And associated embeddings are removed
- [ ] And cleanup metrics are logged

---

### Story 8.7: Rate Limit Fallback Mode (FR7.7)

**Task 8.7.1:** Create in-memory rate limiter
- File: `backend/app/services/rate_limiter.py`
- Sliding window counter using `collections.deque`
- Thread-safe with `threading.Lock`

**Task 8.7.2:** Add fallback logic to rate limit checks
- File: `backend/app/middleware/rate_limit.py`
- Try Redis first, fall back to in-memory on connection error
- Log fallback activation

**Task 8.7.3:** Add rate limit status to health check
- File: `backend/app/api/routes/health.py`
- Report: `rate_limiter: "redis"` or `rate_limiter: "memory_fallback"`

**Acceptance Criteria:**
- [ ] Given Redis rate limiting is unavailable
- [ ] When API requests arrive
- [ ] Then in-memory rate limiting activates
- [ ] And rate limits are still enforced (may be per-worker not global)
- [ ] And health check shows `rate_limiter: "memory_fallback"`

---

### Story 8.8: Graceful Search Degradation (FR7.8)

**Task 8.8.1:** Audit all search paths for fallback coverage
- File: `backend/app/services/rag/hybrid_search.py`
- Verify: `search()`, `search_with_rerank()`, `search_with_library()`
- Ensure all paths have BM25 fallback

**Task 8.8.2:** Add search mode to response
- Return `search_mode: "hybrid" | "bm25_fallback" | "partial"`
- Frontend can display degraded mode indicator

**Task 8.8.3:** Add fallback metrics
- Track: fallback_count, fallback_reasons, fallback_duration
- Alert if fallback rate > 10%

**Acceptance Criteria:**
- [ ] Given OpenAI embedding API is unavailable
- [ ] When a user performs a search
- [ ] Then BM25-only results are returned
- [ ] And response includes `search_mode: "bm25_fallback"`
- [ ] And user sees "Limited search mode" indicator (frontend)

---

### Story 8.9: Retry Cost Controls (FR7.9)

**Task 8.9.1:** Add cost tracking to job metadata
- File: `backend/app/services/job_tracking/tracker.py`
- Track: `retry_cost_usd`, `total_llm_calls`, `total_tokens`
- Update on each LLM call

**Task 8.9.2:** Implement cost circuit breaker
- File: `backend/app/workers/tasks/document_tasks.py`
- Before retry, check `retry_cost_usd < MAX_RETRY_COST` (default $0.50)
- If exceeded, fail permanently with `COST_LIMIT_EXCEEDED`

**Task 8.9.3:** Add cost limit configuration
- File: `backend/app/core/config.py`
- `job_max_retry_cost_usd: float = 0.50`
- `job_cost_alert_threshold_usd: float = 0.30` (alert at 60%)

**Acceptance Criteria:**
- [ ] Given a document fails and retries 3 times costing $0.15 each
- [ ] When total retry cost reaches $0.45
- [ ] Then an alert is logged at 60% threshold ($0.30)
- [ ] And at $0.50, retries halt with `COST_LIMIT_EXCEEDED`
- [ ] And the job is marked as permanently failed

---

### Story 8.10: Priority Queue Worker Allocation (FR7.10)

**Task 8.10.1:** Configure dedicated workers per queue
- File: `backend/app/workers/celery.py`
- Define worker pools: `high_priority`, `default`, `low_priority`

**Task 8.10.2:** Update deployment configuration
- File: `backend/Procfile` or `docker-compose.yml`
- Launch separate worker processes:
  - `celery -A app.workers.celery worker -Q high -c 2`
  - `celery -A app.workers.celery worker -Q default -c 4`
  - `celery -A app.workers.celery worker -Q low -c 2`

**Task 8.10.3:** Add queue routing for task types
- File: `backend/app/workers/celery.py`
- Route urgent tasks (user-initiated) to `high`
- Route batch jobs to `low`
- Route standard processing to `default`

**Acceptance Criteria:**
- [ ] Given 100 batch jobs in `low` queue
- [ ] When a user uploads an urgent document to `high` queue
- [ ] Then the urgent document processes immediately
- [ ] And is not blocked behind batch jobs
- [ ] And dedicated high-priority workers handle it

---

## Additional Context

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| celery | existing | Worker orchestration |
| redis | existing | Queue broker |
| psycopg2 | existing | PostgreSQL transactions |
| structlog | existing | Logging |

No new dependencies required.

### Testing Strategy

**Unit Tests:**
- `test_batch_processing_isolation.py` - Verify per-doc isolation
- `test_transaction_rollback.py` - Verify atomic rollback
- `test_job_persistence.py` - Verify DB persistence before ack
- `test_memory_limits.py` - Verify worker restart on OOM
- `test_session_fallback.py` - Verify DB fallback
- `test_rate_limit_fallback.py` - Verify in-memory fallback
- `test_retry_cost_controls.py` - Verify cost limits

**Integration Tests:**
- Kill Redis mid-job, verify recovery
- Simulate OOM, verify worker restart
- Block OpenAI, verify BM25 fallback

**Chaos Tests (Manual):**
- Use `chaos-monkey.sh` script to randomly kill workers
- Monitor recovery metrics

### Database Migrations

```sql
-- Migration: YYYYMMDD_session_backups.sql
CREATE TABLE session_backups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_key TEXT NOT NULL,
    user_id UUID NOT NULL,
    matter_id UUID NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(session_key)
);

CREATE INDEX idx_session_backups_user ON session_backups(user_id);
CREATE INDEX idx_session_backups_matter ON session_backups(matter_id);

-- RLS Policy
ALTER TABLE session_backups ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users access own sessions" ON session_backups
    FOR ALL USING (user_id = auth.uid());
```

### Configuration Changes

```python
# Add to backend/app/core/config.py

# Story 8.4: Memory limits
worker_max_memory_mb: int = 512

# Story 8.5: Session backup
session_backup_interval_seconds: int = 30
session_backup_enabled: bool = True

# Story 8.9: Cost controls
job_max_retry_cost_usd: float = 0.50
job_cost_alert_threshold_pct: float = 0.60

# Story 8.10: Worker allocation
worker_high_priority_count: int = 2
worker_default_count: int = 4
worker_low_priority_count: int = 2
```

### Notes

- **Backward Compatibility:** All features are additive; existing behavior preserved
- **Feature Flags:** Consider `CHAOS_RESILIENCE_ENABLED=true` for gradual rollout
- **Monitoring:** Add Datadog/Prometheus metrics for all new failure modes
- **Documentation:** Update runbook with new recovery procedures

### Egress Optimization Pattern (CRITICAL)

**All new database queries MUST follow the selective column pattern:**

```python
# BAD - causes excessive egress
.select("*")

# GOOD - use predefined column lists
JOB_LIST_COLUMNS = "id, matter_id, status, progress_pct, ..."
.select(JOB_LIST_COLUMNS)
```

**Story 8.3 (Job Persistence):** Use existing `JOB_LIST_COLUMNS` from `tracker.py` for any new job queries. The `idx_jobs_polling_covering` covering index is already optimized for this pattern.

**Reference:** See `backend/app/services/job_tracking/tracker.py` lines 36-52 for column constants.

---

## Story Priority Order

| Priority | Story | Reason |
|----------|-------|--------|
| P0 | 8.3 | Job persistence - prevents data loss |
| P0 | 8.4 | Memory limits - prevents OOM crashes |
| P0 | 8.1 | Pipeline isolation - prevents cascade failures |
| P1 | 8.2 | Transaction rollback - data consistency |
| P1 | 8.5 | Session fallback - user experience |
| P1 | 8.9 | Cost controls - prevents billing spikes |
| P1 | 8.7 | Rate limit fallback - API stability |
| P2 | 8.6 | Orphan cleanup - storage hygiene |
| P2 | 8.8 | Search degradation - mostly done |
| P2 | 8.10 | Priority workers - operational improvement |

---

*Generated by BMAD Create Tech-Spec Workflow*
