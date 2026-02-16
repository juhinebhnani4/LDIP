# Timeline Engine Overhaul Plan

> **Date:** 2026-02-06
> **Status:** Approved — Phase 1 ready for implementation

## Context

The timeline engine extracts legal events from documents but has two critical failures:
1. **Cross-engine "Timeline Journey" shows empty** for entities — the `entities_involved` column is NULL because entity linking either didn't run or the 0.85 confidence threshold filtered all matches. Chat finds the same data because it queries events directly, not via entity links.
2. **Only 6 events extracted from multiple documents** — same-date dedup groups by `date.isoformat()` only (multiple events on Jan 15 → only 1 kept), and parent-chunk-only processing skips child chunks where most dense text lives.

**Root cause:** the 3-step pipeline (extract → classify → link) is fragile, the dedup is lossy, and entity linking has too strict a threshold.

### Current Architecture

```
Document Upload
    ↓
Chunking (parent/child)
    ↓
Step 1: Date Extraction (Gemini) — per chunk, 5000 char limit
    → Dedup by date only (LOSSY — one event per date)
    → Saves as raw_date in events table
    ↓
Step 2: Classification (Gemini) — batch of 20, confidence 0.70 threshold
    → Updates event_type (filing, hearing, order, etc.)
    ↓
Step 3: Entity Linking (pattern matching + optional Gemini)
    → 0.85 confidence threshold (TOO STRICT)
    → Populates entities_involved array
    → OPTIONAL — may not run if classification produced 0 updates
    ↓
events table → Timeline UI (works) / Cross-Engine Journey (BROKEN — empty entities_involved)
```

---

## Phase 1: Quick Wins (ship in 2-4 days)

### 1.1 Fix same-date deduplication

**File:** `backend/app/workers/tasks/engine_tasks.py` (lines 72-112)

Change grouping key from `d.extracted_date.isoformat()` to `(date_iso, event_type, description_hash)`:

```python
import hashlib

def _dedup_key(d):
    date_str = d.extracted_date.isoformat() if d.extracted_date else "unknown"
    event_type = getattr(d, 'event_type', '') or ''
    desc = getattr(d, 'event_description', '') or ''
    desc_norm = ' '.join(desc.lower().split())[:50]
    desc_hash = hashlib.md5(desc_norm.encode()).hexdigest()[:8]
    return f"{date_str}:{event_type}:{desc_hash}"
```

Rest of scoring/selection logic stays identical. **Expected impact: 2-3x more events preserved.**

### 1.2 Process all chunks (parent + child)

**File:** `backend/app/workers/tasks/engine_tasks.py` (lines 237-238)

Replace:
```python
parent_chunks = [c for c in chunks if c.parent_chunk_id is None]
chunks_to_process = parent_chunks if parent_chunks else chunks
```
With:
```python
chunks_to_process = chunks  # Process all; dedup handles overlaps
```

More Gemini calls per doc but the fixed dedup prevents event explosion.

### 1.3 Fix entity linking reliability + lower threshold

**A) Lower threshold** — `backend/app/engines/timeline/entity_linker.py` (line 43-44)

Change default from `"0.85"` to `"0.70"`. Env var override still works for production tuning.

**B) Always trigger entity linking when events exist** — `backend/app/workers/tasks/engine_tasks.py`

Change the trigger condition from `if updated_count > 0:` to `if updated_count > 0 or total_events > 0:` so entity linking runs even when classification didn't change event types.

### 1.4 Cross-engine journey fallback (text search)

**File:** `backend/app/services/cross_engine_service.py` (lines 144-249)

In `get_entity_journey()`, after the primary `.contains("entities_involved", [entity_id])` query returns 0 results, add a fallback that searches entity name + aliases in the `description` column using PostgreSQL full-text search (GIN index already exists).

No API/frontend changes needed — same endpoint, same response shape.

---

## Phase 2: Medium-Term (2-4 weeks)

### 2.1 Single-pass unified extraction (merge 3 Celery tasks → 1)

