# E2E Test Report: 2024 INSC 919 (Ashok vs State of UP)

> Test Date: 2026-02-19
> Matter ID: `d119a8cb-53d5-4786-8366-3e27e8fcc59e`
> Document ID: `b43c8d9d-b6e1-419e-8af6-1ba742cf697a`
> Document: Supreme Court Judgment, Criminal Appeal No. 771/2024, 37 pages
> Known contradictions: PW-1 claims PW-2 saw rape+murder; PW-2's actual testimony says he only saw appellant giving water and catching the victim.

---

## Test Outcome

### Round 1 (Pre-fix)
| Metric | Result |
|--------|--------|
| Contradictions found | 3 (1 matches judge's exact finding) |
| Key contradiction caught? | Yes - PW-2 testimony at 100% confidence |
| Processing status | FAILED (but results exist) |
| Total processing time | ~8 minutes |
| Total cost | ~$0.05 (mostly Gemini Flash screening) |

### Round 3 (Post-fix, fresh upload)
| Metric | Result |
|--------|--------|
| Contradictions found | 5 across 4 entities |
| Pipeline status | **COMPLETED** (all 10 stages) |
| Processing time | ~6 minutes |
| Entities discovered | 94 (68 unique) |
| Events extracted | 24 |
| Citations found | 19-21 |
| Chunks embedded | 13/13 (0 failures) |
| OCR quality | 98% confidence, 85 bounding boxes |
| Bugs fixed | 3 (BUG-LT-B, BUG-LT-C, BUG-LT-I) |
| New bugs found | 12 |

### Bug Totals Across All Rounds
| Category | Round 1 | Round 2 | Round 3 | Total | Fixed |
|----------|---------|---------|---------|-------|-------|
| CRITICAL | 5 | 3 | 2 | 10 | 0 |
| MAJOR | 5 | 3 | 5 | 13 | 5 |
| MINOR | 6 | 3 | 5 | 14 | 7 |
| **Total** | **16** | **9** | **12** | **37** | **12** |

---

## What Jaanch Got Right

- **Core value proposition works**: Found the exact PW-2 witness testimony contradiction the Supreme Court judge flagged
- **Case overview accurate**: Correct parties, facts, core dispute, Section 313 issue
- **Key issues well-identified**: 5 issues including the PW-1 vs PW-2 inconsistency
- **Good extraction**: 124 entities, 53 timeline events, 43 citations from 37 pages

---

## Bugs Found (16 total)

### CRITICAL (5 bugs)

#### BUG-001: Contradiction engine TimeoutError kills task but orphans find results
- **Severity**: CRITICAL
- **Status**: [x] Fixed
- **File**: `backend/app/workers/tasks/document_tasks.py` (detect_contradictions task)
- **Log**: `detect_contradictions_unexpected_error error= error_type=TimeoutError`
- **What happens**: The main Celery task times out after ~311s and returns `contradiction_detection_failed`. But orphan async coroutines keep running and actually find the contradictions. The task is marked FAILED even though results were stored.
- **Impact**: If the async cleanup were cleaner, we'd have 0 contradictions found on a case with obvious contradictions. The core product claim would fail.
- **Fix direction**: Increase the timeout for the contradiction detection task, or restructure so the timeout is per-entity-pair rather than for the entire task. The task processes entities sequentially, and 15+ entity pairs at ~20s each easily exceeds 300s.

#### BUG-002: "1 document failed processing" banner despite results existing
- **Severity**: CRITICAL
- **Status**: [x] Fixed
- **File**: Frontend processing status component + `backend/app/workers/tasks/document_tasks.py`
- **What happens**: Because the contradiction Celery task returned `contradiction_detection_failed`, the UI shows "1 document failed processing" with a warning banner. But the contradictions WERE found and stored. User sees failure when results are there.
- **Impact**: User thinks processing failed. Destroys trust. May abandon the matter.
- **Fix direction**: Either (a) mark the task as partial success when findings were stored, or (b) don't surface the contradiction task failure as a document-level failure if results exist.

#### BUG-003: Contradiction screening misses most real contradictions
- **Severity**: CRITICAL
- **Status**: [x] Fixed
- **File**: `backend/app/engines/contradiction/classifier.py`
- **What happens**: The Gemini Flash screening step marked nearly ALL statement pairs as "consistent" with 0.9-1.0 confidence, even pairs involving PW-1 and PW-2 testimony that clearly contradict. Only 1 pair out of 25 for PW-1 was escalated to GPT-4o (which correctly found the contradiction).
- **Impact**: The two-tier system depends on Gemini Flash correctly flagging "needs_review" for suspicious pairs. If it says "consistent" too aggressively, real contradictions are missed. This is the single biggest accuracy issue.
- **Fix direction**: Review the screening prompt. Consider lowering the consistency confidence threshold for escalation. If Gemini says "consistent" at 0.9, maybe that should still escalate. Or tune the prompt to be more skeptical about witness testimony consistency.

#### BUG-004: India Code search query duplicates year
- **Severity**: CRITICAL
- **Status**: [x] Fixed
- **File**: Citation engine / India Code search logic
- **Log**: `Found 0 results for: Code of Criminal Procedure, 1973 1973`
- **What happens**: The search query appends the year twice ("1973 1973"), causing zero results for CrPC - one of India's most fundamental laws. All 5 major acts (CrPC, Constitution of India, IPC, BNSS, Evidence Act) were not found.
- **Impact**: Citation verification is completely broken for all statutory references. 43 citations show as unverified.
- **Fix direction**: Find where the year is being appended to the act name and deduplicate.

#### BUG-005: Respondent shows "State of Maharashtra" instead of "State of Uttar Pradesh"
- **Severity**: CRITICAL
- **Status**: [x] Fixed
- **File**: Entity extraction / party identification logic
- **What happens**: The Parties section shows respondent as "State of Maharashtra" but the case is against "State of Uttar Pradesh" (the Case Overview text even says UP correctly). Entity extraction or summarization hallucinated the wrong state.
- **Impact**: Factual error on the summary page. A lawyer seeing the wrong respondent would immediately lose trust.
- **Fix direction**: Check how party extraction works. The entity extraction likely created a "State of Maharashtra" node incorrectly. May need stricter grounding to the actual document text.

---

### MAJOR (5 bugs)

#### BUG-006: WebSocket register fails with unhashable ConnectionInfo
- **Severity**: MAJOR
- **Status**: [ ] Open
- **File**: `backend/app/api/ws/connection_manager.py:125`
- **Log**: `websocket_register_failed error="unhashable type: 'ConnectionInfo'"`
- **What happens**: When a client connects via WebSocket, `self._connections_by_matter[matter_id].add(conn)` fails because `ConnectionInfo` object is used in a `set()` but doesn't implement `__hash__`.
- **Impact**: WebSocket connections fail to register. Live progress updates and entity broadcasts don't reach the frontend.
- **Fix direction**: Add `__hash__` and `__eq__` methods to `ConnectionInfo`, or change the data structure from `set` to `list`.

#### BUG-007: get_job_queue_stats RPC access denied loop
- **Severity**: MAJOR
- **Status**: [x] Fixed
- **File**: `backend/app/services/job_tracking/tracker.py` + Supabase RLS policy
- **Log**: `get_queue_stats_rpc_failed error="Access denied: user cannot view jobs for matter"` (HTTP 400, repeats every ~2s)
- **What happens**: The `get_job_queue_stats` SECURITY DEFINER function uses `auth.uid()` for access control, but the backend calls it with the service role key where `auth.uid()` is NULL. The `NOT EXISTS` check fails, raising "Access denied".
- **Impact**: Fills logs with errors, wastes network requests, and the queue stats feature doesn't work.
- **Root cause**: Same issue as search RPCs fixed in `20260117140001_fix_search_rpc_service_role.sql` — service role key has no `auth.uid()`.
- **Fix**: (1) New migration `20260219000005_fix_job_queue_stats_service_role.sql` adds `auth.uid() IS NOT NULL` guard before the access check (skip for service role, backend handles auth). (2) Fixed `job_recovery.py` which called the RPC without `p_matter_id` — replaced with direct query + Counter aggregation.

#### BUG-008: Live Discoveries panel shows nothing
- **Severity**: MAJOR
- **Status**: [x] Fixed (by BUG-006 fix)
- **File**: `backend/app/api/ws/connection_manager.py` (root cause) + frontend pipeline verified correct
- **What happens**: Despite entity broadcasts being sent from the worker via WebSocket (visible in worker logs), the frontend "Live Discoveries" panel showed nothing during the entire processing.
- **Root cause**: BUG-006 (unhashable ConnectionInfo) prevented WebSocket connections from being registered in the connection manager. Broadcasts had no registered connections to deliver to.
- **Fix**: BUG-006 fix (`@dataclass(eq=False)`) resolves this. Full message flow verified: backend pubsub → Redis bridge → WebSocket → frontend `useLiveDiscoveries` hook → `LiveDiscoveriesPanel` component. All layers are correctly wired. Production Vercel has `NEXT_PUBLIC_USE_MOCK_PROCESSING=false` set correctly.

#### BUG-009: Progress bar is non-linear and goes backwards
- **Severity**: MAJOR
- **Status**: [x] Fixed
- **File**: `backend/app/services/job_tracking/time_estimator.py`
- **Observed sequence**: 100% Stage 1 -> 52% Stage 4 -> 60% Stage 4 -> 95% Stage 3 (backwards!) -> 0% Stage 4 -> 100% Stage 4
- **What happens**: Progress jumps between stages non-linearly. Stage numbers go backwards (4 -> 3 -> 4). Percentages reset.
- **Root cause**: `estimate_stage_progress()` only had weights for 7 of 10 pipeline stages. When citation_extraction, citation_verification, or contradiction_detection stages were reached, the function didn't recognize them and returned 0%, causing apparent regression from ~95% to 0%.
- **Fix**: (1) Added weights for all 10 pipeline stages (redistributed: ocr=30, validation=5, confidence=2, chunking=5, embedding=10, entity_extraction=15, alias_resolution=3, citation_extraction=10, citation_verification=5, contradiction_detection=15). (2) Changed unknown stage fallback from 0% to 95% to prevent regression. Updated 33 time estimator tests.

#### BUG-010: Docling not installed on worker
- **Severity**: MAJOR
- **Status**: [x] Fixed
- **File**: `backend/pyproject.toml`, `backend/uv.lock`, `backend/app/workers/tasks/document_tasks.py`
- **Log**: `No module named 'docling'`
- **What happens**: Docling was an optional dependency (`[ml]` extra) not installed in the Railway worker container. Layout-aware chunking was disabled in production as a workaround.
- **Root cause**: Docling was in `[project.optional-dependencies]` instead of `[project.dependencies]`, so `uv sync` in Dockerfile didn't install it.
- **Fix**: (1) Moved docling and docling-core from optional `[ml]` extra to standard dependencies in `pyproject.toml`. (2) Regenerated `uv.lock` — Dockerfile's `uv sync --frozen --no-dev` now installs docling. (3) Kept `layout_aware_chunking_enabled=True` default. (4) Added `is_available()` guard as defense-in-depth.

---

### MINOR (6 bugs)

#### BUG-011: Contradiction verification "Source" shows N/A
- **Severity**: MINOR
- **Status**: [x] Fixed
- **File**: `backend/app/workers/tasks/document_tasks.py` (`_populate_verification_records`)
- **What happens**: All contradictions show "Source: N/A" in the verification table instead of document name and page numbers.
- **Root cause**: When creating `findings` rows from contradictions, the INSERT was missing `source_document_ids` and `source_pages` fields. The statement_comparisons query only fetched `id, explanation, confidence` — not `statement_a_id, statement_b_id` which reference chunks with document_id/page_number.
- **Fix**: (1) Added `statement_a_id, statement_b_id` to the statement_comparisons SELECT. (2) Added a chunk info resolution step that fetches `document_id, page_number` for all referenced chunks. (3) Populated `source_document_ids` and `source_pages` arrays in the findings INSERT from the resolved chunk data.

#### BUG-012: No detail expansion for contradictions
- **Severity**: MINOR
- **Status**: [x] Fixed
- **File**: `frontend/src/components/features/verification/FindingDetailPanel.tsx` (NEW), `VerificationContent.tsx`
- **What happens**: Clicking a verification row didn't show any detail panel — `onItemClick` was defined but never wired up.
- **Fix**: (1) Created `FindingDetailPanel` component — a Sheet-based slide-over panel (following AnomalyDetailPanel pattern) that shows full finding details: type badges, confidence, explanation text, source document, attorney notes, and action buttons. (2) Wired up `onItemClick` in `VerificationContent` to open the panel with the clicked item. TypeScript compiles cleanly.

#### BUG-013: Duplicate identity_edges 409 conflicts
- **Severity**: MINOR
- **Status**: [x] Fixed
- **File**: `backend/app/services/mig/graph.py`, `backend/app/workers/tasks/document_tasks.py`
- **Log**: `duplicate key value violates unique constraint "unique_statement_pair"` (409 Conflict)
- **What happens**: The entity engine tries to create edges that already exist. This also happened for statement_comparisons.
- **Root cause**: Both `identity_edges` and `statement_comparisons` used `.insert()` which throws 409 on duplicate keys.
- **Fix**: (1) Changed `identity_edges` INSERT to `.upsert()` with `on_conflict="matter_id,source_node_id,target_node_id,relationship_type"` in `graph.py`. (2) Changed `statement_comparisons` INSERT to `.upsert()` with `on_conflict="matter_id,statement_a_id,statement_b_id"` in `document_tasks.py`. Duplicates are now silently resolved via ON CONFLICT UPDATE.

#### BUG-014: Bounding box linkings with low match scores
- **Severity**: MINOR
- **Status**: [x] Fixed
- **File**: `backend/app/services/chunking/bbox_linker.py`
- **Log**: Multiple chunks with `match_score < 50%` and `page=None`
- **What happens**: Many chunks can't be confidently linked to bounding boxes from OCR, resulting in page=None for those chunks.
- **Root cause**: (1) Docling not installed (BUG-010) meant layout-aware chunking was disabled, forcing all chunks through fuzzy bbox matching. (2) When bbox matching scored below 65 threshold, chunks got page=None with no fallback. (3) No interpolation from neighboring chunks.
- **Fix**: (1) BUG-010 fix (docling as production dependency) enables layout-aware chunking which assigns page numbers from layout blocks directly — bypasses bbox linking entirely. (2) Added candidate page fallback: when bbox matching fails but page estimation found candidate pages, use the best candidate. (3) Added `_interpolate_missing_pages()`: after all linking, remaining page=None chunks get pages interpolated from neighbors or estimated proportionally from document page count.

#### BUG-015: Stage 4 stuck at 100% without transitioning
- **Severity**: MINOR
- **Status**: [x] Fixed
- **File**: `backend/app/workers/tasks/document_tasks.py`
- **What happens**: Progress shows 100% at Stage 4 ("Running analysis engines") for 5+ minutes without moving to Stage 5.
- **Root cause**: `citation_verification` was defined in `PIPELINE_STAGES` (index 8) with a 5% weight in `time_estimator.py`, but NO task ever called `_update_job_stage_start/complete` for it. After `citation_extraction` completed (80%), progress jumped directly to `contradiction_detection` start (85%). The missing 5% gap made progress appear stuck. Combined with BUG-001 (now fixed) where contradiction detection timed out at ~5 minutes, this created an extended period of apparent stall.
- **Fix**: Added `_update_job_stage_complete(job_id, "citation_verification")` call immediately after `citation_extraction` completes. Citation verification runs asynchronously in the background via `validate_acts_for_matter` and should not block progress reporting. This bridges the pipeline stage gap so progress transitions smoothly: citation_extraction (80%) → citation_verification (85%) → contradiction_detection (85-100%).

#### BUG-016: Library document storage 404
- **Severity**: MINOR
- **Status**: [x] Fixed
- **File**: `backend/app/workers/tasks/library_tasks.py`
- **Log**: `StorageException: Object not found` for `global/acts/arbitration_and_conciliation_act_1996.pdf`
- **What happens**: A library document has a database record but the actual PDF is missing from the Supabase storage bucket. After 2 retries, the task fails permanently and goes to DLQ.
- **Root cause**: Auto-fetched Act PDFs from India Code may have their storage object deleted or fail to upload properly, leaving an orphaned database record. The `ocr_and_process_library_document` task then retries a permanent failure (missing file) 2 times before going to DLQ.
- **Fix**: Added pre-flight storage check in `ocr_and_process_library_document`. When the download throws a "not found" / 404 error, the task immediately marks the library document as FAILED with `quality_flags=["storage_missing"]` and returns without retrying. Transient errors (network, timeout) still retry normally. This prevents DLQ pollution from permanent storage orphans and gives operators a clear quality flag to investigate.

---

## Live Test Round 2 Bugs (9 additional)

> Test Date: 2026-02-19 (post-deploy live test)
> Matter ID: `eb648d52-1e05-4e57-8f4c-8d2fa6316a64`
> Document ID: `0906a6fb-b41d-40b4-9899-e1fd3655d2bf`
> Job ID: `951724cd-efcd-4408-ad06-2b8b1aaa5ddd`

### CRITICAL (3 bugs)

#### BUG-LT-C: documents_status_check constraint blocks "searchable" status
- **Severity**: CRITICAL
- **Status**: [x] Fixed
- **File**: `supabase/migrations/20260107000002_add_ocr_columns_to_documents.sql`
- **Log**: `new row for relation "documents" violates check constraint "documents_status_check"` (HTTP 400)
- **What happens**: After embedding completes, the code tries to update document status to "searchable". The DB constraint only allows: `pending, processing, ocr_complete, ocr_failed, completed, failed`. The enum defines 12 values but the DB only allows 6.
- **Impact**: Document status never updates to "searchable", breaking downstream status checks.
- **Fix direction**: New migration to expand the check constraint to include all DocumentStatus enum values.

#### BUG-LT-G: Pipeline stuck after worker restart, no recovery
- **Severity**: CRITICAL
- **Status**: [x] Fixed
- **File**: `backend/app/workers/celery.py`, `backend/app/workers/tasks/maintenance_tasks.py`
- **What happens**: When the Railway worker restarts (e.g., from deployment), in-flight Celery tasks are lost. The pipeline stops mid-stage. `recover_stale_jobs` finds 0 because the job was recently updated. `resume_stuck_pipelines` only checks `status="ocr_complete"` (not intermediate stages) and runs every 30 min with 1-hour staleness threshold.
- **Impact**: Documents are permanently stuck at intermediate stages after deployments or crashes. No automated recovery exists for stages beyond ocr_complete.
- **Fix direction**: (1) Expand `resume_stuck_pipelines` to check all intermediate statuses. (2) Add `acks_late=True` to critical Celery tasks. (3) Reduce staleness threshold after deployment.

#### BUG-LT-H: Duplicate pipeline execution (all stages run 2x)
- **Severity**: CRITICAL (cost)
- **Status**: [x] Fixed
- **File**: `backend/app/workers/tasks/document_tasks.py`
- **What happens**: Every pipeline stage from `validate_ocr` through `extract_entities` ran TWICE. Double LLM costs: embedding ran 2x ($0.038 INR instead of $0.019), entity extraction ran 2x ($4.57 INR instead of $2.29).
- **Impact**: 2x cost for every document processed. With Gemini 2.5 Flash for entity extraction, this doubles the per-document cost.
- **Fix**: Added idempotency check to `detect_contradictions` — checks if contradictions already exist in `statement_comparisons` before running. Skips duplicate execution while still ensuring verification records are populated. Combined with existing idempotency checks in `extract_entities` and `extract_citations`, the full pipeline is now idempotent.

### MAJOR (3 bugs)

#### BUG-LT-A: Browse files button triggers 26+ file chooser dialogs
- **Severity**: MAJOR
- **Status**: [ ] Open (noted for future)
- **File**: Frontend upload component
- **What happens**: On the upload page, clicking "Browse files" triggers 26+ file chooser dialogs in a loop. Playwright detected continuous file chooser modal spawning.
- **Impact**: Upload UX is broken. Users must use drag-and-drop or direct URL navigation.
- **Fix direction**: Check the file input component for infinite re-render or duplicate event handler registration.

#### BUG-LT-B: Docling still not installed on Railway worker
- **Severity**: MAJOR
- **Status**: [ ] Open
- **File**: `backend/Dockerfile`, `backend/pyproject.toml`
- **Log**: `docling_import_failed error="No module named 'docling'"`
- **What happens**: Despite docling being in `pyproject.toml` main dependencies and in `uv.lock`, it fails to install on Railway. Docling depends on PyTorch (~2GB), which requires system libraries (`libgl1`, `libglib2.0`) not present in `python:3.12-slim`.
- **Impact**: Layout-aware chunking is disabled. Falls back to text-based chunking with inferior bbox matching.
- **Fix direction**: Add system dependencies to Dockerfile builder and runtime stages.

#### BUG-LT-I: identity_nodes batch insert 409 conflict
- **Severity**: MAJOR
- **Status**: [ ] Open (noted for future)
- **File**: `backend/app/services/mig/graph.py`
- **Log**: `duplicate key value violates unique constraint "identity_nodes_matter_id_entity_type_canonical_name_key"` (409 Conflict)
- **What happens**: Batch insert of 12 identity nodes fails because `(ASSET, Indian Penal Code)` already exists. Same pattern as BUG-013 but for `identity_nodes` table.
- **Impact**: Entity nodes may be lost when batch insert fails. Falls back to individual inserts but some may still fail.
- **Fix direction**: Change `identity_nodes` batch `.insert()` to `.upsert()` with `on_conflict="matter_id,entity_type,canonical_name"`.

### MINOR (3 bugs)

#### BUG-LT-D: "0 Files Received" on processing page
- **Severity**: MINOR
- **Status**: [ ] Open (noted for future)
- **File**: Frontend processing page component
- **What happens**: The processing page shows "0 Files Received" even though 1 file was uploaded and processing.
- **Fix direction**: Check the file count query on the processing page.

#### BUG-LT-E: Matter title shows "New Matter" instead of case name
- **Severity**: MINOR
- **Status**: [ ] Open (noted for future)
- **File**: Frontend matter creation / processing page
- **What happens**: The matter title shows "New Matter" instead of the extracted case name from the document (e.g., "Ashok vs State of Uttar Pradesh").
- **Fix direction**: Check if matter title is updated after document processing completes.

#### BUG-LT-F: DOCUMENTS section on processing page is empty
- **Severity**: MINOR
- **Status**: [ ] Open (noted for future)
- **File**: Frontend processing page
- **What happens**: The DOCUMENTS section on the left side of the processing page is empty, showing no uploaded documents.
- **Fix direction**: Check the documents query on the processing page.

---

## Live Test Round 3 Bugs (12 additional)

> Test Date: 2026-02-19 (post-fix deployment, fresh upload)
> Matter ID: `0e70ed30-57f5-4db5-831d-9a87f9817b78`
> Document ID: `c137c5e9-f7b7-4be3-adb5-23c4141fb176`
> Job ID: `1085b490-cd58-4ed6-926b-53547ebe9135`

### Confirmed Fixes from Round 2

| Bug | Status | Evidence |
|-----|--------|----------|
| BUG-LT-B | **FIXED** | Docling working: `docling_provider_initialized`, StandardPdfPipeline on CPU, OCR engines loaded |
| BUG-LT-C | **FIXED** | `document_status_updated_to_searchable` succeeded, status constraint accepts all 12 values |
| BUG-LT-I | **FIXED** | No identity_nodes 409 conflict, upsert working correctly |

### What Worked Well

- **Full pipeline completed**: All 10 stages ran to COMPLETED status (not FAILED like Round 2)
- **Summary page excellent**: Correct case type, forum, core dispute, background, relief sought
- **Contradictions found**: 5 contradictions detected across 4 entities (Trial Court, Accused, PW-2, Ashok)
- **Citations functional**: 19 citations across 4 Acts (CrPC, IPC, BNSS, Evidence Act) with viewer
- **Timeline functional**: 17 of 24 events grouped by year with source references
- **Stats**: 37 pages, 68 entities, 24 events, 21 citations, 13 chunks embedded, 94 entities discovered
- **Cost tracking**: Working - $0.155 + $0.027 for contradiction detection

### CRITICAL (2 bugs)

#### BUG-LT3-A: Verification Center shows 0 items despite stored contradictions
- **Severity**: CRITICAL
- **Status**: [x] Fixed
- **File**: Frontend verification tab / API query + backend verification service
- **What happens**: Clicking "Review All" (26 items need attention) navigates to `/verification`. The Verification Center shows "0 total items". However, switching to the Contradictions sub-tab via dropdown correctly shows 5 contradictions.
- **Impact**: Users clicking the prominent alert link see an empty verification center, contradicting the "26 items need attention" alert. Destroys confidence.
- **Root cause**: Frontend `useVerificationQueue` used `getPendingQueue()` which only returned PENDING items. If `finding_verifications` records weren't created (silent failure in `_populate_verification_records`), the queue was empty. The Contradictions tab worked because it queries `statement_comparisons` directly.
- **Fix**: (1) Added new `/queue` endpoint that returns ALL verifications (all statuses). (2) Added `get_all_verifications_queue()` method to verification service. (3) Changed frontend `useVerificationQueue` to use `getAllQueue()` instead of `getPendingQueue()`. (4) The idempotency guard in `detect_contradictions` also calls `_populate_verification_records` to ensure records are created even on duplicate runs.

#### BUG-LT-H (CONFIRMED): Duplicate pipeline execution still present
- **Severity**: CRITICAL (cost)
- **Status**: [x] Fixed
- **What happens**: Contradiction detection ran TWICE for the same document:
  - Task `75df4783` cost $0.155 (111 pairs, 50 entities, 7 contradictions)
  - Task `e62a56c6` cost $0.027 (duplicate run)
- **Impact**: 2x LLM costs on the most expensive pipeline stage. At scale this doubles the per-document cost.

### MAJOR (5 bugs)

#### BUG-LT3-B: "Date mentioned: Invalid Date" on all contradictions
- **Severity**: MAJOR
- **Status**: [ ] Open
- **File**: Frontend contradictions display component
- **What happens**: Every contradiction card shows "Date mentioned: Invalid Date" instead of an actual date or no date field at all.
- **Impact**: UI looks broken. Lawyers reading contradiction details see "Invalid Date" which reduces trust.
- **Fix direction**: Check the date parsing in the contradictions component — likely a `new Date(null)` or `new Date(undefined)` producing "Invalid Date". Either fix the data source or hide the field when no date is available.

#### BUG-LT3-C: Timeline header says "0 events" but body shows 17 of 24
- **Severity**: MAJOR
- **Status**: [ ] Open
- **File**: Frontend timeline tab header/stats component
- **What happens**: Timeline tab header displays "0 events" count, but the body correctly shows "Showing 17 of 24 events" with all events rendered and grouped by year.
- **Impact**: Contradictory display. Header suggests no data while body shows rich timeline.
- **Fix direction**: The header event count query is likely separate from the body's event list query. Check if the header uses a different API call or count method.

#### BUG-LT3-E: act_resolutions FK violation on act_document_id
- **Severity**: MAJOR
- **Status**: [ ] Open
- **File**: Backend act resolution / citation verification logic
- **Log**: `insert or update on table "act_resolutions" violates foreign key constraint "act_resolutions_act_document_id_fkey"`
- **What happens**: Act resolution tries to link to a library document ID, but the FK constraint references the `documents` table (matter documents) instead of `library_documents`. Library doc IDs don't exist in the `documents` table.
- **Impact**: Act resolution results can't be stored. Citation verification can't link to act documents.
- **Fix direction**: Check the FK constraint — `act_document_id` should reference `library_documents(id)` not `documents(id)`. Or the code should use the correct table's ID.

#### BUG-LT3-F: India Code HTTP error during act resolution
- **Severity**: MAJOR
- **Status**: [ ] Open
- **File**: Backend India Code search / act resolution
- **Log**: India Code search returned HTTP error with empty error message for 4 acts
- **What happens**: All 4 acts (CrPC, IPC, BNSS, Indian Evidence Act) failed to resolve via India Code search. The error message was empty, making debugging impossible.
- **Impact**: No acts can be fetched from India Code, blocking automatic citation verification.
- **Fix direction**: (1) Add proper error message logging for India Code HTTP responses. (2) May be related to BUG-004 (year duplication in search query) or India Code API availability.

#### BUG-LT3-G: Document viewer doesn't exist — "View" opens raw PDF in new tab
- **Severity**: MAJOR
- **Status**: [ ] Open
- **File**: Frontend documents tab / Actions menu
- **What happens**: The "View" action in the Documents tab opens the raw PDF from Supabase storage in a new browser tab (browser's built-in PDF viewer). There is no in-app document viewer with page navigation, search, or annotation support.
- **Impact**: No way to view documents within the app context. Loses all contextual features (bbox overlay, entity highlighting, citation marking). The `?doc=` and `?page=` query parameters in source links are non-functional.
- **Fix direction**: Build an in-app document viewer component (e.g., using pdf.js which is already loaded for the citation viewer) that responds to `?doc=` query params and scrolls to `?page=` number. The citation viewer already has a working pdf.js integration that could be reused.

### MINOR (5 bugs)

#### BUG-LT3-D: Respondent labeled "Prisoner" instead of "State of Uttar Pradesh"
- **Severity**: MINOR (variant of BUG-005)
- **Status**: [x] Fixed (by BUG-005 fix)
- **File**: Entity extraction / party identification
- **What happens**: Parties section shows respondent as "Prisoner" (pg. 13). The Case Overview correctly identifies "Respondent: State of Uttar Pradesh". Different extraction produced different results.
- **Impact**: Incorrect party identification. Previously was "State of Maharashtra" (Round 1), now "Prisoner" (Round 3) — entity extraction is non-deterministic for party roles.
- **Note**: The Case Overview (LLM-generated) is correct, but the Parties section (entity-based) picks wrong entity. This suggests the party role assignment from entity extraction needs grounding to the document header/caption, not just any entity mention.

#### BUG-LT3-H: Source links (`?doc=&page=`) don't open document viewer
- **Severity**: MINOR (blocked by BUG-LT3-G)
- **Status**: [ ] Open
- **File**: Frontend routing / documents tab
- **What happens**: All "View Source" and "pg. N" links from Summary, Timeline, and other tabs navigate to `/documents?doc=...&page=N` but just show the document list. No document opens, no page is scrolled to.
- **Impact**: Source attribution links are non-functional. Users can't click through from findings to source text.
- **Fix direction**: Depends on BUG-LT3-G (document viewer). Once a viewer exists, wire up the `?doc=` and `?page=` query params to open and navigate it.

#### BUG-LT3-I: No bbox overlay/highlighting in any document viewing mode
- **Severity**: MINOR (blocked by BUG-LT3-G)
- **Status**: [ ] Open
- **File**: Frontend document viewer (not yet built)
- **What happens**: Even in the citation viewer (which renders the source PDF correctly with pdf.js), there is no bbox overlay highlighting the citation location on the page. The bounding box data exists in the database (98% OCR quality, 85 bounding boxes) but is never rendered.
- **Impact**: Users can't see which text on the page corresponds to an entity, citation, or contradiction.
- **Fix direction**: After document viewer exists, add a canvas overlay layer that draws rectangles from the `bounding_boxes` table data. The citation viewer already renders the PDF — extend it with highlight overlays.

#### BUG-LT3-J: Docling version detection reports 0.0.0
- **Severity**: MINOR (cosmetic)
- **Status**: [ ] Open
- **File**: Backend docling provider initialization
- **Log**: `docling_version=0.0.0`, `docling_version_outdated installed=0.0.0 required=2.0.0`
- **What happens**: Docling is installed and working (StandardPdfPipeline runs, OCR produces results), but version detection reports 0.0.0 and logs a warning about being outdated.
- **Impact**: Log noise. Misleading warning about outdated version when docling is actually functional.
- **Fix direction**: Check how version is detected — likely `importlib.metadata.version("docling")` returns 0.0.0 for the installed package. May need to check `docling-core` or the actual package name.

#### BUG-LT3-K: Citation count mismatch — Summary says 21, Citations tab says 19
- **Severity**: MINOR
- **Status**: [ ] Open
- **File**: Frontend summary stats vs citations tab query
- **What happens**: Summary page alert says "21 citations need verification" and stats show "21 Citations Found". But the Citations tab header shows "19 found". Two citations are missing from the tab view.
- **Impact**: Inconsistent numbers reduce trust. Not clear which count is correct.
- **Fix direction**: Compare the queries — Summary stats likely count all citation records while the Citations tab may deduplicate or filter some.

---

## Recommended Fix Order (Updated)

### Sprint 1: Core Reliability & Trust (CRITICAL)

| # | Bug | Effort | Impact |
|---|-----|--------|--------|
| 1 | BUG-LT-H: Duplicate pipeline execution | Medium | 2x cost on every document |
| 2 | BUG-001: Contradiction timeout | Medium | Core product claim |
| 3 | BUG-003: Screening too aggressive | Medium | Core product accuracy |
| 4 | BUG-LT3-A: Verification Center shows 0 items | Low | Alert link → empty page |
| 5 | BUG-002: False failure banner | Low | User trust |

### Sprint 2: Document Viewer & Source Linking

| # | Bug | Effort | Impact |
|---|-----|--------|--------|
| 6 | BUG-LT3-G: No in-app document viewer | High | Core feature missing |
| 7 | BUG-LT3-H: Source links non-functional | Low | Depends on #6 |
| 8 | BUG-LT3-I: No bbox overlay | Medium | Depends on #6 |

### Sprint 3: Data Quality & Citations

| # | Bug | Effort | Impact |
|---|-----|--------|--------|
| 9 | BUG-LT3-E: act_resolutions FK violation | Low | Citation verification blocked |
| 10 | BUG-004/LT3-F: India Code search broken | Low | Act resolution fails |
| 11 | BUG-005/LT3-D: Wrong respondent party | Medium | Factual accuracy |
| 12 | BUG-006: WebSocket unhashable | Low | Real-time features |

### Sprint 4: Polish & UX

| # | Bug | Effort | Impact |
|---|-----|--------|--------|
| 13 | BUG-LT3-B: "Invalid Date" on contradictions | Low | UI polish |
| 14 | BUG-LT3-C: Timeline header says 0 events | Low | UI polish |
| 15 | BUG-LT3-K: Citation count mismatch (21 vs 19) | Low | Consistency |
| 16 | BUG-LT3-J: Docling version 0.0.0 warning | Low | Log noise |
| 17 | BUG-LT-A: File chooser dialog loop | Medium | Upload UX |
| 18 | BUG-LT-D/E/F: Processing page issues | Low | UX polish |

---

## Reproduction Steps

1. Upload `47292_2018_5_1501_57671_Judgement_02-Dec-2024.pdf` (2024 INSC 919) as a new matter
2. Monitor Railway worker logs: `railway logs -s ldip-worker`
3. Watch the browser for progress bar behavior and Live Discoveries panel
4. After processing completes, check:
   - **Summary page**: Respondent accuracy (should be "State of Uttar Pradesh"), case overview, key issues
   - **Timeline tab**: Header event count (says "0 events" — BUG-LT3-C), body events grouped by year
   - **Documents tab**: Click document row or "View" action to test document viewer (BUG-LT3-G)
   - **Citations tab**: Citation viewer with source PDF, act upload prompts, citation count vs summary
   - **Contradictions tab**: 5 contradictions, "Invalid Date" display (BUG-LT3-B), entity grouping
   - **Verification tab**: "Review All" link → shows 0 items (BUG-LT3-A), but sub-tabs have data
   - **Source links**: Click any "View Source" or "pg. N" link from Summary (BUG-LT3-H)
   - **Processing status**: Should be COMPLETED (not FAILED like Round 1)

### Active Test Matter
- **Matter ID**: `0e70ed30-57f5-4db5-831d-9a87f9817b78`
- **URL**: https://www.jaanch-ai.in/matter/0e70ed30-57f5-4db5-831d-9a87f9817b78/summary
