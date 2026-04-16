---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
inputDocuments: ['OPERATIONS-DASHBOARD-PLAN.md']
---

# LDIP Operations Dashboard - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for the LDIP Operations Dashboard, decomposing the requirements from the Operations Dashboard Plan into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: Cross-matter job visibility — admin sees ALL processing jobs across ALL users and ALL matters in a single sortable table
FR2: Historical date range filtering — view past jobs for any date range, not just current/today
FR3: Sortable table columns — sort by any column (document, matter, user, status, stage, queue wait, processing time, retries, error, created at)
FR4: Filterable by status — filter jobs by Queued / Processing / Failed / Completed
FR5: Filterable by pipeline stage — filter by any of 15+ pipeline stages (validation, chunking, embedding, entities, citations, etc.)
FR6: Filterable by matter — dropdown of all matters across the system
FR7: Filterable by user — dropdown of all users who uploaded documents
FR8: CSV export — download currently filtered job list as a CSV spreadsheet file
FR9: Bottleneck analysis — show average time per pipeline stage as horizontal bar chart, highlighting the slowest stage
FR10: Top errors view — show most frequent error patterns with occurrence count and last-seen timestamp
FR11: Queue wait analysis — show average wait time, longest wait (with document name), and count of documents currently waiting
FR12: Page count impact — group documents by size buckets (<50, 50-100, >100 pages) with average processing time per bucket
FR13: System events log — show non-pipeline errors: deploys/restarts, Redis failures, rate limits, worker crashes, database errors
FR14: Live feed — real-time scrolling log merging pipeline stage changes and system events by timestamp, with incremental polling
FR15: Human-readable messages — translate all internal stage names and error codes to plain English display names
FR16: Pagination — paginated results for jobs table, system events, and live feed with page navigation controls

### NonFunctional Requirements

NFR1: Admin-only access — parent `/admin/page.tsx` (server component) checks `NEXT_PUBLIC_ADMIN_EMAILS` and redirects non-admins. Sub-pages at `/admin/operations/*` inherit protection. Backend endpoints use `Depends(require_admin_access)` from `app.api.deps` (line 617).
NFR2: Polling-based updates — 30s interval with `document.visibilityState` check (pause when tab hidden), staleness detection at 60s. Follow exact pattern from `useQueueStatus.ts` (lines 96-153): `fetchInProgressRef` guard, visibility listener with 100ms debounce, cleanup on unmount.
NFR3: Async-safe database calls — paginated/aggregate Supabase queries wrapped in `asyncio.to_thread()` (pattern from `tracker.py` lines 619-658). Simple single-row lookups may call sync client directly (pattern from `pipeline.py` lines 186-209).
NFR4: Non-blocking logging — structlog DB event sink uses `collections.deque` (O(1) append) + `threading.Thread` background drain every 5s. Batch-inserts to Supabase. On DB failure: discards events, logs warning to stdout. On shutdown: flushes via `atexit` handler. Never blocks the logging pipeline.
NFR5: Sensitive data sanitization — passwords, tokens, and secrets automatically redacted (`[REDACTED]`) before writing to system_events. Pattern already exists in `celery.py` lines 434-442 (sanitizes kwargs in DLQ handler).
NFR6: Error deduplication — identical errors (same event_type + first 100 chars of message) within 60-second window deduplicated in-memory before writing to system_events.
NFR7: Cross-process logging — DB event sink initialized in API process (`main.py` line 61 calls `configure_logging()`) AND Worker processes. CRITICAL: must add `configure_logging()` call to `celery.py` at MODULE LEVEL before line 293 (where `_logger = structlog.get_logger(__name__)` caches the logger). Cannot use `@worker_ready.connect` (line 375) because `cache_logger_on_first_use=True` in `logging.py` line 131 means loggers are frozen on first `get_logger()` call. The import + call must be injected between lines 291-292 in celery.py.
NFR8: Response format consistency — all admin API endpoints return `{ data: {...} }` wrapper (pattern from `quota.py` queue-status endpoint, lines 326-399). Use Pydantic response models.
NFR9: RPC service role compatibility — `SECURITY DEFINER` RPCs must handle `auth.uid() = NULL` case (service role bypasses auth). Pattern from `20260219000005_fix_job_queue_stats_service_role.sql`. Grant `EXECUTE` to `service_role`.

### Additional Requirements (Code-Verified)

