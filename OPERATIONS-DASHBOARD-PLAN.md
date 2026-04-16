# Operations Dashboard — Full Research & Implementation Plan

**Date**: 2026-03-02
**Status**: Planned (not yet implemented)
**Page URL**: `/admin/operations`

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [What Was Researched](#2-what-was-researched)
3. [Key Findings — What Already Exists](#3-key-findings--what-already-exists)
4. [Key Findings — What's Missing (The Gap)](#4-key-findings--whats-missing-the-gap)
5. [Real Error Patterns From Worker Logs](#5-real-error-patterns-from-worker-logs)
6. [GAPS FOUND IN THIS PLAN](#6-gaps-found-in-this-plan)
7. [The Solution — Operations Dashboard](#7-the-solution--operations-dashboard)
8. [Frontend UI Mockups (All 4 Tabs)](#8-frontend-ui-mockups-all-4-tabs)
9. [Database Schema — What Exists vs What We Need](#9-database-schema--what-exists-vs-what-we-need)
10. [Backend API Endpoints (4 New Endpoints)](#10-backend-api-endpoints-4-new-endpoints)
11. [Frontend Architecture](#11-frontend-architecture)
12. [Files to Create](#12-files-to-create)
13. [Files to Modify](#13-files-to-modify)
14. [Implementation Order](#14-implementation-order)
15. [Verification Checklist](#15-verification-checklist)
16. [Deployment](#16-deployment)

---

## 1. Problem Statement

Juhi (admin/non-technical user) needs full visibility into the document processing system. She needs to answer questions like:

- **"Why is the queue always blocked?"** — Which stage takes the longest? Is it Gemini rate limits, system shutdown, or something else?
- **"Which user's documents are consuming the queue?"** — Are 120-page documents blocking everything?
- **"What keeps failing and retrying?"** — Which documents keep going again and again?
- **"What happened yesterday?"** — Full history, not just "what's happening now"
- **"Did the system restart?"** — Non-pipeline errors like deploys, Redis failures, worker crashes

She described wanting something like **"an Excel sheet that I can track"** — sortable, filterable, across all users and all matters, with full history.

### Requirements (from Juhi):

1. See all processing jobs across ALL users and ALL matters (not just her own)
2. Full history — not just today, but any date range
3. Sortable and filterable like a spreadsheet
4. Root cause analysis — why is the queue blocked? Which stage? Which error?
5. Pipeline errors AND non-pipeline errors (worker crashes, Redis down, deploys)
6. Retry tracking — what keeps failing and retrying
7. Human-readable — she's non-technical, no raw logs
8. Export to CSV for offline analysis

---

## 2. What Was Researched

### Files Explored (Backend)

| File | What we looked for | Key findings |
|------|-------------------|--------------|
| `backend/app/api/routes/admin/monitoring.py` | Existing admin API pattern | Uses `require_admin_access` dependency, `get_service_client()` for cross-matter queries |
| `backend/app/api/routes/admin/pipeline.py` | Admin pipeline management | Has `retry_all_failed`, `skip_stuck_jobs`, `get_pipeline_status` |
| `backend/app/api/routes/admin/quota.py` | Admin quota monitoring | LLM quota API with rate limiting |
| `backend/app/api/routes/admin/maintenance.py` | Admin maintenance | Cleanup and data management |
| `backend/app/api/routes/admin/__init__.py` | Router registration pattern | Exports all admin routers with `__all__` |
| `backend/app/api/routes/jobs.py` | Job management API | Per-matter job list, retry, skip, cancel — but scoped to single matter |
| `backend/app/api/deps.py` (line 617) | Admin auth pattern | `require_admin_access()` checks `ADMIN_EMAILS` env var |
| `backend/app/main.py` (line 385-392) | Router wiring | Admin routers registered at lines 386-389 with `prefix="/api"` |
| `backend/app/core/logging.py` | Structlog config | Processor chain with optional Axiom integration, `JSONRenderer` is last |
| `backend/app/core/config.py` | Settings | All env var configurations |
| `backend/app/services/pubsub_service.py` | Real-time broadcasting | Redis pub/sub with channels like `matter:{id}:document:{id}:status` |
| `backend/app/services/job_tracking.py` | Job tracking service | Creates/updates `processing_jobs` and `job_stage_history` records |
| `backend/app/services/job_recovery.py` | Stuck job detection | Finds jobs stuck in PROCESSING state >30 min, auto-recovers |
| `backend/app/workers/celery.py` (line 401-487) | Celery signals | `@task_failure.connect` logs to DLQ, `@task_retry.connect` logs retries |
| `backend/app/api/routes/ws.py` | WebSocket endpoint | Per-matter WebSocket at `/ws/{matter_id}`, auth + ping/pong |
| `backend/app/api/ws/connection_manager.py` | WS connection manager | Manages per-matter WebSocket connections |

### Files Explored (Frontend)

| File | What we looked for | Key findings |
|------|-------------------|--------------|
| `frontend/src/app/(dashboard)/admin/page.tsx` | Admin dashboard page | Server component, admin auth via `NEXT_PUBLIC_ADMIN_EMAILS`, widgets grid |
| `frontend/src/components/features/admin/QueueDepthWidget.tsx` | Queue monitoring widget | Uses `useQueueStatus()` hook with 30s polling, visibility detection |
| `frontend/src/components/features/processing/ProcessingQueue.tsx` | Job list component | Per-matter job filtering, bulk retry/cancel — but single matter only |
| `frontend/src/components/features/processing/ProcessingStatusWidget.tsx` | Progress widget | Per-matter progress bar with ETA, 10s auto-refresh |
| `frontend/src/components/features/dashboard/ActivityFeed.tsx` | Activity feed | Zustand store, groups by day, limited activity types |
| `frontend/src/hooks/useQueueStatus.ts` | Polling hook pattern | 30s interval, `document.visibilityState` check, staleness detection — **this is the pattern to follow** |
| `frontend/src/lib/api/admin-queue.ts` | Admin API client pattern | Type-safe API functions with error handling |
| `frontend/src/stores/activityStore.ts` | Zustand store pattern | State management for activity feed |
| `frontend/src/types/activity.ts` | Activity types | Icon/color configuration per activity type |

### Files Explored (Database)

| File | What we looked for | Key findings |
|------|-------------------|--------------|
| `supabase/migrations/20260114000001_create_processing_jobs_table.sql` | Full schema for processing_jobs + job_stage_history | Complete table definitions, RLS policies, indexes, helper function |
| `supabase/migrations/20260106000001_create_documents_table.sql` | Documents schema | `filename`, `page_count`, `uploaded_by` (FK to `auth.users.id`) |
| `supabase/migrations/20260106000001_create_matters_table.sql` | Matters schema | `title` column |

### Log Files Analyzed

| File | What we found |
|------|--------------|
| `worker_logs.txt` (first 100 lines) | `entity_alias_resolution_batch` running MANY LLM calls (10 pairs per batch, dozens of batches per doc), all using gemini-2.5-flash |
| `tmp_logs.txt` (first 100 lines) | "Starting Container" events (deploy/restart), Voyage `RateLimitError` ("You have not yet added your payment method"), `circuit_breaker_failure`, Supabase 400 on `match_library_chunks_for_matter_voyage` |

---

## 3. Key Findings — What Already Exists

### Backend Infrastructure (Very Complete)

1. **`processing_jobs` table** — Tracks every document processing job with:
   - `status`: QUEUED / PROCESSING / COMPLETED / FAILED / CANCELLED / SKIPPED
   - `current_stage`: Which pipeline stage it's on
   - `error_message`, `error_code`: Why it failed
   - `retry_count`, `max_retries`: Retry tracking
   - `created_at`, `started_at`, `completed_at`: Full timing data
   - `metadata` (JSONB): Recovery attempts, partial progress, etc.

2. **`job_stage_history` table** — Granular stage-by-stage tracking:
   - One row per stage per job attempt
   - `stage_name`: ocr, validation, chunking, embedding, entity_extraction, alias_resolution
   - `status`: PENDING / IN_PROGRESS / COMPLETED / FAILED / SKIPPED
   - `started_at`, `completed_at`: Duration per stage
   - `error_message`: Stage-specific errors

3. **Celery signals** (`backend/app/workers/celery.py` lines 401-487):
   - `@task_failure.connect` → logs `celery_task_failed_dlq` (permanent failures) or `celery_task_failed`
   - `@task_retry.connect` → logs `celery_task_retrying` with retry number and reason
   - Includes sanitization of sensitive kwargs (password/secret/token → [REDACTED])

4. **Job Recovery Service** (`backend/app/services/job_recovery.py`):
   - Auto-detects jobs stuck in PROCESSING state >30 minutes
   - Auto-recovers up to 3 times before giving up
   - Resets document status and re-queues

5. **Redis Pub/Sub** (`backend/app/services/pubsub_service.py`):
   - Broadcasts document_status, job_progress, job_status_change, processing_summary
   - Channel pattern: `matter:{matter_id}:document:{document_id}:status`

6. **WebSocket** (`backend/app/api/routes/ws.py`):
   - Per-matter real-time updates at `/api/ws/{matter_id}`
   - JWT auth, ping/pong keepalive

7. **Admin Auth** (`backend/app/api/deps.py` line 617):
   ```python
   async def require_admin_access(
       request: Request,
       user: AuthenticatedUser = Depends(get_current_user),
   ) -> AuthenticatedUser:
   ```
   Checks `ADMIN_EMAILS` env var (comma-separated list).

### Frontend Infrastructure (Scattered)

1. **QueueDepthWidget** — Shows Celery queue depths (default, llm, heavy, low queues)
2. **ProcessingQueue** — Per-matter job list with filtering (but SINGLE matter only)
3. **ProcessingStatusWidget** — Per-matter progress bar
4. **ActivityFeed** — Per-user activity log (limited types)
5. **useQueueStatus hook** — 30s polling with visibility detection (the pattern to follow)

---

## 4. Key Findings — What's Missing (The Gap)

| What exists | What's missing |
|-------------|---------------|
| Per-matter job views | **Cross-matter admin view** — see ALL jobs across ALL users |
| Current status only | **Historical view** — filter by date range, see past jobs |
| Basic status (queued/processing/done) | **Root cause analysis** — which stage is the bottleneck, which errors recur |
| Pipeline errors only | **System events** — deploys, Redis failures, worker crashes, rate limits |
| Technical log format | **Human-readable messages** — "Retry 2 of 3" not "celery_task_retrying" |
| No CSV export | **Export capability** — download filtered job list as spreadsheet |
| No bottleneck analysis | **Stage duration averages** — which pipeline stage takes longest |
| No error frequency tracking | **Top errors** — which errors happen most often |
| No document size impact | **Page count analysis** — big documents blocking the queue |

---

## 5. Real Error Patterns From Worker Logs

These were found by reading actual `worker_logs.txt` and `tmp_logs.txt` from production:

### Structlog Events That Must Be Captured

| Log Event | Human-Readable Message | Level | Source File |
|-----------|----------------------|-------|-------------|
| `application_starting` / "Starting Container" | **"System restarted (new deploy)"** | INFO (special capture) | Railway container logs |
| `voyage_rerank_failed` (RateLimitError) | **"Voyage rate limit hit (3 RPM limit)"** | ERROR | backend/app/services/ |
| `circuit_breaker_failure` | **"Voyage rerank circuit breaker tripped"** | WARN | backend/app/services/ |
| `celery_task_failed_dlq` | **"Task gave up after 3 retries"** | CRITICAL | backend/app/workers/celery.py:447 |
| `celery_task_retrying` | **"Retrying task (attempt 2 of 3)"** | WARN | backend/app/workers/celery.py:479 |
| HTTP 400/500 from Supabase | **"Database error"** | ERROR | Various service files |
| `redis_client_init_failed` | **"Redis connection failed"** | ERROR | backend/app/services/ |
| `websocket_error` | **"WebSocket disconnected"** | ERROR | backend/app/api/routes/ws.py:256 |

### Key Insights from Log Analysis

1. **`entity_alias_resolution_batch` runs MANY batches** (10 pairs per batch, dozens of batches per document). This explains why the queue appears "stuck" on alias resolution — it's not stuck, it's just processing many batches. The dashboard should show batch progress, not just "in progress".

2. **Voyage rate limits ("3 RPM" free tier)** cause `circuit_breaker_failure` events. These degrade search quality but don't fail the pipeline. They should appear in System Events as warnings.

3. **"Starting Container"** events in Railway logs indicate deploys or restarts. These should be captured as informational system events.

4. **Supabase 400 errors** on `match_library_chunks_for_matter_voyage` RPC indicate the Voyage vector search is failing, triggering fallback to OpenAI embeddings.

### Where Retry/Failure Data Lives

| Data Point | Location |
|-----------|----------|
| Celery retry count | `processing_jobs.retry_count` / `max_retries` |
| Last failure reason | `processing_jobs.error_message` |
| Auto-recovery count | `processing_jobs.metadata.recovery_attempts` |
| Stage-level retries | `job_stage_history` rows — each retry creates new IN_PROGRESS row after FAILED |
| DLQ permanent failures | Celery signal `@task_failure.connect` → logs `celery_task_failed_dlq` |
| Task retry events | Celery signal `@task_retry.connect` → logs `celery_task_retrying` |

---

## 6. GAPS FOUND IN THIS PLAN

After a second deep-dive into the codebase (50+ additional files checked), here are **11 gaps** that need to be addressed before implementation.

### Gap 1: CRITICAL — `auth.users` Cannot Be Joined Directly

**The plan says**: RPC function `get_admin_jobs_overview()` joins `processing_jobs → documents → auth.users` to get user emails.

**The problem**: Supabase's `auth.users` table is in a separate schema and **cannot be joined from RPC functions** running under `SECURITY DEFINER`. No existing RPC in the codebase joins `auth.users`. The codebase never queries `auth.users` directly.

**What actually exists**: A `public.users` table (created in `supabase/migrations/20260104000000_create_users_table.sql`) that mirrors `auth.users` via a signup trigger. It has columns: `id` (PK, refs auth.users), `email`, `full_name`, `avatar_url`, `created_at`, `last_login`.

**The fix**: RPC must join `processing_jobs → documents → public.users` (NOT `auth.users`). Also, existing code uses a `profiles` table for user data lookups (see `backend/app/api/routes/exports.py` lines 156-164).

---

### Gap 2: CRITICAL — Worker Processes Don't Initialize Logging

**The plan says**: The structlog DB sink runs in "both API and Worker processes."

**The problem**: Only `backend/app/main.py` (line 61) calls `configure_logging()`. The worker entry point `backend/app/workers/celery.py` does **NOT** call `configure_logging()`. Workers are separate Celery processes that start independently — they never run `main.py`.

**Impact**: The DB event sink would ONLY capture errors from the API process. All worker errors (which is where most pipeline errors happen — Gemini 429, timeouts, OOM) would be missed entirely.

**The fix**: Add `configure_logging()` call to `celery.py` worker initialization (after line 291 where structlog is already imported). This is an additional file modification not in the original plan.

---

### Gap 3: HIGH — Structlog Processors Are Synchronous

**The plan says**: DB sink writes to Supabase when log events occur.

**The problem**: Structlog processors run **synchronously** in the log call chain. The Supabase client is also sync (`get_service_client()` returns a sync `Client`). A direct DB write in a structlog processor would:
1. Block the calling thread on every ERROR log
2. If the DB is slow/down, slow down ALL logging
3. If the DB write fails, potentially crash the logging pipeline

**Evidence**: The existing Axiom integration (`logging.py` lines 30-64) uses the `axiom-py` library which handles batching/async internally. We can't just do a raw `.insert()` in a processor.

**The fix**: Use an in-memory queue + background thread pattern:
- Processor appends events to a `collections.deque` (non-blocking)
- Background thread drains the queue every 5 seconds and batch-inserts to Supabase
- On failure, events are discarded (logged to stdout) — never blocks the log pipeline
- On shutdown, flush remaining events

---

### Gap 4: HIGH — `get_service_client()` Is Sync, Endpoints Are Async

**The plan says**: Operations endpoints call RPC functions.

**The problem**: `get_service_client()` returns a **synchronous** Supabase `Client`. All admin API routes are `async def`. Calling sync Supabase methods directly in an async endpoint blocks the event loop.

**Evidence**: Existing admin routes (e.g., `monitoring.py` lines 138-144) wrap calls in `asyncio.to_thread()`:
```python
supabase = get_service_client()
result = await asyncio.to_thread(lambda: supabase.rpc("get_chunk_metrics").execute())
```

**The fix**: All 4 operations endpoints must use `asyncio.to_thread()` for every Supabase call. The plan's endpoint implementations must follow this pattern.

---

### Gap 5: MEDIUM — Plan Has Incomplete Stage Names

**The plan says**: Stage names are: OCR, chunking, embedding, entity_extraction, alias_resolution, citation_extraction, contradiction_detection.

**The actual stage names** (from `document_tasks.py` line 279-286 `PIPELINE_STAGES`):
```python
PIPELINE_STAGES = [
    "validation",
    "confidence",
    "chunking",
    "embedding",
    "entity_extraction",
    "alias_resolution",
    "citation_extraction",
    "citation_verification",    # ← MISSING from plan
    "contradiction_detection",
]
```

**Additional stages from engine_tasks.py** (NOT in the plan at all):
- `"date_extraction"` — Timeline date extraction
- `"event_classification"` — Timeline event classification
- `"entity_linking"` — Entity linking
- `"anomaly_detection"` — Anomaly detection

**Additional stages from summary_tasks.py**:
- `"db_queries"` — Summary data gathering
- `"validation_and_cache"` — Summary validation
- `"completed"` / `"retrying"` / `"failed"` — Summary status stages

**Total**: 13+ distinct stage names, not the 7 in the plan.

**The fix**: Update stage name → human-readable mapping to include ALL 13+ stages:

| Internal | Display |
|----------|---------|
| `validation` | "Validating document" |
| `confidence` | "Checking quality" |
| `chunking` | "Splitting into sections" |
| `embedding` | "Making searchable" |
| `entity_extraction` | "Finding people & places" |
| `alias_resolution` | "Matching name variants" |
| `citation_extraction` | "Finding legal references" |
| `citation_verification` | "Verifying citations" |
| `contradiction_detection` | "Checking contradictions" |
| `date_extraction` | "Extracting dates" |
| `event_classification` | "Classifying events" |
| `entity_linking` | "Linking entities" |
| `anomaly_detection` | "Detecting anomalies" |
| `db_queries` | "Generating summary" |
| `validation_and_cache` | "Finalizing summary" |

---

### Gap 6: MEDIUM — No DateRangePicker Component Exists

**The plan says**: Jobs table has a "Date range: calendar picker."

**The problem**: The frontend has `frontend/src/components/ui/calendar.tsx` (shadcn/ui calendar based on react-day-picker 9.13.0), but **no DateRangePicker or DatePicker wrapper** component exists.

**Existing pattern**: `TimelineFilterBar.tsx` (lines 355-376) uses raw `<input type="date">` elements, not a proper DatePicker.

**The fix**: Either:
1. Create a DateRangePicker component wrapping the existing `calendar.tsx` (more polished)
2. Use simple `<input type="date">` like TimelineFilterBar (faster to implement, less polished)

---

### Gap 7: MEDIUM — No DataTable (Advanced Table) Component

**The plan says**: Jobs Table is a "sortable, filterable table."

**The problem**: The frontend has a basic shadcn/ui `Table` component (`frontend/src/components/ui/table.tsx`) — plain HTML table wrappers with no sorting, filtering, or pagination built in. There is no `DataTable` component.

**The fix**: Either:
1. Build custom sorting/filtering on top of the basic Table component (our approach — simpler, no new dependency)
2. Add `@tanstack/react-table` for full-featured DataTable (heavier, but more powerful)

---

### Gap 8: MEDIUM — CSV Export Has No Existing Pattern

**The plan says**: "Export CSV: download filtered results as spreadsheet."

**The problem**: The codebase has export infrastructure (`backend/app/api/routes/exports.py`) for PDF, Word, and PowerPoint — but **no CSV export** exists. The existing pattern generates files, uploads to Supabase Storage, and returns signed download URLs.

**The fix**: CSV export should be done **client-side** (simpler). The frontend already has the data from the API call — just convert to CSV string and trigger a browser download. No backend changes needed.

```typescript
function exportJobsToCsv(jobs: OperationsJob[]): void {
  const headers = ['Document', 'Pages', 'Matter', 'User', 'Status', 'Stage', ...];
  const rows = jobs.map(j => [j.document_filename, j.document_page_count, ...]);
  const csv = [headers, ...rows].map(r => r.join(',')).join('\n');
  // Trigger browser download
}
```

---

### Gap 9: LOW — `recovery_attempts` Is Never Written

**The plan says**: Dashboard shows `processing_jobs.metadata.recovery_attempts` for auto-recovery count.

**The problem**: The code in `jobs.py` (line 455) **reads** `recovery_attempts` from metadata, but **no code ever writes/increments it**. The field always returns 0.

**Evidence**: Searched all callers of `update_job_status()` and metadata writes — none set `recovery_attempts`.

**Impact**: The "Retries" column in the Jobs Table will always show the Celery retry count (`retry_count`), which is correct. But the auto-recovery count from the job recovery service is invisible.

**The fix**: Not blocking for the dashboard — we use `retry_count` from `processing_jobs` (which IS updated). But if we want recovery visibility, we'd need to fix `job_recovery.py` to increment `metadata.recovery_attempts` (separate task).

---

### Gap 10: LOW — `completed_stages` / `total_stages` Not Updated

**The plan says**: Progress shown as percentage.

**The problem**: `processing_jobs.completed_stages` is never incremented when stages complete. `total_stages` defaults to 7 (hardcoded in `tracker.py` line 1324) but the actual pipeline has 9-13 stages depending on the document.

**Impact**: `progress_pct` may be inaccurate. The dashboard should compute progress from `job_stage_history` (count COMPLETED stages / count total stage rows) rather than relying on `progress_pct`.

**The fix**: Use `progress_pct` when available (it IS updated for some tasks), but also show the current stage name prominently — stage name is more reliable than percentage.

---

### Gap 11: LOW — `audit_logs` Table Already Exists for Event Logging

**Interesting finding**: A `public.audit_logs` table already exists (`supabase/migrations/20260106000011_create_audit_logs_table.sql`) with columns: `event_type`, `action`, `result` (success/denied/error/blocked), `details` (jsonb), `created_at`. It has **no RLS** (service role access only).

**However**: This is for security audit events (login, access denied, etc.), not system operational events. We still need the separate `system_events` table because:
- Different purpose (operations vs security)
- Different retention needs
- Different query patterns
- Mixing them would make both harder to query

---

## Summary of Gaps

| # | Severity | Gap | Fix |
|---|----------|-----|-----|
| 1 | CRITICAL | `auth.users` can't be joined in RPC | Use `public.users` table instead |
| 2 | CRITICAL | Workers don't initialize logging | Add `configure_logging()` to `celery.py` |
| 3 | HIGH | Structlog processors are sync | Use in-memory queue + background thread for DB writes |
| 4 | HIGH | `get_service_client()` is sync | Wrap all calls in `asyncio.to_thread()` |
| 5 | MEDIUM | Plan has 7 stages, reality has 13+ | Expand stage name mapping |
| 6 | MEDIUM | No DateRangePicker component | Use `<input type="date">` or create wrapper |
| 7 | MEDIUM | No DataTable component | Build custom sorting on basic Table |
| 8 | MEDIUM | No CSV export pattern | Do client-side CSV generation |
| 9 | LOW | `recovery_attempts` never written | Use `retry_count` instead |
| 10 | LOW | `completed_stages` inaccurate | Show stage name over percentage |
| 11 | LOW | `audit_logs` exists but different purpose | Keep separate `system_events` table |

---

## 7. The Solution — Operations Dashboard

### Architecture Decision: Polling (not WebSocket/SSE)

**Why polling?** Only one admin user (Juhi). Polling is:
- Simpler to implement and debug
- More reliable (no connection drops to handle)
- Works with existing patterns (`useQueueStatus` hook uses 30s polling)
- Uses `since` parameter for incremental updates (live feed tab)

### Page Structure: 4 Tabs

| Tab | Purpose | Data Source |
|-----|---------|-------------|
| **Jobs Table** | Excel-like sortable/filterable table of ALL jobs | `processing_jobs` + `documents` + `matters` + `auth.users` |
| **Bottleneck Analysis** | Root cause — which stage is slow, which errors recur | `job_stage_history` aggregation |
| **System Events** | Non-pipeline errors (deploys, Redis, rate limits) | New `system_events` table |
| **Live Feed** | Real-time scrolling log of what's happening now | `job_stage_history` + `system_events` merged |

---

## 8. Frontend UI Mockups (All 4 Tabs)

### Tab 1: Jobs Table (the "Excel sheet")

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  [Filters: Status ▼] [Stage ▼] [Matter ▼] [User ▼] [Date: Mar 1-2 ▼] [Export] │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Document          │ Matter        │ User          │ Status     │ Stage          │
│                   │               │               │            │                │
│ Affidavit.pdf     │ Smith v Jones │ juhi@...      │ ⏳ Active  │ embedding      │
│ 42 pages          │               │               │ 75%        │ 12 min so far  │
│                   │               │               │            │                │
│ Rejoinder.pdf     │ Shah v Mehta  │ priya@...     │ ⚠ Retry 2  │ embedding      │
│ 15 pages          │               │               │ of 3       │ Error: 429     │
│                   │               │               │            │                │
│ Contract.pdf      │ Patel v Gupta │ juhi@...      │ ✗ Failed   │ chunking       │
│ 120 pages         │               │               │ Gave up    │ Error: timeout │
│                   │               │               │            │                │
│ Petition.pdf      │ Smith v Jones │ amit@...      │ ✓ Done     │ completed      │
│ 8 pages           │               │               │ 3 min total│                │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Queue Wait │ Process Time │ Retries │ Error              │ Created          │
│ 2 min      │ 10 min...    │ 0       │ —                  │ Mar 2, 10:30 AM  │
│ 5 min      │ 8 min...     │ 2       │ Gemini 429 rate    │ Mar 2, 10:25 AM  │
│ 45 min     │ 22 min       │ 3       │ Timeout after 3    │ Mar 2, 9:50 AM   │
│ 1 min      │ 3 min        │ 0       │ —                  │ Mar 2, 10:15 AM  │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Showing 1-50 of 234 jobs                                    [← Prev] [Next →]  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

**Columns** (all sortable by clicking header):
- **Document**: filename + page count
- **Matter**: matter title
- **User**: email of who uploaded the document
- **Status**: Queued / Active / Retry X of Y / Failed / Done
- **Current Stage**: human-readable name (e.g., "Making searchable" instead of "embedding")
- **Queue Wait**: time from `created_at` → `started_at` (how long it waited in queue)
- **Processing Time**: time from `started_at` → `completed_at`, or "X min so far" if still active
- **Retries**: count of retry attempts
- **Error**: last error message (shortened)
- **Created At**: when the job was first queued

**Filters** (top bar):
- **Status**: All / Queued / Processing / Failed / Completed
- **Stage**: All / OCR / Chunking / Embedding / Entities / Citations / etc.
- **Matter**: dropdown of all matters
- **User**: dropdown of all users
- **Date range**: calendar picker (defaults to last 7 days)
- **Export CSV**: download filtered results as spreadsheet

### Tab 2: Bottleneck Analysis (the "why is queue blocked" view)

```
┌──────────────────────────────────────────────────────────────────┐
│  STAGE DURATION (avg time per stage, last 7 days)               │
│                                                                  │
│  OCR              ██████████████████████████  8 min avg          │
│  Chunking         ████████                   3 min avg          │
│  Embedding        ██████████████████████████████████  12 min avg │ ← BOTTLENECK
│  Entity Extract   ████████████               5 min avg          │
│  Citations        ██████████                 4 min avg          │
│  Contradictions   ████████████████           6 min avg          │
├──────────────────────────────────────────────────────────────────┤
│  TOP ERRORS (last 7 days)                                        │
│                                                                  │
│  Gemini 429 rate limit         ████████████████  23 occurrences │
│  Timeout (>30 min)             ████████          12 occurrences │
│  OCR extraction failed         ████              6 occurrences  │
│  Redis connection lost         ██                3 occurrences  │
│  Worker OOM killed             █                 1 occurrence   │
├──────────────────────────────────────────────────────────────────┤
│  QUEUE WAIT TIME (how long docs wait before processing starts)   │
│                                                                  │
│  Average wait: 8 minutes                                         │
│  Longest wait today: 45 minutes (Contract.pdf, 120 pages)        │
│  Documents waiting now: 3                                        │
├──────────────────────────────────────────────────────────────────┤
│  BIG DOCUMENTS (page count impact on queue)                      │
│                                                                  │
│  >100 pages: 4 docs (avg 35 min each) ← these block the queue  │
│  50-100 pages: 8 docs (avg 15 min each)                         │
│  <50 pages: 42 docs (avg 5 min each)                            │
└──────────────────────────────────────────────────────────────────┘
```

This tab answers: **"Why is the queue blocked?"**
- Which stage takes longest → if embedding is 12 min avg, that's the bottleneck
- Which errors keep happening → if Gemini 429 is 23 times, that's the root cause
- Big documents blocking the queue → 120-page documents take 35 min
- Queue wait time → are documents waiting too long to start?

### Tab 3: System Events (non-pipeline errors)

```
┌──────────────────────────────────────────────────────────────────┐
│  SYSTEM EVENTS                          [Date: Mar 1-2 ▼]       │
├──────────────────────────────────────────────────────────────────┤
│  Mar 2, 10:45 AM  ✗  Worker crashed: out of memory              │
│  Mar 2, 10:30 AM  ⚠  Gemini API: 429 rate limit (5th time)     │
│  Mar 2, 10:15 AM  ⚠  Redis connection lost briefly              │
│  Mar 2, 9:00 AM   ℹ  New deploy detected (service restarted)   │
│  Mar 1, 11:30 PM  ✗  Database connection pool exhausted         │
│  Mar 1, 8:00 PM   ℹ  Scheduled maintenance: job recovery ran   │
│  ...                                                             │
├──────────────────────────────────────────────────────────────────┤
│  Showing 1-50 of 89 events                  [← Prev] [Next →]  │
└──────────────────────────────────────────────────────────────────┘
```

### Tab 4: Live Feed (real-time scrolling log)

Real-time streaming of what's happening RIGHT NOW:
- Pipeline events from `job_stage_history` (stage started, completed, failed)
- System events from `system_events` table
- Merged by timestamp, newest first
- Auto-polls every 5 seconds using `since` parameter for incremental updates
- Human-readable messages only (no raw JSON)

---

## 9. Database Schema — What Exists vs What We Need

### Already Exists (no changes needed)

**`processing_jobs` table** (from `20260114000001_create_processing_jobs_table.sql`):
```sql
CREATE TABLE public.processing_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  document_id uuid REFERENCES public.documents(id) ON DELETE CASCADE,
  job_type text NOT NULL,           -- DOCUMENT_PROCESSING, OCR, VALIDATION, CHUNKING, etc.
  status text NOT NULL DEFAULT 'QUEUED',  -- QUEUED, PROCESSING, COMPLETED, FAILED, CANCELLED, SKIPPED
  celery_task_id text,
  current_stage text,
  total_stages int DEFAULT 7,
  completed_stages int DEFAULT 0,
  progress_pct int DEFAULT 0,
  estimated_completion timestamptz,
  error_message text,
  error_code text,
  retry_count int DEFAULT 0,
  max_retries int DEFAULT 3,
  metadata jsonb DEFAULT '{}',
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);
```

**`job_stage_history` table** (same migration file):
```sql
CREATE TABLE public.job_stage_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id uuid NOT NULL REFERENCES public.processing_jobs(id) ON DELETE CASCADE,
  stage_name text NOT NULL,
  status text NOT NULL DEFAULT 'PENDING',  -- PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED
  started_at timestamptz,
  completed_at timestamptz,
  error_message text,
  metadata jsonb DEFAULT '{}',
  created_at timestamptz DEFAULT now()
);
```

**Existing Indexes**:
- `idx_processing_jobs_matter_status` (matter_id, status)
- `idx_processing_jobs_document_status` (document_id, status)
- `idx_processing_jobs_celery` (celery_task_id)
- `idx_processing_jobs_matter_created` (matter_id, created_at DESC)
- `idx_processing_jobs_job_type` (job_type)
- `idx_processing_jobs_status` (status)
- `idx_job_stage_history_job` (job_id)
- `idx_job_stage_history_job_stage` (job_id, stage_name)

**Existing RLS**: Both tables have RLS enabled — users can only see jobs from their own matters (via `matter_attorneys` join). The admin operations endpoints will use `get_service_client()` which bypasses RLS.

### New: `system_events` Table

```sql
CREATE TABLE public.system_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type text NOT NULL,        -- e.g. 'deploy_restart', 'rate_limit', 'worker_crash', etc.
  level text NOT NULL DEFAULT 'ERROR',  -- INFO, WARN, ERROR, CRITICAL
  message text NOT NULL,           -- Human-readable message
  source text,                     -- Which service: 'api', 'worker', etc.
  metadata jsonb DEFAULT '{}',     -- Extra context (task_name, error_type, etc.)
  created_at timestamptz DEFAULT now()
);

-- Index for time-range queries (dashboard polling)
CREATE INDEX idx_system_events_created_at ON system_events(created_at DESC);
-- Index for level filtering
CREATE INDEX idx_system_events_level ON system_events(level);
```

### New Indexes on Existing Tables

```sql
-- For bottleneck analysis: stage duration aggregation over time
CREATE INDEX idx_job_stage_history_created_at ON job_stage_history(created_at DESC);

-- For cross-matter job listing with time filtering
CREATE INDEX idx_processing_jobs_created_at ON processing_jobs(created_at DESC);
```

### New RPC Functions

**`get_admin_jobs_overview()`** — Cross-matter job list with user emails:

> **GAP 1 FIX**: Uses `public.users` (NOT `auth.users`) for email lookup.

```sql
CREATE OR REPLACE FUNCTION public.get_admin_jobs_overview(
  p_status text DEFAULT NULL,
  p_stage text DEFAULT NULL,
  p_matter_id uuid DEFAULT NULL,
  p_user_email text DEFAULT NULL,
  p_date_from timestamptz DEFAULT NULL,
  p_date_to timestamptz DEFAULT NULL,
  p_sort_by text DEFAULT 'created_at',
  p_sort_dir text DEFAULT 'DESC',
  p_limit int DEFAULT 50,
  p_offset int DEFAULT 0
)
RETURNS TABLE (
  job_id uuid,
  document_filename text,
  document_page_count int,
  matter_title text,
  matter_id uuid,
  user_email text,
  status text,
  current_stage text,
  progress_pct int,
  error_message text,
  retry_count int,
  max_retries int,
  queue_wait_seconds double precision,
  processing_seconds double precision,
  created_at timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  metadata jsonb,
  total_count bigint
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
-- Join chain: processing_jobs → documents → public.users (NOT auth.users)
-- WHERE filters applied dynamically
-- Computes queue_wait_seconds = EXTRACT(EPOCH FROM (started_at - created_at))
-- Computes processing_seconds = EXTRACT(EPOCH FROM (COALESCE(completed_at, now()) - started_at))
$$ ... $$;
```

**`get_admin_bottleneck_stats()`** — Aggregated analytics:
```sql
CREATE OR REPLACE FUNCTION public.get_admin_bottleneck_stats(
  p_date_from timestamptz DEFAULT (now() - interval '7 days'),
  p_date_to timestamptz DEFAULT now()
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$ ... $$;
-- Returns:
-- {
--   "stage_durations": [{"stage": "embedding", "avg_seconds": 720, "count": 45}, ...],
--   "top_errors": [{"error": "Gemini 429 rate limit", "count": 23}, ...],
--   "queue_wait": {"avg_seconds": 480, "max_seconds": 2700, "waiting_now": 3},
--   "page_buckets": [{"bucket": ">100", "count": 4, "avg_seconds": 2100}, ...]
-- }
```

---

## 10. Backend API Endpoints (4 New Endpoints)

All endpoints live in `backend/app/api/routes/admin/operations.py` and require admin access.

### Endpoint 1: `GET /api/admin/operations/jobs`

**Purpose**: Paginated, filterable, sortable list of ALL processing jobs across ALL matters and users.

**Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | null | Filter: QUEUED / PROCESSING / FAILED / COMPLETED |
| `stage` | string | null | Filter by current_stage |
| `matter_id` | uuid | null | Filter by matter |
| `user_email` | string | null | Filter by uploader email |
| `date_from` | ISO datetime | null | Start of date range |
| `date_to` | ISO datetime | null | End of date range |
| `sort_by` | string | "created_at" | Column to sort by |
| `sort_dir` | string | "DESC" | ASC or DESC |
| `limit` | int | 50 | Page size |
| `offset` | int | 0 | Page offset |

**Response**:
```json
{
  "jobs": [
    {
      "job_id": "uuid",
      "document_filename": "Affidavit.pdf",
      "document_page_count": 42,
      "matter_title": "Smith v Jones",
      "matter_id": "uuid",
      "user_email": "juhi@example.com",
      "status": "PROCESSING",
      "status_display": "Active — 75%",
      "current_stage": "embedding",
      "stage_display": "Making searchable",
      "progress_pct": 75,
      "error_message": null,
      "retry_count": 0,
      "max_retries": 3,
      "queue_wait_seconds": 120,
      "processing_seconds": 720,
      "created_at": "2026-03-02T10:30:00Z",
      "started_at": "2026-03-02T10:32:00Z",
      "completed_at": null
    }
  ],
  "total_count": 234,
  "limit": 50,
  "offset": 0
}
```

**Implementation**: Calls `get_admin_jobs_overview()` RPC function via `get_service_client()` (bypasses RLS). Adds human-readable display fields (`status_display`, `stage_display`) server-side.

**Stage name mapping** (internal → human-readable) — **Gap 5 fix: expanded from 8 to 15 stages**:
| Internal | Display |
|----------|---------|
| `validation` | "Validating document" |
| `confidence` | "Checking quality" |
| `chunking` | "Splitting into sections" |
| `embedding` | "Making searchable" |
| `entity_extraction` | "Finding people & places" |
| `alias_resolution` | "Matching name variants" |
| `citation_extraction` | "Finding legal references" |
| `citation_verification` | "Verifying citations" |
| `contradiction_detection` | "Checking contradictions" |
| `date_extraction` | "Extracting dates" |
| `event_classification` | "Classifying events" |
| `entity_linking` | "Linking entities" |
| `anomaly_detection` | "Detecting anomalies" |
| `db_queries` | "Generating summary" |
| `validation_and_cache` | "Finalizing summary" |

### Endpoint 2: `GET /api/admin/operations/bottlenecks`

**Purpose**: Aggregated analytics for root cause analysis.

**Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `date_from` | ISO datetime | 7 days ago | Start of analysis period |
| `date_to` | ISO datetime | now | End of analysis period |

**Response**:
```json
{
  "stage_durations": [
    {"stage": "embedding", "stage_display": "Making searchable", "avg_seconds": 720, "count": 45},
    {"stage": "ocr", "stage_display": "Extracting text", "avg_seconds": 480, "count": 38}
  ],
  "top_errors": [
    {"error_pattern": "Gemini 429 rate limit", "count": 23, "last_seen": "2026-03-02T10:30:00Z"},
    {"error_pattern": "Timeout after 30 min", "count": 12, "last_seen": "2026-03-02T09:50:00Z"}
  ],
  "queue_wait": {
    "avg_seconds": 480,
    "max_seconds": 2700,
    "max_document": "Contract.pdf (120 pages)",
    "waiting_now": 3
  },
  "page_buckets": [
    {"bucket": ">100 pages", "count": 4, "avg_processing_seconds": 2100},
    {"bucket": "50-100 pages", "count": 8, "avg_processing_seconds": 900},
    {"bucket": "<50 pages", "count": 42, "avg_processing_seconds": 300}
  ]
}
```

### Endpoint 3: `GET /api/admin/operations/events`

**Purpose**: System events log (non-pipeline errors).

**Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `date_from` | ISO datetime | 7 days ago | Start date |
| `date_to` | ISO datetime | now | End date |
| `level` | string | null | Filter: INFO / WARN / ERROR / CRITICAL |
| `limit` | int | 50 | Page size |
| `offset` | int | 0 | Page offset |

**Response**:
```json
{
  "events": [
    {
      "id": "uuid",
      "event_type": "rate_limit",
      "level": "ERROR",
      "message": "Voyage rate limit hit (3 RPM limit)",
      "source": "worker",
      "metadata": {"provider": "voyage", "error": "RateLimitError"},
      "created_at": "2026-03-02T10:30:00Z"
    }
  ],
  "total_count": 89,
  "limit": 50,
  "offset": 0
}
```

### Endpoint 4: `GET /api/admin/operations/feed`

**Purpose**: Live feed — merged pipeline events + system events, sorted by time.

**Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `since` | ISO datetime | null | Only return events after this timestamp (for incremental polling) |
| `limit` | int | 50 | Max events to return |

**Response**:
```json
{
  "items": [
    {
      "type": "stage_change",
      "message": "Affidavit.pdf — Making searchable (started)",
      "level": "info",
      "timestamp": "2026-03-02T10:32:00Z",
      "matter_title": "Smith v Jones",
      "document_filename": "Affidavit.pdf"
    },
    {
      "type": "system_event",
      "message": "Voyage rate limit hit (3 RPM limit)",
      "level": "error",
      "timestamp": "2026-03-02T10:30:00Z"
    }
  ],
  "latest_timestamp": "2026-03-02T10:32:00Z"
}
```

The `latest_timestamp` is used as the `since` parameter for the next poll.

---

## 11. Frontend Architecture

### Patterns to Reuse (from existing codebase)

| Pattern | Source | How we use it |
|---------|--------|---------------|
| Polling with visibility detection | `frontend/src/hooks/useQueueStatus.ts` | Same pattern for all tabs — only poll when browser tab is visible |
| Admin API client | `frontend/src/lib/api/admin-queue.ts` | Same structure for type-safe API functions |
| Admin page auth guard | `frontend/src/app/(dashboard)/admin/page.tsx` | Same `NEXT_PUBLIC_ADMIN_EMAILS` check |
| Card/widget layout | `frontend/src/components/features/admin/QueueDepthWidget.tsx` | Same shadcn/ui Card components |
| Table component | shadcn/ui Table | For the Jobs Table tab |
| Badge component | shadcn/ui Badge | For status badges (color-coded) |
| Tabs component | shadcn/ui Tabs | For the 4-tab layout |

### Component Tree

```
/admin/operations/page.tsx (Server Component)
  └── OperationsDashboard.tsx (Client Component)
      ├── Tabs
      │   ├── Tab 1: JobsTable.tsx
      │   │   ├── Filter bar (Select, DatePicker, Button)
      │   │   ├── Table (sortable headers, paginated rows)
      │   │   └── Pagination controls
      │   ├── Tab 2: BottleneckPanel.tsx
      │   │   ├── Stage Duration bars
      │   │   ├── Top Errors list
      │   │   ├── Queue Wait stats
      │   │   └── Page Bucket stats
      │   ├── Tab 3: SystemEventsLog.tsx
      │   │   ├── Date/level filters
      │   │   ├── Event list (icon + message + timestamp)
      │   │   └── Pagination
      │   └── Tab 4: LiveFeedPanel.tsx
      │       └── Auto-scrolling event list (5s polling)
      └── useOperationsDashboard.ts (hook)
```

### Hook: `useOperationsDashboard.ts`

Manages state for all 4 tabs:
- **Jobs tab**: filters, sort column/direction, pagination (page, limit), data
- **Bottleneck tab**: date range, data
- **Events tab**: date range, level filter, pagination, data
- **Live feed**: `since` timestamp, items array, auto-polling
- **Shared**: active tab, loading states, error states
- **Key feature**: Tab switching doesn't lose state (each tab's state persists)

### API Client: `admin-operations.ts`

```typescript
// Types
export interface OperationsJob {
  job_id: string;
  document_filename: string;
  document_page_count: number;
  matter_title: string;
  matter_id: string;
  user_email: string;
  status: string;
  status_display: string;
  current_stage: string;
  stage_display: string;
  progress_pct: number;
  error_message: string | null;
  retry_count: number;
  max_retries: number;
  queue_wait_seconds: number;
  processing_seconds: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface BottleneckData { ... }
export interface SystemEvent { ... }
export interface LiveFeedItem { ... }

// API functions
export async function getJobs(filters: JobFilters): Promise<JobsResponse>;
export async function getBottlenecks(dateRange: DateRange): Promise<BottleneckData>;
export async function getEvents(filters: EventFilters): Promise<EventsResponse>;
export async function getLiveFeed(since: string | null): Promise<FeedResponse>;

// CSV export
export function exportJobsToCsv(jobs: OperationsJob[]): void;
```

---

## 12. Files to Create

### 1. `supabase/migrations/YYYYMMDD_add_operations_dashboard.sql`
- `system_events` table
- New indexes on `job_stage_history` and `processing_jobs`
- `get_admin_jobs_overview()` RPC function
- `get_admin_bottleneck_stats()` RPC function

### 2. `backend/app/core/db_event_sink.py`
Structlog processor that intercepts ERROR/CRITICAL events and writes to `system_events` table.

**Key design decisions** (updated with Gap 2, 3, 4 fixes):
- Runs in BOTH API and Worker processes (Gap 2: must add `configure_logging()` to `celery.py`)
- **Uses in-memory queue + background thread** (Gap 3 fix):
  - Processor appends events to `collections.deque` (non-blocking, O(1))
  - Background `threading.Thread` drains queue every 5 seconds
  - Batch-inserts to Supabase via `get_service_client()` (sync client, runs in own thread)
  - On DB failure: discards events and logs warning to stdout — never blocks log pipeline
  - On process shutdown: flushes remaining events via `atexit` handler
- In-memory dedup: same error within 60 seconds → skip (prevents flood)
- Sanitizes sensitive fields: password, token, secret → `[REDACTED]`
- Captures special INFO events: `application_starting` (deploy detection)
- Uses `get_service_client()` to write (bypasses RLS, sync is fine in background thread)

### 3. `backend/app/api/routes/admin/operations.py`
4 admin endpoints (see Section 9 above):
- `GET /api/admin/operations/jobs`
- `GET /api/admin/operations/bottlenecks`
- `GET /api/admin/operations/events`
- `GET /api/admin/operations/feed`

All use `Depends(require_admin_access)` and `get_service_client()`.

### 4. `frontend/src/lib/api/admin-operations.ts`
TypeScript API client with types and functions (see Section 10 above).

### 5. `frontend/src/hooks/useOperationsDashboard.ts`
React hook managing state for all 4 tabs (see Section 10 above).

### 6. Frontend page + components:
- `frontend/src/app/(dashboard)/admin/operations/page.tsx` — Server component with admin auth
- `frontend/src/components/features/admin/operations/OperationsDashboard.tsx` — Main client component
- `frontend/src/components/features/admin/operations/JobsTable.tsx` — Sortable/filterable table
- `frontend/src/components/features/admin/operations/BottleneckPanel.tsx` — Analytics view
- `frontend/src/components/features/admin/operations/SystemEventsLog.tsx` — Event log
- `frontend/src/components/features/admin/operations/LiveFeedPanel.tsx` — Real-time feed

---

## 13. Files to Modify (5 — updated from 4)

### 1. `backend/app/main.py` (line ~389)
Add after existing admin router registrations:
```python
from app.api.routes.admin import operations as admin_operations
# ...
app.include_router(admin_operations.router, prefix="/api")
```
**Note** (Gap 5 import pattern): Follow existing import style — `from app.api.routes.admin import operations as admin_operations`

### 2. `backend/app/api/routes/admin/__init__.py`
Add:
```python
from app.api.routes.admin.operations import router as operations_router
```
And update `__all__`.

### 3. `backend/app/core/logging.py` (line ~112)
Add database event sink to structlog processor chain, BEFORE `JSONRenderer`:
```python
# GAP 3 FIX: Use queue-based sink, not direct DB writes
from app.core.db_event_sink import DatabaseEventSink
db_sink = DatabaseEventSink()  # Uses in-memory queue + background thread
processors.append(db_sink)

# JSONRenderer must be last
processors.append(structlog.processors.JSONRenderer())
```

### 4. `backend/app/workers/celery.py` (NEW — Gap 2 fix)
**This was MISSING from the original plan.** Workers don't call `configure_logging()`, so the DB event sink would never capture worker errors.

Add after line 291 (where structlog is already imported):
```python
from app.core.logging import configure_logging
configure_logging()
```

### 5. `frontend/src/app/(dashboard)/admin/page.tsx` (line ~72)
Add link card to `/admin/operations` (similar to existing Usage Dashboard link card):
```tsx
<Link href="/admin/operations" className="block">
  <Card className="hover:border-primary/50 transition-colors cursor-pointer">
    <CardHeader className="pb-2">
      <div className="flex items-center gap-2">
        <Activity className="h-5 w-5 text-primary" />
        <CardTitle className="text-lg">Operations Dashboard</CardTitle>
      </div>
      <CardDescription>
        Processing queue visibility — all jobs, bottleneck analysis, system events, live feed
      </CardDescription>
    </CardHeader>
    <CardContent>
      <span className="text-sm text-primary font-medium">View dashboard →</span>
    </CardContent>
  </Card>
</Link>
```

---

## 14. Implementation Order

| Step | What | Dependencies |
|------|------|-------------|
| 1 | Database migration (system_events table + indexes + RPC functions) | None |
| 2 | `backend/app/core/db_event_sink.py` (structlog → DB processor) | Step 1 |
| 3 | Wire sink into `backend/app/core/logging.py` | Step 2 |
| 4 | `backend/app/api/routes/admin/operations.py` (4 endpoints) | Step 1 |
| 5 | Wire router into `main.py` and `admin/__init__.py` | Step 4 |
| 6 | `frontend/src/lib/api/admin-operations.ts` (API client) | Step 4 |
| 7 | `frontend/src/hooks/useOperationsDashboard.ts` (hook) | Step 6 |
| 8 | Frontend page + 4 tab components | Steps 6, 7 |
| 9 | Add link card on admin page | Step 8 |
| 10 | Deploy | All steps |

---

## 15. Verification Checklist

| # | Test | Expected Result |
|---|------|----------------|
| 1 | Open `/admin/operations` | Jobs tab shows all jobs across all matters |
| 2 | Sort by Queue Wait descending | See which documents waited longest |
| 3 | Filter by Status=Failed | See all failures with error messages |
| 4 | Filter by User | See which user's documents are in queue |
| 5 | Filter by date range (yesterday) | See historical jobs, not just today |
| 6 | Switch to Bottleneck tab | Identify which stage takes longest |
| 7 | Check Top Errors section | Confirm Gemini 429 / timeout patterns visible |
| 8 | Switch to System Events | Verify non-pipeline errors appear (rate limits, deploys) |
| 9 | Switch to Live Feed | Watch real-time events stream in every 5 seconds |
| 10 | Click Export CSV | Download filtered job list as spreadsheet |
| 11 | Non-admin user visits `/admin/operations` | Redirected to `/dashboard` |
| 12 | Upload a document while watching Live Feed | See processing stages appear in real-time |

---

## 16. Deployment

```bash
# 1. Run migration against Supabase (one-time)
# (Via Supabase dashboard or supabase db push)

# 2. Backend API (from repo root)
railway up -s LDIP

# 3. Backend Worker (from repo root)
railway up -s ldip-worker

# 4. Frontend
cd frontend && vercel --prod
```

**Important**: Deploy BOTH `LDIP` and `ldip-worker` — they share the same codebase. The `db_event_sink` runs in both processes.
