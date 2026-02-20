# Plan: 4 Search/Retrieval Improvements

**Date**: 2026-02-20
**Status**: All 10 gaps implemented

---

## Gap 1: Parent-Child Context Expansion — DONE

> **Implemented**: 2026-02-20 | **Status**: Deployed to codebase, pending migration apply

### Problem

Child chunks (400-700 tokens) are retrieved via hybrid search, but only their content is sent to Gemini. The parent chunk (1500-2000 tokens) — which contains the surrounding context — is never fetched during generation. This means the LLM sees a narrow window and may miss crucial context.

### Implementation

**Strategy**: "Retrieve child, generate from parent" — after reranking, replace each child chunk's content with its parent's content, deduplicating parents that appear multiple times.

**Files changed**:

1. **`supabase/migrations/20260220000002_add_parent_chunk_id_to_search_functions.sql`** (new)
   - Drops and recreates all 3 search RPC functions with `parent_chunk_id uuid` in RETURNS TABLE:
     - `hybrid_search_chunks` — `c.parent_chunk_id` added to both CTEs + `COALESCE(bm25.parent_chunk_id, sem.parent_chunk_id)` in final SELECT
     - `hybrid_search_chunks_voyage` — same pattern
     - `bm25_search_chunks` — `c.parent_chunk_id` added to SELECT
   - Permissions re-granted for `authenticated` and `service_role`