**Database (5 items):**
- Create new `system_events` table: id (uuid PK), event_type (text), level (text: INFO/WARN/ERROR/CRITICAL), message (text), source (text: 'api'/'worker'), metadata (jsonb), created_at (timestamptz DEFAULT now()). No RLS (service role only, like `audit_logs` table pattern).
- Add index `idx_job_stage_history_created_at` on `job_stage_history(created_at DESC)` — needed for bottleneck stage duration queries. Currently only has `idx_job_stage_history_job` (job_id) and `idx_job_stage_history_job_stage` (job_id, stage_name).
- Add index `idx_processing_jobs_created_at` on `processing_jobs(created_at DESC)` — needed for cross-matter time-range listing. Current indexes are matter-scoped.
- Create `get_admin_jobs_overview()` SECURITY DEFINER RPC: joins `processing_jobs → documents → public.users` (NOT `auth.users` — Gap 1). Must handle `auth.uid() = NULL`. Grant to `service_role`. Use offset-based pagination (`.range(offset, offset + limit - 1)` pattern from `tracker.py`). NOTE: `processing_jobs.document_id` is nullable (matter-level jobs have no document) — use LEFT JOIN to `documents`. Dynamic ORDER BY (sort_by + sort_dir) cannot be done reliably in SQL CASE expressions — RPC returns unsorted results, sorting done in Python application layer.
- Create `get_admin_bottleneck_stats()` SECURITY DEFINER RPC: aggregates from `job_stage_history` (stage durations via `completed_at - started_at`) and `processing_jobs` (error frequencies via first 100 chars of `error_message`). Date-range filtered. Grant to `service_role`.

**Backend (6 items):**
- New file `backend/app/api/routes/admin/operations.py`: 4 endpoints with `router = APIRouter(prefix="/admin/operations", tags=["admin-operations"])`. Each uses `Depends(require_admin_access)`. Calls RPCs via `get_service_client()` wrapped in `asyncio.to_thread()` (pattern from `admin/monitoring.py` lines 48-52). Jobs endpoint applies sort_by/sort_dir in Python after RPC returns (not in SQL). Follow `PipelineStatusResponse` Pydantic model pattern from `admin/pipeline.py`.
- New file `backend/app/core/db_event_sink.py`: structlog processor class. `__call__` appends to `collections.deque` (O(1), thread-safe). Background `threading.Thread` drains every 5s. Uses `get_service_client().table("system_events").insert([...]).execute()` — follows `audit_service.py` lines 185-217 async DB write pattern. `get_service_client()` creates new client each call (no caching), thread-safe. On DB failure: discard events + log warning to stdout. On shutdown: flush via `atexit` handler. Sanitize sensitive fields before write (pattern from `celery.py` lines 434-442).
- Modify `backend/app/core/logging.py` (line ~112): add `DatabaseEventSink()` processor BEFORE `JSONRenderer` in production processor chain.
- Modify `backend/app/workers/celery.py`: add `configure_logging()` call for worker processes (Gap 2 fix). MUST be at module level between lines 291-292 (before `_logger = structlog.get_logger(__name__)`). Cannot use `@worker_ready.connect` because `cache_logger_on_first_use=True` freezes loggers on first `get_logger()` call.
- Modify `backend/app/main.py` (line ~389): add `from app.api.routes.admin import operations as admin_operations` and `app.include_router(admin_operations.router, prefix="/api")`.
- Modify `backend/app/api/routes/admin/__init__.py`: add `from app.api.routes.admin.operations import router as operations_router` and update `__all__`.
- Stage name mapping for ALL 15 `JobType` enum values (from `backend/app/models/job.py` lines 9-44): validation, confidence, chunking, embedding, entity_extraction, alias_resolution, citation_extraction, citation_verification, contradiction_detection, date_extraction, event_classification, entity_linking, anomaly_detection, summary_generation (+ db_queries, validation_and_cache from summary_tasks.py).

**Frontend (7 items):**
- New file `frontend/src/lib/api/admin-operations.ts`: type-safe API client following `admin-queue.ts` pattern (lines 65-180). Runtime transformers with `toNumber()`/`toString()` safe converters. Handle both camelCase and snake_case. Export as `adminOperationsApi` object.
- New file `frontend/src/hooks/useOperationsDashboard.ts`: follows `useQueueStatus.ts` pattern exactly — `fetchInProgressRef` guard, `document.visibilityState` listener, `setInterval` cleanup. Manages state for all 4 tabs independently.
- New file `frontend/src/app/(dashboard)/admin/operations/page.tsx`: `'use client'` component (same pattern as `admin/usage/page.tsx`). Admin auth inherited from parent `/admin/page.tsx` server component.
- 4 tab components in `frontend/src/components/features/admin/operations/`: `JobsTable.tsx`, `BottleneckPanel.tsx`, `SystemEventsLog.tsx`, `LiveFeedPanel.tsx`.
- Use existing UI components: `Tabs`/`TabsList`/`TabsTrigger`/`TabsContent` (from `ui/tabs.tsx`), `Select`/`SelectItem` (from `ui/select.tsx`), `Badge` with `variant="destructive"` for failed status (from `ui/badge.tsx`), `Input type="date"` (from `ui/input.tsx`), `Table`/`TableHeader`/`TableRow`/`TableCell` (from `ui/table.tsx`). Recharts `^3.7.0` already in `package.json` — use `ResponsiveContainer`, `BarChart` (horizontal), `Tooltip`, `Cell` for per-bar colors (pattern from `admin/usage/page.tsx` lines 400-450). Loading states: `isLoading && !data ? spinner : error && !data ? error card : data ? content : null` (same pattern).
- Client-side CSV export: follow proven pattern from `CostReportWidget.tsx` lines 113-147 — build rows array, join with commas, create `Blob('text/csv')`, `createElement('a')`, set `download` attr, click, `revokeObjectURL`, show `toast.success`. No backend needed.
- Modify `frontend/src/app/(dashboard)/admin/page.tsx` (line ~72): add link card to `/admin/operations` (same pattern as existing Usage Dashboard link card at lines 73-88, using `Activity` lucide icon).

