# Story 14.11: Global Search RAG Wiring

Status: complete

## Story

As an **attorney**,
I want **to search across all my matters using the global search bar**,
so that I can **quickly find relevant documents and matters by keyword or concept without navigating to each matter individually**.

## Acceptance Criteria

1. **Global Search API Endpoint Created**
   - When authenticated user calls GET /api/search?q=query, they receive search results across ALL their matters
   - Response includes matters and documents matching the query
   - Results are ranked by relevance using hybrid search (BM25 + semantic)
   - Response matches frontend `SearchResult` interface from GlobalSearch.tsx

2. **Matter-Level Access Control**
   - When searching, only results from matters the user has access to are returned
   - RLS ensures users cannot see results from matters they don't belong to
   - Search respects OWNER, EDITOR, VIEWER roles (all can search)

3. **Search Results Include Context**
   - Each result includes: id, type (matter/document), title, matterId, matterTitle, matchedContent
   - Document results include a snippet of matched content (50-100 chars around match)
   - Matter results include the matter description or first document summary as matchedContent

4. **Frontend GlobalSearch Wired to API**
   - GlobalSearch.tsx `performSearch` calls GET /api/search?q=query
   - Remove mock data and simulated delay
   - Loading state shows while API request is in-flight
   - Errors display user-friendly message with retry option

5. **Debounce and Performance**
   - Search is debounced at 300ms (already implemented in frontend)
   - Backend returns results within 500ms for typical queries
   - Limit results to 20 items to prevent over-fetching

6. **Empty and Error States**
   - When no results found, display "No results found for 'query'"
   - When API error occurs, display error message and allow retry
   - When query is empty, show no results (already implemented)

7. **Tests Added**
   - Backend: pytest tests for /api/search endpoint with auth and RLS
   - Frontend: Update GlobalSearch.test.tsx to mock API calls

## Tasks / Subtasks

