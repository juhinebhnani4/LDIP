# Story 2B.7: Integrate Cohere Rerank

Status: review

## Story

As an **attorney**,
I want **search results ranked by relevance using AI**,
So that **the most pertinent documents appear first**.

## Acceptance Criteria

1. **Given** hybrid search returns 20 candidates **When** Cohere Rerank v3 processes them **Then** candidates are reranked by relevance to the query **And** the top 3 most relevant are returned

2. **Given** reranking is applied **When** results are returned **Then** each result includes a relevance_score from Cohere **And** results are ordered by this score descending

3. **Given** a query is vague **When** reranking occurs **Then** Cohere identifies the most contextually relevant matches **And** precision improves by 40-70% vs. hybrid search alone

4. **Given** Cohere API is unavailable **When** reranking fails **Then** the system falls back to RRF-ranked results **And** a warning is logged

## Tasks / Subtasks

- [x] Task 1: Create Cohere Rerank Service (AC: #1, #2)
  - [x] Create `backend/app/services/rag/reranker.py`
  - [x] Implement `CohereRerankService` class with async methods
  - [x] Method: `rerank(query: str, documents: list[str], top_n: int = 3) -> RerankResult`
  - [x] Use `cohere` Python SDK with async client
  - [x] Use model: `rerank-v3.5` (latest stable, best for retrieval)
  - [x] Add retry logic with tenacity (max 3 retries, exponential backoff)
  - [x] Include relevance_score in response
  - [x] Return original index mapping for result correlation

- [x] Task 2: Create Rerank Data Models (AC: #2)
  - [x] Create `backend/app/models/rerank.py`
  - [x] Define `RerankRequest` Pydantic model
  - [x] Define `RerankResult` dataclass with fields: document_index, relevance_score
  - [x] Define `RerankedSearchResult` extending SearchResult with relevance_score
  - [x] Define `RerankedSearchResponse` Pydantic model for API responses

- [x] Task 3: Integrate Reranker into Hybrid Search Service (AC: #1, #3, #4)
  - [x] Add `search_with_rerank()` method to `HybridSearchService`
  - [x] Input: `query: str, matter_id: str, hybrid_limit: int = 20, rerank_top_n: int = 3`
  - [x] Pipeline: `hybrid_search(limit=20) -> rerank(top_n=3) -> return`
  - [x] Map chunk content to documents for Cohere API
  - [x] Correlate reranked results back to original SearchResult objects
  - [x] Add `include_rerank: bool` parameter to existing `search()` method

- [x] Task 4: Implement Graceful Fallback (AC: #4)
  - [x] Wrap Cohere API calls in try-catch
  - [x] On CohereError or timeout: log warning and return RRF-ranked results
  - [x] Set timeout: 10 seconds for rerank API call
  - [x] Track fallback metrics via structlog
  - [x] Return `rerank_used: bool` flag in response meta

- [x] Task 5: Add Rerank API Endpoint (AC: #1, #2)
  - [x] Update `backend/app/api/routes/search.py`
  - [x] Add `POST /api/matters/{matter_id}/search/rerank` endpoint
  - [x] Request body: `{ query: string, limit?: number, top_n?: number }`
  - [x] Response: `{ data: RerankedSearchResult[], meta: { query, matter_id, rerank_used, fallback_reason? } }`
  - [x] Register in router

- [x] Task 6: Update Existing Hybrid Search Endpoint (AC: #1)
  - [x] Add optional `rerank: boolean` query parameter to existing hybrid search endpoint
  - [x] When `rerank=true`: call `search_with_rerank()` instead of `search()`
  - [x] Default: `rerank=false` (backward compatible)
  - [x] Update response model to include optional relevance_score

- [x] Task 7: Create Frontend Types and API Client (AC: #2)
  - [x] Update `frontend/src/types/search.ts`
    - Add `RerankedSearchResult` interface extending `SearchResult`
    - Add `RerankedSearchResponse` type
    - Add `RerankSearchRequest` interface
  - [x] Update `frontend/src/lib/api/search.ts`
    - Add `searchWithRerank(matterId, request): Promise<RerankedSearchResponse>`
    - Update `hybridSearch()` to accept optional `rerank` parameter

- [x] Task 8: Write Backend Unit Tests
  - [x] Create `backend/tests/services/rag/test_reranker.py`
    - Test rerank with valid documents
    - Test rerank with empty results (should return empty)
    - Test relevance_score ordering
    - Test retry logic with mock failures
    - Test fallback on Cohere API error
  - [x] Update `backend/tests/services/rag/test_hybrid_search.py`
    - Add tests for `search_with_rerank()` method
    - Test rerank integration
    - Test fallback behavior

- [x] Task 9: Write Backend Integration Tests
  - [x] Added tests to `backend/tests/integration/test_search_integration.py`
    - Test full pipeline: query -> hybrid search -> rerank -> results
    - Test fallback to RRF when Cohere unavailable (mock timeout)
    - Test top_n parameter affects result count
    - Test matter isolation preserved through rerank

- [x] Task 10: Write API Tests
  - [x] API tests covered in unit tests for search routes
    - Test `rerank=true` parameter on hybrid endpoint
    - Test error handling and fallback responses
    - Test response format compliance

- [x] Task 11: Add Environment Configuration
  - [x] Add `COHERE_API_KEY` to `backend/app/core/config.py` Settings
  - [x] Add validation for API key (required when rerank feature used)
  - [x] Update `.env.example` with `COHERE_API_KEY=`
  - [x] Document API key retrieval from Cohere Dashboard

- [x] Task 12: Update Service Exports and Registration
  - [x] Update `backend/app/services/rag/__init__.py` - Add reranker exports
  - [x] Update `backend/app/models/__init__.py` - Add rerank model exports
  - [x] Ensure all new modules are properly imported

## Dev Notes

### CRITICAL: Existing Infrastructure to Use

**From Story 2b-6 (Hybrid Search):**
- `HybridSearchService` in `backend/app/services/rag/hybrid_search.py` - Provides top 20 candidates
- `SearchResult` dataclass - Contains id, document_id, content, rrf_score, etc.
- `SearchWeights` for configurable BM25/semantic weighting
- `SearchResponse` and `SearchResultItem` in `backend/app/models/search.py`
- API routes at `/api/matters/{matter_id}/search`
- 4-layer matter isolation via `validate_namespace()` and RLS

**Key integration point:** The hybrid search `limit=20` parameter already anticipates downstream reranking. This story completes that pipeline.

### Architecture Requirements (MANDATORY)

**From [architecture.md](../_bmad-output/architecture.md):**

#### Cohere Rerank Design
From architecture Domain-Driven Constraints section:
- **Cohere Rerank v3** (40-70% precision gain for legal retrieval)
- Model: `rerank-v3.5` (latest stable version as of 2026)
- Top-20 candidates from hybrid search -> Top-3 after reranking

#### LLM Routing Rules (MUST FOLLOW)
```
| Task | Model | Rationale |
|------|-------|-----------|
| Hybrid search | N/A (SQL/embedding) | No LLM needed |
| Reranking | Cohere Rerank v3.5 | Specialized, cost-effective |
| Q&A synthesis | GPT-4 | User-facing, accuracy critical |
```

**CRITICAL:** Cohere Rerank is NOT an LLM - it's a specialized cross-encoder model optimized for document relevance scoring. Much cheaper than LLM calls.

#### 4-Layer Matter Isolation (MUST PRESERVE)
```
Layer 1: RLS policies on chunks table (already enforced)
Layer 2: Vector namespace filtering (already enforced in hybrid_search)
Layer 3: Redis key prefix (not applicable to rerank)
Layer 4: API middleware validates matter access (already enforced)
```
**No additional isolation needed in reranker** - documents come from already-isolated hybrid search results.

### Cohere Rerank API Reference

**Model:** `rerank-v3.5`
- Latest Cohere reranking model (released 2024)
- Optimized for English retrieval
- 4096 token context window per document
- Returns relevance_score 0.0-1.0

**API Request Example:**
```python
import cohere

co = cohere.Client(api_key="...")

results = co.rerank(
    model="rerank-v3.5",
    query="What is the termination clause?",
    documents=[
        "The contract may be terminated with 30 days notice...",
        "Payment shall be made within 15 business days...",
        "Either party may terminate for material breach...",
    ],
    top_n=3,
    return_documents=False,  # We have original docs, just need scores
)

# Response structure:
# results.results[0].index = 2 (original document index)
# results.results[0].relevance_score = 0.987
```

**Pricing (as of 2026):**
- $0.002 per 1,000 documents (very cost-effective)
- No token-based pricing
- ~100 documents per second throughput

### Implementation Pattern

**CohereRerankService:**
```python
# backend/app/services/rag/reranker.py

from dataclasses import dataclass
from typing import Sequence

import cohere
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

RERANK_MODEL = "rerank-v3.5"
DEFAULT_TOP_N = 3
RERANK_TIMEOUT_SECONDS = 10


@dataclass
class RerankResultItem:
    """Single reranked document result."""
    index: int  # Original document index
    relevance_score: float


@dataclass
class RerankResult:
    """Rerank operation result."""
    results: list[RerankResultItem]
    query: str
    model: str
    rerank_used: bool  # False if fallback occurred
    fallback_reason: str | None


class CohereRerankServiceError(Exception):
    """Exception for Cohere rerank service errors."""

    def __init__(
        self,
        message: str,
        code: str = "RERANK_ERROR",
        is_retryable: bool = True,
    ):
        self.message = message
        self.code = code
        self.is_retryable = is_retryable
        super().__init__(message)


class CohereRerankService:
    """Service for reranking search results using Cohere Rerank v3.5.

    Takes candidate documents from hybrid search and reranks them
    based on relevance to the query using Cohere's cross-encoder model.

    CRITICAL: Implements graceful fallback - if Cohere API fails,
    returns original RRF-ranked results with warning logged.
    """

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.cohere_api_key
        self._client = None  # Lazy initialization

    @property
    def client(self) -> cohere.Client:
        """Get Cohere client (lazy initialization)."""
        if self._client is None:
            if not self._api_key:
                raise CohereRerankServiceError(
                    message="Cohere API key not configured",
                    code="COHERE_NOT_CONFIGURED",
                    is_retryable=False,
                )
            self._client = cohere.Client(api_key=self._api_key)
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def rerank(
        self,
        query: str,
        documents: Sequence[str],
        top_n: int = DEFAULT_TOP_N,
    ) -> RerankResult:
        """Rerank documents by relevance to query.

        Args:
            query: Search query for relevance scoring.
            documents: List of document texts to rerank.
            top_n: Number of top results to return (default 3).

        Returns:
            RerankResult with sorted results by relevance_score.

        Raises:
            CohereRerankServiceError: If reranking fails after retries.
        """
        if not documents:
            return RerankResult(
                results=[],
                query=query,
                model=RERANK_MODEL,
                rerank_used=True,
                fallback_reason=None,
            )

        logger.info(
            "cohere_rerank_start",
            query_len=len(query),
            document_count=len(documents),
            top_n=top_n,
        )

        try:
            response = self.client.rerank(
                model=RERANK_MODEL,
                query=query,
                documents=list(documents),
                top_n=min(top_n, len(documents)),
                return_documents=False,
            )

            results = [
                RerankResultItem(
                    index=r.index,
                    relevance_score=r.relevance_score,
                )
                for r in response.results
            ]

            logger.info(
                "cohere_rerank_complete",
                query_len=len(query),
                top_score=results[0].relevance_score if results else 0,
                result_count=len(results),
            )

            return RerankResult(
                results=results,
                query=query,
                model=RERANK_MODEL,
                rerank_used=True,
                fallback_reason=None,
            )

        except cohere.CohereError as e:
            logger.warning(
                "cohere_rerank_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise CohereRerankServiceError(
                message=f"Cohere API error: {e!s}",
                code="COHERE_API_ERROR",
                is_retryable=True,
            ) from e
```

**Integration into HybridSearchService:**
```python
# Add to backend/app/services/rag/hybrid_search.py

async def search_with_rerank(
    self,
    query: str,
    matter_id: str,
    hybrid_limit: int = 20,
    rerank_top_n: int = 3,
    weights: SearchWeights | None = None,
) -> RerankedSearchResult:
    """Execute hybrid search with Cohere reranking.

    Pipeline: hybrid_search(limit=20) -> rerank(top_n=3)

    Args:
        query: Search query text.
        matter_id: REQUIRED - matter UUID for isolation.
        hybrid_limit: Candidates from hybrid search (default 20).
        rerank_top_n: Final results after reranking (default 3).
        weights: Optional custom weights for hybrid search.

    Returns:
        RerankedSearchResult with relevance_score from Cohere.
    """
    # Step 1: Get candidates from hybrid search
    hybrid_result = await self.search(
        query=query,
        matter_id=matter_id,
        limit=hybrid_limit,
        weights=weights,
    )

    if not hybrid_result.results:
        return RerankedSearchResult(
            results=[],
            query=query,
            matter_id=matter_id,
            rerank_used=False,
            fallback_reason="No hybrid search results",
        )

    # Step 2: Extract content for reranking
    documents = [r.content for r in hybrid_result.results]

    # Step 3: Rerank with fallback
    try:
        reranker = get_cohere_rerank_service()
        rerank_result = await reranker.rerank(
            query=query,
            documents=documents,
            top_n=rerank_top_n,
        )

        # Step 4: Map reranked indices back to original results
        reranked_results = []
        for item in rerank_result.results:
            original = hybrid_result.results[item.index]
            reranked_results.append(
                RerankedSearchResultItem(
                    **vars(original),
                    relevance_score=item.relevance_score,
                )
            )

        return RerankedSearchResult(
            results=reranked_results,
            query=query,
            matter_id=matter_id,
            weights=weights or SearchWeights(),
            total_candidates=hybrid_result.total_candidates,
            rerank_used=True,
            fallback_reason=None,
        )

    except CohereRerankServiceError as e:
        # Graceful fallback to RRF-ranked results
        logger.warning(
            "rerank_fallback_to_rrf",
            matter_id=matter_id,
            error=e.message,
        )

        # Return top N from RRF results instead
        fallback_results = [
            RerankedSearchResultItem(
                **vars(r),
                relevance_score=None,  # No Cohere score
            )
            for r in hybrid_result.results[:rerank_top_n]
        ]

        return RerankedSearchResult(
            results=fallback_results,
            query=query,
            matter_id=matter_id,
            weights=weights or SearchWeights(),
            total_candidates=hybrid_result.total_candidates,
            rerank_used=False,
            fallback_reason=e.message,
        )
```

### Previous Story Intelligence

**FROM Story 2b-6 (Hybrid Search) - CRITICAL CONTEXT:**
- Hybrid search returns top 20 candidates via RRF fusion
- `SearchResult` dataclass has: id, matter_id, document_id, content, page_number, chunk_type, token_count, bm25_rank, semantic_rank, rrf_score
- `HybridSearchResult` wrapper has: results, query, matter_id, weights, total_candidates
- Service uses `validate_namespace()` and `validate_search_results()` for security
- API endpoint: `POST /api/matters/{matter_id}/search`
- structlog logging throughout

**Key files to reference:**
- [backend/app/services/rag/hybrid_search.py](backend/app/services/rag/hybrid_search.py) - Extend this service
- [backend/app/api/routes/search.py](backend/app/api/routes/search.py) - Add rerank endpoint
- [backend/app/models/search.py](backend/app/models/search.py) - Extend models
- [backend/app/services/rag/embedder.py](backend/app/services/rag/embedder.py) - Pattern for external API service

### Git Intelligence

Recent commits:
```
5d4d398 feat(search): implement hybrid BM25+pgvector search with RRF fusion (Story 2b-6)
ddd2b24 fix(chunking): address code review issues for Story 2b-5
971e20e feat(chunking): implement parent-child chunking for RAG pipeline (Story 2b-5)
```

**Recommended commit message:** `feat(search): integrate Cohere Rerank for top-20 to top-3 refinement (Story 2b-7)`

### Critical Architecture Constraints

**FROM PROJECT-CONTEXT.md - MUST FOLLOW EXACTLY:**

#### Backend Technology Stack
- **Python 3.12+** - use modern syntax (match statements, type hints)
- **FastAPI 0.115+** - async endpoints where beneficial
- **Pydantic v2** - use model_validator, not validator (v1 syntax)
- **structlog** for logging - NOT standard logging library
- **tenacity** for retry logic - already used in embedder.py

#### API Response Format (MANDATORY)
```python
# Success - reranked results
{
  "data": [
    {
      "id": "uuid",
      "document_id": "uuid",
      "content": "...",
      "chunk_type": "child",
      "rrf_score": 0.034,
      "relevance_score": 0.987,  # NEW from Cohere
      "bm25_rank": 3,
      "semantic_rank": 5
    }
  ],
  "meta": {
    "query": "...",
    "matter_id": "uuid",
    "total_candidates": 20,
    "rerank_used": true,
    "fallback_reason": null
  }
}

# Error
{ "error": { "code": "RERANK_FAILED", "message": "...", "details": {} } }
```

#### Naming Conventions
| Layer | Convention | Example |
|-------|------------|---------|
| Database columns | snake_case | `relevance_score` |
| TypeScript variables | camelCase | `relevanceScore` |
| Python functions | snake_case | `search_with_rerank` |
| Python classes | PascalCase | `CohereRerankService` |
| API endpoints | kebab-case | `/api/search/rerank` |

### File Organization

```
backend/app/
├── services/
│   └── rag/
│       ├── __init__.py                     (UPDATE - export reranker)
│       ├── hybrid_search.py                (UPDATE - add search_with_rerank)
│       └── reranker.py                     (NEW) - Cohere rerank service
├── api/
│   └── routes/
│       └── search.py                       (UPDATE - add rerank endpoint)
├── models/
│   ├── __init__.py                         (UPDATE - export rerank models)
│   ├── search.py                           (UPDATE - add reranked models)
│   └── rerank.py                           (NEW) - Rerank-specific models
├── core/
│   └── config.py                           (UPDATE - add COHERE_API_KEY)

frontend/src/
├── types/
│   └── search.ts                           (UPDATE - add reranked types)
└── lib/
    └── api/
        └── search.ts                       (UPDATE - add rerank method)

backend/tests/
├── services/
│   └── rag/
│       ├── test_reranker.py                (NEW)
│       └── test_hybrid_search.py           (UPDATE - add rerank tests)
├── integration/
│   └── test_rerank_integration.py          (NEW)
└── api/
    └── test_search.py                      (UPDATE - add rerank endpoint tests)
```

### Testing Guidance

#### Unit Tests

```python
# backend/tests/services/rag/test_reranker.py

import pytest
from unittest.mock import MagicMock, patch

from app.services.rag.reranker import (
    CohereRerankService,
    CohereRerankServiceError,
    RerankResult,
)


@pytest.fixture
def mock_cohere_client():
    """Mock Cohere client."""
    with patch("app.services.rag.reranker.cohere.Client") as mock:
        client = mock.return_value
        yield client


@pytest.mark.asyncio
async def test_rerank_returns_sorted_results(mock_cohere_client):
    """Test rerank returns results sorted by relevance_score."""
    mock_response = MagicMock()
    mock_response.results = [
        MagicMock(index=2, relevance_score=0.95),
        MagicMock(index=0, relevance_score=0.82),
        MagicMock(index=1, relevance_score=0.65),
    ]
    mock_cohere_client.rerank.return_value = mock_response

    service = CohereRerankService()
    service._client = mock_cohere_client

    result = await service.rerank(
        query="contract termination",
        documents=["doc1", "doc2", "doc3"],
        top_n=3,
    )

    assert result.rerank_used is True
    assert len(result.results) == 3
    # Original index 2 should be first (highest score)
    assert result.results[0].index == 2
    assert result.results[0].relevance_score == 0.95


@pytest.mark.asyncio
async def test_rerank_empty_documents_returns_empty():
    """Test rerank with empty documents returns empty result."""
    service = CohereRerankService()

    result = await service.rerank(
        query="test",
        documents=[],
        top_n=3,
    )

    assert result.results == []
    assert result.rerank_used is True


@pytest.mark.asyncio
async def test_search_with_rerank_fallback(mock_cohere_client):
    """Test search_with_rerank falls back to RRF on Cohere error."""
    mock_cohere_client.rerank.side_effect = Exception("API timeout")

    # Test that fallback returns RRF results
    # ...
```

#### Integration Tests

```python
# backend/tests/integration/test_rerank_integration.py

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_rerank_endpoint_returns_relevance_scores(
    client: AsyncClient,
    test_matter_with_chunks: Matter,
    auth_headers: dict,
):
    """Test rerank endpoint includes relevance_score in results."""
    response = await client.post(
        f"/api/matters/{test_matter_with_chunks.id}/search/rerank",
        headers=auth_headers,
        json={
            "query": "contract termination clause",
            "top_n": 3,
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert "data" in data
    assert "meta" in data
    assert data["meta"]["rerank_used"] is True

    # Each result should have relevance_score
    for result in data["data"]:
        assert "relevance_score" in result
        assert 0 <= result["relevance_score"] <= 1


@pytest.mark.asyncio
async def test_rerank_fallback_on_api_error(
    client: AsyncClient,
    test_matter_with_chunks: Matter,
    auth_headers: dict,
    mock_cohere_unavailable,  # Fixture that makes Cohere return errors
):
    """Test graceful fallback when Cohere API is unavailable."""
    response = await client.post(
        f"/api/matters/{test_matter_with_chunks.id}/search/rerank",
        headers=auth_headers,
        json={"query": "test", "top_n": 3}
    )

    # Should still succeed with fallback
    assert response.status_code == 200
    data = response.json()

    assert data["meta"]["rerank_used"] is False
    assert data["meta"]["fallback_reason"] is not None


@pytest.mark.asyncio
async def test_hybrid_search_with_rerank_param(
    client: AsyncClient,
    test_matter_with_chunks: Matter,
    auth_headers: dict,
):
    """Test hybrid search endpoint with rerank=true parameter."""
    response = await client.post(
        f"/api/matters/{test_matter_with_chunks.id}/search?rerank=true",
        headers=auth_headers,
        json={
            "query": "contract termination",
            "limit": 20,
        }
    )

    assert response.status_code == 200
    # Results should be reranked (top 3 returned)
    assert len(response.json()["data"]) <= 3
```

### Anti-Patterns to AVOID

```python
# WRONG: Not handling Cohere API failures
result = co.rerank(...)  # Could throw, crashes the request

# CORRECT: Wrap in try-catch with fallback
try:
    result = co.rerank(...)
except cohere.CohereError:
    return fallback_to_rrf_results()

# WRONG: Using synchronous Cohere client in async context
def sync_rerank():
    return co.rerank(...)  # Blocks event loop

# CORRECT: Use async patterns (Cohere SDK is sync, wrap appropriately)
async def async_rerank():
    return await asyncio.to_thread(co.rerank, ...)  # Or use dedicated executor

# WRONG: Hardcoding model version
model = "rerank-english-v2.0"  # Outdated

# CORRECT: Use constant with latest version
RERANK_MODEL = "rerank-v3.5"  # Latest as of 2026

# WRONG: Returning all 20 results after reranking
results = co.rerank(top_n=20)  # Defeats purpose of reranking

# CORRECT: Use appropriate top_n (default 3)
results = co.rerank(top_n=3)  # Return most relevant

# WRONG: Losing matter isolation context
reranked = rerank(documents)  # No matter_id tracking

# CORRECT: Preserve matter_id through pipeline
result.matter_id = hybrid_result.matter_id  # Maintain isolation proof
```

### Performance Considerations

- **Cohere API latency:** ~100-200ms for 20 documents
- **Timeout:** Set 10s timeout to prevent hung requests
- **Caching:** Consider caching rerank results by query+document hash (TTL: 1 hour)
- **Batch size:** Cohere handles up to 1000 documents per request, but 20 is optimal for our use case
- **Token limits:** Documents are truncated at 4096 tokens by Cohere automatically

### Dependencies to Add

```bash
# backend/
uv add cohere           # Cohere Python SDK
```

### Environment Variables Required

```bash
# backend/.env
COHERE_API_KEY=...   # From Cohere Dashboard (https://dashboard.cohere.ai/api-keys)
```

### Manual Steps Required After Implementation

#### Dependencies
- [ ] Run: `cd backend && uv add cohere`

#### Environment Variables
- [ ] Add to `backend/.env`: `COHERE_API_KEY=...` (from Cohere Dashboard)
- [ ] Add to `backend/.env.example`: `COHERE_API_KEY=`
- [ ] Add to Railway production: Same environment variable

#### Manual Tests
- [ ] Test rerank endpoint with valid query: should return top 3 results with relevance_score
- [ ] Test fallback: Set invalid COHERE_API_KEY and verify fallback to RRF results
- [ ] Test hybrid search with `?rerank=true` parameter
- [ ] Compare results: hybrid search vs hybrid+rerank (rerank should have better relevance ordering)
- [ ] Verify matter isolation: Cross-matter search should still fail
- [ ] Test timeout behavior: Verify 10s timeout works (may need to mock slow API)

### Downstream Dependencies

This story completes the RAG search pipeline:
- **Epic 3 (Citation Engine):** Uses reranked search for finding citation contexts
- **Epic 11 (Q&A Panel):** RAG retrieval now returns most relevant chunks
- **Epic 5 (Contradiction Engine):** Entity-grouped queries benefit from reranking
- **Epic 6 (Engine Orchestrator):** Routes queries through complete search pipeline

### Project Structure Notes

- Reranker is an optional enhancement - hybrid search works without it
- Graceful fallback ensures system resilience
- `rerank_used` flag in response allows UI to show fallback state if needed
- No database changes required - reranking is purely service-layer

### References

- [Source: architecture.md#Cohere-Rerank] - Design requirements
- [Source: project-context.md#LLM-Routing] - Model selection rules
- [Source: 2b-6-hybrid-search-bm25-pgvector.md] - Previous story context
- [Source: Cohere Rerank API Docs](https://docs.cohere.com/reference/rerank) - API reference
- [Source: Cohere Rerank Guide](https://docs.cohere.com/docs/rerank-guide) - Best practices
- [Source: Cohere Python SDK](https://github.com/cohere-ai/cohere-python) - SDK documentation

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

1. **Cohere SDK Async Pattern**: The Cohere Python SDK is synchronous, so we use `asyncio.to_thread()` to run rerank calls without blocking the event loop.

2. **Lazy Client Initialization**: The CohereRerankService uses lazy initialization for the Cohere client to avoid errors when the API key is not configured (allows graceful handling of missing configuration).

3. **Graceful Fallback Design**: When Cohere API fails (timeout, error, or missing API key), the system returns RRF-ranked results from hybrid search with `rerank_used=false` and `fallback_reason` populated. This ensures service availability even when Cohere is unavailable.

4. **Retry Logic**: Uses tenacity with exponential backoff (max 3 retries) for transient Cohere API failures.

5. **Integration Tests**: Added to existing `test_search_integration.py` rather than creating separate file to maintain test organization consistency.

6. **API Design**: Both dedicated `/rerank` endpoint and `rerank=true` query parameter on existing hybrid search endpoint provide flexibility for different use cases.

### File List

**New Files Created:**
- `backend/app/services/rag/reranker.py` - Cohere Rerank service implementation
- `backend/app/models/rerank.py` - Rerank request/response Pydantic models
- `backend/tests/services/rag/test_reranker.py` - Unit tests for reranker service

**Files Modified:**
- `backend/app/services/rag/hybrid_search.py` - Added `search_with_rerank()` method, `RerankedSearchResult`, `RerankedSearchResultItem` dataclasses
- `backend/app/services/rag/__init__.py` - Added reranker exports
- `backend/app/models/search.py` - Added `rerank`, `rerank_top_n`, `relevance_score`, `rerank_used`, `fallback_reason` fields
- `backend/app/api/routes/search.py` - Added `/rerank` endpoint and `rerank` query parameter support
- `backend/app/core/config.py` - Added `cohere_api_key` setting
- `backend/.env.example` - Added `COHERE_API_KEY` documentation
- `backend/tests/services/rag/test_hybrid_search.py` - Added rerank integration tests
- `backend/tests/integration/test_search_integration.py` - Added rerank pipeline integration tests
- `frontend/src/types/search.ts` - Added rerank-related TypeScript types
- `frontend/src/lib/api/search.ts` - Added `searchWithRerank()` function and updated `hybridSearch()`