### FR Coverage Map

| FR | Epic | Description |
|----|------|-------------|
| FR1 | Epic 1 | Cross-matter job visibility in sortable table |
| FR2 | Epic 1 | Historical date range filtering |
| FR3 | Epic 1 | Sortable table columns (10 columns) |
| FR4 | Epic 1 | Filterable by status (Queued/Processing/Failed/Completed) |
| FR5 | Epic 1 | Filterable by pipeline stage (15+ stages) |
| FR6 | Epic 1 | Filterable by matter (dropdown of all matters) |
| FR7 | Epic 1 | Filterable by user (dropdown of all users) |
| FR8 | Epic 1 | CSV export of filtered job list |
| FR9 | Epic 2 | Bottleneck analysis — avg time per stage as bar chart |
| FR10 | Epic 2 | Top errors — most frequent error patterns |
| FR11 | Epic 2 | Queue wait analysis — avg/max wait, currently waiting |
| FR12 | Epic 2 | Page count impact — size buckets with avg processing time |
| FR13 | Epic 3 | System events log — non-pipeline errors |
| FR14 | Epic 3 | Live feed — real-time merged pipeline + system events |
| FR15 | Epic 1 | Human-readable stage names and error messages |
| FR16 | Epic 1 | Pagination for jobs table, events, and feed |

**All 16 FRs mapped. Zero gaps.**

## Epic List

### Epic 1: Cross-Matter Job Visibility

Admin can see ALL processing jobs across all users and matters in one sortable, filterable table — sort by any column, filter by status/stage/matter/user/date range, export to CSV, with human-readable names and pagination. This is the foundation epic that creates the page shell, API infrastructure, and core Jobs Table.

**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR7, FR8, FR15, FR16
**NFRs addressed:** NFR1 (admin auth), NFR2 (polling), NFR3 (async DB), NFR8 (response format), NFR9 (RPC service role)
**Standalone:** Yes — delivers complete "I can see everything" value independently.

### Epic 2: Pipeline Bottleneck Intelligence

Admin can identify which pipeline stage is the bottleneck, see the most frequent error patterns, understand queue wait times, and see how document size impacts processing — answering "why is the queue blocked?" Uses only existing tables (job_stage_history, processing_jobs). Adds the Bottleneck tab with Recharts bar charts.

**FRs covered:** FR9, FR10, FR11, FR12
**NFRs addressed:** NFR3 (async DB), NFR8 (response format), NFR9 (RPC service role)
**Requires:** Epic 1 (page shell and API client)

### Epic 3: System Health Monitoring & Live Feed

Admin can see non-pipeline system errors (deploys, Redis failures, rate limits, worker crashes, DB errors) and watch a real-time merged log of all pipeline + system activity. Most infrastructure-heavy epic — creates the system_events table, db_event_sink structlog processor, wires logging into both API and Worker processes.

**FRs covered:** FR13, FR14
**NFRs addressed:** NFR4 (non-blocking logging), NFR5 (sanitization), NFR6 (dedup), NFR7 (cross-process logging)
**Requires:** Epic 1 (page shell and API client)

### Dependency Structure

- **Epic 1** → Standalone (creates page, API infrastructure, Jobs tab)
- **Epic 2** → Requires Epic 1's page shell; uses only existing DB tables
- **Epic 3** → Requires Epic 1's page shell; creates new DB infrastructure
- **Epic 2 and Epic 3 are independent of each other** — deliverable in any order after Epic 1

---

## Epic 1: Cross-Matter Job Visibility

### Story 1.1: Jobs Overview Database & API

**As an** admin,
**I want** a backend API that returns all processing jobs across all users and matters with pagination,
**So that** I have the data foundation for the operations dashboard.

**Acceptance Criteria:**

**Given** no indexes exist on `processing_jobs(created_at)` or `job_stage_history(created_at)`
**When** the migration runs
**Then** `idx_processing_jobs_created_at` and `idx_job_stage_history_created_at` indexes are created (both `DESC`)

