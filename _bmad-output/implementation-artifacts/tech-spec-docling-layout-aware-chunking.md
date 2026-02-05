# Tech Spec: Docling Layout-Aware Chunking Integration

## Overview

Integrate Docling's layout detection into the chunking pipeline so that:
1. **Docling** detects document structure (paragraphs, headings, tables, stamps, figures) with bounding boxes
2. **Google Document AI** continues to handle all OCR (text extraction) - especially critical for Hindi/Gujarati
3. **Chunking** respects structural boundaries instead of splitting arbitrarily by `\n\n`
4. **Page/bbox assignment** becomes deterministic instead of fuzzy-matched post-hoc

## Problem Statement

Currently:
- OCR extracts text as a flat string → chunker splits by character patterns (`\n\n`, `. `, etc.)
- After chunking, `bbox_linker.py` uses 65% fuzzy matching to **reconstruct** which pages/bboxes each chunk belongs to
- This is lossy and error-prone (stamps/seals bleed into text, wrong page assignments)

Ideal flow:
- Docling extracts layout map **before** chunking → chunker respects block boundaries
- Chunks are created with page/bbox info **at creation time** — no fuzzy reconstruction needed

## Architecture

### Current Pipeline
```
PDF → Google Doc AI (OCR) → flat text string → ParentChildChunker → fuzzy bbox linking → save
```

### Proposed Pipeline
```
PDF → [Parallel]
        ├─ Google Doc AI (OCR) → extracted_text (unchanged)
        └─ Docling (layout) → LayoutMap (NEW)
    → Layout-aware chunker (uses both) → chunks with page/bbox already set → save
```

## Data Models

### New: `LayoutBlock` (in `table_extraction/models.py`)
```python
class LayoutBlock(BaseModel):
    """A structural block detected by Docling."""
    block_type: str  # "paragraph", "heading", "table", "figure", "stamp", "caption", "list"
    page_number: int
    bbox: BoundingBox
    text_start: int | None = None  # Character offset in full text (if applicable)
    text_end: int | None = None
    reading_order: int  # Order within document
    confidence: float = 0.9

class DocumentLayout(BaseModel):
    """Layout map for a document extracted by Docling."""
    document_id: str
    blocks: list[LayoutBlock]
    page_count: int
    processing_time_ms: int | None = None
    error: str | None = None
```

### Updated: `ChunkData` (in `chunking/parent_child_chunker.py`)
```python
@dataclass
class ChunkData:
    # ... existing fields ...
    page_number: int | None = None      # NOW SET AT CREATION (not via bbox_linker)
    bbox_ids: list[UUID] = field(default_factory=list)
    block_types: list[str] = field(default_factory=list)  # NEW: what this chunk contains
    char_start: int | None = None       # NEW: position in original text
    char_end: int | None = None         # NEW: position in original text
```

## Implementation Plan

### Phase 1: Layout Extraction Service (Non-breaking, Additive)

**File: `backend/app/services/table_extraction/layout_extractor.py`** (NEW)

```python
class LayoutExtractor:
    """Extract document layout using Docling."""

    async def extract_layout(self, file_path: Path, document_id: str) -> DocumentLayout:
        """Extract structural layout map from PDF.

        Uses Docling with OCR disabled (we use Google Doc AI for text).
        Returns block-level structure with types and bounding boxes.
        """
        result = self.converter.convert(str(file_path))
        doc = result.document

        blocks = []
        reading_order = 0

        # Iterate through document body structure
        for page_idx, page in enumerate(doc.pages):
            for item in page.items:  # paragraphs, headings, tables, etc.
                block = LayoutBlock(
                    block_type=self._map_item_type(item),
                    page_number=page_idx + 1,
                    bbox=self._extract_bbox(item),
                    text_start=item.text_anchor.start if hasattr(item, 'text_anchor') else None,
                    text_end=item.text_anchor.end if hasattr(item, 'text_anchor') else None,
                    reading_order=reading_order,
                    confidence=getattr(item, 'score', 0.9),
                )
                blocks.append(block)
                reading_order += 1

        return DocumentLayout(
            document_id=document_id,
            blocks=blocks,
            page_count=len(doc.pages),
        )
```

**Changes to existing `extractor.py`:**
- Add `extract_layout()` method that reuses the same converter
- Keep `extract_tables()` unchanged (still works independently)

### Phase 2: Layout-Aware Chunker (Backward Compatible)

**File: `backend/app/services/chunking/parent_child_chunker.py`**

