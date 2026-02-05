# Tech Spec: Unified Pipeline with Layout-First Chunking

**Status**: Draft
**Author**: Claude
**Date**: 2026-02-05
**Epic**: Pipeline Unification & Bbox Linking Fix

---

## 1. Executive Summary

This spec details changes to unify the document processing pipeline and fix bbox/page linking. The approach ensures **zero breaking changes** through:
- Backward-compatible function signatures
- Feature flags for gradual rollout
- Fallback paths for edge cases
- No database schema changes required

---

## 2. Problem Statement

### Current Issues

| Issue | Impact | Severity |
|-------|--------|----------|
| Duplicate task execution | LLM quota waste, race conditions | High |
| No Docling for large docs | Poor chunking quality (>30 pages) | High |
| Event loop errors | Entity extraction fails with solo pool | High |
| Poor bbox linking (25%) | Users can't navigate to source pages | High |
| Two code paths | Maintenance burden, feature parity issues | Medium |

### Root Causes

1. **Duplicate dispatch**: `resolve_aliases` always calls `_dispatch_downstream_tasks()`, but large doc path already dispatches these tasks
2. **No Docling**: Large doc path skips layout extraction entirely
3. **Event loop**: `engine_tasks.py` uses custom `_run_async()` incompatible with solo pool
4. **Bbox linking**: Fuzzy text matching (25% success) instead of direct block→chunk inheritance

---

## 3. Solution Overview

### Architecture Change

```
BEFORE:
┌─────────────────────────────────────────────────────────────┐
│ Small docs: OCR → validate → chunk (Docling) → embed → ... │
│ Large docs: OCR chunks → merge → chunk (text) → embed → ...│
│                                    ↑ No Docling!           │
└─────────────────────────────────────────────────────────────┘

AFTER:
┌─────────────────────────────────────────────────────────────┐
│ ALL docs: OCR → validate → chunk (Docling) → embed → ...   │
│                              ↑ Same path, same quality     │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Synchronous Docling | Fast (2-4 sec for 400 pages), no deadlock risk |
| No new DB tables | Layout blocks are transient, chunks already have page_number |
| Feature flags | Safe rollout, easy rollback |
| Backward-compatible signatures | No breaking changes to existing callers |

---

## 4. Detailed Implementation

### Phase 1: Fix Duplicate Dispatch

#### 4.1.1 Add `skip_downstream_dispatch` Parameter

**File**: `backend/app/workers/tasks/document_tasks.py`

**Current signature** (line ~4500):
```python
@celery_app.task(...)
def resolve_aliases(
    self,
    prev_result: dict | None = None,
    document_id: str | None = None,
    matter_id: str | None = None,
    job_id: str | None = None,
) -> dict:
```

**New signature** (backward compatible):
```python
@celery_app.task(...)
def resolve_aliases(
    self,
    prev_result: dict | None = None,
    document_id: str | None = None,
    matter_id: str | None = None,
    job_id: str | None = None,
    skip_downstream_dispatch: bool = False,  # NEW - defaults to False for backward compat
) -> dict:
```

**Implementation change** (around line 4590):
```python
# BEFORE:
downstream_triggered = _dispatch_downstream_tasks(
    document_id=doc_id,
    matter_id=matter_id,
    job_id=job_id,
)

# AFTER:
if skip_downstream_dispatch:
    logger.info(
        "resolve_aliases_skip_downstream",
        document_id=doc_id,
        reason="skip_downstream_dispatch=True (unified chain handles dispatch)"
    )
    downstream_triggered = {"skipped": True, "reason": "unified_chain"}
else:
    downstream_triggered = _dispatch_downstream_tasks(
        document_id=doc_id,
        matter_id=matter_id,
        job_id=job_id,
    )
```

**Backward Compatibility**:
- Default `skip_downstream_dispatch=False` means existing callers unchanged
- Small doc chain (documents.py) continues working as before
- Only large doc path sets `skip_downstream_dispatch=True`

#### 4.1.2 Update Large Doc Path

**File**: `backend/app/workers/tasks/chunked_document_tasks.py`

**In `_trigger_parallel_processing()`** (around line 1077):
```python
# BEFORE:
entity_chain = celery_chain(
    extract_entities.s(document_id=document_id, ...),
    resolve_aliases.s(),
)

