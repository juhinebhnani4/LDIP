# Batch Optimization Plan: Reduce Gemini API Calls Per Document

## Current State (as of 2026-02-27) — Deep Audit Verified

Every number below is traced from Celery task → extractor method → `generate_content()` call.
Call counts verified by reading actual loop structures, not comments or docs.

### Pipeline stages: 100-page document, ~80 parent chunks

| Stage | Provider | Batched? | Batch Size | Gemini Calls | GPT-4 Calls | Share | Call Site |
|---|---|---|---|---|---|---|---|
| Entity extraction | Gemini | **YES** (default ON) | 5 chunks/call | **16** | 0 | 6% | `extractor.py:865` |
| Citation extraction | Gemini | **YES** (default ON) | 3 chunks/call | **27** | 0 | 10% | `citation/extractor.py:468` |
| Date extraction | Gemini | **NO** | 1 chunk/call | **80-95** | 0 | **29%** | `date_extractor.py:597` |
| Event classification | Gemini | **YES** (always ON) | 20 events/call | **3-5** | 0 | 1% | `event_classifier.py:584` |
| Entity linking | None | N/A | N/A | **0** | 0 | 0% | Pattern/regex only |
| OCR validation | Gemini | **YES** (always ON) | 20 words/call | **1-3** | 0 | <1% | `gemini_validator.py:216` |
| Alias resolution | Gemini | **YES** (medium tier) | variable | **0-5** | 0 | 1% | `entity_resolver.py:565,660` |
| Contradiction screening | Gemini | **NO** | 1 pair/call | **50-250** | 0 | **43%** | `contradiction/comparator.py:634` |
| Contradiction escalation | GPT-4 | N/A | 1 pair/call | 0 | **5-50** | — | `contradiction/comparator.py:705` |
| Injection detection | Gemini | N/A | 1/doc | **0-1** | 0 | <1% | `injection_detector.py:296` |
| **TOTAL (pipeline)** | | | | **~180-400** | **~5-50** | | |

**Typical case estimate: ~280 Gemini + ~15 GPT-4** (used for optimization calculations below)

### Variability notes

- **Date extraction 80-95**: 80 chunks × 1 call each, plus extra calls when a chunk >5000 chars
  triggers internal sub-chunking via `_split_into_chunks()` (date_extractor.py:520)
- **Contradiction screening 50-250**: Capped at 50 pairs/entity (`max_pairs=50` at comparator.py:741) × number of entities (1-5 typical).
  A doc with 5 distinct entities = up to 250 screening calls
- **Event classification 3-5**: Depends on date count. ~75 dates → ceil(75/20) = 4 calls
- **Alias resolution 0-5**: Most pairs resolve via Jaro-Winkler similarity; only ambiguous
  pairs (0.60-0.85 similarity) go to Gemini. `analyze_batch_context()` accepts arbitrary
  batch sizes (no hardcoded limit)

### Citation verification (deferred, runs after Act becomes available)

Citation verification is NOT part of the main ingestion pipeline's synchronous chain.
It fires later when an Act PDF becomes available, via THREE possible triggers:

| Trigger | How | Code |
|---|---|---|
| **Manual Act upload** | User uploads Act PDF via UI | `citations.py:1381` → `trigger_verification_on_act_upload.delay()` |
| **India Code auto-fetch** | Pipeline auto-downloads Act from indiacode.nic.in | `act_validation_tasks.py:846` → `trigger_verification_on_act_upload.delay()` |
| **Scheduled catch-up** | Periodic task picks up missed validations | `act_validation_tasks.py:1051` → `validate_acts_for_matter` → fetch → verify |

**Auto-fetch chain** (automatic, fires from `extract_citations` at `document_tasks.py:5640`):
```
extract_citations (finds unique acts)
  → validate_acts_for_matter (pattern matching, 0 LLM calls)
    → fetch_acts_from_india_code (HTTP download, 0 LLM calls)
      → _update_matter_resolutions_from_cache
        → _link_act_from_library (creates library_document)
        → ocr_and_process_library_document (OCR → chunk → embed, no Gemini)
        → trigger_verification_on_act_upload (Gemini calls happen here)
```

Act validation uses pure pattern matching (`known_acts.json` + regex garbage detection) — **0 LLM calls**.
Library document processing is lighter: OCR → chunk → embed only. No entity/citation/contradiction extraction.

**Per-citation verification Gemini calls** (in `verification_tasks.py:48-192`):

| Call | Provider | Per-Citation | When |
|---|---|---|---|
| `compare_quoted_text()` | Gemini | 0-1 | Only if quoted text exists and isn't an exact string match |
| `_generate_verification_explanation()` | Gemini | 1 | Always |
| `_generate_not_found_explanation()` | Gemini | 0-1 | Only if section not found in Act |