- [x] Task 1: Create Global Search API endpoint (AC: #1, #2)
  - [x] 1.1: Create `backend/app/api/routes/global_search.py`
  - [x] 1.2: Implement `GET /api/search` with query param `q` (required) and `limit` (default 20, max 50)
  - [x] 1.3: Query all matters user has access to (via matter_attorneys table)
  - [x] 1.4: For each accessible matter, run hybrid search and aggregate results
  - [x] 1.5: Register router in `backend/app/main.py`

- [x] Task 2: Create Global Search models (AC: #1, #3)
  - [x] 2.1: Create `backend/app/models/global_search.py`
  - [x] 2.2: Define GlobalSearchResultItem with camelCase aliases matching frontend
  - [x] 2.3: Define GlobalSearchResponse with data array and meta

- [x] Task 3: Create Global Search service (AC: #1, #2, #3)
  - [x] 3.1: Create `backend/app/services/global_search_service.py`
  - [x] 3.2: Implement `search_across_matters(user_id, query, limit)` method
  - [x] 3.3: Get all matter_ids user has access to from matter_attorneys
  - [x] 3.4: For each matter, execute hybrid_search with rerank=false, limit=10
  - [x] 3.5: Merge and re-rank results by RRF score across all matters
  - [x] 3.6: Map chunk results to GlobalSearchResultItem format
  - [x] 3.7: Add matter results (matching matter titles) to response

- [x] Task 4: Wire frontend to real API (AC: #4, #6)
  - [x] 4.1: Create `frontend/src/lib/api/globalSearch.ts` with search function
  - [x] 4.2: Update `GlobalSearch.tsx` performSearch to call API
  - [x] 4.3: Remove getMockSearchResults function
  - [x] 4.4: Add error state and retry button
  - [x] 4.5: Handle API errors with toast notification

- [x] Task 5: Write tests (AC: #7)
  - [x] 5.1: Create `backend/tests/api/test_global_search.py`
  - [x] 5.2: Test returns only results from accessible matters
  - [x] 5.3: Test returns both matter and document results
  - [x] 5.4: Test respects limit parameter
  - [x] 5.5: Update `frontend/src/components/features/dashboard/GlobalSearch.test.tsx` with API mocks

## Dev Notes

### Critical Architecture Patterns

**IMPORTANT: Matter Isolation (4-Layer Security)**
- Layer 1: Authentication (Supabase Auth - user must be logged in)
- Layer 2: RLS (matter_members table enforces access at database level)
- Layer 3: API (membership check before any query)
- Layer 4: Service (validate_namespace on every search operation)

For global search, we CANNOT use the existing `/matters/{matter_id}/search` endpoint directly because we need to search across ALL matters. Instead:
1. Query `matter_members` to get all matter_ids for the user
2. Execute parallel searches across each matter
3. Merge results with cross-matter RRF

**Hybrid Search Service - ALREADY EXISTS**
DO NOT create new search logic. Use existing `HybridSearchService` from:
- [hybrid_search.py](backend/app/services/rag/hybrid_search.py)
- Use `search()` method with `limit=10` per matter (then aggregate)
- Do NOT use `search_with_rerank()` for global search (too slow across many matters)

**API Response Format (from project-context.md)**
```typescript
// Success response
{
  "data": [...],
  "meta": { "query": "...", "total": 10 }
}

// Error response
{
  "error": {
    "code": "SEARCH_FAILED",
    "message": "...",
    "details": {}
  }
}
```

### Type Mapping (Backend to Frontend)

**Frontend SearchResult interface (GlobalSearch.tsx:14-21):**
```typescript
interface SearchResult {
  id: string;
  type: 'matter' | 'document';
  title: string;
  matterId: string;
  matterTitle: string;
  matchedContent: string;
}
```

**Backend GlobalSearchResultItem (new model):**
```python
class GlobalSearchResultItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: Literal["matter", "document"]
    title: str
    matter_id: str = Field(..., alias="matterId")
    matter_title: str = Field(..., alias="matterTitle")
    matched_content: str = Field(..., alias="matchedContent")
```

### Implementation Approach

**Service Layer Pattern:**
```python
# backend/app/services/global_search_service.py

class GlobalSearchService:
    def __init__(self, hybrid_search: HybridSearchService | None = None):
        self.hybrid_search = hybrid_search or get_hybrid_search_service()

    async def search_across_matters(
        self,
        user_id: str,
        query: str,
        limit: int = 20,
    ) -> GlobalSearchResponse:
        # 1. Get all matters user has access to
        # 2. Search each matter in parallel (asyncio.gather)
        # 3. Merge results with cross-matter RRF
        # 4. Also search matter titles/descriptions
        # 5. Return unified response
```

**Parallel Search Pattern:**
```python
import asyncio

# Search all matters in parallel
search_tasks = [
    self.hybrid_search.search(
        query=query,
        matter_id=matter_id,
        limit=10,  # Get top 10 from each matter
    )
    for matter_id in accessible_matter_ids
]
results = await asyncio.gather(*search_tasks, return_exceptions=True)
```

**Cross-Matter RRF Merge:**
```python
# After gathering results from all matters, merge with RRF
# rrf_score = sum(1 / (k + rank)) for each result's rank across matters
# k = 60 (standard RRF constant)
```

### Files to Create

| File | Purpose |
|------|---------|
| `backend/app/models/global_search.py` | Pydantic models for global search |
| `backend/app/services/global_search_service.py` | Search across matters service |
| `backend/app/api/routes/global_search.py` | API endpoint |
| `backend/tests/api/test_global_search.py` | Backend tests |
| `frontend/src/lib/api/globalSearch.ts` | API client |

### Files to Modify

| File | Changes |
|------|---------|
| `backend/app/main.py` | Register global_search router |
| `frontend/src/components/features/dashboard/GlobalSearch.tsx` | Wire to API |
| `frontend/src/components/features/dashboard/GlobalSearch.test.tsx` | Add API mocks |

### Files to Reference (NO changes)

| File | Purpose |
|------|---------|
| [hybrid_search.py](backend/app/services/rag/hybrid_search.py) | Reuse HybridSearchService |
| [search.py](backend/app/api/routes/search.py) | Follow API patterns |
| [models/search.py](backend/app/models/search.py) | Follow model patterns |
| [project-context.md](_bmad-output/project-context.md) | API standards |

### Performance Considerations

1. **Parallel Matter Search**: Use `asyncio.gather()` to search all matters concurrently
2. **Per-Matter Limit**: Limit to 10 results per matter to avoid overwhelming the merge
3. **Total Limit**: Final limit of 20 results after merge
4. **No Reranking**: Skip Cohere rerank for global search (too slow for multi-matter)
5. **Response Time Target**: < 500ms for typical queries (3-5 matters, 10 results each)

### Matter Title Matching

In addition to document content search, include matter title matches:
```python
# Query matters table for title matches
matters_query = supabase.from_("matters").select(
    "id, title, description"
).ilike("title", f"%{query}%").in_("id", accessible_matter_ids).limit(5)

# Add matter results to response with type="matter"
for matter in matters_result:
    results.append(GlobalSearchResultItem(
        id=matter["id"],
        type="matter",
        title=matter["title"],
        matter_id=matter["id"],
        matter_title=matter["title"],
        matched_content=matter.get("description", "")[:100],
    ))
```

### Frontend API Client

```typescript
// frontend/src/lib/api/globalSearch.ts
import { apiClient } from './client';

interface SearchResult {
  id: string;
  type: 'matter' | 'document';
  title: string;
  matterId: string;
  matterTitle: string;
  matchedContent: string;
}

interface GlobalSearchResponse {
  data: SearchResult[];
  meta: {
    query: string;
    total: number;
  };
}

export async function globalSearch(
  query: string,
  limit = 20
): Promise<SearchResult[]> {
  const params = new URLSearchParams({ q: query, limit: limit.toString() });
  const response = await apiClient.get<GlobalSearchResponse>(
    `/api/search?${params.toString()}`
  );
  return response.data;
}
```

### Frontend Changes

Update `GlobalSearch.tsx` performSearch:
```typescript
// BEFORE (mock)
const searchResults = getMockSearchResults(searchQuery);
setResults(searchResults);

// AFTER (real API)
try {
  const searchResults = await globalSearch(searchQuery);
  setResults(searchResults);
} catch (error) {
  setError('Search failed. Please try again.');
  toast.error('Search failed');
}
```

### Testing Strategy

**Backend Tests:**
```python
@pytest.mark.asyncio
async def test_global_search_returns_only_accessible_matters(
    client: AsyncClient, test_user: User, other_user: User
):
    """Verify user only sees results from their matters."""
    # Create matter for test_user
    # Create matter for other_user
    # Search as test_user
    # Assert only test_user's matter results returned

@pytest.mark.asyncio
async def test_global_search_includes_matter_and_document_results(
    client: AsyncClient, test_user: User
):
    """Verify both matter titles and document content are searched."""
    # Create matter with title matching query
    # Add document with content matching query
    # Search
    # Assert both matter and document results present
```

**Frontend Tests:**
```typescript
vi.mock('@/lib/api/globalSearch', () => ({
  globalSearch: vi.fn(),
}));

test('calls API on search input', async () => {
  vi.mocked(globalSearch).mockResolvedValue([
    { id: '1', type: 'matter', ... }
  ]);

  render(<GlobalSearch />);
  await userEvent.type(screen.getByRole('searchbox'), 'contract');

  await waitFor(() => {
    expect(globalSearch).toHaveBeenCalledWith('contract');
  });
});
```

### Edge Cases

1. **No accessible matters**: Return empty results (not an error)
2. **One matter has error**: Log error, continue with other matters (partial results OK)
3. **Query too short**: Minimum 2 characters (enforce in API)
4. **Empty query**: Return empty results (handled in frontend)

### Security Checklist

- [x] User ID extracted from auth token (not request body) - via `Depends(get_current_user)` in route
- [x] Matter access verified via matter_attorneys table - service queries `matter_attorneys` for accessible matters
- [x] No matter_id exposed that user doesn't have access to - only queries matters from `matter_attorneys` join
- [x] Search queries logged for audit (structlog) - `global_search_request` and `global_search_response` log events

### References

- [Source: GlobalSearch.tsx](frontend/src/components/features/dashboard/GlobalSearch.tsx) - Frontend component to wire
- [Source: hybrid_search.py](backend/app/services/rag/hybrid_search.py) - Existing search service to reuse
- [Source: routes/search.py](backend/app/api/routes/search.py) - API patterns to follow
- [Source: models/search.py](backend/app/models/search.py) - Model patterns to follow
- [Source: project-context.md](_bmad-output/project-context.md) - API standards
- [Source: Story 9.1](implementation-artifacts/9-1-dashboard-header.md) - GlobalSearch original implementation
- [Source: sprint-status.yaml](implementation-artifacts/sprint-status.yaml) - Story tracking

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

1. Created global search models in `backend/app/models/global_search.py` with camelCase aliases matching frontend interface
2. Created `GlobalSearchService` in `backend/app/services/global_search_service.py` that:
   - Queries `matter_attorneys` table to get all accessible matters for the user
   - Executes parallel hybrid searches across all matters using `asyncio.gather`
   - Merges results using cross-matter RRF (Reciprocal Rank Fusion)
   - Includes matter title matches alongside document content matches
3. Created API endpoint at `GET /api/search` with query validation (min 2 chars, max 500 chars for query; max 50 for limit)
4. Wired frontend `GlobalSearch.tsx` to use real API:
   - Created `frontend/src/lib/api/globalSearch.ts` API client
   - Replaced mock data with real API calls
   - Added error state with retry button
   - Added toast notification on error
5. Created comprehensive tests:
   - Backend API: 13 tests covering auth, matter isolation, result formats, and error handling
   - Backend Service: 22 tests covering snippet extraction, RRF merge, matter matching
   - Frontend: 15 tests covering UI and API integration

### Code Review Fixes (2026-01-16)

1. **[CRITICAL FIX]** Document results now return `document_id` instead of `chunk_id` for correct navigation
2. **[FIX]** Match snippets now center around query match (50-100 chars) instead of taking first 100 chars
3. **[FIX]** Added service-level unit tests (`test_global_search_service.py` with 22 tests)
4. **[FIX]** Security checklist verified and marked complete

### File List

**Created:**
- `backend/app/models/global_search.py` - Pydantic models for global search
- `backend/app/services/global_search_service.py` - Cross-matter search service
- `backend/app/api/routes/global_search.py` - API endpoint
- `backend/tests/api/test_global_search.py` - Backend API tests (13 tests)
- `backend/tests/services/test_global_search_service.py` - Backend service tests (22 tests)
- `frontend/src/lib/api/globalSearch.ts` - API client

**Modified:**
- `backend/app/main.py` - Registered global_search router
- `frontend/src/components/features/dashboard/GlobalSearch.tsx` - Wired to real API
- `frontend/src/components/features/dashboard/GlobalSearch.test.tsx` - Added API integration tests