# AFTER:
entity_chain = celery_chain(
    extract_entities.s(document_id=document_id, ...),
    resolve_aliases.s(skip_downstream_dispatch=True),  # Prevent duplicate dispatch
)
```

**Side Effect Analysis**:
- No side effects - only prevents duplicate task dispatch
- If `skip_downstream_dispatch` is incorrectly set, downstream tasks won't run
- Mitigation: Log when skipping, monitor for missing downstream tasks

---

### Phase 2: Fix Event Loop Issues

#### 4.2.1 Replace Custom `_run_async()`

**File**: `backend/app/workers/tasks/engine_tasks.py`

**Remove these functions** (lines 46-84):
```python
# DELETE:
_task_loop_storage = threading.local()

def _get_task_event_loop() -> asyncio.AbstractEventLoop:
    ...

def _run_async(coro):
    ...

def _cleanup_task_loop():
    ...
```

**Add import**:
```python
from app.workers.utils import run_async
```

**Replace all calls**:
```python
# BEFORE:
result = _run_async(some_async_function())

# AFTER:
result = run_async(some_async_function())
```

**Files with `_run_async()` calls to update**:
- `extract_dates_from_document` task
- `classify_events_for_document` task
- `link_entities_for_matter` task
- `detect_timeline_anomalies` task

**Remove finally cleanup blocks**:
```python
# DELETE these patterns:
finally:
    _cleanup_task_loop()
```

**Backward Compatibility**:
- `run_async()` from utils.py already exists and works
- Same behavior, just using the shared utility
- Works with both gevent pool and solo pool

**Side Effect Analysis**:
- Positive: Fixes "Event loop is closed" errors
- Risk: None - shared utility is battle-tested
- Mitigation: Test with both pool types

---

### Phase 3: Enable Docling for All Documents

#### 4.3.1 Feature Flag (Already Exists)

**File**: `backend/app/core/config.py`

**Current** (line ~202):
```python
layout_aware_chunking_enabled: bool = Field(
    default=False,  # Currently disabled
    description="Enable Docling layout-aware chunking"
)
```

**Change to**:
```python
layout_aware_chunking_enabled: bool = Field(
    default=True,  # Enable by default
    description="Enable Docling layout-aware chunking"
)
```

**Alternative - Environment Variable Override**:
```python
layout_aware_chunking_enabled: bool = Field(
    default=os.getenv("LAYOUT_AWARE_CHUNKING_ENABLED", "true").lower() == "true",
    description="Enable Docling layout-aware chunking"
)
```

**Backward Compatibility**:
- Can set `LAYOUT_AWARE_CHUNKING_ENABLED=false` to disable
- Existing fallback to text-based chunking still works
- No code changes needed if feature disabled

#### 4.3.2 Add Docling Timeout (Safety)

**File**: `backend/app/services/table_extraction/docling_provider.py`

**Add timeout configuration** (around line 113):
```python
# BEFORE:
pipeline_options = PdfPipelineOptions()
pipeline_options.do_table_structure = True
pipeline_options.do_ocr = False

# AFTER:
pipeline_options = PdfPipelineOptions()
pipeline_options.do_table_structure = True
pipeline_options.do_ocr = False
pipeline_options.document_timeout = 120.0  # 2 minute max for safety
```

**Side Effect Analysis**:
- Positive: Prevents hung Docling processes
- Risk: Very large docs (1000+ pages) might timeout
- Mitigation: 120 sec is generous (400 pages takes ~4 sec)

---

### Phase 4: Add Block ID Tracking

#### 4.4.1 Add ID to LayoutBlock Model

**File**: `backend/app/services/table_extraction/models.py`

**Find LayoutBlock class and add ID**:
```python
from uuid import UUID, uuid4
from pydantic import Field

