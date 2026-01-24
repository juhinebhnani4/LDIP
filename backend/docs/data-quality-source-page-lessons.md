# Data Quality: Source Page Linkage - Lessons Learned

## Executive Summary

Timeline events, citations, and entities were not navigating to the correct PDF page because `source_page` was either NULL or incorrectly defaulting to page 1. This document captures what we learned and how to prevent it across all engines.

## The Problem

When users click "Source: Document" on timeline events, citations, or entities, the PDF viewer should open to the exact page where that data was found. Instead:
- **48% of timeline events** had NULL `source_page` → defaulted to page 1
- **Citations** silently fell back to page 1 when page detection failed
- Users couldn't verify AI-extracted information against source documents

## Root Cause Analysis

### Pipeline Flow

```
PDF File
    ↓
Document AI OCR → BoundingBoxes (with accurate page_number)
    ↓
Semantic Chunking → Chunks (initially NO page_number)
    ↓
link_chunks_to_bboxes (fuzzy matching, threshold=50%)
    ↓
    ├─ Match found → chunk.page_number = bbox.page_number ✓
    └─ Match failed → chunk.page_number = NULL ✗
    ↓
Extraction Engines read chunks
    ├─ Citations: source_page = chunk.page_number OR 1 (WRONG!)
    ├─ Timeline: source_page = chunk.page_number (NULL)
    └─ Entities: page_number = chunk.page_number (NULL)
```

### The Single Point of Failure

**`link_chunks_to_bboxes`** (fuzzy text matching) is the critical step. When it fails:
1. Chunk has `page_number = NULL`
2. All downstream engines inherit this NULL
3. Citations silently use `or 1` fallback → WRONG PAGE
4. Timeline/Entities save NULL → navigation broken

### Why Fuzzy Matching Fails

| Cause | Example | Impact |
|-------|---------|--------|
| OCR errors | "Section 138" → "Secti0n 13B" | No match |
| Multilingual text | Hindi/Gujarati mixed with English | Encoding issues |
| Tables/Headers | Repeated text across pages | Wrong page matched |
| Text spanning bboxes | Long sentences split | Partial match |
| Threshold too strict | Was 70%, now 50% | Still misses edge cases |

## Affected Components

### Files with Silent `or 1` Fallback

```
backend/app/engines/citation/storage.py:163
    "source_page": extraction_result.page_number or 1,

backend/app/engines/citation/verifier.py:406
    page_number=first_chunk.page_number or 1,

backend/app/engines/citation/verifier.py:466
    page_number=matching_chunk.page_number or 1,

backend/app/api/routes/citations.py:1563
    source_page = citation.source_page or 1

backend/app/services/summary_service.py:472
    source_page = row.get("page_number") or 1

backend/app/services/summary_service.py:1241
    page=page_number or 1,
```

### Data Tables Affected

| Table | Field | Engine |
|-------|-------|--------|
| `events` | `source_page` | Timeline |
| `citations` | `source_page` | Citations |
| `entities` (MIG) | `page_number` | Entity Extraction |
| `chunks` | `page_number` | All (upstream) |

## Prevention Strategies

### 1. Remove Silent Fallbacks

**Before (BAD):**
```python
"source_page": extraction_result.page_number or 1,
```

**After (GOOD):**
```python
"source_page": extraction_result.page_number,  # Allow NULL
"source_page_confidence": "low" if extraction_result.page_number is None else "high",
```

### 2. Add Validation at Save Time

```python
# In engines that save to DB
def save_with_validation(record: dict, table: str):
    if record.get("document_id") and not record.get("source_page"):
        logger.warning(
            "missing_source_page",
            table=table,
            record_id=record.get("id"),
            document_id=record.get("document_id"),
        )
        # Option A: Mark for manual review
        record["requires_page_review"] = True
        # Option B: Estimate from chunk position
        # record["source_page"] = estimate_page_from_chunk_index(...)
```

### 3. Track Data Quality Metrics

