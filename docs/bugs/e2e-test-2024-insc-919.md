# E2E Test Report: 2024 INSC 919 (Ashok vs State of UP)

> Test Date: 2026-02-19
> Matter ID: `d119a8cb-53d5-4786-8366-3e27e8fcc59e`
> Document ID: `b43c8d9d-b6e1-419e-8af6-1ba742cf697a`
> Document: Supreme Court Judgment, Criminal Appeal No. 771/2024, 37 pages
> Known contradictions: PW-1 claims PW-2 saw rape+murder; PW-2's actual testimony says he only saw appellant giving water and catching the victim.

---

## Test Outcome

| Metric | Result |
|--------|--------|
| Contradictions found | 3 (1 matches judge's exact finding) |
| Key contradiction caught? | Yes - PW-2 testimony at 100% confidence |
| Processing status | FAILED (but results exist) |
| Total processing time | ~8 minutes |
| Total cost | ~$0.05 (mostly Gemini Flash screening) |

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
- **Status**: [ ] Open
- **File**: `backend/app/workers/tasks/document_tasks.py` (detect_contradictions task)
- **Log**: `detect_contradictions_unexpected_error error= error_type=TimeoutError`
- **What happens**: The main Celery task times out after ~311s and returns `contradiction_detection_failed`. But orphan async coroutines keep running and actually find the contradictions. The task is marked FAILED even though results were stored.
- **Impact**: If the async cleanup were cleaner, we'd have 0 contradictions found on a case with obvious contradictions. The core product claim would fail.
- **Fix direction**: Increase the timeout for the contradiction detection task, or restructure so the timeout is per-entity-pair rather than for the entire task. The task processes entities sequentially, and 15+ entity pairs at ~20s each easily exceeds 300s.

#### BUG-002: "1 document failed processing" banner despite results existing
- **Severity**: CRITICAL
- **Status**: [ ] Open
- **File**: Frontend processing status component + `backend/app/workers/tasks/document_tasks.py`
- **What happens**: Because the contradiction Celery task returned `contradiction_detection_failed`, the UI shows "1 document failed processing" with a warning banner. But the contradictions WERE found and stored. User sees failure when results are there.
- **Impact**: User thinks processing failed. Destroys trust. May abandon the matter.
- **Fix direction**: Either (a) mark the task as partial success when findings were stored, or (b) don't surface the contradiction task failure as a document-level failure if results exist.

#### BUG-003: Contradiction screening misses most real contradictions
- **Severity**: CRITICAL
- **Status**: [ ] Open
- **File**: `backend/app/engines/contradiction/classifier.py`
- **What happens**: The Gemini Flash screening step marked nearly ALL statement pairs as "consistent" with 0.9-1.0 confidence, even pairs involving PW-1 and PW-2 testimony that clearly contradict. Only 1 pair out of 25 for PW-1 was escalated to GPT-4o (which correctly found the contradiction).
- **Impact**: The two-tier system depends on Gemini Flash correctly flagging "needs_review" for suspicious pairs. If it says "consistent" too aggressively, real contradictions are missed. This is the single biggest accuracy issue.
- **Fix direction**: Review the screening prompt. Consider lowering the consistency confidence threshold for escalation. If Gemini says "consistent" at 0.9, maybe that should still escalate. Or tune the prompt to be more skeptical about witness testimony consistency.

#### BUG-004: India Code search query duplicates year
- **Severity**: CRITICAL
- **Status**: [ ] Open
- **File**: Citation engine / India Code search logic
- **Log**: `Found 0 results for: Code of Criminal Procedure, 1973 1973`
- **What happens**: The search query appends the year twice ("1973 1973"), causing zero results for CrPC - one of India's most fundamental laws. All 5 major acts (CrPC, Constitution of India, IPC, BNSS, Evidence Act) were not found.
- **Impact**: Citation verification is completely broken for all statutory references. 43 citations show as unverified.
- **Fix direction**: Find where the year is being appended to the act name and deduplicate.

#### BUG-005: Respondent shows "State of Maharashtra" instead of "State of Uttar Pradesh"
- **Severity**: CRITICAL
- **Status**: [ ] Open
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

## Recommended Fix Order

| Priority | Bug | Effort | Impact |
|----------|-----|--------|--------|
| 1 | BUG-001: Contradiction timeout | Medium | Core product claim |
| 2 | BUG-003: Screening too aggressive | Medium | Core product accuracy |
| 3 | BUG-002: False failure banner | Low | User trust |
| 4 | BUG-005: Wrong respondent | Medium | Factual accuracy |
| 5 | BUG-004: India Code year duplication | Low | Citation engine |
| 6 | BUG-006: WebSocket unhashable | Low | Real-time features |
| 7 | BUG-007: RPC access denied loop | Low | Log noise, performance |
| 8 | BUG-009: Progress bar chaos | Medium | UX during processing |
| 9 | BUG-008: Live Discoveries empty | Low-Med | UX engagement |
| 10 | BUG-010: Docling not installed | Low | Chunking quality |
| 11-16 | Minor bugs | Low each | Polish |

---

## Reproduction Steps

1. Upload `47292_2018_5_1501_57671_Judgement_02-Dec-2024.pdf` (2024 INSC 919) as a new matter
2. Monitor Railway worker logs: `railway logs -s ldip-worker`
3. Watch the browser for progress bar behavior and Live Discoveries panel
4. After processing, check:
   - Summary page for respondent accuracy
   - Verification tab for contradiction details
   - Citation tab for India Code verification status
   - Processing status banner