class LayoutBlock(BaseModel):
    """A semantic block from Docling layout extraction."""
    id: UUID = Field(default_factory=uuid4)  # ADD THIS LINE
    block_type: str
    text_content: str | None = None
    page_number: int
    bbox: BoundingBox | None = None
    reading_order: int = 0
    # ... rest of fields
```

**Backward Compatibility**:
- `default_factory=uuid4` means ID auto-generated
- Existing code that creates LayoutBlock without ID still works
- No database changes - blocks are transient

#### 4.4.2 Add `source_block_ids` to ChunkData

**File**: `backend/app/services/chunking/parent_child_chunker.py`

**Find ChunkData dataclass** (around line 33):
```python
@dataclass
class ChunkData:
    id: UUID
    content: str
    chunk_type: str
    chunk_index: int
    parent_id: UUID | None
    token_count: int
    page_number: int | None = None
    bbox_ids: list[UUID] = field(default_factory=list)
    block_types: list[str] = field(default_factory=list)
    layout_derived: bool = False
    source_block_ids: list[UUID] = field(default_factory=list)  # ADD THIS LINE
```

**Backward Compatibility**:
- `default_factory=list` means empty list if not provided
- Existing chunk creation code unchanged
- Field is informational only - not stored in DB

#### 4.4.3 Track Block IDs During Chunk Creation

**File**: `backend/app/services/chunking/parent_child_chunker.py`

**In `_create_parent_chunk_from_blocks()` or similar** (find the method that creates parent chunks from layout blocks):

```python
def _create_parent_chunk_from_blocks(
    self,
    blocks: list[LayoutBlock],
    chunk_index: int,
    document_id: str,
) -> ChunkData:
    content = "\n\n".join(b.text_content for b in blocks if b.text_content)
    pages = sorted(set(b.page_number for b in blocks))

    return ChunkData(
        id=uuid4(),
        content=content,
        chunk_type="parent",
        chunk_index=chunk_index,
        parent_id=None,
        token_count=self._count_tokens(content),
        page_number=pages[0] if pages else None,
        block_types=[b.block_type for b in blocks],
        layout_derived=True,
        source_block_ids=[b.id for b in blocks],  # ADD THIS LINE
    )
```

**Side Effect Analysis**:
- No side effects - informational field only
- Useful for debugging and future cross-engine correlation
- Not persisted to database (unless we add column later)

---

### Phase 5: Unified Chain Factory

#### 4.5.1 Create Chain Factory

**Create file**: `backend/app/workers/tasks/pipeline_chains.py`

```python
"""
Unified task chains for document processing.

This module provides factory functions that create consistent task chains
for both small and large documents, ensuring feature parity.
"""

from celery import chain as celery_chain

from app.workers.tasks.document_tasks import (
    validate_ocr,
    calculate_confidence,
    chunk_document,
    embed_chunks,
    extract_entities,
    resolve_aliases,
)


def create_post_ocr_chain(
    document_id: str,
    matter_id: str,
    job_id: str,
    skip_downstream_dispatch: bool = False,
):
    """
    Create unified post-OCR processing chain.

    This chain runs after OCR completes (for both small and large docs).
    Docling layout extraction happens in chunk_document task.

    Args:
        document_id: Document UUID
        matter_id: Matter UUID
        job_id: Processing job UUID
        skip_downstream_dispatch: If True, resolve_aliases won't dispatch
            extract_citations/extract_dates (use when chain already includes them)

    Returns:
        Celery chain ready for apply_async()
    """
    return celery_chain(
        validate_ocr.s(
            document_id=document_id,
            matter_id=matter_id,
            job_id=job_id,
        ),
        calculate_confidence.s(),
        chunk_document.s(skip_bbox_linking=False),
        embed_chunks.s(),
        extract_entities.s(),
        resolve_aliases.s(skip_downstream_dispatch=skip_downstream_dispatch),
    )


def create_full_processing_chain(
    document_id: str,
    matter_id: str,
    job_id: str,
):
    """
    Create full document processing chain (OCR + post-OCR).

    For small documents only. Large documents use parallel OCR
    then call create_post_ocr_chain().
    """
    from app.workers.tasks.document_tasks import process_document

    return celery_chain(
        process_document.s(
            document_id=document_id,
            matter_id=matter_id,
            job_id=job_id,
        ),
        # process_document returns and triggers post-OCR chain
    )