**Current:** 3 separate Gemini calls per chunk: extract dates → classify events → link entities.

**New:** One `extract_events_from_document` task with a unified prompt that returns events with dates + types + entity mentions in a single call.

**Files to modify:**
- `backend/app/engines/timeline/prompts.py` — New `UNIFIED_EVENT_EXTRACTION_PROMPT` (event-first, not date-first)
- `backend/app/engines/timeline/date_extractor.py` — New `extract_events_sync()` method
- `backend/app/workers/tasks/engine_tasks.py` — New task, feature-flagged
- `backend/app/models/timeline.py` — New `ExtractedEvent` model with `entity_mentions: list[str]`

**New prompt concept** (event-first, not date-first):
```
Extract all LEGAL EVENTS from this document text. For each event provide:
1. Date (YYYY-MM-DD), precision, original text
2. Event type (filing/hearing/order/notice/transaction/document/deadline/incident)
3. Clear description (10-20 words, past tense, actor-first)
4. All entity names mentioned (people, organizations, courts, institutions)
5. Confidence score
```

**Expected impact:** ~1/3 Gemini cost, better entity coverage, no more "entity linking didn't run" failures.

### 2.2 Document-level context header

Prepend a lightweight document context header (case number, court, parties, doc type) to each chunk extraction request so the LLM can resolve "the petitioner" to "Shri Nirav Jobalia" across chunks.

### 2.3 Semantic deduplication

Replace `SequenceMatcher` dedup with embedding-based cosine similarity. Add `description_embedding vector(768)` column to events table.

---

## Phase 3: Long-Term (1-3 months)

### 3.1 Event relationship graph
New `event_relationships` table with typed edges: `caused_by`, `led_to`, `supersedes`, `responds_to`, `follows_from`. Enables causal chain visualization.

### 3.2 Causal chain detection
LLM-based: identify sequential/causal relationships between events. Detect missing links (notice without reply, hearing without order).

### 3.3 Cross-document event correlation
Detect when events from different documents refer to the same real-world occurrence. Merge with provenance tracking.

### 3.4 Attorney feedback loop
`verified_by`, `verified_at`, `attorney_notes` columns. Use verified events as few-shot examples. Track extraction quality per matter type.

### 3.5 Incremental enrichment
New document → extract events → cross-reference existing → enrich entity links → detect new causal chains → invalidate only affected cache.

---

## What to Keep vs Replace

**Keep:** Events table schema, GIN indexes, Redis caching, EntityResolver, circuit breaker, cost tracking, anomaly detection, frontend cross-engine hooks, TimelineBuilder aggregation logic.

**Replace (Phase 2):** 3-step pipeline → single-pass, date-first prompt → event-first, SequenceMatcher → embedding dedup.

**Modify (Phase 1):** Dedup grouping key, chunk selection, entity linking threshold + trigger, cross-engine journey query.

---

## Verification

### Phase 1 Testing
1. **Unit tests:** Same-date different-event dedup preserves all events; true duplicates still merge; entity matching at 0.70 threshold; text search fallback returns results
2. **Integration:** Reprocess a known document with `force_reprocess=True`, verify event count increases and `entities_involved` is populated
3. **Manual:** Open entity detail panel → "Timeline Journey" → verify events now appear
4. **Regression:** Existing timeline API responses maintain shape, chat timeline still works, manual event CRUD unaffected

### Phase 2 Testing
- A/B comparison: old pipeline vs unified pipeline on same documents
- Event count, quality, entity coverage metrics
- Gemini cost comparison (target: ~1/3 of current)

---

## Implementation Order

1. Fix dedup key (1.1) — highest impact, simplest change
2. Process all chunks (1.2) — unlocks more events
3. Lower entity threshold + fix trigger (1.3) — populates entities_involved
4. Add journey text search fallback (1.4) — immediate UX fix for cross-engine
5. Write unit tests for all Phase 1 changes
6. Reprocess existing documents to backfill
7. Phase 2.1 unified extraction (after Phase 1 validated in production)