```python
# Add to all extraction engines
class DataQualityMetrics:
    def __init__(self):
        self.total_records = 0
        self.with_source_page = 0
        self.with_bbox_ids = 0
        self.fallback_to_page_1 = 0  # NEW: Track this!

    def report(self):
        return {
            "source_page_coverage": self.with_source_page / self.total_records,
            "bbox_coverage": self.with_bbox_ids / self.total_records,
            "fallback_rate": self.fallback_to_page_1 / self.total_records,  # Alert if > 10%
        }
```

### 4. Improve Bbox Linking

```python
# In bbox_linker.py
def link_chunk_to_bboxes(chunk, bboxes, document_id):
    result = fuzzy_match(chunk.content, bboxes)

    if result.score < MATCH_THRESHOLD:
        # NEW: Try secondary strategies before giving up
        result = try_exact_substring_match(chunk, bboxes)
        if not result:
            result = estimate_page_from_chunk_position(chunk, document)
        if not result:
            logger.warning("bbox_linking_failed", chunk_id=chunk.id)
            return LinkResult(page_number=None, confidence="none")

    return LinkResult(
        page_number=result.page,
        bbox_ids=result.bbox_ids,
        confidence="high" if result.score > 80 else "medium"
    )
```

### 5. Add Frontend Indicators

```typescript
// In TimelineEventCard.tsx, CitationCard.tsx, etc.
{event.sourcePage ? (
  <Link to={`/doc/${docId}?page=${event.sourcePage}`}>
    Document, pg {event.sourcePage}
  </Link>
) : (
  <Tooltip content="Page number could not be determined">
    <Link to={`/doc/${docId}`} className="text-amber-600">
      Document <AlertIcon />
    </Link>
  </Tooltip>
)}
```

### 6. Pipeline Ordering Guarantee

```python
# In document processing task
async def process_document_complete(document_id: str):
    # STEP 1: OCR (creates bboxes with page_number)
    await run_ocr(document_id)

    # STEP 2: Chunking
    await create_chunks(document_id)

    # STEP 3: MUST complete before any extraction
    await link_chunks_to_bboxes(document_id)

    # Validate before proceeding
    coverage = await check_chunk_page_coverage(document_id)
    if coverage < 0.9:
        logger.warning("low_chunk_page_coverage", coverage=coverage)
        # Option: Re-run with lower threshold or different strategy

    # STEP 4: Now safe to run extraction engines
    await asyncio.gather(
        extract_citations(document_id),
        extract_dates(document_id),
        extract_entities(document_id),
    )
```

## Checklist for New Engines

When building a new extraction engine, ensure:

- [ ] **Source tracking**: Does the engine save `document_id`, `source_page`, `source_bbox_ids`?
- [ ] **No silent fallbacks**: Never use `page_number or 1` - allow NULL and handle in UI
- [ ] **Validation**: Log warnings when source_page is NULL for records with document_id
- [ ] **Metrics**: Track source_page coverage in engine output
- [ ] **UI handling**: Show indicator when page is unknown, don't silently go to page 1
- [ ] **Backfill script**: Create a backfill script for data recovery if needed

## Monitoring & Alerts

Add these Supabase queries as scheduled health checks:

```sql
-- Check for high % of NULL source_page in events
SELECT
    matter_id,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE source_page IS NULL) as null_pages,
    ROUND(COUNT(*) FILTER (WHERE source_page IS NULL)::numeric / COUNT(*) * 100, 1) as null_pct
FROM events
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY matter_id
HAVING COUNT(*) FILTER (WHERE source_page IS NULL)::numeric / COUNT(*) > 0.3;

-- Check for suspicious page 1 concentration in citations
SELECT
    matter_id,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE source_page = 1) as page_1_count,
    ROUND(COUNT(*) FILTER (WHERE source_page = 1)::numeric / COUNT(*) * 100, 1) as page_1_pct
FROM citations
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY matter_id
HAVING COUNT(*) > 10 AND COUNT(*) FILTER (WHERE source_page = 1)::numeric / COUNT(*) > 0.5;
```