```

#### 4.5.2 Update API Route (Optional - Low Priority)

**File**: `backend/app/api/routes/documents.py`

The current inline chain can optionally be replaced with the factory:

```python
# BEFORE (line ~552):
task_chain = chain(
    process_document.s(...),
    validate_ocr.s(),
    calculate_confidence.s(),
    chunk_document.s(),
    embed_chunks.s(),
    extract_entities.s(),
    resolve_aliases.s(),
)

# AFTER (optional):
from app.workers.tasks.pipeline_chains import create_post_ocr_chain

task_chain = chain(
    process_document.s(document_id=document_id, matter_id=matter_id, job_id=job_id),
    # process_document triggers post_ocr_chain on completion
)
```

**Note**: This is optional. The existing inline chain works fine.

#### 4.5.3 Update Large Doc Path

**File**: `backend/app/workers/tasks/chunked_document_tasks.py`

**In `_trigger_parallel_processing()`** (around line 1029):

```python
# BEFORE: Separate RAG and entity chains
rag_chain = celery_chain(
    chunk_document.s(...),
    embed_chunks.s(),
    extract_citations.s(),
    detect_contradictions.s(),
)

entity_chain = celery_chain(
    extract_entities.s(...),
    resolve_aliases.s(),
)

extract_dates_from_document.apply_async(...)

# AFTER: Use unified chain
from app.workers.tasks.pipeline_chains import create_post_ocr_chain

# Single unified chain - same as small docs
post_ocr_chain = create_post_ocr_chain(
    document_id=document_id,
    matter_id=matter_id,
    job_id=job_id,
    skip_downstream_dispatch=False,  # Let resolve_aliases dispatch downstream
)
post_ocr_chain.apply_async()
```

**Side Effect Analysis**:
- Removes duplicate task dispatch (extract_citations, extract_dates)
- Same task order as small docs
- Downstream dispatch happens via resolve_aliases

---

## 5. Rollback Plan

### Per-Phase Rollback

| Phase | Rollback Method |
|-------|-----------------|
| Phase 1 | Set `skip_downstream_dispatch=False` (default) |
| Phase 2 | Revert engine_tasks.py to use custom `_run_async()` |
| Phase 3 | Set `LAYOUT_AWARE_CHUNKING_ENABLED=false` |
| Phase 4 | No rollback needed - fields are optional |
| Phase 5 | Revert to inline chains in chunked_document_tasks.py |

### Full Rollback

If major issues found:
1. Revert all file changes via git
2. Redeploy previous version
3. No database rollback needed (no schema changes)

---

## 6. Testing Strategy

### Unit Tests

```python
# test_resolve_aliases_skip_dispatch.py
def test_resolve_aliases_with_skip_flag():
    """Verify skip_downstream_dispatch prevents task dispatch."""
    result = resolve_aliases(
        document_id="test-doc",
        skip_downstream_dispatch=True,
    )
    assert result["downstream_tasks"]["skipped"] == True

def test_resolve_aliases_without_skip_flag():
    """Verify default behavior dispatches tasks."""
    result = resolve_aliases(
        document_id="test-doc",
        # skip_downstream_dispatch defaults to False
    )
    assert "extract_citations" in result["downstream_tasks"]
```

### Integration Tests

```python
# test_unified_pipeline.py
def test_large_doc_uses_docling():
    """Verify large documents get Docling layout extraction."""
    # Upload 50-page document
    # Wait for processing
    # Check chunks have layout_derived=True
    # Check chunks have page_number set

def test_no_duplicate_tasks():
    """Verify tasks run exactly once for large docs."""
    # Upload large document
    # Monitor task execution
    # Assert extract_citations runs once
    # Assert extract_dates runs once
```

### E2E Tests

```bash
# Manual verification
1. Upload 10-page document (small path)
2. Upload 50-page document (large path)
3. Compare:
   - Both should have Docling layout extraction
   - Both should have ~100% page linking
   - Large doc should NOT have duplicate tasks