**Given** the `get_admin_jobs_overview()` RPC is created
**When** called via service role
**Then** it returns `processing_jobs` LEFT JOINed to `documents` (filename, page_count) and `public.users` (email), LEFT JOINed to `matters` (title), with offset-based pagination
**And** handles `auth.uid() = NULL` for service role (pattern from `20260219000005_fix_job_queue_stats_service_role.sql`)
**And** jobs with null `document_id` (matter-level jobs) return null document/user fields
**And** accepts filter params: `p_status`, `p_stage`, `p_matter_id`, `p_user_email`, `p_date_from`, `p_date_to`, `p_limit`, `p_offset`
**And** returns total count alongside paginated results

**Given** an authenticated admin calls `GET /api/admin/operations/jobs`
**When** providing optional query params: `status`, `stage`, `matter_id`, `user_email`, `date_from`, `date_to`, `sort_by`, `sort_dir`, `limit` (default 50), `offset` (default 0)
**Then** returns `{ data: { jobs: [...], total: N, limit: N, offset: N } }` with Pydantic response model
**And** each job includes computed fields: `queue_wait_seconds` (started_at - created_at), `processing_seconds` (completed_at - started_at, or now - started_at if active), `status_display` ("Retry 2 of 3" / "Failed" / "Done"), `stage_display` (human-readable from stage mapping)
**And** sorting is applied in Python after RPC returns (not in SQL)
**And** the endpoint uses `Depends(require_admin_access)` and calls RPC via `asyncio.to_thread()`

**Given** a non-admin user calls the endpoint
**When** the request is processed
**Then** returns 403 Forbidden

**Technical notes:**
- New file: `supabase/migrations/YYYYMMDD_add_operations_dashboard.sql` — indexes + `get_admin_jobs_overview()` RPC (SECURITY DEFINER, GRANT EXECUTE to service_role)
- New file: `backend/app/api/routes/admin/operations.py` — `router = APIRouter(prefix="/admin/operations", tags=["admin-operations"])`
- Modify: `backend/app/main.py` (~line 389) — `app.include_router(admin_operations.router, prefix="/api")`
- Modify: `backend/app/api/routes/admin/__init__.py` — add `operations_router` export
- Stage name mapping constant: all 15 `JobType` enum values (from `backend/app/models/job.py` lines 9-44) + `db_queries`, `validation_and_cache` from summary_tasks.py. IMPORTANT: stage names are stored LOWERCASE in DB (e.g., `"entity_extraction"` not `"ENTITY_EXTRACTION"`) — mapping keys must match lowercase values.
- RPC must use selective column queries (not `SELECT *`) to reduce Supabase egress — follow `JOB_LIST_COLUMNS` / `JOB_LIST_ITEM_COLUMNS` pattern from `tracker.py`. Only select: `processing_jobs(id, status, current_stage, error_message, retry_count, max_retries, created_at, started_at, completed_at, metadata)`, `documents(filename, page_count)`, `public.users(email)`, `matters(title)`.
- No overlap with existing endpoints: `queue-status` (aggregate Celery health), `chunk-metrics` (per-matter chunks), `quality-metrics` (RAG quality), `pipeline/*` (trigger/retry). This is the first cross-matter individual-job-level admin view.
- Pattern references: `admin/monitoring.py` lines 48-52 (asyncio.to_thread RPC call), `admin/pipeline.py` (Pydantic response models), `20260219000005` (service role RPC pattern)

---

### Story 1.2: Operations Dashboard Page Shell & Jobs Table

**As an** admin,
**I want** to navigate to `/admin/operations` and see a table of all processing jobs with pagination and human-readable names,
**So that** I can see what's happening across the entire system at a glance.

**Acceptance Criteria:**

**Given** an admin is on the admin dashboard (`/admin`)
**When** they see the dashboard
**Then** an "Operations Dashboard" link card is visible (using `Activity` lucide icon, same pattern as Usage Dashboard card at lines 73-88)
**And** clicking it navigates to `/admin/operations`

**Given** an admin navigates to `/admin/operations`
**When** the page loads
**Then** they see 4 tabs: Jobs (active by default), Bottleneck, System Events, Live Feed
**And** the last 3 tabs show "Coming soon" placeholder content
**And** the Jobs tab shows a loading spinner while data fetches

**Given** the Jobs table has loaded data
**When** data is displayed
**Then** the table shows columns: Document (filename + page count), Matter (title), User (email), Status, Stage, Queue Wait, Processing Time, Retries, Error, Created At
**And** stage names show human-readable labels (e.g., "Extracting entities" not "entity_extraction")
**And** status shows formatted display (e.g., "Retry 2 of 3", "Failed — gave up", "Done in 3 min")
**And** failed jobs show `Badge variant="destructive"`
**And** queue wait and processing time show human-readable durations ("5 min", "2 hr 10 min", "12 min so far")