For 30 citations → up to **90 Gemini calls**, processed serially (1 citation at a time).
These are deferred to a background queue (`queue="default"` or `queue="low"`),
so they don't block the main ingestion pipeline or the user.

### Query-time calls (per user question, not per document)

| Stage | Provider | Calls | Call Site |
|---|---|---|---|
| RAG answer generation | Gemini | 1 | `rag/generator.py:247` |
| Query rewriting | Gemini | 0-1 | `query_rewriter.py:136` (only follow-ups) |
| Conversation summarizer | Gemini | 0-1 | `summarizer.py:135` (cached in Redis) |
| Summary generation | GPT-4 | 1 | `summary_service.py` (one-time per matter) |

### Key findings

1. **Contradiction screening (~43%) and date extraction (~29%) account for ~72% of all Gemini calls**
2. Entity extraction and citation extraction are already batched — no changes needed
3. Entity linking uses pattern matching (rapidfuzz) in the pipeline path — 0 LLM calls
4. Event classification batches 20 events/call — only 3-5 calls total
5. OCR validation and alias resolution are already efficient (1-5 calls each)
6. Citation verification is user-triggered (Act upload), not part of ingestion — excluded from pipeline totals
7. `validate_act_name_with_llm()` in `citation/validation.py:498` exists but is **dead code** — never called

### Configs that control existing batching

```python
# config.py — already set, already working
entity_extraction_use_batch: bool = True        # 5 chunks/call (config.py:120)
entity_extraction_batch_size: int = 5           # (config.py:121)
citation_batching_enabled: bool = True          # 3 chunks/call (config.py:335)
citation_batch_size: int = 3                    # (config.py:334)
```

Set `*_ENABLED=false` via env var to disable (falls back to 1 chunk/call).

### Rate limiter bottleneck

```python
# config.py:134-136 — current free tier settings
gemini_max_concurrent_requests: int = 1    # Only 1 parallel call allowed
gemini_min_request_delay: float = 6.0      # 6 seconds between calls
gemini_requests_per_minute: int = 10       # 10 RPM
```

At 10 RPM with ~281 calls → **~28 minutes** of Gemini rate-limiting per document.
Upgrading to paid tier (1000 RPM) would cut this to ~17 seconds.

---

## Optimization Opportunity: Date Extraction Batching

### Why date extraction, not contradiction screening

| Factor | Date extraction | Contradiction screening |
|---|---|---|
| Calls | ~80 | ~150 (3 entities × 50 pairs) |
| Batching difficulty | Low (concat chunks) | High (each pair needs specific context) |
| Proven pattern | Citations already do this at batch=3 | No analogous batch pattern exists |
| Quality risk | Low (dates are explicit) | High (nuanced reasoning per pair) |
| Implementation effort | 4 files, mechanical | Major architectural rework |

Contradiction screening batching is a separate, larger project. Date extraction batching is low-hanging fruit.

### With batch=3 on date extraction

```
BEFORE (typical case)               AFTER
─────────────────────               ─────
Contradiction:       150 calls      Contradiction:       150 calls  (unchanged)
Date extraction:      80 calls      Date extraction:      27 calls  (80÷3=27)
Citation extraction:  27 calls      Citation extraction:  27 calls  (unchanged)
Entity extraction:    16 calls      Entity extraction:    16 calls  (unchanged)
Event classification:  4 calls      Event classification:  4 calls  (unchanged)
Others (OCR+alias+inj): 4 calls    Others:                4 calls  (unchanged)
─────────────────────────────       ─────────────────────────────
TOTAL:              ~281 calls      TOTAL:              ~228 calls  (-19%)
```

Note: Sub-chunking of large chunks (>5000 chars) may add 10-15 extra calls in practice,
but batch mode reduces these too since 3 sub-chunks would fit in 1 batch call.

### Impact on quota

| Tier | RPD | Docs/day now (281 calls) | Docs/day after (228 calls) | Improvement |
|---|---|---|---|---|
| Free (250 RPD) | 250 | ~0.9 | ~1.1 | +23% |
| Tier 1 (1,000 RPD) | 1,000 | ~3.6 | ~4.4 | +23% |

---

## Files Impacted

Only 4 files need changes. Entity and citation extraction are already done.

| # | File | Change |
|---|---|---|
| 1 | `backend/app/engines/timeline/prompts.py` | Add `DATE_EXTRACTION_BATCH_PROMPT` template |
| 2 | `backend/app/engines/timeline/date_extractor.py` | Add `extract_dates_batch_sync()` + `_parse_batch_response()` |
| 3 | `backend/app/workers/tasks/engine_tasks.py` | Change per-chunk loop → batch loop (lines 341-350) |
| 4 | `backend/app/core/config.py` | Add `date_extraction_batch_size: int = 3` |

---

## Detailed Changes