```

---

## 7. Monitoring & Alerts

### Key Metrics to Watch

| Metric | Expected Change | Alert Threshold |
|--------|-----------------|-----------------|
| `extract_citations` task count per doc | 1 (was 2 for large) | >1 per doc |
| `extract_dates` task count per doc | 1 (was 2 for large) | >1 per doc |
| Chunk page_number coverage | ~100% (was 25%) | <80% |
| `layout_extraction_complete` events | +1 per large doc | 0 for large docs |
| Event loop errors | 0 | Any occurrence |

### Log Entries to Add

```python
# In resolve_aliases when skipping
logger.info(
    "resolve_aliases_skip_downstream",
    document_id=doc_id,
    skip_downstream_dispatch=True,
)

# In chunk_document when Docling runs
logger.info(
    "layout_extraction_complete",
    document_id=doc_id,
    blocks_count=len(layout.blocks),
    pages_count=layout.page_count,
    processing_time_ms=layout.processing_time_ms,
)
```

---

## 8. Implementation Checklist

### Phase 1: Fix Duplicate Dispatch
- [ ] Add `skip_downstream_dispatch` param to `resolve_aliases`
- [ ] Add conditional skip logic in `resolve_aliases`
- [ ] Update entity chain in `_trigger_parallel_processing()`
- [ ] Add logging for skip events
- [ ] Test with large document

### Phase 2: Fix Event Loop
- [ ] Remove custom `_run_async()` functions from engine_tasks.py
- [ ] Add import for shared `run_async`
- [ ] Replace all `_run_async()` calls
- [ ] Remove `_cleanup_task_loop()` finally blocks
- [ ] Test entity extraction with solo pool

### Phase 3: Enable Docling
- [ ] Change `layout_aware_chunking_enabled` default to True
- [ ] Add `document_timeout=120.0` to Docling provider
- [ ] Test with 50+ page document
- [ ] Verify fallback works when Docling fails

### Phase 4: Block ID Tracking
- [ ] Add `id: UUID` to LayoutBlock model
- [ ] Add `source_block_ids` to ChunkData
- [ ] Update chunk creation to track block IDs
- [ ] Verify no side effects

### Phase 5: Unified Chain
- [ ] Create `pipeline_chains.py`
- [ ] Update `_trigger_parallel_processing()` to use unified chain
- [ ] Remove duplicate chain definitions
- [ ] Test large document processing

### Final Verification
- [ ] E2E test: 10-page document
- [ ] E2E test: 50-page document
- [ ] E2E test: 400-page document
- [ ] Verify no duplicate tasks in logs
- [ ] Verify ~100% page linking
- [ ] Verify no event loop errors

---

## 9. Open Questions

1. **Should we backfill page_number for existing chunks?**
   - Option A: No - only new documents get improved linking
   - Option B: Yes - run migration to re-chunk existing documents
   - Recommendation: Option A for now, consider backfill later

2. **Should unified chain include extract_citations directly?**
   - Current: resolve_aliases dispatches extract_citations
   - Alternative: Include in chain for explicit ordering
   - Recommendation: Keep current - dispatch pattern works, less change

3. **What if Docling fails for a document?**
   - Current: Falls back to text-based chunking
   - Fallback preserves functionality, just loses layout quality
   - Recommendation: Keep fallback, log failures for monitoring

---

## 10. Appendix: File Changes Summary

| File | Lines Changed | Risk Level |
|------|---------------|------------|
| `document_tasks.py` | ~10 lines | Low |
| `chunked_document_tasks.py` | ~30 lines | Medium |
| `engine_tasks.py` | ~50 lines (delete + replace) | Low |
| `config.py` | 1 line | Low |
| `models.py` | 1 line | Low |
| `docling_provider.py` | 1 line | Low |
| `parent_child_chunker.py` | ~5 lines | Low |
| `pipeline_chains.py` (new) | ~60 lines | Low |

**Total**: ~160 lines changed, 1 new file created, 0 database migrations
