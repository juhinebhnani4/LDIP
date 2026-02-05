# Pipeline Resilience Improvements

## Issues Discovered (Jan 2026)

### 1. Missing Constant Caused Silent Worker Failure
**File:** `app/services/act_cache_service.py`
**Issue:** `CACHED_ACT_URL_EXPIRES` was referenced but never defined
**Impact:** Celery worker couldn't import tasks, causing all dispatched tasks to be silently dropped
**Fix:** Added constant definition using settings value

### 2. Standalone Task Calls Don't Update Job Status
**Issue:** When tasks are called via `apply_async` with just `document_id`, they don't have `job_id` to update progress
**Impact:** Jobs show as QUEUED even after processing completes
**Root Cause:** Job tracking designed for chained execution, not standalone calls

### 3. Idempotency Gap in Chunking
**Issue:** Jobs stuck at "chunking" because chunks existed but task kept trying to re-chunk
**Impact:** Recovery attempts failed repeatedly with "chunk already exists" errors
**Fix:** Added idempotency check to verify BOTH parent AND child chunks exist

### 4. Orphaned QUEUED Jobs
**Issue:** Jobs could be set to QUEUED but never have Celery task dispatched
**Cause:** Worker crash, restart, or failed dispatch
**Fix:** Added `dispatch_stuck_queued_jobs` maintenance task (runs every 5 minutes)

---

## Improvements Implemented

### 1. Job ID Lookup Helper Function
**File:** `app/workers/tasks/document_tasks.py`
**Function:** `_lookup_job_id_for_document(document_id)`

When tasks are called standalone (without `prev_result`), this function looks up the active job_id from the database so job progress can still be updated.

```python
def _lookup_job_id_for_document(document_id: str) -> str | None:
    """Lookup job_id from database when not provided in task chain."""
    # Finds active (QUEUED/PROCESSING) job for document
    # Enables standalone task calls to update job progress
```

### 2. Idempotency Check Helpers
**File:** `app/workers/tasks/document_tasks.py`

Added helper functions to check if work is already complete:

- `_check_embedding_complete(document_id)` - Returns (is_complete, total_chunks, embedded_chunks)
- `_check_entities_exist(matter_id)` - Returns (has_entities, entity_count)

### 3. Idempotency Checks in Tasks

**embed_chunks task:**
```python
# IDEMPOTENCY CHECK: Skip if embedding is already complete
is_embedding_complete, total_chunks, embedded_chunks = _check_embedding_complete(doc_id)
if is_embedding_complete and not force:
    # Update job stage and return success
    _update_job_stage_complete(job_id, "embedding", matter_id)
    return {"status": "embedding_complete", ...}
```

**extract_entities task:**
```python
# IDEMPOTENCY CHECK: Skip if entities already exist for this matter
has_entities, entity_count = _check_entities_exist(matter_id)
if has_entities and not force:
    # Update job stage and return success
    _update_job_stage_complete(job_id, "entity_extraction", matter_id)
    return {"status": "entities_extracted", ...}
```

### 4. Pre-flight Import Validation
**File:** `app/workers/celery.py`

Added startup validation to catch import errors early:

```python
# Validates all task modules import correctly
# Logs critical error and raises if imports fail
# Warns if critical tasks are not registered
```

Critical tasks validated:
- `process_document`
- `embed_chunks`
- `extract_entities`
- `resolve_aliases`
- `recover_stale_jobs`
- `dispatch_stuck_queued_jobs`

### 5. Job Status Sync Maintenance Task
**File:** `app/workers/tasks/maintenance_tasks.py`
**Task:** `sync_stale_job_status`
**Schedule:** Every 15 minutes (jobs stale for 30+ minutes)

Syncs job status based on actual document state:
- Checks chunks, embeddings, entities
- Updates job stage and progress to match reality
- Handles cases where tasks completed but status wasn't updated

### 6. Dispatch Stuck QUEUED Jobs Task
**File:** `app/workers/tasks/maintenance_tasks.py`
**Task:** `dispatch_stuck_queued_jobs`
**Schedule:** Every 5 minutes (jobs QUEUED for 10+ minutes)

Re-dispatches orphaned QUEUED jobs that never had Celery tasks sent.

---

## Celery Beat Schedule

| Task | Schedule | Purpose |
|------|----------|---------|
| `recover_stale_jobs` | Configurable | Recover jobs stuck in PROCESSING |
| `dispatch_stuck_queued_jobs` | 5 min | Re-dispatch orphaned QUEUED jobs |
| `sync_stale_job_status` | 15 min | Sync job status with actual state |
| `cleanup_stale_chunks` | 1 hour | Clean up old chunk records |

---

## Utility Scripts

| Script | Purpose |
|--------|---------|
| `check_jobs.py` | Quick status check of all jobs |
| `dispatch_queued_jobs.py` | Manually dispatch stuck QUEUED jobs |
| `fix_stuck_chunking_jobs.py` | Fix jobs stuck at chunking with existing chunks |
| `sync_job_status.py` | Manually sync job status based on actual document state |
| `reset_stuck_jobs.py` | Reset stuck jobs for fresh reprocessing |

---

## How to Use

### Check Job Status
```bash
cd backend
.venv\Scripts\python check_jobs.py
```

### Manually Dispatch Stuck Jobs
```bash
cd backend
.venv\Scripts\python dispatch_queued_jobs.py
```

### Manually Sync Job Status
```bash
cd backend
.venv\Scripts\python sync_job_status.py
```

### Fix Jobs Stuck at Chunking
```bash
cd backend
.venv\Scripts\python fix_stuck_chunking_jobs.py -y --requeue
```

---

## Testing Recommendations

1. **Test task imports** - Verify all task modules import cleanly
2. **Test idempotency** - Run same task twice, verify no duplicate data
3. **Test recovery** - Simulate worker crash mid-task, verify recovery works
4. **Test orphaned jobs** - Create QUEUED job without dispatch, verify maintenance picks it up
5. **Test job status sync** - Run task, don't update job, verify sync task fixes it
