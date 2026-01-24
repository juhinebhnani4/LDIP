# Data Quality Fixes Plan

## Executive Summary

Database audit revealed critical data quality issues across Timeline, Citations, Chunks, and Documents. The root cause is incomplete pipeline implementation where spatial data (page_number, bbox_ids) exists but isn't carried through extraction pipelines.

## Current State (Audit Results)

| Feature | Issue | Severity |
|---------|-------|----------|
| Timeline `source_page` | 100% NULL | CRITICAL |
| Timeline `source_bbox_ids` | 100% EMPTY | CRITICAL |
| Timeline `entities_involved` | 100% EMPTY | HIGH |
| Timeline `event_type` | 100% raw_date | HIGH |
| Citations `target_bbox_ids` | 100% EMPTY | HIGH |
| Citations `target_page` | 48% NULL | MEDIUM |
| Chunks `page_number` | 78% NULL | HIGH |
| Chunks `bbox_ids` | 86% NULL | HIGH |
| Documents `page_count` | 84% NULL | MEDIUM |

## The Pattern That Works (Citations Source)

Citations successfully populate `source_page` (100%) and `source_bbox_ids` (79%) because:

1. **Chunk Selection**: Queries include `page_number, bbox_ids`
2. **Per-Chunk Processing**: Each chunk processed individually
3. **Data Passed Through**: `page_number` passed to extractor, `bbox_ids` passed to storage
4. **Storage Accepts Both**: Storage function has parameters for both fields

## Implementation Plan

### Phase 1: Fix Timeline Extraction (CRITICAL)

**Files to modify:**
- `backend/app/workers/tasks/engine_tasks.py`
- `backend/app/engines/timeline/date_extractor.py`

**Changes:**
1. Load chunks WITH page_number and bbox_ids
2. Process per-chunk instead of combining all text
3. Pass page_number and bbox_ids through extraction pipeline
4. Deduplicate dates that appear in multiple chunks

**Estimated Impact:** Fixes 846 events with NULL source_page

### Phase 2: Enable Timeline Classification & Entity Linking (HIGH)

**Files to modify:**
- `backend/app/workers/tasks/engine_tasks.py`
- `backend/app/workers/tasks/document_tasks.py` (dispatch)

**Changes:**
1. Enable auto_classify after date extraction
2. Trigger entity linking after classification
3. Add to pipeline dispatch sequence

**Estimated Impact:** Fixes 846 events with raw_date type, 846 with empty entities

### Phase 3: Fix Citations Target Page/Bbox (HIGH)

**Files to modify:**
- `backend/app/engines/citation/storage.py`
- `backend/app/services/verification/verification_service.py`

**Changes:**
1. Implement target bbox matching when Act document is available
2. Fix section_index lookup fallback for target_page

**Estimated Impact:** Fixes 484 citations with NULL target_page

### Phase 4: Fix Upstream Chunk Data (HIGH)

**Files to modify:**
- `backend/app/services/chunking/bbox_linker.py`
- `backend/app/workers/tasks/document_tasks.py`

**Changes:**
1. Ensure bbox_linker runs for all documents
2. Fix any conditions that skip bbox linking

**Estimated Impact:** Fixes 78% of chunks missing page_number

### Phase 5: Backfill Existing Data

**Scripts to create:**
- `backend/scripts/backfill_event_pages.py`
- `backend/scripts/backfill_doc_page_count.py`
- `backend/scripts/run_event_classification.py`
- `backend/scripts/run_entity_linking.py`

### Phase 6: Document Page Count (MEDIUM)

**Files to modify:**
- `backend/app/workers/tasks/document_tasks.py`

**Changes:**
1. Save page_count after OCR completion

**Estimated Impact:** Fixes 21 documents with NULL page_count

---

## Fix Tracking

### Fix #1: Timeline source_page - Per-chunk extraction ✅ DONE
- [x] Modify engine_tasks.py to load chunks with bbox_ids
- [x] Change to per-chunk processing
- [x] Pass page_number to date_extractor
- [x] Handle duplicate dates across chunks (added _deduplicate_extracted_dates)
- [ ] Test with sample document

### Fix #2: Timeline source_bbox_ids - Accept and pass bbox_ids ✅ DONE
- [x] Add bbox_ids parameter to date_extractor (all methods updated)
- [x] Pass bbox_ids from chunk to extractor
- [x] Update ExtractedDate creation to use provided bbox_ids
- [x] Updated ChunkWithContent model to include bbox_ids
- [x] Updated _parse_chunk_with_content to return bbox_ids
- [ ] Test bbox population

### Fix #3: Timeline event_type - Enable auto-classification ✅ DONE
- [x] Enable auto_classify=True in document_tasks.py dispatch
- [x] Enable auto_classify=True in chunked_document_tasks.py dispatch
- [ ] Test classification runs

### Fix #4: Timeline entities_involved - Enable entity linking ✅ DONE
- [x] Add entity linking dispatch after classification completes in classify_events_for_document
- [ ] Test entity linking runs

### Fix #5: Citations target_page - Fix section_index lookup
- [ ] Review current section_index usage
- [ ] Fix fallback logic
- [ ] Test target page population

### Fix #6: Citations target_bbox_ids - Implement matching
- [ ] Design bbox matching for Act documents
- [ ] Implement in verification service
- [ ] Test target highlighting

### Fix #7: Chunks page_number/bbox_ids - Fix bbox_linker
- [ ] Audit when bbox_linker skips
- [ ] Fix conditions
- [ ] Test chunk linking

### Fix #8: Documents page_count - Save from OCR
- [ ] Add page_count save after OCR
- [ ] Backfill existing documents

### Backfill Script ✅ CREATED
- [x] Created `backend/scripts/backfill_timeline_data.py`
- [ ] Run dry-run to verify
- [ ] Run actual backfill

---

## Testing Strategy

1. **Unit Test**: Each fix in isolation
2. **Integration Test**: Full pipeline with new document upload
3. **Backfill Test**: Run backfill on subset, verify data
4. **UI Test**: Verify frontend displays correct page/highlighting

---

## Rollback Plan

Each fix is independent. If issues arise:
1. Revert specific file changes
2. Existing data unaffected (backfills are additive)
3. Pipeline continues to work with NULL values (graceful degradation)

---

## Success Metrics

| Metric | Before | Target |
|--------|--------|--------|
| Timeline source_page populated | 0% | >90% |
| Timeline source_bbox_ids populated | 0% | >80% |
| Timeline classified (not raw_date) | 0% | 100% |
| Timeline entities linked | 0% | >70% |
| Citations target_page populated | 52% | >90% |
| Chunks with page_number | 22% | >80% |

---

## Start Date: 2026-01-24
## Status: IN PROGRESS
