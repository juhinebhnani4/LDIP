# Plan: 4 Search/Retrieval Improvements

**Date**: 2026-02-20
**Status**: 5 of 8 gaps implemented (Gaps 1-5 done)

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

5 of 8 gaps complete (Gaps 1-5). Gaps 6-8 are lower priority (medium/low/none).

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Parent expansion blows token budget on summary queries (12 chunks x 2000 tokens) | Cap parent content at `max_chunk_content` from QueryProfile; log token counts |
| Wrong RRF weights degrade retrieval quality | Ship with conservative weights (1.5/0.7 not 2.0/0.0); monitor via Inspector debug mode which already shows per-result scores |
| Migration breaks production search | New migration only adds optional params with defaults — backward compatible. Existing calls without filters continue working. |
| `'simple'` tokenizer misses English stemming (e.g., "running" won't match "run") | Acceptable tradeoff: semantic search covers stemming gaps. BM25 with 'simple' gives exact match which is more important for legal text. |
| Metadata filter subquery on `documents` table slow for large matters | `document_type` is indexed; join is on primary key. For page_range, filter is on indexed `chunks.page_number`. Should be fine up to 100k chunks. |

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

### Gap 6: Chunk Deduplication Before Generation — PARTIAL ISSUE (Medium Priority)

> **Status**: Not started | **Priority**: MEDIUM | **Effort**: 2-4 hours

#### Problem

Parent context expansion (Gap 1) deduplicates at the parent level — if multiple child chunks share a parent, only the highest-ranked child is kept. However, **inter-parent boundary overlap is not deduplicated**. Adjacent parent chunks share 100-token overlaps at boundaries. When 3+ parent chunks are sent to the LLM, ~200-300 tokens of redundant text exist between them.

#### Current State

| Aspect | Status |
|---|---|
| Parent-level deduplication | **DONE** — `adapters.py:807-824`, `seen_parents` set |
| Inter-parent boundary overlap | **NOT deduplicated** — 100-token overlap per boundary |
| Content-level dedup in `_format_context()` | **NONE** — `prompts.py:190-235` formats chunks sequentially |
| Estimated token waste | 8-15% (~200-750 tokens out of ~5250 per query) |

#### Accuracy Impact

- **Medium** — duplicate passages can cause LLMs to **over-weight** repeated information, skewing answers
- Redundant boundary text wastes context window space that could hold more relevant content
- At scale (1000+ queries/day), ~$30-90/month in wasted tokens

#### Implementation Plan

1. **Add sliding-window dedup in `_format_context()`** (`prompts.py:190`)
   - After assembling chunks, detect overlapping text spans at chunk boundaries
   - Strip duplicate boundary text from subsequent chunks
   - Preserve chunk metadata (source, page number) unchanged
2. **Alternative**: Trim parent chunks to exclude overlap regions before sending to LLM
   - Store `overlap_tokens` count in chunk metadata during chunking
   - Trim first/last `overlap_tokens` from each chunk in context assembly

#### Long-term Considerations

- If switching to larger context models, overlap waste becomes proportionally less significant
- Semantic deduplication (embedding-based similarity between chunks) could catch non-boundary duplicates too
- Monitor actual redundancy rate via token counting in production logs

---

### Gap 7: Vector Quantization — NOT AN ISSUE (Monitor Only)

> **Status**: No action needed | **Priority**: LOW | **Effort**: N/A (monitoring only)

#### Problem Statement

With 1536-dim OpenAI + 1024-dim Voyage vectors stored as full float32, storage and memory could become concerns at scale. Int8 or scalar quantization could halve memory and speed search.

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

**When to revisit:**
- Chunk count exceeds 500K (add monitoring metric)
- Query latency exceeds 500ms consistently
- Storage costs become meaningful (>$50/month for vectors)

#### Long-term Options (if needed)

1. **halfvec (float16)** — pgvector 0.7+ supports `halfvec(1536)`, 2x compression, ~2-3% accuracy loss. Best first step.
2. **Dimension reduction** — Switch to `text-embedding-3-large` with PCA to 768 dims. Better quality at fewer dims.
3. **Scalar quantization** — int8 via application-layer quantization. 4x compression, ~5-10% accuracy loss.
4. **Separate vector DB** — If RLS overhead becomes significant at millions of vectors, consider Pinecone/Weaviate.

#### Action Item

Add a chunk count metric to monitoring dashboard. Alert when any single matter exceeds 50K chunks or global count exceeds 500K.

---

### Gap 8: HNSW Index Tuning — NOT AN ISSUE

> **Status**: No action needed | **Priority**: NONE | **Effort**: N/A

#### Problem Statement

`ef_construction=64` was suggested as too conservative for legal precision. Bumping to `ef_construction=128` and `ef_search=128` at query time would improve recall.

#### Analysis

**ef_construction=64 is well-suited for this architecture.** The system compensates through multiple layers:

1. **Matter isolation** — every query filters by `matter_id`, so effective HNSW search space is 100-10K vectors (not millions). At this scale, ef_construction=64 provides near-perfect recall.

2. **Hybrid search redundancy** — BM25 catches exact keyword matches that HNSW might miss. RRF fusion ensures both contribute. If HNSW misses a result, BM25 likely catches it.

3. **Reranking safety net** — 50 candidates fed to Cohere Rerank v3.5. Even if HNSW ranks a relevant result at position 25-30, reranker surfaces it to top-3.

4. **Dynamic weights** — CITATION queries boost BM25 (1.5x) for exact legal references. SUMMARY queries boost semantic (1.3x). Application-level tuning > index-level tuning.

5. **No ef_search override needed** — pgvector default (~40) is sufficient given the small per-matter index size. Setting `ef_search=128` would add latency with negligible recall improvement.

**Benchmark**: Increasing ef_construction from 64→128 would yield ~2-5% better HNSW recall in isolation, but after hybrid fusion + reranking, the end-to-end improvement would be <1%. Not worth the 2x slower index build time.

#### When to Revisit

- If a single matter exceeds 100K chunks (unlikely for legal case files)
- If reranking is removed from the pipeline (recall would depend more heavily on HNSW alone)
- If switching from hybrid to semantic-only search

---

## Future Improvements Priority Matrix

| # | Gap | Is It Real? | Accuracy Impact | Efficiency Impact | Priority | Action |
|---|---|---|---|---|---|---|
| 5 | Table-aware embedding | **YES — FIXED (Gap 5)** | **High** — now searchable | N/A — resolved | **DONE** | Deployed to codebase |
| 6 | Chunk boundary dedup | Partial — boundary overlap exists | Medium — LLM over-weighting risk | Low — ~8-15% token waste | **MEDIUM** | Implement |
| 7 | Vector quantization | No (at current scale) | None | None now | LOW | Monitor |
| 8 | HNSW tuning | No — architecture compensates | None | None | NONE | No action |