**Given** more than 50 jobs exist
**When** viewing the jobs table
**Then** pagination controls show "Showing 1-50 of N jobs" with Prev/Next buttons
**And** clicking Next loads the next page

**Given** the page is visible
**When** 30 seconds elapse
**Then** data refreshes automatically via polling
**And** polling pauses when tab is hidden (`document.visibilityState`)
**And** a staleness indicator shows if data is >60s old

**Given** the API returns an error
**When** no previous data exists
**Then** an error card is displayed with retry option

**Technical notes:**
- New file: `frontend/src/app/(dashboard)/admin/operations/page.tsx` — `'use client'` component (pattern from `admin/usage/page.tsx`)
- New file: `frontend/src/lib/api/admin-operations.ts` — type-safe API client with `toNumber()`/`toString()` runtime transformers, camelCase/snake_case handling, export as `adminOperationsApi` object
- New file: `frontend/src/hooks/useOperationsDashboard.ts` — `fetchInProgressRef` guard, `document.visibilityState` listener with 100ms debounce, `setInterval` cleanup, `isMountedRef` (pattern from `useQueueStatus.ts` lines 96-153)
- New file: `frontend/src/components/features/admin/operations/JobsTable.tsx`
- Modify: `frontend/src/app/(dashboard)/admin/page.tsx` (~line 72) — add link card
- Uses: `Table`/`TableHeader`/`TableRow`/`TableHead`/`TableCell` (from `ui/table.tsx`), `Badge` (from `ui/badge.tsx`), `Tabs`/`TabsList`/`TabsTrigger`/`TabsContent` (from `ui/tabs.tsx`)
- Loading pattern: `isLoading && !data ? spinner : error && !data ? error card : data ? content : null`

---

### Story 1.3: Jobs Table Sorting, Filtering & CSV Export

**As an** admin,
**I want** to sort by any column, filter by status/stage/matter/user/date range, and export the filtered list as CSV,
**So that** I can investigate specific problems and share reports.

**Acceptance Criteria:**

**Given** the jobs table is displayed
**When** the admin clicks a column header
**Then** the table sorts by that column ascending
**And** clicking the same header again reverses to descending
**And** a sort indicator (arrow icon) shows on the active column

**Given** the filter bar is visible above the table
**When** the admin selects Status = "Failed" from the Status dropdown
**Then** only failed jobs are shown
**And** the total count and pagination update to reflect the filter

**Given** the Stage filter dropdown
**When** opened
**Then** lists all 15+ pipeline stages with human-readable names (same mapping as table display)
**And** selecting a stage filters to jobs currently at or completed that stage

**Given** the Matter filter dropdown
**When** opened
**Then** lists all matters across the system (populated from jobs data or a separate lookup)
**And** selecting a matter filters to only that matter's jobs

**Given** the User filter dropdown
**When** opened
**Then** lists all users who have uploaded documents (populated from jobs data)
**And** selecting a user filters to only that user's jobs

**Given** date range inputs (From / To) using `Input type="date"`
**When** the admin sets a date range
**Then** only jobs with `created_at` within that range are shown
**And** defaults to last 7 days on initial load

**Given** multiple filters are applied simultaneously
**When** viewing the table
**Then** all filters combine with AND logic
**And** clearing a filter re-fetches with remaining filters

**Given** filters are applied and results are visible
**When** the admin clicks "Export CSV"
**Then** a CSV file downloads containing all currently visible columns and rows
**And** filename includes the current date (e.g., `operations-jobs-2026-03-02.csv`)
**And** uses Blob+download pattern from `CostReportWidget.tsx` lines 113-147
**And** a success toast appears via `sonner`

**Given** no jobs match the current filters
**When** viewing the table
**Then** an empty state message shows "No jobs match the current filters"

**Technical notes:**
- Sorting: client-side on current page data (sort_by/sort_dir state in hook, applied before render)
- Filtering: params sent to API on each fetch cycle (status, stage, matter_id, user_email, date_from, date_to)
- Filter dropdowns: `Select`/`SelectTrigger`/`SelectContent`/`SelectItem` from `ui/select.tsx`
- Date inputs: `Input type="date"` from `ui/input.tsx`
- CSV export: build rows array from current data, `new Blob([csvString], { type: 'text/csv' })`, `createElement('a')`, `a.download = filename`, `a.click()`, `URL.revokeObjectURL()`, `toast.success("CSV exported")`
- Filter state managed in `useOperationsDashboard.ts` hook, persisted across tab switches

---

## Epic 2: Pipeline Bottleneck Intelligence

### Story 2.1: Bottleneck Stats Database & API

**As an** admin,
**I want** an API that returns pipeline stage duration averages, error frequencies, queue wait stats, and page count impact,
**So that** I can identify root causes of queue congestion.

**Acceptance Criteria:**