## Recovery Scripts

Existing backfill scripts:
- `scripts/backfill_timeline_data.py` - Timeline events source_page
- `scripts/backfill_citation_pages.py` - Citation source_page
- `scripts/backfill_chunk_page_numbers.py` - Chunk page_number from bboxes
- `scripts/backfill_citation_source_bboxes.py` - Citation bbox linkage

## Summary

| Issue | Root Cause | Prevention |
|-------|------------|------------|
| NULL source_page | Fuzzy bbox matching fails | Improve matching + allow NULL |
| Wrong page (1) | Silent `or 1` fallback | Remove fallbacks, show UI warning |
| No visibility | No metrics/logging | Add coverage tracking |
| Cascading failures | Pipeline ordering | Validate bbox linking before extraction |
| **Multi-page chunks** | **Chunk page != citation page** | **Per-citation bbox detection** |

---

## Addendum: Multi-Page Chunk Issue (2026-01-24)

### New Issue Discovered

Even when `source_page` is populated (not NULL, not 1), it can still be **wrong** when chunks span multiple pages.

**Example**: "Section 205(C) of the Companies Act"
- Chunk contains text from pages 7-8
- Chunk assigned `page_number = 7` (most common page among matched bboxes)
- Citation extracted and saved with `source_page = 7`
- But the actual citation text appears on **page 8** in the PDF

### Root Cause

```
Bbox linking: chunk matches bboxes on pages 7 and 8
    ↓
page_number = Counter(bbox_pages).most_common(1) → page 7
    ↓
ALL citations from this chunk get source_page = 7  ← WRONG for citations on page 8
```

The chunk-level page number is correct for WHERE THE CHUNK STARTS, but not for where specific citations within that chunk appear.

### The Fix (Implemented)

**Per-citation bbox page detection** in `backend/app/engines/citation/storage.py`:

```python
def _find_citation_page_from_bboxes(citation_text: str, bboxes: list[dict]) -> int | None:
    """Find the actual page where citation text appears in bboxes."""

    # Strategy 1: Exact substring match
    for bbox in bboxes:
        if citation_text.lower() in bbox["text"].lower():
            return bbox["page_number"]

    # Strategy 2: Section phrase match (e.g., "section 205(c)")
    section_match = re.search(r"section\s+\d+(?:\s*\([^)]+\))?", citation_text.lower())
    if section_match:
        for bbox in bboxes:
            if section_match.group(0) in bbox["text"].lower():
                return bbox["page_number"]

    # Strategy 3: Word overlap (3+ matching words)
    # ... fallback logic

    return None  # Fall back to chunk page
```

Modified `save_citations()` to:
1. Fetch bboxes linked to the chunk
2. For each citation, search bboxes for the citation text
3. Use the bbox's page_number if found, else fall back to chunk page

### Files Modified

| File | Change |
|------|--------|
| `backend/app/engines/citation/storage.py` | Added `_find_citation_page_from_bboxes()`, modified `save_citations()` |
| `backend/scripts/backfill_citation_pages.py` | Added `find_page_from_bboxes()`, improved backfill logic |
| `backend/scripts/diagnose_citation_pages.py` | New diagnostic script for data quality |

### Prevention for Future

1. **New documents**: Automatically use per-citation bbox detection during extraction
2. **Existing data**: Run `backfill_citation_pages.py` with improved logic
3. **Monitoring**: Check for high page-1 concentration (see diagnostic script)

### Key Insight

**Chunk page_number ≠ Citation page_number** when content spans pages.

The solution is to defer page detection to the finest granularity available:
- Chunk-level page → good for chunk navigation
- Bbox-level page → better for citation/entity navigation

---

*Document created: 2026-01-24*
*Author: Claude Code analysis of Nirav Jobalia matter*
*Updated: 2026-01-24 - Added multi-page chunk fix*
