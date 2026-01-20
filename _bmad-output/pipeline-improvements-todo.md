# Pipeline Improvements TODO

## Summary of Issues Found
- Chunk 33 got stuck in "processing" with no auto-recovery
- Job stuck at 100% - merge never triggered after all chunks completed
- Entity extraction failed silently due to missing Gemini config
- Bbox linking is extremely slow (O(n²) with 29K boxes)
- Strict status dependencies block pipeline even when data is available
- No manual triggers for stuck tasks
- Recovery mechanisms exist but aren't scheduled

---

## Category 1: Manual Triggers & Admin API

### 1.1 Create Admin Pipeline Trigger Endpoints ✅ DONE
**Priority**: HIGH | **Effort**: Medium
**File**: `app/api/routes/admin/pipeline.py` (new)

- [x] POST `/admin/pipeline/documents/{document_id}/trigger/{task_name}` - Trigger any task manually
- [x] POST `/admin/pipeline/documents/{document_id}/retry-failed` - Retry all failed tasks
- [x] POST `/admin/pipeline/documents/{document_id}/reset-status` - Reset document to specific status
- [x] GET `/admin/pipeline/documents/{document_id}/pipeline-status` - Show status of all pipeline stages
- [x] POST `/admin/pipeline/matters/{matter_id}/reprocess-stuck` - Find and reprocess stuck documents

**Implemented**: Created `app/api/routes/admin/pipeline.py` with all 5 endpoints. All endpoints require admin access via `require_admin_access` dependency. Supports 14 pipeline tasks (process_document, chunk_document, extract_entities, etc.).

### 1.2 Add Force Flag to All Tasks ✅ DONE
**Priority**: HIGH | **Effort**: Low
**Files**: `app/workers/tasks/document_tasks.py`, `app/workers/tasks/engine_tasks.py`

- [x] Add `force: bool = False` parameter to all task functions
- [x] When `force=True`, skip status validation checks
- [x] Log when force mode is used for audit trail

**Implemented**: Added `force` parameter to `extract_entities`, `chunk_document`, and `embed_chunks` tasks with audit logging.

---

## Category 2: Parallel Processing

### 2.1 Dispatch Independent Tasks in Parallel After OCR ✅ DONE
**Priority**: HIGH | **Effort**: Medium
**File**: `app/workers/tasks/chunked_document_tasks.py`

- [x] After OCR completes, dispatch these in parallel:
  - `chunk_document` (needed for search)
  - `extract_entities` (can work on raw text)
  - `extract_dates_from_document` (can work on raw text)
  - `extract_citations` (can work on raw text)
- [x] Use Celery `group()` for parallel dispatch
- [x] Each task updates its own feature flag independently

**Implemented**:
- Created `_trigger_parallel_processing()` function that dispatches 4 tasks in parallel
- Replaces old `_trigger_rag_reprocessing()` (kept for backward compat)
- Each task dispatched independently with try/catch for graceful degradation
- Uses `skip_bbox_linking=True` for chunk_document for faster search availability
- Uses `force=True` for extract_entities to skip status validation
- Returns dict with triggered/failed task lists for monitoring

### 2.2 Make Entity Extraction Work on Raw Text ✅ DONE
**Priority**: MEDIUM | **Effort**: Medium
**File**: `app/workers/tasks/document_tasks.py`

- [x] Add fallback: if no chunks exist, extract from `extracted_text` directly
- [x] Split raw text into windows for batch processing
- [x] This allows entity extraction before chunking completes

**Implemented**:
- When no chunks found, falls back to document's `extracted_text`
- Splits raw text into 8000-char windows (~2000 tokens) with 500-char overlap
- Each window processed like a chunk for entity extraction
- Returns `used_raw_text_fallback: true` in result when fallback is used
- Enables parallel entity extraction with chunking (runs before chunks are created)

### 2.3 Decouple Bbox Linking from Chunking ✅ DONE
**Priority**: MEDIUM | **Effort**: Low
**File**: `app/workers/tasks/document_tasks.py`

