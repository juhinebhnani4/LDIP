# Story 2B.6: Implement Hybrid Search with RRF Fusion

Status: done

## Story

As a **developer**,
I want **hybrid search combining BM25 keyword search and pgvector semantic search**,
So that **attorneys find relevant content whether they remember exact terms or just concepts**.

## Acceptance Criteria

1. **Given** I search for a query **When** hybrid search executes **Then** BM25 keyword search runs via PostgreSQL tsvector **And** semantic search runs via pgvector with HNSW index **And** results are merged using Reciprocal Rank Fusion (RRF)

2. **Given** RRF fusion is applied **When** results are merged **Then** documents appearing in both result sets rank higher **And** the top 20 candidates are returned for reranking

3. **Given** a matter has embeddings **When** semantic search is performed **Then** only embeddings with matter_id filter are searched **And** cross-matter results are impossible (4-layer isolation maintained)

4. **Given** a query contains exact legal terms (e.g., "Section 138 NI Act") **When** search executes **Then** BM25 finds exact matches **And** semantic search finds conceptually similar content

## Tasks / Subtasks

- [x] Task 1: Add tsvector column and GIN index to chunks table (AC: #1)
  - [x] Create migration `20260108000004_add_hybrid_search.sql`
  - [x] Add `fts tsvector` generated column: `GENERATED ALWAYS AS (to_tsvector('english', content)) STORED`
  - [x] Create GIN index: `CREATE INDEX idx_chunks_fts ON public.chunks USING GIN (fts)`
  - [x] Verify index works with existing data after migration

- [x] Task 2: Create Embedding Service for OpenAI text-embedding-3-small (AC: #3)
  - [x] Create `backend/app/services/rag/embedder.py`
  - [x] Implement `EmbeddingService` class with async methods
  - [x] Method: `embed_text(text: str) -> list[float]` (1536 dimensions)
  - [x] Method: `embed_batch(texts: list[str]) -> list[list[float]]` (batch up to 100)
  - [x] Use `openai` Python SDK with async client
  - [x] Add retry logic with tenacity (max 3 retries, exponential backoff)
  - [x] Add embedding caching in Redis (TTL: 24 hours)

- [x] Task 3: Create BM25 Search Function (AC: #1, #4)
  - [x] Add SQL function `bm25_search_chunks` to migration
  - [x] Input: `query_text text, filter_matter_id uuid, match_count int`
  - [x] Use `websearch_to_tsquery('english', query_text)` for query parsing
  - [x] Use `ts_rank_cd()` for BM25-style ranking
  - [x] MANDATORY: Include `WHERE matter_id = filter_matter_id` for security
  - [x] Return: chunk_id, matter_id, document_id, content, rank, row_number

- [x] Task 4: Create Semantic Search Function Enhancement (AC: #1, #3)
  - [x] Create `semantic_search_chunks` function
  - [x] Use cosine similarity: `1 - (embedding <=> query_embedding)`
  - [x] MANDATORY: Include `WHERE matter_id = filter_matter_id`
  - [x] Return: chunk_id, matter_id, document_id, content, similarity, row_number

- [x] Task 5: Create RRF Hybrid Search SQL Function (AC: #1, #2)
  - [x] Add SQL function `hybrid_search_chunks` to migration
  - [x] Input parameters:
    - `query_text text` - keyword query
    - `query_embedding vector(1536)` - semantic query embedding
    - `filter_matter_id uuid` - REQUIRED for isolation
    - `match_count int DEFAULT 20` - candidates for reranking
    - `full_text_weight float DEFAULT 1.0`
    - `semantic_weight float DEFAULT 1.0`
    - `rrf_k int DEFAULT 60` - RRF smoothing constant
  - [x] Implementation:
    - Execute BM25 search as CTE with `ROW_NUMBER() OVER (ORDER BY rank DESC)`
    - Execute semantic search as CTE with `ROW_NUMBER() OVER (ORDER BY similarity DESC)`
    - FULL OUTER JOIN both CTEs on chunk_id
    - Apply RRF formula: `COALESCE(1.0 / (rrf_k + bm25.rn), 0) * full_text_weight + COALESCE(1.0 / (rrf_k + semantic.rn), 0) * semantic_weight`
    - Return top N by combined RRF score
  - [x] Return: chunk_id, matter_id, document_id, content, page_number, chunk_type, bm25_rank, semantic_rank, rrf_score

- [x] Task 6: Create Hybrid Search Service (AC: #1, #2, #3, #4)
  - [x] Create `backend/app/services/rag/hybrid_search.py`
  - [x] Implement `HybridSearchService` class
  - [x] Method: `search(query: str, matter_id: str, limit: int = 20, weights: SearchWeights = None) -> HybridSearchResult`
  - [x] Steps:
    1. Validate matter_id using `validate_namespace()`
    2. Generate embedding via EmbeddingService
    3. Call `hybrid_search_chunks` RPC
    4. Validate results via `validate_search_results()`
    5. Return typed results
  - [x] Use existing `namespace.py` functions for validation

- [x] Task 7: Create Embedding Population Celery Task (AC: #3)
  - [x] Update `backend/app/workers/tasks/document_tasks.py`
  - [x] Add `embed_chunks` Celery task (queue: 'default')
  - [x] Process in batches of 50 chunks (API limits)
  - [x] Rate limit: Max 3000 tokens/min for OpenAI embeddings
  - [x] Chain: `chunk_document -> embed_chunks`
  - [x] Update document status via pubsub: `embedding_complete`

- [x] Task 8: Create Search API Endpoints (AC: #1, #2, #4)
  - [x] Create `backend/app/api/routes/search.py`
  - [x] `POST /api/matters/{matter_id}/search` - Hybrid search endpoint
    - Request body: `{ query: string, limit?: number, bm25_weight?: number, semantic_weight?: number }`
    - Response: `{ data: SearchResult[], meta: { query, matter_id, total_candidates, bm25_weight, semantic_weight } }`
  - [x] `POST /api/matters/{matter_id}/search/bm25` - BM25-only search
  - [x] `POST /api/matters/{matter_id}/search/semantic` - Semantic-only search
  - [x] Register router in `backend/app/main.py`

- [x] Task 9: Create Frontend Search Types and API Client (AC: #1, #2)
  - [x] Create `frontend/src/types/search.ts`
    - `SearchResult` interface
    - `SearchRequest` interface
    - `SearchWeights` interface
    - `SearchResponse`, `SingleModeSearchResponse` types
  - [x] Create `frontend/src/lib/api/search.ts`
    - `hybridSearch(matterId, request): Promise<SearchResponse>`
    - `bm25Search(matterId, request): Promise<SingleModeSearchResponse>`
    - `semanticSearch(matterId, request): Promise<SingleModeSearchResponse>`
  - [x] Export types from `frontend/src/types/index.ts`

- [x] Task 10: Write Backend Unit Tests
  - [x] Create `backend/tests/services/rag/test_embedder.py`
    - Test embedding generation (mock OpenAI)
    - Test batch embedding
    - Test caching behavior
    - Test retry logic
  - [x] Create `backend/tests/services/rag/test_hybrid_search.py`
    - Test RRF score calculation
    - Test matter isolation validation
    - Test weight parameter effects
    - Test edge cases (no results, single source results)

- [x] Task 11: Write Backend Integration Tests
  - [x] Create `backend/tests/integration/test_search_integration.py`
    - Test full pipeline: query -> embedding -> search -> results
    - Test matter isolation (cross-matter search fails)
    - Test BM25 vs semantic vs hybrid result quality
    - Test with mocked embeddings

- [x] Task 12: Write Security Tests (AC: #3)
  - [x] Create `backend/tests/security/test_search_isolation.py`
    - Add hybrid search cross-matter attack test
    - Verify matter_id cannot be omitted
    - Verify results are validated post-query
    - Add Layer 2 test for hybrid search

## Dev Notes

### CRITICAL: Existing Infrastructure

**The following already exists and MUST be reused:**

1. **Chunks table** with `embedding vector(1536)` column - [supabase/migrations/20260106000002_create_chunks_table.sql](supabase/migrations/20260106000002_create_chunks_table.sql)
2. **HNSW index** on embeddings - `idx_chunks_embedding` with `m=16, ef_construction=64`
3. **`match_chunks` function** for semantic search - already in migration
4. **Namespace validation** - [backend/app/services/rag/namespace.py](backend/app/services/rag/namespace.py) with `get_namespace_filter()`, `validate_namespace()`, `validate_search_results()`
5. **`build_hybrid_search_query()`** - stub exists in namespace.py, ready for use

### Architecture Requirements (MANDATORY)

**From [architecture.md](../_bmad-output/architecture.md):**

#### 4-Layer Matter Isolation (MUST FOLLOW)
```
Layer 1: RLS policies on chunks table ✓ (exists)
Layer 2: Vector namespace filtering ✓ (exists in namespace.py)
Layer 3: Redis key prefix - `matter:{matter_id}:embeddings:*`
Layer 4: API middleware validates matter access
```

**CRITICAL:** Every search query MUST include `matter_id` filter. Use `validate_namespace()` before any query.

#### Hybrid Search Design

From architecture ADR section:
- BM25 via PostgreSQL tsvector (keyword precision)
- pgvector HNSW for semantic search (conceptual matching)
- RRF fusion with configurable weights
- Top 20 candidates for Cohere reranking (Story 2b-7)

#### RRF Fusion Formula
```
score = 1/(k + rank_bm25) * bm25_weight + 1/(k + rank_semantic) * semantic_weight
```
- Default `k = 60` (industry standard smoothing constant)
- Default weights: `bm25_weight = 1.0`, `semantic_weight = 1.0`

### SQL Implementation Pattern

**Hybrid Search Function:**
```sql
-- Add to migration: 20260108000001_add_chunks_fts.sql

-- Step 1: Add FTS column to chunks
ALTER TABLE public.chunks
ADD COLUMN fts tsvector
GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

-- Step 2: Create GIN index for FTS
CREATE INDEX idx_chunks_fts ON public.chunks USING GIN (fts);

-- Step 3: Create hybrid search function
CREATE OR REPLACE FUNCTION public.hybrid_search_chunks(
  query_text text,
  query_embedding vector(1536),
  filter_matter_id uuid,
  match_count integer DEFAULT 20,
  full_text_weight float DEFAULT 1.0,
  semantic_weight float DEFAULT 1.0,
  rrf_k integer DEFAULT 60
)
RETURNS TABLE (
  id uuid,
  matter_id uuid,
  document_id uuid,
  content text,
  page_number integer,
  chunk_type text,
  token_count integer,
  bm25_rank integer,
  semantic_rank integer,
  rrf_score float
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- CRITICAL: matter_id is REQUIRED
  IF filter_matter_id IS NULL THEN
    RAISE EXCEPTION 'filter_matter_id is required - security violation';
  END IF;

  -- Verify user access (defense in depth)
  IF NOT EXISTS (
    SELECT 1 FROM public.matter_attorneys ma
    WHERE ma.matter_id = filter_matter_id AND ma.user_id = auth.uid()
  ) THEN
    RAISE EXCEPTION 'Access denied to matter %', filter_matter_id;
  END IF;

  RETURN QUERY
  WITH bm25_results AS (
    SELECT
      c.id,
      c.matter_id,
      c.document_id,
      c.content,
      c.page_number,
      c.chunk_type,
      c.token_count,
      ROW_NUMBER() OVER (ORDER BY ts_rank_cd(c.fts, websearch_to_tsquery('english', query_text)) DESC) AS rn
    FROM public.chunks c
    WHERE c.matter_id = filter_matter_id
      AND c.fts @@ websearch_to_tsquery('english', query_text)
    LIMIT LEAST(match_count, 30) * 2
  ),
  semantic_results AS (
    SELECT
      c.id,
      c.matter_id,
      c.document_id,
      c.content,
      c.page_number,
      c.chunk_type,
      c.token_count,
      ROW_NUMBER() OVER (ORDER BY c.embedding <=> query_embedding) AS rn
    FROM public.chunks c
    WHERE c.matter_id = filter_matter_id
      AND c.embedding IS NOT NULL
    ORDER BY c.embedding <=> query_embedding
    LIMIT LEAST(match_count, 30) * 2
  )
  SELECT
    COALESCE(bm25.id, sem.id) AS id,
    COALESCE(bm25.matter_id, sem.matter_id) AS matter_id,
    COALESCE(bm25.document_id, sem.document_id) AS document_id,
    COALESCE(bm25.content, sem.content) AS content,
    COALESCE(bm25.page_number, sem.page_number) AS page_number,
    COALESCE(bm25.chunk_type, sem.chunk_type) AS chunk_type,
    COALESCE(bm25.token_count, sem.token_count) AS token_count,
    bm25.rn::integer AS bm25_rank,
    sem.rn::integer AS semantic_rank,
    (
      COALESCE(1.0 / (rrf_k + bm25.rn), 0.0) * full_text_weight +
      COALESCE(1.0 / (rrf_k + sem.rn), 0.0) * semantic_weight
    )::float AS rrf_score
  FROM bm25_results bm25
  FULL OUTER JOIN semantic_results sem ON bm25.id = sem.id
  ORDER BY rrf_score DESC
  LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION public.hybrid_search_chunks IS
  'Hybrid BM25+semantic search with RRF fusion - MANDATORY matter isolation';
```

### Embedding Service Implementation

```python
# backend/app/services/rag/embedder.py

from functools import lru_cache
from typing import Sequence

import structlog
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.services.memory.redis_keys import get_embedding_cache_key

logger = structlog.get_logger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
MAX_BATCH_SIZE = 100
MAX_TOKENS_PER_REQUEST = 8191


class EmbeddingService:
    """Service for generating OpenAI embeddings with caching."""

    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._redis = None  # Lazy load

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for single text."""
        if not text.strip():
            raise ValueError("Cannot embed empty text")

        # Check cache first
        cache_key = get_embedding_cache_key(text)
        cached = await self._get_cached(cache_key)
        if cached:
            logger.debug("embedding_cache_hit", text_len=len(text))
            return cached

        # Generate embedding
        response = await self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
            dimensions=EMBEDDING_DIMENSIONS,
        )

        embedding = response.data[0].embedding

        # Cache result
        await self._cache_embedding(cache_key, embedding)

        logger.info(
            "embedding_generated",
            text_len=len(text),
            tokens=response.usage.total_tokens,
        )

        return embedding

    async def embed_batch(
        self,
        texts: Sequence[str],
        skip_empty: bool = True,
    ) -> list[list[float] | None]:
        """Generate embeddings for batch of texts."""
        if len(texts) > MAX_BATCH_SIZE:
            raise ValueError(f"Batch size {len(texts)} exceeds max {MAX_BATCH_SIZE}")

        # Filter and track empty texts
        valid_indices = []
        valid_texts = []
        for i, text in enumerate(texts):
            if text.strip():
                valid_indices.append(i)
                valid_texts.append(text)
            elif not skip_empty:
                raise ValueError(f"Empty text at index {i}")

        if not valid_texts:
            return [None] * len(texts)

        # Generate embeddings
        response = await self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=valid_texts,
            dimensions=EMBEDDING_DIMENSIONS,
        )

        # Map back to original indices
        results: list[list[float] | None] = [None] * len(texts)
        for i, embedding_data in enumerate(response.data):
            original_idx = valid_indices[i]
            results[original_idx] = embedding_data.embedding

        logger.info(
            "batch_embeddings_generated",
            batch_size=len(texts),
            valid_count=len(valid_texts),
            tokens=response.usage.total_tokens,
        )

        return results
```

### Hybrid Search Service Implementation

```python
# backend/app/services/rag/hybrid_search.py

from dataclasses import dataclass

import structlog

from app.services.rag.embedder import EmbeddingService
from app.services.rag.namespace import (
    validate_namespace,
    validate_search_results,
)
from app.services.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)


@dataclass
class SearchWeights:
    """Weights for hybrid search components."""
    bm25: float = 1.0
    semantic: float = 1.0

    def __post_init__(self):
        if not (0 <= self.bm25 <= 2):
            raise ValueError("bm25 weight must be between 0 and 2")
        if not (0 <= self.semantic <= 2):
            raise ValueError("semantic weight must be between 0 and 2")


@dataclass
class SearchResult:
    """Single hybrid search result."""
    id: str
    matter_id: str
    document_id: str
    content: str
    page_number: int | None
    chunk_type: str
    token_count: int
    bm25_rank: int | None
    semantic_rank: int | None
    rrf_score: float


@dataclass
class HybridSearchResult:
    """Hybrid search response."""
    results: list[SearchResult]
    query: str
    matter_id: str
    weights: SearchWeights
    total_candidates: int


class HybridSearchService:
    """Service for hybrid BM25 + semantic search with RRF fusion."""

    def __init__(self):
        self.embedder = EmbeddingService()

    async def search(
        self,
        query: str,
        matter_id: str,
        limit: int = 20,
        weights: SearchWeights | None = None,
    ) -> HybridSearchResult:
        """
        Execute hybrid search with RRF fusion.

        Args:
            query: Search query text
            matter_id: REQUIRED - matter UUID for isolation
            limit: Max results to return (default 20 for reranking)
            weights: Optional custom weights for BM25/semantic

        Returns:
            HybridSearchResult with ranked results
        """
        # CRITICAL: Validate matter_id first
        validate_namespace(matter_id)

        weights = weights or SearchWeights()

        logger.info(
            "hybrid_search_start",
            query_len=len(query),
            matter_id=matter_id,
            limit=limit,
            bm25_weight=weights.bm25,
            semantic_weight=weights.semantic,
        )

        # Generate query embedding
        query_embedding = await self.embedder.embed_text(query)

        # Execute hybrid search via RPC
        supabase = get_supabase_client()
        response = await supabase.rpc(
            "hybrid_search_chunks",
            {
                "query_text": query,
                "query_embedding": query_embedding,
                "filter_matter_id": matter_id,
                "match_count": limit,
                "full_text_weight": weights.bm25,
                "semantic_weight": weights.semantic,
                "rrf_k": 60,
            }
        ).execute()

        if response.data is None:
            logger.warning("hybrid_search_no_results", matter_id=matter_id)
            return HybridSearchResult(
                results=[],
                query=query,
                matter_id=matter_id,
                weights=weights,
                total_candidates=0,
            )

        # Validate results (defense in depth)
        validated = validate_search_results(response.data, matter_id)

        # Map to typed results
        results = [
            SearchResult(
                id=r["id"],
                matter_id=r["matter_id"],
                document_id=r["document_id"],
                content=r["content"],
                page_number=r.get("page_number"),
                chunk_type=r["chunk_type"],
                token_count=r.get("token_count", 0),
                bm25_rank=r.get("bm25_rank"),
                semantic_rank=r.get("semantic_rank"),
                rrf_score=r["rrf_score"],
            )
            for r in validated
        ]

        logger.info(
            "hybrid_search_complete",
            matter_id=matter_id,
            result_count=len(results),
            top_score=results[0].rrf_score if results else 0,
        )

        return HybridSearchResult(
            results=results,
            query=query,
            matter_id=matter_id,
            weights=weights,
            total_candidates=len(response.data),
        )
```

### Previous Story Intelligence

**FROM Story 2b-5 (Parent-Child Chunking):**
- Chunks table populated with `content`, `chunk_type`, `token_count`
- Celery task chain pattern: `process_document -> validate_ocr -> calculate_confidence -> chunk_document`
- structlog logging throughout
- EmbeddingService should chain after `chunk_document` task

**FROM Story 2b-4 (Bounding Boxes):**
- `bbox_ids` array on chunks for highlight support
- Reading order preserved for search result context

**FROM Story 2b-1 (OCR):**
- `extracted_text` on documents table
- Document status management via pubsub

**Key files to reference:**
- [backend/app/services/rag/namespace.py](backend/app/services/rag/namespace.py) - MUST use for all queries
- [backend/app/services/chunk_service.py](backend/app/services/chunk_service.py) - Chunk retrieval patterns
- [backend/app/workers/tasks/document_tasks.py](backend/app/workers/tasks/document_tasks.py) - Celery task patterns
- [supabase/migrations/20260106000002_create_chunks_table.sql](supabase/migrations/20260106000002_create_chunks_table.sql) - Existing schema

### Git Intelligence

Recent commits:
```
ddd2b24 fix(chunking): address code review issues for Story 2b-5
971e20e feat(chunking): implement parent-child chunking for RAG pipeline (Story 2b-5)
d0ca6da fix(bbox): address code review issues for Story 2b-4
```

**Recommended commit message:** `feat(search): implement hybrid BM25+pgvector search with RRF fusion (Story 2b-6)`

### Critical Architecture Constraints

**FROM PROJECT-CONTEXT.md - MUST FOLLOW EXACTLY:**

#### Backend Technology Stack
- **Python 3.12+** - use modern syntax (match statements, type hints)
- **FastAPI 0.115+** - async endpoints where beneficial
- **Pydantic v2** - use model_validator, not validator (v1 syntax)
- **structlog** for logging - NOT standard logging library
- **Celery + Redis** - for background tasks

#### API Response Format (MANDATORY)
```python
# Success - search results
{
  "data": [
    {
      "id": "uuid",
      "document_id": "uuid",
      "content": "...",
      "chunk_type": "child",
      "rrf_score": 0.034,
      "bm25_rank": 3,
      "semantic_rank": 5
    }
  ],
  "meta": {
    "total": 45,
    "weights": { "bm25": 1.0, "semantic": 1.0 }
  }
}

# Error
{ "error": { "code": "SEARCH_FAILED", "message": "...", "details": {} } }
```

#### Naming Conventions
| Layer | Convention | Example |
|-------|------------|---------|
| Database columns | snake_case | `rrf_score`, `bm25_rank` |
| TypeScript variables | camelCase | `rrfScore`, `bm25Rank` |
| Python functions | snake_case | `hybrid_search`, `embed_text` |
| Python classes | PascalCase | `HybridSearchService`, `EmbeddingService` |
| API endpoints | kebab-case | `/api/search/hybrid` |

### File Organization

```
backend/app/
├── services/
│   └── rag/
│       ├── __init__.py                     (UPDATE - export new services)
│       ├── namespace.py                    (EXISTS - use for validation)
│       ├── embedder.py                     (NEW) - OpenAI embedding service
│       └── hybrid_search.py                (NEW) - Hybrid search service
├── api/
│   └── routes/
│       ├── __init__.py                     (UPDATE - register search router)
│       └── search.py                       (NEW) - Search API endpoints
├── workers/
│   └── tasks/
│       └── document_tasks.py               (UPDATE - add embed_chunks task)

frontend/src/
├── types/
│   └── search.ts                           (NEW) - Search type definitions
└── lib/
    └── api/
        └── search.ts                       (NEW) - Search API client

backend/tests/
├── services/
│   └── rag/
│       ├── test_embedder.py                (NEW)
│       └── test_hybrid_search.py           (NEW)
├── integration/
│   └── test_hybrid_search_integration.py   (NEW)
└── security/
    ├── test_cross_matter_penetration.py    (UPDATE - add search tests)
    └── test_4_layer_isolation.py           (UPDATE - add Layer 2 search test)

supabase/migrations/
└── 20260108000001_add_chunks_fts.sql       (NEW) - FTS column + hybrid function
```

### Testing Guidance

#### Unit Tests

```python
# backend/tests/services/rag/test_hybrid_search.py

import pytest
from unittest.mock import AsyncMock, patch

from app.services.rag.hybrid_search import (
    HybridSearchService,
    SearchWeights,
    SearchResult,
)


@pytest.fixture
def mock_embedder():
    """Mock EmbeddingService."""
    with patch("app.services.rag.hybrid_search.EmbeddingService") as mock:
        embedder = mock.return_value
        embedder.embed_text = AsyncMock(return_value=[0.1] * 1536)
        yield embedder


@pytest.mark.asyncio
async def test_search_validates_matter_id(mock_embedder):
    """Test that search rejects invalid matter_id."""
    service = HybridSearchService()

    with pytest.raises(ValueError, match="Invalid UUID"):
        await service.search("test query", "not-a-uuid")


@pytest.mark.asyncio
async def test_search_applies_weights(mock_embedder):
    """Test custom weights are passed to RPC."""
    # Test that weights parameter affects the query
    ...


@pytest.mark.asyncio
async def test_rrf_score_calculation():
    """Test RRF formula produces expected scores."""
    # Given: doc ranked #1 in BM25, #3 in semantic
    # k=60, both weights=1.0
    # Expected: 1/(60+1) + 1/(60+3) = 0.0164 + 0.0159 = 0.0323
    ...
```

#### Integration Tests

```python
# backend/tests/integration/test_hybrid_search_integration.py

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_hybrid_search_returns_ranked_results(
    client: AsyncClient,
    test_matter_with_chunks: Matter,
    auth_headers: dict,
):
    """Test full hybrid search pipeline."""
    response = await client.post(
        "/api/search/hybrid",
        headers=auth_headers,
        json={
            "query": "contract termination clause",
            "matter_id": str(test_matter_with_chunks.id),
            "limit": 10,
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert "data" in data
    assert len(data["data"]) <= 10

    # Results should be sorted by RRF score descending
    scores = [r["rrf_score"] for r in data["data"]]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_cross_matter_search_blocked(
    client: AsyncClient,
    test_matter_a: Matter,
    test_matter_b: Matter,
    user_a_headers: dict,
):
    """Test that user cannot search another user's matter."""
    response = await client.post(
        "/api/search/hybrid",
        headers=user_a_headers,  # User A's token
        json={
            "query": "test",
            "matter_id": str(test_matter_b.id),  # User B's matter
        }
    )

    assert response.status_code in [403, 404]
```

### Anti-Patterns to AVOID

```python
# WRONG: Search without matter_id validation
async def search(query: str):
    return await supabase.rpc("hybrid_search_chunks", {"query_text": query})

# CORRECT: Always validate and include matter_id
async def search(query: str, matter_id: str):
    validate_namespace(matter_id)
    return await supabase.rpc("hybrid_search_chunks", {
        "query_text": query,
        "filter_matter_id": matter_id,  # MANDATORY
    })

# WRONG: Creating new embeddings table
CREATE TABLE embeddings (...)  # DON'T - use existing chunks.embedding

# CORRECT: Use existing embedding column
UPDATE public.chunks SET embedding = $1 WHERE id = $2

# WRONG: Using ts_rank instead of ts_rank_cd
SELECT ts_rank(fts, query)  # Basic TF, no proximity

# CORRECT: Use ts_rank_cd for better BM25-like ranking
SELECT ts_rank_cd(fts, query)  # Cover density ranking

# WRONG: Hardcoding RRF k constant
rrf_score = 1.0 / (60 + rank)  # Hardcoded

# CORRECT: Parameterize k for tuning
rrf_score = 1.0 / (rrf_k + rank)  # Configurable

# WRONG: No result validation
return response.data  # Could leak cross-matter data

# CORRECT: Validate results post-query
validated = validate_search_results(response.data, matter_id)
return validated
```

### Performance Considerations

- **HNSW warmup:** Index already exists with `m=16, ef_construction=64`; consider `ef_search=40` at query time for quality/speed balance
- **GIN index on fts:** Efficient tsvector matching
- **Batch embeddings:** Process 50 chunks per API call, max 8K tokens
- **Embedding caching:** 24-hour TTL in Redis for repeated queries
- **Query timeout:** Set 10s timeout on RPC calls

### Dependencies to Add

```bash
# backend/
uv add openai           # Embeddings API
uv add tenacity         # Retry logic (may already exist)
```

### Environment Variables Required

```bash
# backend/.env
OPENAI_API_KEY=sk-...   # For embeddings (text-embedding-3-small)
```

### Manual Steps Required After Implementation

#### Migrations
- [ ] Create: `supabase/migrations/20260108000001_add_chunks_fts.sql`
- [ ] Run: `supabase migration up` (or via Supabase Dashboard)
- [ ] Verify: Check `fts` column and GIN index exist on chunks table

#### Environment Variables
- [ ] Add to `backend/.env`: `OPENAI_API_KEY=sk-...` (from OpenAI Dashboard)
- [ ] Add to Railway: Same environment variable

#### Manual Tests
- [ ] Upload a document and verify embeddings are generated after chunking
- [ ] Test hybrid search with exact term: "Section 138"
- [ ] Test hybrid search with semantic query: "contract breach remedies"
- [ ] Verify BM25-only and semantic-only endpoints work
- [ ] Test cross-matter search is blocked (use different user)
- [ ] Verify RRF scores in API response

### Downstream Dependencies

This story enables:
- **Story 2b-7 (Cohere Rerank):** Takes top 20 from hybrid search for refinement
- **Epic 3 (Citation Engine):** Uses semantic search for citation context
- **Epic 11 (Q&A Panel):** RAG retrieval for chat responses
- **Epic 6 (Engine Orchestrator):** Routes queries to hybrid search

### Project Structure Notes

- Embedding column exists but is NULL - this story populates it
- `match_chunks` function exists for semantic-only search (keep as fallback)
- New `hybrid_search_chunks` function combines both approaches
- FTS column uses GENERATED ALWAYS for automatic maintenance

### References

- [Source: architecture.md#Hybrid-Search] - Design requirements
- [Source: project-context.md#Matter-Isolation] - 4-layer enforcement
- [Source: supabase/migrations/20260106000002_create_chunks_table.sql] - Existing schema
- [Source: backend/app/services/rag/namespace.py] - Namespace validation patterns
- [Source: 2b-5-parent-child-chunking.md] - Previous story patterns
- [Source: Supabase Hybrid Search Docs](https://supabase.com/docs/guides/ai/hybrid-search) - RRF implementation
- [Source: pgvector GitHub](https://github.com/pgvector/pgvector) - HNSW configuration
- [Source: AWS pgvector Guide](https://aws.amazon.com/blogs/database/optimize-generative-ai-applications-with-pgvector-indexing-a-deep-dive-into-ivfflat-and-hnsw-techniques/) - Index tuning

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

1. **Database Migration**: Created `20260108000004_add_hybrid_search.sql` with FTS column, GIN index, and three SQL functions (bm25_search_chunks, semantic_search_chunks, hybrid_search_chunks) with mandatory matter isolation
2. **Embedding Service**: Implemented `EmbeddingService` in embedder.py with OpenAI text-embedding-3-small, Redis caching with 24h TTL, batch support, and retry logic via tenacity
3. **Hybrid Search Service**: Implemented `HybridSearchService` in hybrid_search.py supporting hybrid, BM25-only, and semantic-only search modes with RRF fusion (k=60)
4. **Celery Task**: Added `embed_chunks` task to document_tasks.py that processes chunks in batches of 50 with rate limiting
5. **API Endpoints**: Created search.py routes at `/api/matters/{matter_id}/search` with hybrid, BM25, and semantic endpoints using matter role authorization
6. **Frontend Types**: Created search.ts types and search.ts API client with full TypeScript support
7. **Tests**: Unit tests for embedding and hybrid search services, integration tests for search pipeline, and security tests for matter isolation
8. **4-Layer Isolation**: All SQL functions require matter_id, validate user access via auth.uid(), and filter results. Service layer uses validate_namespace() and validate_search_results()

### Design Decisions

1. **API Route Structure**: Used `/api/matters/{matter_id}/search` instead of `/api/search?matter_id=` to leverage existing `require_matter_role` dependency for consistent authorization
2. **Supabase RPC**: Used synchronous Supabase client (not async) as that's the pattern in the existing codebase
3. **Async Pattern**: EmbeddingService uses AsyncOpenAI; Celery task creates event loop to run async code in sync context
4. **RRF Default k=60**: Industry standard smoothing constant, configurable via parameter

### File List

**New Files Created:**
- `supabase/migrations/20260108000004_add_hybrid_search.sql`
- `backend/app/services/rag/embedder.py`
- `backend/app/services/rag/hybrid_search.py`
- `backend/app/api/routes/search.py`
- `backend/app/models/search.py`
- `frontend/src/types/search.ts`
- `frontend/src/lib/api/search.ts`
- `backend/tests/services/rag/__init__.py`
- `backend/tests/services/rag/test_embedder.py`
- `backend/tests/services/rag/test_hybrid_search.py`
- `backend/tests/integration/test_search_integration.py`
- `backend/tests/security/test_search_isolation.py`

**Modified Files:**
- `backend/app/services/rag/__init__.py` - Added exports for embedder and hybrid_search
- `backend/app/services/memory/__init__.py` - Added EMBEDDING_CACHE_TTL and embedding_cache_key exports
- `backend/app/services/memory/redis_keys.py` - Added embedding_cache_key function and EMBEDDING_CACHE_TTL constant
- `backend/app/workers/tasks/document_tasks.py` - Added embed_chunks Celery task
- `backend/app/main.py` - Registered search router
- `frontend/src/types/index.ts` - Added search type exports
- `_bmad-output/implementation-artifacts/sprint-status.yaml` - Updated story status