### 1. `backend/app/engines/timeline/prompts.py` — New batch prompt

**Current single-chunk prompt** (`DATE_EXTRACTION_USER_PROMPT`):
```
Extract all dates from this legal document text with surrounding context:

<document_content>{text}</document_content>
```

**New batch prompt** (`DATE_EXTRACTION_BATCH_PROMPT`):
```
Extract all dates from these legal document sections.
Each section has a unique CHUNK_ID. Group your output by chunk_id.

[CHUNK:{chunk_id_1}] (page {page_number_1})
{content_1}

[CHUNK:{chunk_id_2}] (page {page_number_2})
{content_2}

[CHUNK:{chunk_id_3}] (page {page_number_3})
{content_3}

Return JSON grouped by chunk_id:
{"chunks": {"chunk_id_1": {"dates": [...]}, "chunk_id_2": {"dates": [...]}}}
```

Follows the exact same `[CHUNK:id]` marker pattern as citation extraction,
which has been running at batch=3 in production without quality issues.

### 2. `backend/app/engines/timeline/date_extractor.py` — New batch method

**Current methods:**
- `extract_dates_sync()` — processes 1 chunk, returns `DateExtractionResult`
- `_extract_single_sync()` — internal sync Gemini call for 1 chunk (line 555)
- `_call_gemini_extract()` — async Gemini call for 1 chunk (line 303)

**New method to add:**
```python
def extract_dates_batch_sync(
    self,
    chunks: list[dict],   # [{id, content, page_number, bbox_ids}]
    document_id: str,
    matter_id: str | None = None,
) -> dict[str, DateExtractionResult]:
    """Extract dates from multiple chunks in a single Gemini call.

    Args:
        chunks: List of chunk dicts with id, content, page_number, bbox_ids.
        document_id: Document ID for cost tracking.
        matter_id: Matter ID for cost tracking.

    Returns:
        Dict mapping chunk_id → DateExtractionResult.
    """
```

**Implementation pattern** (mirrors `CitationExtractor.extract_from_batch_sync()`):
1. Concatenate chunk texts with `[CHUNK:{id}]` markers
2. Cap each chunk at 5000 chars (same as single-chunk mode)
3. Send single Gemini call with `DATE_EXTRACTION_BATCH_PROMPT`
4. Parse response JSON — expect `{"chunks": {"id": {"dates": [...]}}}`
5. Convert each chunk's dates to `ExtractedDate` objects with correct page_number/bbox_ids
6. On parse failure, fall back to processing chunks individually

**Key detail:** Each `ExtractedDate` needs its `page_number` and `bbox_ids` set from the
chunk metadata, not from the LLM response. The LLM extracts date text/value/context;
the calling code attaches spatial attribution.

### 3. `backend/app/workers/tasks/engine_tasks.py` — Change loop to batch

**Current code** (lines 341-350):
```python
for idx, chunk in enumerate(chunks_to_process):
    chunk_result = date_extractor.extract_dates_sync(
        text=chunk.content,
        document_id=document_id,
        matter_id=matter_id,
        page_number=chunk.page_number,
        bbox_ids=chunk.bbox_ids or [],
    )
    all_dates.extend(chunk_result.dates)
```

**New code:**
```python
batch_size = get_settings().date_extraction_batch_size  # default 3

for i in range(0, len(chunks_to_process), batch_size):
    batch = chunks_to_process[i : i + batch_size]
    batch_dicts = [
        {
            "id": chunk.id if hasattr(chunk, 'id') else str(i + j),
            "content": chunk.content,
            "page_number": chunk.page_number,
            "bbox_ids": chunk.bbox_ids or [],
        }
        for j, chunk in enumerate(batch)
    ]

    batch_results = date_extractor.extract_dates_batch_sync(
        chunks=batch_dicts,
        document_id=document_id,
        matter_id=matter_id,
    )

    for chunk_id, result in batch_results.items():
        all_dates.extend(result.dates)

    # Update progress
    if job_id and total_chunks > 1:
        progress = 30 + int((i + len(batch)) / total_chunks * 40)
        ...
```

### 4. `backend/app/core/config.py` — New config

```python
# Date extraction configuration
date_extraction_batch_size: int = 3          # Chunks per batch Gemini call
```

---

## Risk Analysis

### Why batch=3 is safe for date extraction

| Risk | Mitigation |
|---|---|
| LLM misses dates in longer prompts | 3 chunks ≈ 3-6K tokens — well within attention span |
| Page attribution errors | Page number is passed as metadata per chunk marker, not inferred by LLM |
| Parse failure loses 3 chunks of work | Fallback: retry chunks individually on parse failure |
| Response format change breaks parser | Same `{"chunks": {...}}` format proven in citation extraction |

### Why NOT batch=5 or batch=10