- [x] Make bbox linking optional/async
- [x] Save chunks first, then link bboxes in background
- [x] User can search immediately, bbox highlighting comes later

**Implemented**:
- Added `skip_bbox_linking: bool = False` parameter to `chunk_document` task
- Created new `link_chunks_to_bboxes_task` Celery task that can run independently
- Added `LINK_BBOXES` to admin API's `PipelineTask` enum for manual triggering
- When `skip_bbox_linking=True`, chunks are saved immediately, bbox linking can be done later via background task or manual trigger

---

## Category 3: Remove Blocking Dependencies

### 3.1 Relax Status Check in extract_entities ✅ DONE
**Priority**: HIGH | **Effort**: Low
**File**: `app/workers/tasks/document_tasks.py` (line ~2390)

- [x] Accept any non-failed status OR check if chunks/text exist
- [x] Only skip if previous explicitly failed
- [x] Add `force` parameter to bypass entirely

**Implemented**: Expanded valid statuses to include `ocr_complete`, `chunking_complete`, `validated`, etc. Now only skips on explicit failure statuses. Added `force` parameter.

### 3.2 Relax Status Check in chunk_document ✅ DONE
**Priority**: HIGH | **Effort**: Low
**File**: `app/workers/tasks/document_tasks.py` (line ~1810)

- [x] Accept `ocr_complete` as valid (most common case)
- [x] Check if `extracted_text` exists rather than status
- [x] Add `force` parameter

**Implemented**: Added `ocr_complete` to valid statuses. Now only skips on explicit failure statuses. Added `force` parameter with audit logging.

### 3.3 Relax Status Check in embed_chunks ✅ DONE
**Priority**: MEDIUM | **Effort**: Low

- [x] Check if chunks exist rather than strict status
- [x] Add `force` parameter

**Implemented**: Added `ocr_complete` and `searchable` to valid statuses. Now only skips on explicit failure statuses. Added `force` parameter with audit logging.

---

## Category 4: Enable Recovery Mechanisms

### 4.1 Schedule Recovery Tasks in Celery Beat ✅ DONE
**Priority**: HIGH | **Effort**: Low
**File**: `app/workers/celery.py`

- [x] Add `recover_stale_chunks` to beat_schedule (every 60s)
- [x] Add `trigger_pending_merges` to beat_schedule (every 120s)
- [x] Add `recover_stale_jobs` to beat_schedule (every 5 min)

**Already Implemented**: All three tasks are registered in `celery.py` beat_schedule (lines 81-97).

### 4.2 Add Heartbeat Calls During Long Operations ✅ DONE
**Priority**: MEDIUM | **Effort**: Low
**File**: `app/workers/tasks/chunked_document_tasks.py`

- [x] Call `update_heartbeat()` after each major step in `process_single_chunk`:
  - After status update to PROCESSING (line 546)
  - After PDF download (line 560)
  - Before OCR call (line 578)
  - After OCR completes (line 587)

**Already Implemented**: Heartbeat calls are in place at key points in `process_single_chunk`. The `OCRChunkService.update_heartbeat()` method updates `processing_started_at` timestamp.

### 4.3 Implement Stale Detection Threshold Config ✅ DONE
**Priority**: LOW | **Effort**: Low
**File**: `app/core/config.py`

- [x] Add `CHUNK_STALE_THRESHOLD_SECONDS = 90` (configurable)
- [x] Add `JOB_STALE_THRESHOLD_SECONDS = 300` (configurable)

**Implemented**:
- Added `chunk_stale_threshold_seconds` (default 90s) to config
- Added `chunk_recovery_enabled` master switch
- Added `chunk_max_recovery_retries` (default 3)
- Updated `ocr_chunk_service.detect_stale_chunks()` to use config
- Updated `chunk_recovery_service` to use config for max retries
- Updated `health.py` pipeline endpoint to use config threshold
- Note: Job stale timeout already existed as `job_stale_timeout_minutes`

---

## Category 5: Configuration & Validation

### 5.1 Validate Gemini Config on Startup ✅ DONE
**Priority**: HIGH | **Effort**: Low
**File**: `app/core/config.py` or `app/main.py`