Update `chunk_document()` signature:
```python
def chunk_document(
    self,
    document_id: str,
    text: str,
    layout: DocumentLayout | None = None,  # NEW: optional layout map
) -> ChunkingResult:
```

**Behavior:**
- If `layout=None`: current behavior (split by separators, fuzzy bbox linking later)
- If `layout` provided: use block boundaries to guide splitting

**Algorithm when layout is provided:**
1. Sort blocks by `reading_order`
2. Group consecutive blocks until token limit reached
3. Prefer breaking **between** blocks rather than within
4. For each chunk, record which blocks it contains → derive page_number and block_types
5. Return chunks with page/bbox already populated

### Phase 3: Wire Into Pipeline

**File: `backend/app/workers/tasks/document_tasks.py`**

In `chunk_document` task (~line 2475-2477), change:

```python
# BEFORE:
chunker = ParentChildChunker()
result = chunker.chunk_document(doc_id, doc.extracted_text)
all_chunks = result.parent_chunks + result.child_chunks
if not skip_bbox_linking:
    await link_chunks_to_bboxes(all_chunks, doc_id, bbox_service)

# AFTER:
# 1. Extract layout (if enabled and file available)
layout = None
if settings.layout_aware_chunking_enabled:
    layout = await _extract_layout_for_document(doc_id, matter_id)

# 2. Chunk with layout awareness
chunker = ParentChildChunker()
result = chunker.chunk_document(doc_id, doc.extracted_text, layout=layout)
all_chunks = result.parent_chunks + result.child_chunks

# 3. Only run fuzzy bbox linking if layout wasn't used
if not skip_bbox_linking and layout is None:
    await link_chunks_to_bboxes(all_chunks, doc_id, bbox_service)
```

### Phase 4: Configuration

**File: `backend/app/core/config.py`**

```python
# Layout-aware chunking (Story: Docling Integration)
layout_aware_chunking_enabled: bool = False  # Feature flag, off by default
```

## Files Changed

| File | Change Type | Risk |
|------|-------------|------|
| `backend/app/services/table_extraction/models.py` | Add models | None (additive) |
| `backend/app/services/table_extraction/layout_extractor.py` | New file | None |
| `backend/app/services/table_extraction/extractor.py` | Add method | Low (additive) |
| `backend/app/services/chunking/parent_child_chunker.py` | Add optional param | Low (backward compatible) |
| `backend/app/workers/tasks/document_tasks.py` | Conditional logic | Medium |
| `backend/app/core/config.py` | Add flag | None |

## Files NOT Changed (Downstream Unchanged)

- All embedding code
- All entity extraction
- All 6 analysis engines
- All API routes
- Frontend
- Database schema
- `bbox_linker.py` (remains as fallback, not removed)

## Rollout Strategy

1. **Phase 1**: Deploy with `layout_aware_chunking_enabled=False` (no behavior change)
2. **Phase 2**: Enable for specific test matters via environment override
3. **Phase 3**: Compare chunk quality metrics (page accuracy, bbox coverage)
4. **Phase 4**: If metrics improve, enable by default

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Docling slow on large PDFs | Run layout extraction in parallel with OCR (already async) |
| Docling layout detection inaccurate for Indian legal docs | Feature flag allows instant rollback; fuzzy linker remains as fallback |
| Docling not installed in prod | Graceful degradation: if import fails, fall back to current behavior |
| Breaking existing chunk assignments | New documents only; existing chunks untouched |

## Testing Plan

1. **Unit tests** for `LayoutExtractor` with sample PDFs
2. **Integration test**: Upload doc with flag on vs off, compare chunk page assignments
3. **Accuracy test**: For 10 sample docs, manually verify page assignments are correct
4. **Performance test**: Measure added latency from Docling extraction

## Success Metrics

- **Page assignment accuracy**: Target 95%+ (vs current ~80% with fuzzy matching)
- **Processing time**: No more than 20% increase in total ingestion time
- **Stamp/seal contamination**: Zero stamp text bleeding into legal paragraphs

## Dependencies

- `docling>=2.0.0` (already in pyproject.toml optional deps)
- `docling-core>=2.0.0`

## Estimated Effort

- Phase 1 (Layout extraction service): 2-3 hours
- Phase 2 (Layout-aware chunker): 3-4 hours
- Phase 3 (Pipeline wiring): 1-2 hours
- Phase 4 (Config + tests): 1-2 hours
- **Total: ~8-10 hours**
