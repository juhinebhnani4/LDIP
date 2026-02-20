# Plan: 4 Search/Retrieval Improvements

**Date**: 2026-02-20
**Status**: Gaps 1-3 implemented — Gap 4 pending

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

## Gap 4: Metadata Filtering at Search Time

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

### Fix

**Layer 1: Database (new migration)**

Add optional filter parameters to `hybrid_search_chunks` and `hybrid_search_chunks_voyage`:

```sql
CREATE OR REPLACE FUNCTION public.hybrid_search_chunks(
  query_text text,
  query_embedding vector(1536),
  filter_matter_id uuid,
  match_count integer DEFAULT 20,
  full_text_weight float DEFAULT 1.0,
  semantic_weight float DEFAULT 1.0,
  rrf_k integer DEFAULT 60,
  -- NEW FILTER PARAMS:
  filter_document_ids uuid[] DEFAULT NULL,
  filter_document_types text[] DEFAULT NULL,
  filter_page_min integer DEFAULT NULL,
  filter_page_max integer DEFAULT NULL
)
```

Add WHERE clauses:
```sql
WHERE c.matter_id = filter_matter_id
  AND (filter_document_ids IS NULL OR c.document_id = ANY(filter_document_ids))
  AND (filter_document_types IS NULL OR c.document_id IN (
    SELECT id FROM documents WHERE document_type = ANY(filter_document_types)
  ))
  AND (filter_page_min IS NULL OR c.page_number >= filter_page_min)
  AND (filter_page_max IS NULL OR c.page_number <= filter_page_max)
```

Same changes for `bm25_search_chunks` and `hybrid_search_chunks_voyage`.

**Layer 2: Backend Models**

`backend/app/models/search.py` — Add filter fields to `SearchRequest`:

```python
class SearchFilters(BaseModel):
    document_ids: list[str] | None = None
    document_types: list[str] | None = None  # ["case_file", "act", "annexure", "other"]
    page_min: int | None = None
    page_max: int | None = None

class SearchRequest(BaseModel):
    query: str
    limit: int = 20
    bm25_weight: float = 1.0
    semantic_weight: float = 1.0
    rerank: bool = True
    rerank_top_n: int = 3
    filters: SearchFilters | None = None  # NEW
```

**Layer 3: Backend Service**

`backend/app/services/rag/hybrid_search.py` — Pass filters through:

- `search()` method — accept optional `filters: SearchFilters` param
- Include in RPC params: `filter_document_ids`, `filter_document_types`, `filter_page_min`, `filter_page_max`
- Same for `search_with_rerank()` and `search_with_rerank_and_library()`

**Layer 4: API Routes**

`backend/app/api/routes/search.py` — Extract filters from request body and pass to service.

**Layer 5: Frontend**

1. **`frontend/src/types/search.ts`** — Add `SearchFilters` interface
2. **`frontend/src/lib/api/search.ts`** — Pass filters in API calls
3. **New component: `frontend/src/components/features/chat/SearchFilters.tsx`**
   - Collapsible filter panel above/beside chat input
   - Document type multi-select (checkboxes: Case File, Act, Annexure, Other)
   - Page range inputs (min/max number inputs)
   - Document selector (dropdown of documents in the matter)
   - "Clear filters" button
4. **Wire into chat component** — Pass active filters with each search query

**Layer 6: Orchestrator integration**

`backend/app/engines/orchestrator/adapters.py` — Pass filters from the chat context through to the search service. The orchestrator context dict can carry `search_filters` from the frontend.

**Effort**: ~1-2 days

---

## Implementation Order

| Order | Gap | Effort | Status |
|---|---|---|---|
| ~~1~~ | ~~**Gap 1**: Parent context expansion~~ | ~~2 hrs~~ | **DONE** (2026-02-20) |
| ~~2~~ | ~~**Gap 3**: Hindi/Gujarati fix~~ | ~~15 min~~ | **DONE** (2026-02-20) — Fixed 7 items (2 functions, 3 indexes, 1 Python file, + regression comments). Found and fixed `idx_documents_extracted_text` which original plan missed. |
| ~~3~~ | ~~**Gap 2**: Dynamic RRF weights~~ | ~~30 min~~ | **DONE** (2026-02-20) |
| 4 | **Gap 4**: Metadata filtering | 1-2 days | Pending — largest scope, needs frontend work |

Gaps 2-3 can ship in one PR. Gap 4 is a separate feature PR.

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Parent expansion blows token budget on summary queries (12 chunks x 2000 tokens) | Cap parent content at `max_chunk_content` from QueryProfile; log token counts |
| Wrong RRF weights degrade retrieval quality | Ship with conservative weights (1.5/0.7 not 2.0/0.0); monitor via Inspector debug mode which already shows per-result scores |
| Migration breaks production search | New migration only adds optional params with defaults — backward compatible. Existing calls without filters continue working. |
| `'simple'` tokenizer misses English stemming (e.g., "running" won't match "run") | Acceptable tradeoff: semantic search covers stemming gaps. BM25 with 'simple' gives exact match which is more important for legal text. |
| Metadata filter subquery on `documents` table slow for large matters | `document_type` is indexed; join is on primary key. For page_range, filter is on indexed `chunks.page_number`. Should be fine up to 100k chunks. |