- [x] Check `GEMINI_API_KEY` is set
- [x] Validate `GEMINI_MODEL` against available models list
- [x] Log warning (not error) if not configured - don't block startup
- [ ] Add health check endpoint for config status

**Implemented**:
- Added `is_gemini_configured` and `is_openai_configured` properties to Settings class
- Added startup warnings in `main.py` lifespan handler
- Fixed default `gemini_model` from invalid `gemini-3-flash` to `gemini-2.0-flash`

### 5.2 Update .env.example with All Required Variables ✅ DONE
**Priority**: MEDIUM | **Effort**: Low
**File**: `.env.example`

- [x] Add `GEMINI_API_KEY=` with comment
- [x] Add `GEMINI_MODEL=gemini-2.0-flash` with comment about valid models
- [x] Document which features require which keys

**Implemented**: Added Gemini configuration section to `.env.example` with API key, model selection, and links to documentation.

### 5.3 Add Pipeline Health Check Endpoint ✅ DONE
**Priority**: MEDIUM | **Effort**: Medium
**File**: `app/api/routes/health.py`

- [x] GET `/health/pipeline` returns:
  - `gemini_configured`: bool
  - `gemini_model`: string (if configured)
  - `openai_configured`: bool
  - `cohere_configured`: bool
  - `documentai_configured`: bool
  - `stale_chunks_count`: int
  - `pending_merges_count`: int
  - `stuck_jobs_count`: int
  - `processing_jobs_count`: int
  - `status`: "healthy" | "degraded" | "warning"

**Implemented**: Added `/api/health/pipeline` endpoint that checks LLM configuration and counts stuck processing jobs/chunks.

---

## Category 6: Performance Optimizations

### 6.1 Optimize Bbox Linking (O(n²) → O(n)) ✅ DONE
**Priority**: MEDIUM | **Effort**: High
**File**: `app/services/chunking/bbox_linker.py`

**Implemented**:
- [x] Created `BboxPageIndex` class that pre-indexes bboxes by page number
- [x] Added `estimate_pages_for_chunk()` to identify candidate pages (typically 1-3) using quick fuzzy match
- [x] Added `get_bboxes_for_pages()` to retrieve only relevant bboxes
- [x] Added `_link_chunk_with_page_index()` for optimized O(n) linking
- [x] Modified `link_chunks_to_bboxes()` to use page index by default (controllable via `use_optimized` flag)
- [x] Added performance logging (load_time, link_time, avg_per_chunk_ms)

**Optimization Details**:
- Before: Each chunk scanned all 29K bboxes → O(n * m) where n=chunks, m=bboxes
- After: Each chunk scans only bboxes on 1-3 candidate pages → O(n * p) where p≈100-500 bboxes/page
- Coarse-then-fine search: Initial search with larger step size, then refine around best match
- All 45 chunking tests pass

### 6.2 Batch Entity Saves ✅ DONE
**Priority**: LOW | **Effort**: Medium
**File**: `app/services/mig/graph.py`

**Implemented**:
- [x] Added `_save_entities_batch()` method that batches all DB operations
- [x] Added `_batch_find_existing_entities()` - single query to find all existing entities
- [x] Added `_batch_create_entities()` - single insert for all new entities
- [x] Added `_batch_update_mention_counts()` - concurrent updates using asyncio.gather
- [x] Added `_batch_insert_mentions()` - single insert for all mentions

**Optimization Details**:
- Before: N entities = N queries (find) + N inserts/updates + N*M mention inserts
- After: N entities = 1 query (find all) + 1 batch insert (new) + concurrent updates + 1 batch mention insert
- All 16 MIG graph tests pass

---

## Category 7: Progressive UI Updates

### 7.1 Broadcast Feature Availability ✅ DONE
**Priority**: MEDIUM | **Effort**: Medium
**File**: `app/services/pubsub_service.py`