**Given** the `get_admin_bottleneck_stats()` RPC is created as SECURITY DEFINER
**When** called with date range params (`p_date_from`, `p_date_to`)
**Then** returns four result sets:
1. Stage durations: average `completed_at - started_at` per `stage_name` from `job_stage_history` (only COMPLETED stages), ordered by duration descending
2. Error frequencies: top errors grouped by first 100 chars of `error_message` from `processing_jobs` where status='FAILED', with occurrence count and most recent `created_at`
3. Queue wait stats: average and max `started_at - created_at` from `processing_jobs`, the document name with longest wait, and count where status='QUEUED' (currently waiting)
4. Page count buckets: group `documents.page_count` into ranges (<50, 50-100, >100) with document count and avg processing time per bucket via JOIN to `processing_jobs`
**And** handles `auth.uid() = NULL` for service role
**And** is granted EXECUTE to `service_role`

**Given** an authenticated admin calls `GET /api/admin/operations/bottlenecks`
**When** providing optional `date_from` and `date_to` (default last 7 days)
**Then** returns `{ data: { stage_durations: [...], top_errors: [...], queue_wait: { avg_seconds, max_seconds, max_wait_document, currently_waiting }, page_count_impact: [...] } }`
**And** the longest-duration stage is flagged with `is_bottleneck: true`
**And** the endpoint uses `Depends(require_admin_access)` and `asyncio.to_thread()`

**Given** a non-admin user calls the endpoint
**When** the request is processed
**Then** returns 403 Forbidden

**Technical notes:**
- Add `get_admin_bottleneck_stats()` to the same migration file as Story 1.1 (`YYYYMMDD_add_operations_dashboard.sql`)
- Add `/bottlenecks` endpoint to existing `backend/app/api/routes/admin/operations.py`
- RPC uses `job_stage_history` index `idx_job_stage_history_created_at` (created in Story 1.1)
- Queue wait: `EXTRACT(EPOCH FROM (started_at - created_at))` for seconds
- Page count impact: LEFT JOIN `processing_jobs` to `documents` on `document_id`, group by CASE buckets
- Pattern: `admin/monitoring.py` lines 48-52 for asyncio.to_thread RPC call

---

### Story 2.2: Bottleneck Analysis Panel

**As an** admin,
**I want** a visual bottleneck analysis tab showing bar charts, error tables, and stats cards,
**So that** I can quickly see why the queue is blocked and which stage is the bottleneck.

**Acceptance Criteria:**

**Given** an admin clicks the "Bottleneck" tab on the operations dashboard
**When** data loads
**Then** shows 4 sections stacked vertically:

**Section 1 — Stage Duration:**
**Given** stage duration data is available
**When** rendered
**Then** shows a horizontal `BarChart` (Recharts `ResponsiveContainer` + `BarChart` with `layout="vertical"`) with avg time per stage in minutes
**And** the bottleneck stage (longest duration) bar is highlighted in red, others in blue
**And** each bar shows the avg duration label (e.g., "12 min avg")

**Section 2 — Top Errors:**
**Given** error frequency data is available
**When** rendered
**Then** shows a table with columns: Error Pattern, Occurrences, Last Seen
**And** rows are ordered by occurrence count descending
**And** error patterns are truncated at 80 chars with tooltip for full text

**Section 3 — Queue Wait:**
**Given** queue wait stats are available
**When** rendered
**Then** shows 3 stats cards in a row: "Average Wait" (e.g., "8 minutes"), "Longest Wait" (e.g., "45 min — Contract.pdf, 120 pages"), "Waiting Now" (e.g., "3 documents")
**And** uses `Card` component from `ui/card.tsx`

**Section 4 — Page Count Impact:**
**Given** page count impact data is available
**When** rendered
**Then** shows a table with 3 rows: "<50 pages", "50-100 pages", ">100 pages"
**And** columns: Document Count, Avg Processing Time
**And** the row with highest avg time is visually highlighted

**Given** a date range picker at the top of the panel
**When** the admin changes the date range
**Then** all 4 sections re-fetch and update
**And** default range is last 7 days

**Given** the API returns an error or no data for the selected range
**When** viewing any section
**Then** that section shows an appropriate empty state ("No data for this date range")

**Technical notes:**
- New file: `frontend/src/components/features/admin/operations/BottleneckPanel.tsx`
- Replace "Coming soon" placeholder in Bottleneck tab (from Story 1.2)
- Recharts `^3.7.0`: `ResponsiveContainer`, `BarChart`, `Bar`, `XAxis`, `YAxis`, `Tooltip`, `Cell` for per-bar colors (pattern from `admin/usage/page.tsx` lines 400-450)
- Stats cards: `Card`/`CardHeader`/`CardTitle`/`CardContent` from `ui/card.tsx`, responsive grid `grid gap-4 sm:grid-cols-3`
- Date range: reuse same `Input type="date"` pattern from Story 1.3
- Add `getBottlenecks(dateRange)` to `adminOperationsApi` in `admin-operations.ts`
- Add bottleneck state management to `useOperationsDashboard.ts` hook