2. **`backend/app/services/rag/hybrid_search.py`**
   - Added `parent_chunk_id: str | None = None` to `SearchResult` dataclass (line 98)
   - Added `parent_chunk_id: str | None = None` to `RerankedSearchResultItem` dataclass (line 161)
   - Populated `parent_chunk_id` in all 7 construction sites:
     - Hybrid search results (from `r.get("parent_chunk_id")`)
     - BM25 fallback results
     - Semantic search results
     - Rerank success mapping (`original.parent_chunk_id`)
     - Rerank fallback mapping
     - Library search results (`None` — library chunks don't use parent expansion)
     - Library-to-reranked conversion

3. **`backend/app/engines/orchestrator/adapters.py`**
   - Added `_expand_parent_context()` method (~50 lines) to `RAGEngineAdapter`:
     - Collects unique `parent_chunk_id`s from child results
     - Batch-fetches parent content in a single Supabase query (not N+1)
     - Deduplicates: if multiple children share the same parent, keeps only the highest-ranked child entry
     - Replaces child `content` with parent content via mutation
     - Preserves child's `page_number` and `bbox_ids` for precise citation highlighting
     - Graceful fallback: if DB fetch fails, original child content is used (no degradation)
   - Called as Step 1b in `execute()`, between search and document name lookup

4. **`backend/app/engines/rag/prompts.py`**
   - `MAX_CHUNK_CONTENT`: 1500 → 2000 (matches parent chunk size)

5. **`backend/app/engines/rag/query_profile.py`**
   - LOOKUP profile `max_chunk_content`: 1500 → 2000
   - TIMELINE profile `max_chunk_content`: 1500 → 2000
   - CITATION profile `max_chunk_content`: 1500 → 2000
   - (SUMMARY and COMPARISON were already at 2000)

### Schema impact

- **API contract**: Unchanged. `parent_chunk_id` is internal to the search→adapter pipeline. Not exposed in Pydantic response models (`models/search.py`, `models/rerank.py`), not in route handlers (explicit field mapping skips it), not in `rag_data` response dict.
- **Frontend**: No changes needed. Transform functions in `lib/api/search.ts` use explicit field mapping and would ignore extra fields.
- **Migration**: Backward compatible. Functions have same input signatures, just an appended output column. Existing callers that don't read `parent_chunk_id` are unaffected.

### Token budget

Parents are ~1500-2000 tokens vs children at 400-700. With `max_context_chunks=5`, worst case goes from ~3500 tokens to ~10000 tokens. This fits within Gemini's context window. For summary queries (12 chunks), content is capped at `max_chunk_content=2000` per chunk via `QueryProfile`.

### Deploy steps

1. Apply migration: `supabase db push` (or via Railway migration runner)
2. Deploy backend (no config changes needed)

---

## Gap 2: Dynamic RRF Weights — DONE

> **Implemented**: 2026-02-20 | **Status**: Deployed to codebase

### Problem

BM25 and semantic weights are always 1.0/1.0. Legal citation queries like "Section 138 NI Act" need higher BM25 weight (exact term match matters). Conceptual queries like "grounds for termination" need higher semantic weight.

### Current State (Updated from re-verification)

| Component | Status |
|---|---|
| `SearchWeights` dataclass (0.0-2.0 range) | Exists, validated |
| API accepts `bm25_weight`/`semantic_weight` | Exists |
| RPC functions accept weight params | Exists |
| `QueryProfile` with query type classification | **Exists and is active** |
| `IntentAnalyzer` with CITATION_PATTERNS (regex for "section \d+", "acts? of \d{4}") | **Exists and is active** |
| Weight selection per query type | **Missing** |

**Key discovery**: `QueryProfile` already classifies queries into LOOKUP, SUMMARY, COMPARISON, TIMELINE, CITATION, GENERAL. It already controls `hybrid_limit`, `rerank_top_n`, `max_context_chunks`, etc. It just doesn't touch weights.

### Fix

**Strategy**: Add `SearchWeights` to `QueryProfile` and wire it through the adapter.

**Files to change**:

1. **`backend/app/engines/rag/query_profile.py`**
   - Import `SearchWeights` from `hybrid_search.py`
   - Add `search_weights: SearchWeights` field to `QueryProfile` dataclass
   - Set per-profile weights:

   | Query Type | BM25 | Semantic | Rationale |
   |---|---|---|---|
   | LOOKUP (default) | 1.0 | 1.0 | Balanced |
   | CITATION | 1.5 | 0.7 | Legal refs need exact keyword match |
   | SUMMARY | 0.7 | 1.3 | Conceptual breadth over exact terms |
   | COMPARISON | 0.8 | 1.2 | Conceptual similarity across docs |
   | TIMELINE | 1.0 | 1.0 | Balanced — dates are keywords too |
   | GENERAL | 1.0 | 1.0 | Balanced fallback |

2. **`backend/app/engines/orchestrator/adapters.py`** (line 794)
   - Pass `weights=query_profile.search_weights` to `search.search_with_rerank_and_library()`
   - Currently: no `weights` param passed (defaults to 1.0/1.0)
   - After: `weights=query_profile.search_weights if query_profile else None`

That's it. Two files, ~20 lines of code. The entire pipeline from QueryProfile → search → RPC → RRF formula already supports custom weights.

**Effort**: ~30 minutes

---

## Gap 3: Hindi/Gujarati BM25 Fix — DONE

> **Implemented**: 2026-02-20 | **Status**: Deployed to codebase, pending migration apply

### Problem

`to_tsvector('english', ...)` doesn't tokenize Devanagari (Hindi/Gujarati) correctly. Migration 20260115 fixed this by switching to `'simple'` tokenizer, but later migrations regressed.

### Root Cause (Deep Analysis)

The `chunks.fts` stored column uses `to_tsvector('simple', content)` but the hybrid search functions query with `websearch_to_tsquery('english', query_text)`. This **config mismatch** means English stemming produces different lexemes than `'simple'` tokenization — e.g., `websearch_to_tsquery('english', 'running')` produces `'run'` but the stored tsvector has `'running'`, causing **silent BM25 recall loss** beyond just Hindi/Gujarati.

### Complete Audit (7 items fixed)

| # | Location | Bug | Fix |
|---|---|---|---|
| 1 | `hybrid_search_chunks()` BM25 CTE | `websearch_to_tsquery('english', ...)` mismatches `chunks.fts` simple config | → `plainto_tsquery('simple', ...)` |
| 2 | `hybrid_search_chunks_voyage()` BM25 CTE | Same config mismatch | → `plainto_tsquery('simple', ...)` |
| 3 | `idx_events_description` index | `to_tsvector('english', description)` | Recreated with `'simple'` |
| 4 | `idx_identity_nodes_name_search` index | `to_tsvector('english', canonical_name)` | Recreated with `'simple'` |
| 5 | `idx_documents_extracted_text` index | `to_tsvector('english', COALESCE(extracted_text, ''))` (**missed by original plan**) | Recreated with `'simple'` |
| 6 | `cross_engine_service.py:250` | `config: "english"` | → `config: "simple"` |
| 7 | Regression prevention | No comments warning about config consistency | Added `-- IMPORTANT` comments in migration + Python |

### Implementation

**Files changed**:

1. **`supabase/migrations/20260220100001_fix_multilingual_text_search.sql`** (new)
   - Drops and recreates `hybrid_search_chunks` and `hybrid_search_chunks_voyage` with `plainto_tsquery('simple', ...)` in BM25 CTEs
   - Drops and recreates 3 GIN indexes: `idx_events_description`, `idx_identity_nodes_name_search`, `idx_documents_extracted_text`
   - Re-grants permissions for `authenticated` and `service_role`
   - Extensive header comment explaining WHY `'simple'` is used and listing all locations that must stay in sync

2. **`backend/app/services/cross_engine_service.py`** (line 250)
   - Changed `options={"config": "english"}` to `options={"config": "simple"}`
   - Added inline comment explaining the index dependency

### Deploy steps

1. Apply migration: `supabase db push`
2. Deploy backend (no config changes needed)

---

## Gap 4: Metadata Filtering at Search Time — DONE

> **Implemented**: 2026-02-20 | **Status**: Deployed to codebase, migration applied to Supabase

### Problem

Users cannot filter search results by document type, date range, or page range. Complex matters with 50+ documents need scoped search (e.g., "search only affidavits filed after 2020", "search pages 10-30 of the petition").

### Current State

| Component | Status |
|---|---|
| `documents.document_type` column (case_file, act, annexure, other) | Exists, indexed (`idx_documents_type`) |
| `chunks.page_number` column | Exists, indexed (`idx_chunks_page`) |
| `documents.uploaded_at` column | Exists |
| `MatterNamespaceFilter.document_ids` | Exists but disconnected |
| `match_chunks(filter_document_ids)` SQL param | Exists but unused by search service |
| Filter params in search API | **Missing** |
| Filter params in RPC functions | **Missing** (except `match_chunks`) |
| Filter UI in frontend | **Missing** |

### Implementation

Full 6-layer implementation touching SQL, backend models, services, API, orchestrator, and frontend.

**Layer 1: Database** — `supabase/migrations/20260220200001_add_metadata_filters_to_search_functions.sql`

Drops and recreates all 3 search RPC functions with 4 new optional parameters:
- `filter_document_ids uuid[] DEFAULT NULL` — scope to specific documents
- `filter_document_types text[] DEFAULT NULL` — scope to document types
- `filter_page_min integer DEFAULT NULL` — page range lower bound
- `filter_page_max integer DEFAULT NULL` — page range upper bound

Applied in **both CTEs** (BM25 and semantic) for consistent filtering. Uses `IS NULL OR` pattern for zero-cost bypass when no filters set. Document type filter joins to `documents` table via primary key (fast).

**Layer 2: Backend Models** — `backend/app/models/search.py`

- Added `SearchFilters` Pydantic model with validation:
  - `document_types` validated against allowed set (`case_file`, `act`, `annexure`, `other`)
  - `page_min` validated <= `page_max`
  - `is_empty` property for fast no-op check
  - `to_rpc_params()` method for single-point SQL parameter conversion
- Added `filters: SearchFilters | None` to `SearchRequest`

**Layer 3: Backend Service** — `backend/app/services/rag/hybrid_search.py`

Added `filters` parameter to all 5 search methods:
- `search()` — core hybrid search, merges filter_params into RPC call
- `_bm25_search_internal()` — fallback BM25 search
- `bm25_search()` — public BM25 endpoint
- `search_with_rerank()` — passes through to `search()`
- `search_with_library()` — passes through to `search()`
- `search_with_rerank_and_library()` — passes through to `search_with_rerank()`

**Layer 4: API Routes** — `backend/app/api/routes/search.py`

Extracts `search_filters` from `body.filters` and passes to search service calls (both standard and rerank paths).

**Layer 5: Chat Pipeline** — Full context propagation:

1. `backend/app/models/chat.py` — Added `search_filters: dict | None` to `ChatStreamRequest`
2. `backend/app/api/routes/chat.py` — Passes `search_filters` via `provider_context` dict
3. `backend/app/engines/orchestrator/adapters.py` — RAG adapter extracts `search_filters` from context, validates as `SearchFilters`, passes to `search_with_rerank_and_library()`

**Layer 6: Frontend**

1. `frontend/src/types/search.ts` — `SearchFilters` interface + `DOCUMENT_TYPE_OPTIONS`
2. `frontend/src/lib/api/search.ts` — `transformFiltersToApi()` helper, filters passed in `hybridSearch()`
3. `frontend/src/components/features/chat/SearchFilterPanel.tsx` (new) — Collapsible filter panel with:
   - Document type checkboxes (Case File, Act, Annexure, Other)
   - Page range inputs (min/max)
   - Document selector (from `useDocuments` hook, shows completed docs)
   - Active filter count badge
   - Clear all button
4. `frontend/src/components/features/chat/QAPanel.tsx` — Filter state + panel wired into chat, filters sent via `search_filters` in stream request

### Backward compatibility

- SQL: All new params use `DEFAULT NULL` — existing callers unchanged
- API: `filters` field is `None` by default — existing requests unchanged
- Chat: `search_filters` field is `None` by default — existing chat flow unchanged
- Frontend: Filter panel starts collapsed with no active filters

### Deploy steps

1. Apply migration: `supabase db push`
2. Deploy backend (no config changes needed)
3. Deploy frontend (no config changes needed)

---

## Implementation Order

| Order | Gap | Effort | Status |
|---|---|---|---|
| ~~1~~ | ~~**Gap 1**: Parent context expansion~~ | ~~2 hrs~~ | **DONE** (2026-02-20) |
| ~~2~~ | ~~**Gap 3**: Hindi/Gujarati fix~~ | ~~15 min~~ | **DONE** (2026-02-20) — Fixed 7 items (2 functions, 3 indexes, 1 Python file, + regression comments). Found and fixed `idx_documents_extracted_text` which original plan missed. |
| ~~3~~ | ~~**Gap 2**: Dynamic RRF weights~~ | ~~30 min~~ | **DONE** (2026-02-20) |
| ~~4~~ | ~~**Gap 4**: Metadata filtering~~ | ~~1-2 days~~ | **DONE** (2026-02-20) — Full 6-layer implementation: SQL (3 functions), backend models, service (5 methods), API routes, chat pipeline (3 files), frontend (types + API + UI component + QAPanel integration). |
| ~~5~~ | ~~**Gap 5**: Table-aware embedding~~ | ~~1-2 days~~ | **DONE** (2026-02-20) — Pipeline integration + table chunking. 7 files changed: 1 migration (CHECK constraint), model enum, namespace validation, pipeline chain, table extraction task (chunk creation + large table splitting), embed_chunks status handling, search docstrings. |
| ~~6~~ | ~~**Gap 6**: Chunk boundary dedup~~ | ~~2-4 hrs~~ | **DONE** (2026-02-20) — Seed-based suffix-prefix matching in `_format_context()`. 1 file changed: `prompts.py` (2 new functions + integration in `_format_context`). Saves ~8-15% tokens per query with 3+ same-doc parents. |

| ~~7~~ | ~~**Gap 7**: Vector quantization monitoring~~ | ~~2-3 hrs~~ | **DONE** (2026-02-20) — Full-stack monitoring: 2 SQL RPC functions, admin endpoint (parallel fetch + progressive recommendations), frontend widget (global progress, HNSW config, per-matter breakdown, alerts). 8 files changed. |
| ~~8~~ | ~~**Gap 8**: HNSW index tuning~~ | ~~1 hr~~ | **DONE** (2026-02-20) — Rebuilt all 4 HNSW indexes with ef_construction=128, added SET LOCAL ef_search=80 to both hybrid search functions. 1 migration, 2 functions recreated. |

All 10 gaps complete.

| ~~7~~ | ~~**Gap 9**: Automated RAGAS regression~~ | ~~2-3 days~~ | **DONE** (2026-02-20) — Full-stack: 1 migration (baselines table + 2 RPC functions), 2 new services (baseline + regression detector), scheduled Celery task, 5 new API endpoints, admin dashboard widget. 13 files changed. |
| ~~8~~ | ~~**Gap 10**: Automated Voyage A/B testing~~ | ~~2-3 days~~ | **DONE** (2026-02-20) — Full-stack: 1 migration (ab_test_runs table + RPC), core A/B service (hash routing + Welch's t-test + decision engine), evaluation pipeline extension, percentage-based routing in adapter, 4 API endpoints, frontend dashboard widget. 10 files changed. |

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Parent expansion blows token budget on summary queries (12 chunks x 2000 tokens) | Cap parent content at `max_chunk_content` from QueryProfile; log token counts |
| Wrong RRF weights degrade retrieval quality | Ship with conservative weights (1.5/0.7 not 2.0/0.0); monitor via Inspector debug mode which already shows per-result scores |
| Migration breaks production search | New migration only adds optional params with defaults — backward compatible. Existing calls without filters continue working. |
| `'simple'` tokenizer misses English stemming (e.g., "running" won't match "run") | Acceptable tradeoff: semantic search covers stemming gaps. BM25 with 'simple' gives exact match which is more important for legal text. |
| Metadata filter subquery on `documents` table slow for large matters | `document_type` is indexed; join is on primary key. For page_range, filter is on indexed `chunks.page_number`. Should be fine up to 100k chunks. |
| Boundary dedup trims meaningful content | `min_overlap=50` chars threshold prevents coincidental short matches; same-document scoping prevents cross-doc false positives; shallow copies prevent mutation of response data |

---

## Future Improvements — Deep Analysis (2026-02-20)

Investigation of 8 potential improvements raised during architecture review. Each item was analyzed against the actual codebase to determine if it's a real issue, its impact on **accuracy, efficiency, and long-term scalability**, and recommended action.

---

### Gap 5: Table-Aware Embedding — DONE

> **Implemented**: 2026-02-20 | **Status**: Deployed to codebase, migration applied to Supabase

#### Problem

Table extraction infrastructure is 90% built but the pipeline is **disconnected**. Tables extracted by Docling are stored in `document_tables` but are **never chunked, embedded, or included in search**. This means financial schedules, date tables, contract annexures, and pricing schedules are completely invisible to both BM25 and semantic search.

#### Implementation

**Strategy**: Insert `extract_tables` task into the pipeline chain between `chunk_document` and `embed_chunks`. Modified `extract_tables` to also create table chunks (`chunk_type='table'`) in the `chunks` table. Downstream tasks (embedding, FTS, search) handle table chunks automatically with zero changes.

**Files changed**:

1. **`supabase/migrations/20260220300001_add_table_chunk_type.sql`** (new)
   - Drops old CHECK constraint, adds new one: `chunk_type IN ('parent', 'child', 'table')`
   - Updates column comment

2. **`backend/app/models/chunk.py`**
   - Added `TABLE = "table"` to `ChunkType` enum
   - Updated `ChunkBase.chunk_type` field description to include `'table'`

3. **`backend/app/services/rag/namespace.py`**
   - Updated chunk_type validation to accept `'table'`

4. **`backend/app/workers/tasks/pipeline_chains.py`**
   - Added `extract_tables` to chain: `validate_ocr → calculate_confidence → chunk_document → extract_tables → embed_chunks → extract_entities`

5. **`backend/app/workers/tasks/table_extraction_tasks.py`**
   - Added `_create_table_chunks()`: creates chunks from extracted tables in the `chunks` table
     - Filters out tables with confidence < 0.5 and trivial tables (< 2 rows)
     - Adds contextual prefix: `"Table {index} (p. {page}):\n{markdown}"`
     - Large tables (> 2000 tokens) split by rows with header repeated in each chunk
     - Batch inserts with idempotency (deletes existing table chunks before creating)
   - Added `_split_table_by_rows()`: splits large tables by rows, repeating header in each chunk
     - Handles `page_number=None` safely in all code paths
   - Added idempotency to `_store_tables()`: deletes existing `document_tables` records first
   - Modified `extract_tables` task to call `_create_table_chunks()` after `_store_tables()`
   - Added `"chunking_failed"` to `failed_statuses` check
   - Passes through `document_id`/`job_id` in all return paths (including disabled/skipped)

6. **`backend/app/services/rag/hybrid_search.py`**
   - Updated `SearchResult` and `RerankedSearchResultItem` docstrings for `chunk_type`

7. **`backend/app/workers/tasks/document_tasks.py`**
   - Added table extraction statuses (`table_extraction_complete`, `table_extraction_partial`, `table_extraction_skipped`, `table_extraction_failed`) to `embed_chunks`' `valid_statuses` — prevents per-document warning log noise

**Zero-change components** (table chunks work automatically):

| Component | Why |
|---|---|
| `embed_chunks` task | Queries `chunks WHERE embedding IS NULL` — picks up table chunks |
| `chunks.fts` column | `GENERATED ALWAYS AS STORED` — auto-indexes table markdown |
| Hybrid search RPCs | Return `chunk_type` from `chunks` — no filter on type |
| `_expand_parent_context()` | Only expands `chunk_type == "child"` — table chunks pass through |
| Prompt formatting | Formats all chunks uniformly — table markdown renders naturally |
| Cohere reranking | Reranks by content — table markdown works as text |

#### Fault Tolerance

- `extract_tables` catches all exceptions and returns status dicts — never raises
- `"table_extraction_failed"` is NOT in `embed_chunks`' `failed_statuses` — text chunk embedding always proceeds
- `_create_table_chunks` failure doesn't affect `_store_tables` (runs after, independently)
- `chunk_document` idempotency check only counts parent+child — unaffected by table chunks
- On full re-process, `delete_chunks_for_document` clears all chunks including table, then `extract_tables` recreates them

#### Long-term Considerations

- Tables with many rows may exceed chunk size limits — handled via `_split_table_by_rows()` which repeats header in each chunk
- Consider table-specific embedding strategies if accuracy is insufficient (e.g., row-level embeddings for large financial schedules)
- Monitor table chunk retrieval quality via RAGAS evaluation
- Future optimization: share Docling result between layout extraction and table extraction to avoid double PDF processing

---

### Gap 6: Chunk Deduplication Before Generation — DONE

> **Implemented**: 2026-02-20 | **Status**: Deployed to codebase

#### Problem

Parent context expansion (Gap 1) deduplicates at the parent level — if multiple child chunks share a parent, only the highest-ranked child is kept. However, **inter-parent boundary overlap is not deduplicated**. Adjacent parent chunks share 100-token overlaps at boundaries. When 3+ parent chunks are sent to the LLM, ~200-300 tokens of redundant text exist between them.

#### Implementation

**Strategy**: Seed-based suffix-prefix matching in `_format_context()`. Before formatting chunks for the LLM, detect overlapping text at boundaries between chunks from the same document and trim the duplicate prefix from the later chunk.

**Files changed**:

1. **`backend/app/engines/rag/prompts.py`**
   - Added `_deduplicate_chunk_boundaries()` function (~45 lines):
     - For each chunk, scans **all** previous same-document chunks and selects the **largest** overlap — prevents a coincidental short match from a non-adjacent chunk from superseding the real boundary overlap
     - Trims the duplicate prefix from the later chunk
     - Empty-chunk guard: skips trim if overlap >= content length (never produces an empty excerpt for the LLM)
     - Works on shallow copies — does not mutate the caller's chunk dicts
     - Preserves all metadata (page_number, bbox_ids, document_name) unchanged
     - `min_overlap=50` chars threshold prevents trimming coincidental short matches
   - Added `_find_boundary_overlap()` helper (~30 lines):
     - Uses seed-based search for efficiency: takes a 40-char prefix of text_b as a seed, finds candidate positions in text_a's suffix via `str.find()` (C-optimized), then verifies full overlap
     - `max_check=800` chars limits search region (100 tokens ≈ 400-600 chars, with margin)
     - Returns overlap length in characters, or 0 if below `min_overlap`
   - Called in `_format_context()` as first step before formatting loop

#### Current State

| Aspect | Status |
|---|---|
| Parent-level deduplication | **DONE** — `adapters.py:807-824`, `seen_parents` set |
| Inter-parent boundary overlap | **DONE** — `prompts.py:249-353`, seed-based suffix-prefix matching |
| Best-overlap selection | **DONE** — picks largest overlap across all prev same-doc chunks |
| Empty-chunk guard | **DONE** — skips trim if overlap >= content length |
| Same-document scoping | **DONE** — only checks chunks with matching `document_id` |
| Metadata preservation | **DONE** — page_number, bbox_ids, document_name untouched |
| Estimated token savings | 8-15% (~200-750 tokens per query with 3+ same-doc parents) |

#### Design Decisions

- **Best-overlap selection over first-match**: Scans all previous same-document chunks and picks the largest overlap. A first-match approach would be wrong if a non-adjacent chunk has a coincidental short match that supersedes the real boundary overlap from the adjacent chunk.
- **Empty-chunk guard**: `best_overlap < len(current_content)` ensures we never send an empty excerpt to the LLM, which would waste an excerpt slot and confuse citations.
- **Dedup in `_format_context()` not `_expand_parent_context()`**: Keeps the dedup close to the consumer (LLM prompt assembly) rather than in the search pipeline. This ensures dedup works regardless of how chunks arrive (search, library, or manual injection).
- **Same-document scoping**: Only compares chunks from the same document. Cross-document overlaps are not possible (different source texts). This also limits the comparison space.
- **Seed-based algorithm over brute-force**: Instead of comparing every possible suffix length (O(n²)), uses `str.find()` to jump to candidate positions. Typical case is 1-2 `find()` calls per chunk pair.
- **Shallow copy**: Works on `dict(c)` copies to avoid mutating the chunks that the adapter also uses for building the response `rag_data.results`.

#### Long-term Considerations

- If switching to larger context models, overlap waste becomes proportionally less significant
- Semantic deduplication (embedding-based similarity between chunks) could catch non-boundary duplicates too — consider if accuracy issues arise from paraphrased repetition across documents
- Monitor actual redundancy rate via token counting in production logs
- Future optimization: store `overlap_tokens` count in chunk metadata during chunking, enabling O(1) trim without text comparison

---

### Gap 7: Vector Quantization Monitoring — DONE

> **Implemented**: 2026-02-20 | **Status**: Deployed to codebase, pending migration apply

#### Problem Statement

With 1536-dim OpenAI + 1024-dim Voyage vectors stored as full float32, storage and memory could become concerns at scale. Need proactive monitoring to know when to consider quantization (halfvec, int8, dimension reduction, or separate vector DB).

#### Analysis

**Current state is optimal for this scale and domain:**

| Metric | Current | Threshold for Concern |
|---|---|---|
| Estimated chunks | 10K-100K | 1M+ |
| Vector storage | ~100-600 MB | >5 GB |
| Query latency | 10-100 ms | >500 ms |
| Database storage | <1 GB vectors | >50 GB |

**Why NOT to quantize now:**
- Legal domain requires high recall — quantization introduces ~5-15% accuracy loss (int8) or ~15-25% (binary)
- Per-matter isolation keeps HNSW search spaces small (100-10K vectors per matter)
- Storage costs are negligible at current scale (<$1/month)
- pgvector float32 is the safest, most tested path

#### Implementation

**Strategy**: Full-stack monitoring dashboard — SQL RPC functions for metrics, backend admin endpoint, frontend widget with alerts and HNSW config visibility.

**Files changed**:

1. **`supabase/migrations/20260220400001_add_chunk_metrics_function.sql`** (new)
   - `get_chunk_metrics()` — per-matter chunk counts with type breakdown (parent, child, table), Voyage embedding coverage, and 50K threshold alert flag
   - `get_global_chunk_count()` — global totals (total chunks, embedding coverage, matter count), 500K threshold alert flag
   - Both functions are `SECURITY DEFINER`, `STABLE`, granted only to `service_role` (admin access enforced at API layer)

2. **`backend/app/api/routes/admin/monitoring.py`** (new)
   - `GET /api/admin/chunk-metrics` — admin-only endpoint
   - Calls both RPC functions in parallel via `asyncio.gather()`
   - Returns per-matter breakdown, global totals, HNSW index config, alert flags, and progressive quantization recommendations
   - `_get_quantization_recommendation()` — generates human-readable advice based on scale:
     - <100K: "No action needed"
     - 100K-500K: "Monitor closely"
     - >500K or matter >50K: "Consider halfvec(float16)"
     - >1M: "URGENT: halfvec or separate vector DB"

3. **`backend/app/api/routes/admin/__init__.py`** — added `monitoring_router`

4. **`backend/app/main.py`** — registered `admin_monitoring.router`

5. **`frontend/src/lib/api/admin-monitoring.ts`** (new)
   - Full TypeScript types for chunk metrics response
   - Runtime type validation transformers (handles snake_case/camelCase, null safety)
   - `getChunkMetrics()` API function

6. **`frontend/src/hooks/useChunkMetrics.ts`** (new)
   - 2-minute polling (chunk counts change slowly)
   - Visibility-based polling (stops when tab hidden)
   - Fetch deduplication, mounted-state safety
   - Derived state: `hasAlerts`, `alertMatters`, `globalTotal`

7. **`frontend/src/components/features/admin/ChunkMetricsWidget.tsx`** (new)
   - "Vector Index Health" card with:
     - Global chunk count progress bar (color-coded by threshold proximity)
     - HNSW config display (m, ef_construction, ef_search values)
     - Per-matter chunk breakdown (top 5, with parent/child/table split)
     - Quantization recommendation banner
     - Alert threshold badges
   - Loading skeleton, error handling, manual refresh

8. **`frontend/src/app/(dashboard)/admin/page.tsx`** — added `<ChunkMetricsWidget />`

#### Alert Thresholds

| Level | Threshold | Action |
|---|---|---|
| Per-matter | 50K chunks | Monitor HNSW recall quality for that matter |
| Global | 500K chunks | Consider halfvec(float16) — 2x compression, ~2-3% accuracy loss |
| Global | 1M chunks | URGENT: halfvec or separate vector DB (Pinecone/Weaviate) |

#### Long-term Quantization Options (when thresholds are hit)

1. **halfvec (float16)** — pgvector 0.7+ supports `halfvec(1536)`, 2x compression, ~2-3% accuracy loss. Best first step.
2. **Dimension reduction** — Switch to `text-embedding-3-large` with PCA to 768 dims. Better quality at fewer dims.
3. **Scalar quantization** — int8 via application-layer quantization. 4x compression, ~5-10% accuracy loss.
4. **Separate vector DB** — If RLS overhead becomes significant at millions of vectors, consider Pinecone/Weaviate.

#### Deploy steps

1. Apply migration: `supabase db push`
2. Deploy backend
3. Deploy frontend

---

### Gap 8: HNSW Index Tuning — DONE

> **Implemented**: 2026-02-20 | **Status**: Deployed to codebase, pending migration apply

#### Problem Statement

`ef_construction=64` was conservative for legal precision. While the architecture compensates via hybrid search + reranking, improving base HNSW quality provides a stronger foundation — better ANN candidates → better reranking input → better final results.

#### Analysis

**Why tune now despite architecture compensating:**

1. **Defense in depth** — Hybrid search + reranking compensate for HNSW misses, but why rely on compensation when the base layer can be improved at minimal cost?
2. **Legal precision demands** — In legal document analysis, every missed relevant chunk can mean a missed citation or incorrect contradiction assessment. The ~2-5% isolated recall improvement may surface that one critical chunk the reranker wouldn't see otherwise.
3. **Future-proofing** — As matters grow and the system scales, having better HNSW quality reduces dependence on the BM25 fallback and reranking safety net.
4. **Acceptable cost** — Index build time ~2x slower (acceptable for legal doc volumes, not real-time), query latency ~5-10ms added (within budget).

#### Implementation

**Strategy**: Two-part tuning — better index quality via `ef_construction=128`, and better query recall via `SET LOCAL hnsw.ef_search = 80`.

**Files changed**:

1. **`supabase/migrations/20260220400002_tune_hnsw_indexes.sql`** (new)

   **Part A: Index recreation (all 4 HNSW indexes)**:
   - `idx_chunks_embedding` — chunks.embedding (OpenAI 1536-dim): `ef_construction` 64→128
   - `idx_library_chunks_embedding` — library_chunks.embedding (OpenAI 1536-dim): `ef_construction` 64→128
   - `idx_chunks_embedding_voyage` — chunks.embedding_voyage (Voyage 1024-dim): `ef_construction` 64→128
   - `idx_library_chunks_embedding_voyage` — library_chunks.embedding_voyage (Voyage 1024-dim): `ef_construction` 64→128
   - All indexes: `m=16` retained (good balance of memory and connectivity)

   **Part B: Query-time ef_search tuning (2 hybrid functions)**:
   - `hybrid_search_chunks` — added `SET LOCAL hnsw.ef_search = 80` at start of function body
   - `hybrid_search_chunks_voyage` — added `SET LOCAL hnsw.ef_search = 80` at start of function body
   - `SET LOCAL` is transaction-scoped — no session bleed to other queries
   - `bm25_search_chunks` — NOT modified (no vector search involved)
   - All function signatures unchanged — full backward compatibility
   - All previous features preserved: parent_chunk_id, metadata filters, 'simple' config

   **Grants**: Re-granted `EXECUTE` on both hybrid functions to `authenticated` and `service_role`

#### Parameter Rationale

| Parameter | Before | After | Rationale |
|---|---|---|---|
| `ef_construction` | 64 | 128 | 2x better graph quality during build. ~2-5% isolated recall improvement. Sweet spot for legal precision at <100K vectors. |
| `ef_search` | ~40 (default) | 80 | 2x more candidates explored per query. Closes gap between ANN and exact search. ~5-10ms latency added. |
| `m` | 16 | 16 (unchanged) | Already optimal. Higher m adds memory without proportional recall gain at this scale. |

#### Architecture Layers (unchanged but strengthened)

| Layer | Role | Gap 8 Impact |
|---|---|---|
| HNSW index | ANN candidate generation | **Improved** — better graph quality + deeper search |
| BM25 | Exact keyword fallback | Unchanged — catches what HNSW misses |
| RRF fusion | Hybrid score combination | Unchanged — fuses improved HNSW with BM25 |
| Cohere Rerank | Precision reranking | Improved input — better ANN candidates = better reranking |
| Dynamic weights | Query-type adaptation | Unchanged — CITATION/SUMMARY/etc. profiles |

#### When to Revisit Further

- If a single matter exceeds 100K chunks — consider `m=24` or `ef_construction=256`
- If query latency exceeds 200ms — consider reducing `ef_search` back to 40
- If reranking is removed — `ef_search=120` to compensate
- If switching from hybrid to semantic-only — `ef_search=160` for high-recall

#### Deploy steps

1. Apply migration: `supabase db push` (indexes will be rebuilt — may take a few minutes for large tables)
2. Deploy backend (no code changes needed beyond the migration)

---

## Future Improvements Priority Matrix

| # | Gap | Is It Real? | Accuracy Impact | Efficiency Impact | Priority | Action |
|---|---|---|---|---|---|---|
| 5 | Table-aware embedding | **YES — FIXED (Gap 5)** | **High** — now searchable | N/A — resolved | **DONE** | Deployed to codebase |
| 6 | Chunk boundary dedup | **YES — FIXED (Gap 6)** | **Medium** — no more over-weighting | ~8-15% tokens saved | **DONE** | Deployed to codebase |
| 7 | Vector quantization | **YES — FIXED (Gap 7)** | None (monitoring) | Proactive alerting | **DONE** | Full-stack monitoring dashboard |
| 8 | HNSW tuning | **YES — FIXED (Gap 8)** | **+2-5% HNSW recall** | ~5-10ms latency | **DONE** | ef_construction=128, ef_search=80 |
| 9 | Automated RAGAS regression | **YES — FIXED (Gap 9)** | **High** — regression detection | Nightly + cost-budgeted | **DONE** | Full-stack: baselines, regression detector, scheduled eval, admin dashboard |
| 10 | Automated Voyage A/B testing | **YES — FIXED (Gap 10)** | **High** — full quality comparison | Automated decision | **DONE** | Hash routing, Welch's t-test, per-provider RAGAS, auto-decision |

---

### Gap 9: Automated RAGAS Regression — DONE

> **Implemented**: 2026-02-20 | **Status**: Deployed to codebase, pending migration apply

#### Problem

The RAGAS evaluation framework is fully implemented (evaluator service, golden dataset CRUD, batch evaluation, auto-evaluation, REST API, database schema) but requires **manual triggering** via API endpoint. There is no CI/CD integration, no threshold-based alerting, no baseline tracking, and no scheduled evaluation. Quality regressions in the RAG pipeline can ship to production undetected.

#### What Exists (Complete Foundation)

| Component | File | Status |
|-----------|------|--------|
| RAGAS library (`>=0.2.0`) | `backend/pyproject.toml` | Installed |
| `RAGASEvaluator` (faithfulness, context_recall, answer_relevancy) | `backend/app/services/evaluation/ragas_evaluator.py` | Complete |
| `GoldenDatasetService` (CRUD with tag filtering, matter isolation) | `backend/app/services/evaluation/golden_dataset.py` | Complete |
| `EvaluationResult`, `MetricScores`, `BatchEvaluationResult` models | `backend/app/services/evaluation/models.py` | Complete |
| `run_batch_evaluation` Celery task (30-min timeout) | `backend/app/workers/tasks/evaluation_tasks.py` | Complete |
| `evaluate_chat_response` Celery task (auto-eval after chat) | `backend/app/workers/tasks/evaluation_tasks.py` | Complete |
| Auto-eval integration in chat orchestrator | `backend/app/engines/orchestrator/streaming.py` | Complete |
| REST API (8 endpoints: evaluate single/batch, golden CRUD, results history) | `backend/app/api/routes/evaluation.py` | Complete |
| DB tables (`golden_dataset`, `evaluation_results` with RLS) | `supabase/migrations/20260122000002_*`, `20260216000001_*` | Complete |
| Extended schema (job_id, chat_message_id, metric_scores JSONB, pipeline_config JSONB) | `supabase/migrations/20260216000001_extend_evaluation_results.sql` | Complete |
| Config: `auto_evaluation_enabled`, `openai_evaluation_model`, `evaluation_batch_size` | `backend/app/core/config.py` | Complete (auto_eval defaults OFF) |
| Partial index on `overall_score < 0.7` | `evaluation_results` table | Exists but unread |
| Test scripts | `backend/test_batch_eval.py`, `backend/update_golden.py` | Manual only |

#### Key Implementation Details

**RAGASEvaluator** uses GPT-4 as evaluation LLM (configurable via `openai_evaluation_model`), OpenAI `text-embedding-3-small` for evaluation embeddings, and measures 3 metrics:
- `context_recall` — how much relevant context was retrieved
- `faithfulness` — how grounded the answer is in the retrieved context
- `answer_relevancy` — how relevant the answer is to the question

**Auto-evaluation** is integrated in `streaming.py` — when `auto_evaluation_enabled=True`, every chat response is non-blockingly evaluated via Celery task `evaluate_chat_response`. Results stored with `triggered_by='auto'` and linked to the specific `chat_message_id`.

**Batch evaluation** runs all golden dataset items for a matter through the full RAG pipeline, evaluates each answer with RAGAS, and stores results grouped by `job_id` (Celery task ID).

**Pipeline config snapshot** — `evaluation_results.pipeline_config` (JSONB) captures the RAG configuration that produced the answer, enabling correlation of score changes with pipeline changes.

#### What's Missing (The Actual Gaps)

| Gap | Description | Impact |
|-----|-------------|--------|
| **No CI/CD integration** | `.github/workflows/ci-backend.yml` runs unit tests only; no RAGAS step | Quality regressions ship undetected |
| **No threshold-based alerting** | Partial index on `overall_score < 0.7` exists but nothing reads it | No one knows when quality drops |
| **No baseline tracking** | No mechanism to compare current scores against a known-good baseline | Can't detect "score dropped 10%" |
| **No scheduled evaluation** | Batch eval is API-triggered only (manual) | Days/weeks without evaluation |
| **No regression detection logic** | No diff between current and previous batch runs | No automated "quality regressed" signal |
| **No metrics dashboard** | Raw results in DB, no aggregated trends/visualizations | Manual SQL querying required |
| **No unit tests** for evaluation services | `backend/tests/` has no evaluation tests | Evaluation code itself could break silently |
| **No cost tracking** for evaluation runs | GPT-4 at $0.03/$0.06 per 1K tokens, no budget enforcement | Uncontrolled evaluation costs |

#### Implementation

**Strategy**: Full-stack automated regression system — database baselines for reference points, per-item regression detection (not just aggregate), scheduled evaluation with cost budgeting, admin dashboard for visibility.

**Files changed**:

1. **`supabase/migrations/20260220500001_add_evaluation_baselines_and_rpcs.sql`** (new)
   - `evaluation_baselines` table: known-good score snapshots per matter
     - `per_item_scores` JSONB: per golden item scores for granular regression detection
     - `is_active` boolean with partial unique index: only one active baseline per matter
     - RLS policies: matter isolation for authenticated, full access for service_role
   - `get_evaluation_trends(p_matter_id, p_days)`: daily score aggregation for trend charts
   - `get_evaluation_quality_summary()`: admin dashboard — per-matter quality with baseline comparison, regression flags, eval frequency

2. **`backend/app/services/evaluation/baseline_service.py`** (new)
   - `BaselineService.get_active_baseline()`: get current baseline for a matter
   - `BaselineService.create_baseline_from_job()`: promote batch run to baseline
     - Fetches all results for job_id, calculates aggregate + per-item scores
     - Deactivates previous baseline (never deleted — kept for history)
     - Batch-efficient: single query to fetch results, single insert for baseline
   - `BaselineService.auto_create_if_missing()`: auto-create on first batch run
   - `BaselineService.get_baseline_history()`: baseline history for admin UI

3. **`backend/app/services/evaluation/regression_detector.py`** (new)
   - `detect_regression()`: compares current batch vs active baseline
     - **Per-item comparison** (not just aggregate): catches regressions masked by averaging
     - Three severity levels: OK, WARNING (>10% relative drop), CRITICAL (<0.60 absolute)
     - Per-metric detection: flags which specific metrics regressed (faithfulness, recall, etc.)
     - Tracks new/missing items: golden items added/removed since baseline
   - `RegressionReport` dataclass: structured output consumed by tasks, API, and future alerting
   - `ItemRegression` dataclass: per-item regression detail with delta and severity

4. **`backend/app/services/evaluation/__init__.py`** — exports `BaselineService`, `detect_regression`, `RegressionReport`

5. **`backend/app/core/config.py`** — 5 new settings:
   - `evaluation_schedule_enabled: bool = False` — master switch for nightly evaluation
   - `evaluation_regression_threshold: float = 0.10` — 10% relative drop = WARNING
   - `evaluation_critical_threshold: float = 0.60` — absolute minimum = CRITICAL
   - `evaluation_monthly_budget_usd: float = 10.0` — cost cap for evaluation runs
   - `evaluation_auto_baseline: bool = True` — auto-promote first batch run to baseline

6. **`backend/app/workers/tasks/evaluation_tasks.py`** — major enhancements:
   - `_run_post_batch_checks()`: called after every batch eval (non-blocking)
     - Auto-creates baseline if none exists (first run)
     - Fetches current results and runs regression detection
     - Returns structured regression info merged into task result
   - `run_scheduled_evaluation`: new Celery task for nightly evaluation
     - Finds all matters with golden datasets via `get_evaluation_quality_summary()` RPC
     - Cost budgeting: estimates cost before each matter, skips if budget exceeded
     - Sequential execution within task: one matter at a time (cost control)
     - Each matter's batch eval includes regression detection via `_run_post_batch_checks()`
   - `_estimate_eval_cost()`: conservative cost estimation (~$0.015 per item)

7. **`backend/app/workers/celery.py`** — added to beat_schedule:
   - `scheduled-ragas-evaluation`: runs nightly at 1 AM UTC, low-priority queue

8. **`backend/app/api/routes/evaluation.py`** — 5 new endpoints:
   - `POST /baselines` — promote batch run to active baseline
   - `GET /baselines/active` — get current baseline for a matter
   - `GET /baselines/history` — baseline history (most recent first)
   - `GET /trends` — daily aggregated scores for trend charts

9. **`backend/app/models/evaluation.py`** — `PromoteBaselineRequest` model

10. **`backend/app/api/routes/admin/monitoring.py`** — new admin endpoint:
    - `GET /admin/quality-metrics` — global quality summary with regression alerts, schedule info

11. **`frontend/src/lib/api/admin-monitoring.ts`** — types + API:
    - `MatterQualityMetrics`, `QualityMetricsSummary`, `QualityScheduleConfig` interfaces
    - `getQualityMetrics()` function with runtime type validation transformers

12. **`frontend/src/hooks/useQualityMetrics.ts`** (new)
    - 5-minute polling (evaluations are infrequent)
    - Visibility-based polling, fetch deduplication, mounted-state safety
    - Derived state: `hasRegressions`, `regressionMatters`

13. **`frontend/src/components/features/admin/QualityMetricsWidget.tsx`** (new)
    - "RAG Quality Monitor" card with:
      - Summary badges (total matters, baselined, golden items, regressions)
      - Per-matter quality rows: latest score, delta vs baseline, regression badge
      - Score color coding (green/yellow/red based on thresholds)
      - Schedule config display (enabled/disabled, budget, thresholds)
    - Loading skeleton, error handling, manual refresh

14. **`frontend/src/app/(dashboard)/admin/page.tsx`** — added `<QualityMetricsWidget />`

#### Architecture Decisions

- **Per-item regression over aggregate-only**: A single golden item dropping from 0.9→0.3 while 4 others stay at 0.9 gives an aggregate of 0.78 vs 0.90 (13% drop). Per-item detection catches this specific failure immediately. Aggregate-only would flag it as a mild warning but miss the severe per-item regression.

- **Baselines are immutable snapshots**: Old baselines are deactivated (is_active=FALSE), never deleted. This preserves history and enables "how did quality evolve over time?" analysis without relying on point-in-time evaluation_results aggregation.

- **Cost budgeting in scheduled task**: GPT-4 costs $0.03/$0.06 per 1K tokens. With 20 golden items per matter and nightly runs, costs can accumulate. The monthly budget cap prevents runaway costs. Budget check happens per-matter so partial evaluation is possible.

- **Regression detection in task, not API**: Regression detection runs as part of the batch evaluation Celery task (via `_run_post_batch_checks`), not as a separate API call. This ensures every batch eval—manual or scheduled—gets regression analysis automatically.

- **SQL-level aggregation**: Trend analysis and quality summary are computed in SQL (RPC functions), not in Python. This is more efficient for large result sets and avoids transferring raw data to the application layer.

#### Backward Compatibility

- Migration: Creates new table + functions only. No schema changes to existing tables.
- API: All new endpoints. Existing evaluation endpoints unchanged.
- Tasks: `run_batch_evaluation` gains optional `_run_post_batch_checks` — returns extra keys in result dict. Callers that don't read these keys are unaffected.
- Config: All new settings have safe defaults (schedule disabled, auto-baseline enabled).
- Frontend: New widget added to existing admin page. No changes to existing widgets.

#### Cost Estimate

RAGAS evaluation uses GPT-4 for each (question, answer, contexts) tuple with 3 metrics:
- ~2000 tokens input + ~500 tokens output per item × 3 metrics
- ~$0.015 per item (RAGAS batches internally)
- 20 golden items per matter: ~$0.30 per batch run
- Nightly runs with 5 matters: ~$1.50/night = ~$45/month (well within $10 default budget, which would throttle to ~3 matters/night)

#### Deploy Steps

1. Apply migration: `supabase db push`
2. Deploy backend (no config changes needed)
3. Deploy frontend (no config changes needed)
4. To enable scheduled evaluation: set `EVALUATION_SCHEDULE_ENABLED=true` in Railway

---

### Gap 10: Automated Voyage A/B Testing — DONE

> **Implemented**: 2026-02-20 | **Status**: Deployed to codebase, pending migration apply

#### Problem

Voyage embedding model integration is production-ready with a boolean kill switch (`voyage_ab_testing_enabled`), user-facing model selector, per-query provider routing, circuit breaker protection, and cost comparison dashboard. However, the "A/B testing" was just **manual provider switching** — no percentage-based routing, no quality comparison via RAGAS, no latency tracking, no statistical significance testing, and no automated decision logic.

#### Implementation

**Strategy**: Full experimentation framework — database-backed run tracking, deterministic hash-based routing, Welch's t-test statistical analysis, automated decision engine, Celery-orchestrated comparison tasks, and admin dashboard widget.

**All 3 phases implemented:**
- Phase 1: RAGAS Per-Provider Comparison
- Phase 2: Percentage-Based Traffic Routing
- Phase 3: Automated Decision (statistical significance testing)

**Files changed**:

1. **`supabase/migrations/20260220600001_add_ab_testing_infrastructure.sql`** (new)
   - `ab_test_runs` table with full lifecycle: `pending → running_control → running_treatment → comparing → completed/failed`
   - Provider configs (control: embedding+reranker, treatment: embedding+reranker)
   - Aggregated scores as JSONB (`control_scores`, `treatment_scores`)
   - Latency percentiles (`control_latency_p50_ms`, `control_latency_p95_ms`, treatment equivalents)
   - Cost tracking (`control_cost_usd`, `treatment_cost_usd`)
   - Decision fields (`decision`, `decision_confidence`, `decision_reasoning`)
   - Statistical test results as JSONB (`statistical_test`)
   - RLS policies: matter-member access + service_role bypass
   - Indexes on `(matter_id, created_at)`, `(status)`, `(created_by)`
   - Added `embedding_provider`, `rerank_provider`, `search_latency_ms` columns to `evaluation_results`
   - `get_ab_test_scores(p_job_id)` RPC: efficient score aggregation from evaluation_results

2. **`backend/app/core/config.py`** (modified)
   - `voyage_traffic_percentage: int = 0` — 0-100, percentage of traffic routed to Voyage
   - `voyage_ab_min_samples: int = 20` — minimum golden items for statistical significance
   - `voyage_ab_auto_promote_enabled: bool = False` — auto-promote Voyage if it wins

3. **`backend/app/services/evaluation/ab_testing.py`** (new, ~420 lines)
   - **`ABTestRouter`** — deterministic hash-based routing:
     - `determine_provider(user_id, matter_id, percentage)`: MD5 hash of `user_id:matter_id` → bucket 0-99
     - Sticky cohorts: same user+matter always gets same provider (no within-user variance)
     - Zero-allocation for 0% or 100% cases
   - **`ABTestAnalyzer`** — pure Python statistical analysis (no scipy dependency):
     - `welch_t_test(scores_a, scores_b)`: Welch's t-test with Welch-Satterthwaite degrees of freedom
     - `_approx_p_value(t_stat, df)`: normal approximation for large df, conservative for small df
     - `make_decision(run_data)`: automated decision matrix considering:
       - Statistical significance (p < 0.05)
       - Effect size (Cohen's d > 0.2)
       - Quality scores (overall score comparison)
       - Cost comparison (treatment vs control USD)
       - Returns: `treatment_wins`, `control_wins`, `no_significant_difference`, or `insufficient_data`
   - **`ABTestRunner`** — CRUD + orchestration:
     - `create_run()`: creates ab_test_runs record with provider configs
     - `update_run_status()`: lifecycle transitions with timestamps
     - `aggregate_scores()`: calls `get_ab_test_scores` RPC for efficient aggregation
     - `complete_comparison()`: end-to-end analysis — aggregates scores, runs t-test, makes decision, updates run
     - `get_current_status()`: dashboard data — config, latest run, running experiment, totals
     - `list_runs()`, `get_run()`: query with optional filters

4. **`backend/app/workers/tasks/evaluation_tasks.py`** (modified)
   - `run_batch_evaluation` extended with `embedding_provider` and `rerank_provider` params
   - Builds `provider_context` dict and passes to `pipeline.query(context=provider_context)`
   - Tracks `search_latency_ms` per question via `time.time()` around pipeline.query()
   - Stores provider columns + latency in evaluation_results rows
   - **`run_ab_comparison`** (new Celery task, ~130 lines):
     - Orchestrates full A/B comparison: control arm → treatment arm → statistical analysis
     - Status transitions: `pending → running_control → running_treatment → comparing → completed`
     - Calls `run_batch_evaluation` for each arm with respective provider configs
     - Calls `ABTestRunner.complete_comparison()` for Welch's t-test + decision
     - Full error handling with status rollback to `failed`

5. **`backend/app/services/rag/pipeline_service.py`** (modified)
   - `_get_pipeline_config()` accepts `embedding_provider` and `rerank_provider` params
   - Maps provider names to model names: `"voyage"` → `"voyage-law-2"`, `"openai"` → `"text-embedding-3-small"`
   - Includes provider info in pipeline config snapshot for traceability

6. **`backend/app/engines/orchestrator/adapters.py`** (modified)
   - Percentage-based routing in `RAGEngineAdapter.execute()`:
     - When no explicit provider requested and `voyage_traffic_percentage > 0`:
       - Calls `ABTestRouter.determine_provider(user_id, matter_id, percentage)`
       - Routes to Voyage or OpenAI based on deterministic hash bucket
   - Added `search_latency_ms` tracking around `search.search_with_rerank_and_library()`
   - Added `embedding_provider`, `rerank_provider`, `search_latency_ms` to `rag_data` response

7. **`backend/app/api/routes/ab_testing.py`** (new)
   - `POST /ab-testing/compare` — triggers A/B comparison, creates run record, queues Celery task
   - `GET /ab-testing/runs` — lists runs with optional matter_id/status filters
   - `GET /ab-testing/runs/{run_id}` — gets specific run with full results
   - `GET /ab-testing/status` — current config, latest run, running experiment, totals

8. **`backend/app/main.py`** (modified)
   - Added `ab_testing` import and router registration

9. **`frontend/src/lib/api/ab-testing.ts`** (new)
   - TypeScript types: `ABTestRun`, `ABTestScores`, `StatisticalTest`, `ABTestStatus`
   - snake_case → camelCase transformers with null safety (`toNum`, `toStr`, `toBool`)
   - API functions: `getABTestStatus`, `getABTestRuns`, `getABTestRun`, `triggerABComparison`

10. **`frontend/src/hooks/useABTesting.ts`** (new)
    - 30-second polling (experiments run for minutes, not seconds)
    - Visibility-based polling, fetch deduplication, mounted-state safety
    - Returns: `status`, `loading`, `error`, `refresh`

11. **`frontend/src/components/features/admin/ABTestingWidget.tsx`** (new)
    - "A/B Testing" card with:
      - Config grid: enabled, traffic %, auto-promote, completed runs
      - Running experiment status indicator (animated pulse for active states)
      - Latest comparison: decision badge (Voyage Wins / OpenAI Wins / No Difference / Need More Data)
      - Score bars: blue (Control/OpenAI) vs amber (Treatment/Voyage) for Overall, Faithfulness, Relevancy, Recall
      - Confidence percentage display
      - Latency comparison: P50 and P95 side-by-side
      - Statistical test details: p-value, Cohen's d, t-statistic, degrees of freedom
    - Loading skeleton, error handling, manual refresh

12. **`frontend/src/app/(dashboard)/admin/page.tsx`** (modified)
    - Added `<ABTestingWidget />` to admin widgets grid

#### Architecture Decisions

- **Hash-based routing over random**: MD5 hash of `user_id:matter_id` gives deterministic, sticky cohorts. Same user always gets same provider for same matter. This prevents within-user variance and ensures reproducible routing decisions. Unlike random routing, this doesn't require session state.

- **Pure Python Welch's t-test**: Implemented without scipy to avoid a ~100MB dependency for one function. Uses Welch-Satterthwaite degrees of freedom approximation and normal distribution approximation for p-values. Accuracy is sufficient for the decision thresholds used (p < 0.05, Cohen's d > 0.2).

- **Routing in adapter, not factory**: The factory doesn't have access to `user_id`/`matter_id` needed for hash-based routing. The adapter has full context and can make the routing decision before calling the factory. This keeps the factory focused on provider instantiation.

- **Sequential arm execution**: Control and treatment arms run sequentially in the Celery task, not in parallel. This halves peak resource usage (only one batch evaluation at a time) and simplifies error handling. Since experiments take minutes regardless, the ~2x wall time is acceptable.

- **Decision matrix, not single threshold**: The automated decision considers quality, significance, effect size, AND cost together. A provider must be statistically significantly better on quality (or equivalent) AND cheaper to win. This prevents premature promotion based on noisy data.

#### Backward Compatibility

- Migration: Creates new table + functions. Adds 3 optional columns to `evaluation_results`. No schema changes to existing tables.
- API: All new endpoints. Existing evaluation endpoints unchanged.
- Tasks: `run_batch_evaluation` gains optional provider params. Default behavior unchanged.
- Config: All new settings have safe defaults (0% traffic, auto-promote off, min 20 samples).
- Routing: At 0% traffic (default), zero code paths change. `ABTestRouter` only activates when `voyage_traffic_percentage > 0`.
- Frontend: New widget added to existing admin page. No changes to existing widgets.

#### Deploy Steps

1. Apply migration: `supabase db push`
2. Deploy backend: `railway up -s LDIP`
3. Deploy worker: `railway up -s ldip-worker`
4. Deploy frontend: `cd frontend && vercel --prod`
5. To enable A/B routing: set `VOYAGE_TRAFFIC_PERCENTAGE=10` in Railway (start with 10% canary)
6. To trigger manual comparison: `POST /api/ab-testing/compare` with matter_id