**Implemented**:
- [x] Added `FeatureType` class with constants: SEARCH, SEMANTIC_SEARCH, ENTITIES, TIMELINE, CITATIONS, BBOX_HIGHLIGHTING
- [x] Added `broadcast_feature_ready()` function for single feature broadcasts
- [x] Added `broadcast_features_batch()` function for bulk feature state updates
- [x] Added feature broadcasts to all relevant task completion points:
  - `search` - after chunking completes (document_tasks.py)
  - `semantic_search` - after embedding completes (document_tasks.py)
  - `entities` - after entity extraction completes (document_tasks.py)
  - `timeline` - after date extraction completes (engine_tasks.py)
  - `citations` - after citation extraction completes (document_tasks.py)
  - `bbox_highlighting` - after bbox linking completes (document_tasks.py)

**Channel Pattern**: `features:{matter_id}:document:{document_id}`
**Event Types**: `feature_ready` (single), `features_update` (batch)

### 7.2 Add Feature Flags to Document Response ✅ DONE
**Priority**: MEDIUM | **Effort**: Low
**File**: `app/api/routes/documents.py`

- [x] Add to document response:
  ```json
  {
    "features": {
      "search": true,
      "semantic_search": false,
      "entities": true,
      "timeline": false,
      "citations": false,
      "bboxHighlighting": false
    }
  }
  ```

**Implemented**:
- Created `DocumentFeatures` model in `app/models/document.py` with 6 feature flags
- Created `DocumentWithFeatures` model extending `Document` to include features
- Updated `DocumentDetailResponse` to use `DocumentWithFeatures`
- Added `_get_document_features()` helper function that queries database for:
  - `search`: Checks if `document_chunks` exist
  - `semantic_search`: Checks if chunks have embeddings (non-null)
  - `entities`: Checks if `identity_nodes` exist
  - `timeline`: Checks if `timeline_events` exist
  - `citations`: Checks if `citations` exist
  - `bbox_highlighting`: Checks if `chunk_bounding_boxes` exist
- Updated `get_document` and `update_document` endpoints to include features

---

## Implementation Order (Suggested)

### Phase 1: Quick Wins (1-2 days)
1. 4.1 - Schedule recovery tasks in Celery Beat
2. 3.1 - Relax status check in extract_entities
3. 3.2 - Relax status check in chunk_document
4. 1.2 - Add force flag to tasks
5. 5.1 - Validate Gemini config on startup

### Phase 2: Manual Controls (2-3 days)
1. 1.1 - Create admin pipeline trigger endpoints
2. 5.3 - Add pipeline health check endpoint
3. 4.2 - Add heartbeat calls

### Phase 3: Parallelization (3-5 days)
1. 2.1 - Dispatch independent tasks in parallel
2. 2.3 - Decouple bbox linking from chunking
3. 2.2 - Make entity extraction work on raw text

### Phase 4: Polish (2-3 days)
1. 7.1 - Broadcast feature availability
2. 7.2 - Add feature flags to document response
3. 6.1 - Optimize bbox linking
4. 5.2 - Update .env.example

---

## Files to Modify

| File | Changes |
|------|---------|
| `app/workers/celery.py` | Add beat_schedule entries |
| `app/workers/tasks/document_tasks.py` | Relax status checks, add force flags |
| `app/workers/tasks/chunked_document_tasks.py` | Parallel dispatch, heartbeats |
| `app/api/routes/admin/pipeline.py` | NEW - Manual trigger endpoints |
| `app/api/routes/health.py` | Pipeline health check |
| `app/core/config.py` | Config validation, thresholds |
| `app/services/chunking/bbox_linker.py` | Performance optimization |
| `app/services/realtime/broadcast.py` | Feature ready events |
| `.env.example` | Document all variables |

---

## Success Metrics

After implementation:
- [ ] No manual intervention needed for stuck chunks (auto-recovery)
- [ ] Entity extraction starts within 30s of OCR completing (parallel)
- [ ] Admin can trigger any task via API
- [ ] User sees entities while embeddings still processing (progressive)
- [ ] Bbox linking doesn't block search functionality
- [ ] Clear visibility into pipeline health via API