---

## Epic 3: System Health Monitoring & Live Feed

### Story 3.1: System Events Infrastructure — Table, Logging Sink & Worker Wiring

**As an** admin,
**I want** the system to automatically capture non-pipeline errors (deploys, Redis failures, rate limits, worker crashes) into a database table,
**So that** I can later view them on the dashboard.

**Acceptance Criteria:**

**Given** the migration runs
**When** `system_events` table is created
**Then** it has columns: `id` (uuid PK, default gen_random_uuid()), `event_type` (text NOT NULL), `level` (text NOT NULL, check IN ('INFO','WARN','ERROR','CRITICAL')), `message` (text NOT NULL), `source` (text NOT NULL, check IN ('api','worker')), `metadata` (jsonb DEFAULT '{}'), `created_at` (timestamptz DEFAULT now())
**And** no RLS is enabled (service role only, like `audit_logs` pattern)
**And** index `idx_system_events_created_at` on `created_at DESC`

**Given** `db_event_sink.py` is created as a structlog processor class
**When** a structlog event at ERROR or CRITICAL level is logged in any process
**Then** the event is appended to an in-memory `collections.deque` (O(1), thread-safe)
**And** a background `threading.Thread` (daemon=True) drains the deque every 5 seconds
**And** drained events are batch-inserted to `system_events` via `get_service_client().table("system_events").insert([...]).execute()`

**Given** sensitive data appears in a log event's kwargs
**When** the sink processes it
**Then** fields matching patterns (password, token, secret, authorization, api_key) are replaced with `[REDACTED]` before writing (pattern from `celery.py` lines 434-442)

**Given** the same error (same `event_type` + first 100 chars of `message`) occurs twice within 60 seconds
**When** the sink processes the second occurrence
**Then** it is deduplicated in-memory (not written to DB)

**Given** the database insert fails
**When** the background thread attempts to drain
**Then** events are discarded (not re-queued), a warning is logged to stdout via `print()` (not structlog, to avoid recursion)
**And** the structlog logging pipeline is never blocked

**Given** the process is shutting down
**When** the `atexit` handler fires
**Then** remaining events in the deque are flushed to DB (best-effort)

**Given** the API process starts
**When** `configure_logging()` is called from `main.py` line 61
**Then** the `DatabaseEventSink` processor is inserted BEFORE `JSONRenderer` in the production processor chain (`logging.py` ~line 112)

**Given** the Worker process starts
**When** `celery.py` module loads
**Then** `configure_logging()` is called at module level between lines 291-292 (BEFORE `_logger = structlog.get_logger(__name__)`)
**And** the DB event sink is active for all subsequent worker log events
**And** this MUST be module-level because `cache_logger_on_first_use=True` (logging.py line 131) freezes loggers on first `get_logger()` call

**Technical notes:**
- Add `system_events` CREATE TABLE to migration file from Story 1.1 (`YYYYMMDD_add_operations_dashboard.sql`)
- New file: `backend/app/core/db_event_sink.py` — class `DatabaseEventSink` with `__call__(self, logger, method_name, event_dict)` structlog processor interface, `collections.deque` buffer, `threading.Thread` drain loop, `atexit.register` flush, sanitization regex, dedup dict with 60s TTL
- Modify: `backend/app/core/logging.py` (~line 112) — add `DatabaseEventSink()` to `shared_processors` list or production-only processors BEFORE `JSONRenderer`
- Modify: `backend/app/workers/celery.py` — add `from app.core.logging import configure_logging` + `configure_logging()` at module level between lines 291-292 (before `_logger = structlog.get_logger(__name__)`)
- Pattern references: `audit_service.py` lines 185-217 (DB write pattern), `celery.py` lines 434-442 (sanitization), `logging.py` line 131 (`cache_logger_on_first_use=True`)
- Thread safety: `get_service_client()` creates new client each call (no caching), safe for background thread in gevent worker

---

### Story 3.2: System Events API & Log Panel

**As an** admin,
**I want** to view non-pipeline system errors on the System Events tab with date filtering and pagination,
**So that** I can investigate infrastructure issues like worker crashes, Redis failures, rate limits, and deploys.

**Acceptance Criteria:**

**Given** an authenticated admin calls `GET /api/admin/operations/events`
**When** providing optional params: `date_from`, `date_to`, `level` (INFO/WARN/ERROR/CRITICAL — filters to that level and above), `limit` (default 50), `offset` (default 0)
**Then** returns `{ data: { events: [...], total: N, limit: N, offset: N } }` queried from `system_events` table
**And** events are ordered by `created_at DESC`
**And** uses `Depends(require_admin_access)` and `asyncio.to_thread()`