- **batch=5**: Entity extraction already uses this, but date extraction prompts are longer
  (include `context_before`/`context_after`), so effective input is larger per chunk.
  At batch=5, total prompt could reach 30K+ tokens — LLM quality degrades.
- **batch=10**: Too much text. Date extraction requires finding subtle date references
  in legal text. Spreading attention across 10 chunks risks missing dates.
- **batch=3**: Matches citation extraction's proven batch size. ~9-15K token inputs.
  Citation extraction has been running at batch=3 in production with no quality issues.

### Fallback strategy

If `extract_dates_batch_sync()` fails to parse the batched response:
1. Log warning with batch details
2. Fall back to `extract_dates_sync()` for each chunk individually
3. This costs 3 extra calls but prevents data loss
4. Same pattern used by `CitationExtractor.extract_from_batch_sync()` (line 520)

---

## What Already Works (No Changes Needed)

### Entity extraction — already batched at 5
- **Config:** `entity_extraction_use_batch=True`, `entity_extraction_batch_size=5`
- **Method:** `MIGEntityExtractor.extract_entities_batch()` (extractor.py:787-943)
- **Prompt:** `BATCH_ENTITY_EXTRACTION_PROMPT` with `=== SECTION {chunk_id} ===` markers
- **Task loop:** `_process_mega_batch()` in document_tasks.py:4254-4500
- **Limits:** 6000 chars/chunk, 25000 chars/batch

### Citation extraction — already batched at 3
- **Config:** `citation_batching_enabled=True`, `citation_batch_size=3`
- **Method:** `CitationExtractor.extract_from_batch_sync()` (extractor.py:399-527)
- **Prompt:** `CITATION_EXTRACTION_PROMPT` with `[CHUNK:chunk_id]` markers
- **Task loop:** Nested batch loop in document_tasks.py:5426-5504
- **Response:** `{"chunks": {"chunk_id": {"citations": [...]}}}`

### Event classification — always batched at 20
- **Method:** `EventClassifier.classify_events_batch_sync()` (event_classifier.py:530)
- **Batch size:** 20 events per call (MAX_BATCH_SIZE, event_classifier.py:49)
- **Result:** 3-5 calls for ~60-100 dates (ceil(N/20)). Triggered when `auto_classify=True`

### Entity linking — no LLM calls in pipeline
- Pipeline path uses fuzzy string matching (rapidfuzz), not Gemini
- Gemini path only used in async mode with `use_gemini=True` (not invoked from pipeline)

### OCR validation — already batched at 20 words
- Only low-confidence words sent to Gemini (not all words)
- Batched in groups of 20 words per call (`gemini_validator.py:216,373`)
- Typical: 1-3 calls per document (depends on OCR quality)

### Alias resolution — already batched at 10 pairs
- Three tiers: high similarity (auto-link, 0 calls), medium (batch LLM, ~2 calls), low (skip, 0 calls)
- Only medium-confidence pairs (0.60-0.85) go to Gemini

---

## Future Optimization: Contradiction Screening Batching

Contradiction screening is the biggest consumer (~150 calls, 53% of typical total).
Currently 1 Gemini screening call per statement pair.

This is a harder problem than date extraction batching:
- Each pair needs specific entity context and two full statement texts
- Batching pairs risks cross-contamination between comparisons
- The two-tier routing (Gemini screens → GPT-4 escalates) makes batching complex
- Quality is critical — missed contradictions are the product's core value prop

**Recommendation:** Tackle this as a separate project after date extraction batching is validated.
Potential approaches:
- Batch 3-5 pairs per screening call with clear pair markers
- Pre-filter obvious non-contradictions (different entities, different topics) before LLM
- Cache screening results to avoid re-screening on document re-processing

---

## Implementation Checklist

- [ ] Add `DATE_EXTRACTION_BATCH_PROMPT` to `prompts.py`
- [ ] Add `extract_dates_batch_sync()` to `DateExtractor` class
- [ ] Add `_parse_batch_response()` to `DateExtractor` class
- [ ] Add `date_extraction_batch_size: int = 3` to `config.py`
- [ ] Update `engine_tasks.py` loop from per-chunk to per-batch
- [ ] Add fallback: on batch parse failure, retry chunks individually
- [ ] Add rate limiter wrapping to the new batch method (use `get_distributed_rate_limiter`)
- [ ] Test with a real document to verify date quality stays consistent

---

## Expected Outcome

| Metric | Before | After |
|---|---|---|
| Total Gemini calls per 100-page doc | ~281 | ~228 |
| Date extraction calls | 80 | 27 |
| Docs/day (free tier, 250 RPD) | ~0.9 | ~1.1 |
| Docs/day (Tier 1, 1,000 RPD) | ~3.6 | ~4.4 |
| Processing time per doc (free tier) | ~28 min | ~23 min |