**Given** a non-admin user calls the endpoint
**When** the request is processed
**Then** returns 403 Forbidden

**Given** an admin clicks the "System Events" tab on the operations dashboard
**When** data loads
**Then** shows a chronological list of events with columns: Timestamp (formatted as "Mar 2, 10:45 AM"), Level (badge colored by severity: INFO=default, WARN=yellow/outline, ERROR=destructive, CRITICAL=destructive+bold), Source (api/worker as small badge), Message (event text)

**Given** the level filter dropdown
**When** the admin selects "ERROR"
**Then** only ERROR and CRITICAL events are shown

**Given** the date range picker
**When** the admin adjusts the date range
**Then** the events list re-fetches with the new range
**And** pagination resets to page 1

**Given** an event row with metadata
**When** the admin clicks the row to expand it
**Then** the metadata JSON is displayed in a formatted expandable section below the row

**Given** more than 50 events exist
**When** viewing the list
**Then** pagination shows "Showing 1-50 of N events" with Prev/Next buttons

**Technical notes:**
- Add `GET /events` endpoint to `backend/app/api/routes/admin/operations.py`
- New file: `frontend/src/components/features/admin/operations/SystemEventsLog.tsx`
- Replace "Coming soon" placeholder in System Events tab (from Story 1.2)
- Add `getEvents(filters)` to `adminOperationsApi` in `admin-operations.ts`
- Add events state + pagination to `useOperationsDashboard.ts` hook
- Level filter: `Select` component with "All", "INFO", "WARN", "ERROR", "CRITICAL" options
- Expandable rows: use `useState` for expanded row ID, render metadata section conditionally

---

### Story 3.3: Live Feed Panel

**As an** admin,
**I want** a real-time scrolling feed that merges pipeline stage changes and system events by timestamp,
**So that** I can watch what's happening across the system right now.

**Acceptance Criteria:**

**Given** an authenticated admin calls `GET /api/admin/operations/feed`
**When** providing `limit` (default 50) and optional `since` (ISO timestamp for incremental polling)
**Then** returns `{ data: { items: [...] } }` where items are merged from:
1. `job_stage_history` rows (type: "pipeline") — includes stage_name, status, joined document filename, joined matter title, timestamp = `started_at` or `completed_at`
2. `system_events` rows (type: "system") — includes event_type, level, message, timestamp = `created_at`
**And** items are sorted by timestamp descending (most recent first)
**And** when `since` is provided, only items newer than that timestamp are returned
**And** uses `Depends(require_admin_access)` and `asyncio.to_thread()`

**Given** an admin clicks the "Live Feed" tab
**When** data loads
**Then** shows a scrolling list of feed items, each displaying:
- Relative timestamp ("2 min ago", "just now")
- Type icon (pipeline items = gear/cog icon, system items = alert-triangle icon)
- Human-readable message (pipeline: "Affidavit.pdf → Embedding completed in Smith v Jones", system: "Worker crashed: out of memory")
- Color coding (pipeline completed=green, pipeline failed=red, system error=red, system warn=yellow, info=neutral)

**Given** the feed is visible and 30 seconds elapse
**When** a poll cycle runs
**Then** new items are fetched using `since` = timestamp of the most recent displayed item
**And** new items are prepended to the top of the feed list
**And** polling pauses when the browser tab is hidden (`document.visibilityState`)

**Given** the admin scrolls down in the feed
**When** they reach the bottom of the currently loaded items
**Then** a "Load more" button fetches the next page of historical items (offset-based)

**Given** no new events have occurred since the last poll
**When** a poll cycle completes with 0 new items
**Then** no visual change occurs (no flicker, no empty state flash, feed stays as-is)

**Given** the feed has items from both pipeline and system sources
**When** displayed
**Then** they are interleaved by timestamp (not grouped by source)

**Technical notes:**
- Add `GET /feed` endpoint to `backend/app/api/routes/admin/operations.py`
- Backend: query `job_stage_history` (JOIN `processing_jobs` → `documents` → `matters` for context) UNION with `system_events`, both filtered by timestamp, ORDER BY timestamp DESC, LIMIT
- For pipeline items: build message from stage_name + status + document filename + matter title using the stage name mapping from Story 1.1
- New file: `frontend/src/components/features/admin/operations/LiveFeedPanel.tsx`
- Replace "Coming soon" placeholder in Live Feed tab (from Story 1.2)
- Add `getLiveFeed(since, limit)` to `adminOperationsApi` in `admin-operations.ts`
- Add feed state (items array + latestTimestamp) to `useOperationsDashboard.ts` — incremental: each poll appends, doesn't replace
- Relative timestamps: compute from `Date.now() - item.timestamp`, update on render (or use a small helper)
- Lucide icons: `Cog` for pipeline, `AlertTriangle` for system events
