# Story 14.1: Summary API Endpoint

Status: done

## Story

As a **legal attorney using LDIP**,
I want **to retrieve an AI-generated executive summary for my matter**,
so that **I can quickly understand the key parties, subject matter, current status, key issues, and actionable items requiring my attention**.

## Acceptance Criteria

1. **AC1: GET /api/matters/{matter_id}/summary endpoint exists**
   - Returns HTTP 200 with MatterSummary data structure
   - Returns HTTP 404 if matter not found or user lacks access
   - Returns HTTP 401 if user not authenticated
   - Validates matter access via RLS (user must be matter member)

2. **AC2: Summary data structure matches frontend TypeScript interface**
   - `matterId`: string - the matter ID
   - `attentionItems[]`: array of items needing action (contradictions, citation issues, timeline gaps)
   - `parties[]`: array of PartyInfo (petitioner/respondent with entity links)
   - `subjectMatter`: object with AI-generated description and source citations
   - `currentStatus`: object with last order date, description, source reference
   - `keyIssues[]`: array of numbered issues with verification status
   - `stats`: object with totalPages, entitiesFound, eventsExtracted, citationsFound, verificationPercent
   - `generatedAt`: ISO timestamp of when summary was generated

3. **AC3: Summary uses GPT-4 for executive summary generation**
   - Retrieves top chunks from the matter via RAG pipeline
   - Includes timeline events, entities, and last order/status
   - Uses GPT-4 (reasoning layer) per architecture LLM routing rules
   - Applies language policing to sanitize legal conclusions

4. **AC4: Summary is cached in Redis with 1-hour TTL**
   - Cache key format: `summary:{matter_id}`
   - Returns cached summary if available and not expired
   - Invalidates cache on document upload or processing completion
   - Regenerates on cache miss or forced refresh

5. **AC5: Attention items are dynamically computed**
   - Count contradictions from `statement_comparisons` table
   - Count unverified citations from `citations` table
   - Count timeline gaps/anomalies from `anomalies` table
   - Return actual counts, not mock data

6. **AC6: Parties extracted from MIG (Matter Identity Graph)**
   - Query `entity_mentions` table for entities with role = 'petitioner' or 'respondent'
   - Link to canonical entity from `identity_nodes`
   - Include source document and page reference

7. **AC7: Stats computed from actual database tables**
   - `totalPages`: SUM of pages from `documents` table
   - `entitiesFound`: COUNT DISTINCT from `identity_nodes`
   - `eventsExtracted`: COUNT from `events` table
   - `citationsFound`: COUNT from `citations` table
   - `verificationPercent`: (verified_count / total_count) * 100 from `finding_verifications`

## Tasks / Subtasks

- [x] **Task 1: Create backend Pydantic models** (AC: #2)
  - [x] 1.1 Create `backend/app/models/summary.py` with all types matching frontend `types/summary.ts`
  - [x] 1.2 Define enums: `AttentionItemType`, `PartyRole`, `KeyIssueVerificationStatus`
  - [x] 1.3 Define models: `AttentionItem`, `PartyInfo`, `SubjectMatter`, `CurrentStatus`, `KeyIssue`, `MatterStats`, `MatterSummary`
  - [x] 1.4 Define response wrapper: `MatterSummaryResponse`

- [x] **Task 2: Create Summary Service** (AC: #3, #4, #5, #6, #7)
  - [x] 2.1 Create `backend/app/services/summary_service.py`
  - [x] 2.2 Implement `get_attention_items(matter_id)` - query contradictions, citations, anomalies tables
  - [x] 2.3 Implement `get_parties(matter_id)` - query entity_mentions + identity_nodes for parties
  - [x] 2.4 Implement `get_stats(matter_id)` - aggregate counts from documents, entities, events, citations tables
  - [x] 2.5 Implement `generate_subject_matter(matter_id, top_chunks)` - GPT-4 summary of subject
  - [x] 2.6 Implement `get_current_status(matter_id)` - find most recent order from events or documents
  - [x] 2.7 Implement `get_key_issues(matter_id, top_chunks)` - GPT-4 extraction of key legal issues
  - [x] 2.8 Implement Redis caching with 1-hour TTL
  - [x] 2.9 Apply language policing to all GPT-4 generated content

- [x] **Task 3: Create API Route** (AC: #1)
  - [x] 3.1 Create `backend/app/api/routes/summary.py` with GET endpoint
  - [x] 3.2 Add matter access validation via `require_matter_role` dependency
  - [x] 3.3 Add optional `force_refresh` query parameter to bypass cache
  - [x] 3.4 Register route in `backend/app/main.py`

- [x] **Task 4: Create GPT-4 prompts for summary generation** (AC: #3)
  - [x] 4.1 Create `backend/app/engines/summary/prompts.py` with prompts for:
    - Subject matter generation prompt
    - Key issues extraction prompt
    - Current status summarization prompt
  - [x] 4.2 Include example outputs in prompts for consistency
  - [x] 4.3 Add language policing instructions to prompts

- [x] **Task 5: Wire frontend to real API** (AC: #1, #2)
  - [x] 5.1 Update `frontend/src/hooks/useMatterSummary.ts` to call real API
  - [x] 5.2 Replace `mockFetcher` with `summaryFetcher` using API client
  - [x] 5.3 Handle error states (404, 401, 500) with ApiError
  - [x] 5.4 Add `forceRefresh` parameter support and `refresh()` function

- [x] **Task 6: Write tests** (AC: all)
  - [x] 6.1 Unit tests for `SummaryService` methods (18 tests)
  - [x] 6.2 Integration tests for GET `/api/matters/{matter_id}/summary` (16 tests)
  - [x] 6.3 Test Redis caching behavior (cache hit, cache miss, force refresh)
  - [x] 6.4 Test matter access control (401 for unauthenticated)
  - [x] 6.5 Test with mock GPT-4 responses (no real API calls in tests)

## Dev Notes

### FR Reference (from MVP Gap Analysis)

> **FR19: Summary Tab** - Display attention banner at top (items needing action: contradictions, citation issues with count and "Review All" link), show Parties section with Petitioner and Respondent cards including entity links and source citations, display Subject Matter with description and source links, show Current Status with last order date, description, and "View Full Order" link, display Key Issues numbered list with verification status badges (Verified/Pending/Flagged), show Matter Statistics cards (pages, entities, events, citations)...

### Architecture Compliance

**LLM Routing (ADR-002 - CRITICAL):**
- Use **GPT-4** for summary generation (reasoning task, user-facing, accuracy critical)
- Do NOT use Gemini for user-facing summaries (higher hallucination rate)
- Apply language policing to sanitize legal conclusions from all outputs

**API Response Format (MANDATORY):**
```python
# Success response
{
  "data": {
    "matterId": "uuid",
    "attentionItems": [...],
    "parties": [...],
    ...
  }
}

# Error response
{
  "error": {
    "code": "MATTER_NOT_FOUND",
    "message": "Matter with ID xyz not found",
    "details": {}
  }
}
```

**Matter Isolation (CRITICAL):**
- Always validate matter access via `require_matter_role` dependency
- Never return data from matters the user doesn't have access to
- Use RLS-enabled Supabase client for all database queries

### Database Tables Used

| Table | Purpose | Query |
|-------|---------|-------|
| `documents` | Total pages | `SELECT SUM(page_count) WHERE matter_id = ?` |
| `identity_nodes` | Entities found | `SELECT COUNT(*) WHERE matter_id = ?` |
| `entity_mentions` | Party identification | `WHERE role IN ('petitioner', 'respondent')` |
| `events` | Events extracted | `SELECT COUNT(*) WHERE matter_id = ?` |
| `citations` | Citations found | `SELECT COUNT(*) WHERE matter_id = ?` |
| `statement_comparisons` | Contradictions | `SELECT COUNT(*) WHERE matter_id = ? AND classification IS NOT NULL` |
| `anomalies` | Timeline gaps | `SELECT COUNT(*) WHERE matter_id = ?` |
| `finding_verifications` | Verification % | `SELECT COUNT(*) WHERE decision = 'approved' / total` |

### Redis Cache Pattern

```python
from app.services.memory.redis_client import get_redis_client
from app.services.memory.redis_keys import summary_cache_key

SUMMARY_CACHE_TTL = 3600  # 1 hour

async def get_cached_summary(matter_id: str) -> MatterSummary | None:
    redis = get_redis_client()
    cached = await redis.get(summary_cache_key(matter_id))
    if cached:
        return MatterSummary.model_validate_json(cached)
    return None

async def cache_summary(matter_id: str, summary: MatterSummary) -> None:
    redis = get_redis_client()
    await redis.setex(
        summary_cache_key(matter_id),
        SUMMARY_CACHE_TTL,
        summary.model_dump_json()
    )
```

### Frontend TypeScript Interface (Source of Truth)

Location: `frontend/src/types/summary.ts`

```typescript
export interface MatterSummary {
  matterId: string;
  attentionItems: AttentionItem[];
  parties: PartyInfo[];
  subjectMatter: SubjectMatter;
  currentStatus: CurrentStatus;
  keyIssues: KeyIssue[];
  stats: MatterStats;
  generatedAt: string;
}

export interface AttentionItem {
  type: 'contradiction' | 'citation_issue' | 'timeline_gap';
  count: number;
  label: string;
  targetTab: string;
}

export interface PartyInfo {
  entityId: string;
  entityName: string;
  role: 'petitioner' | 'respondent' | 'other';
  sourceDocument: string;
  sourcePage: number;
  isVerified: boolean;
}

export interface SubjectMatter {
  description: string;
  sources: SubjectMatterSource[];
  isVerified: boolean;
}

export interface CurrentStatus {
  lastOrderDate: string;
  description: string;
  sourceDocument: string;
  sourcePage: number;
  isVerified: boolean;
}

export interface KeyIssue {
  id: string;
  number: number;
  title: string;
  verificationStatus: 'verified' | 'pending' | 'flagged';
}

export interface MatterStats {
  totalPages: number;
  entitiesFound: number;
  eventsExtracted: number;
  citationsFound: number;
  verificationPercent: number;
}
```

### Project Structure Notes

**New files to create:**
- `backend/app/models/summary.py` - Pydantic models
- `backend/app/services/summary_service.py` - Business logic
- `backend/app/api/routes/summary.py` - API endpoint
- `backend/app/engines/summary/prompts.py` - GPT-4 prompts (optional: could inline)
- `backend/tests/api/test_summary.py` - API tests
- `backend/tests/services/test_summary_service.py` - Service tests

**Files to modify:**
- `frontend/src/hooks/useMatterSummary.ts` - Replace mock with real API
- `backend/app/api/routes/__init__.py` - Register summary router
- `backend/app/services/memory/redis_keys.py` - Add `summary_cache_key` function

### References

- [Source: _bmad-output/implementation-artifacts/mvp-gap-analysis-2026-01-16.md#GAP-API-1]
- [Source: frontend/src/types/summary.ts] - TypeScript interface (lines 1-216)
- [Source: frontend/src/hooks/useMatterSummary.ts] - Mock data structure (lines 14-99)
- [Source: architecture.md#LLM-Routing] - GPT-4 for reasoning/user-facing tasks
- [Source: project-context.md#LLM-Routing] - Never use Gemini for user-facing answers

### Previous Story Context

**Story 10B.1** (Summary Tab Content) implemented:
- All frontend components (SummaryContent, PartiesSection, etc.)
- TypeScript types in `types/summary.ts`
- Mock data hook in `useMatterSummary.ts`
- 98 component tests

**Story 10B.2** (Summary Verification) implemented:
- Inline verification buttons
- Verification badge component
- Notes dialog
- useSummaryVerification hook (local state only)

This story (14.1) completes the Summary Tab by implementing the backend API that the frontend is waiting for.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - all tests passing.

### Completion Notes List

1. Created backend Pydantic models in `backend/app/models/summary.py` matching frontend TypeScript interface exactly with camelCase field aliases
2. Created Summary Service in `backend/app/services/summary_service.py` with:
   - Stats computation from documents, entities, events, citations tables
   - Attention items computed from statement_comparisons, citations, anomalies tables
   - Parties extraction from entity_mentions + identity_nodes with role sorting
   - GPT-4 integration for subject matter, key issues, and current status
   - Redis caching with 1-hour TTL
   - Language policing on all GPT-4 outputs
3. Created API route in `backend/app/api/routes/summary.py` with:
   - GET /api/matters/{matter_id}/summary endpoint
   - Matter access validation via validate_matter_access dependency
   - Optional forceRefresh query parameter
   - Proper error handling for service and unexpected errors
4. Created GPT-4 prompts in `backend/app/engines/summary/prompts.py` with:
   - Subject matter generation prompt with language policing rules
   - Key issues extraction prompt framing issues as questions
   - Current status summarization prompt with source citations
5. Updated frontend hook in `frontend/src/hooks/useMatterSummary.ts`:
   - Replaced mock fetcher with real API call using api.get
   - Added error handling with ApiError type
   - Added forceRefresh option and refresh() function
6. Added summary_cache_key function to redis_keys.py with UUID validation
7. Wrote 34 tests total (16 API route tests + 18 service tests) all passing

### File List

**New Files Created:**
- backend/app/models/summary.py
- backend/app/services/summary_service.py
- backend/app/api/routes/summary.py
- backend/app/engines/summary/__init__.py
- backend/app/engines/summary/prompts.py
- backend/tests/api/routes/test_summary.py
- backend/tests/services/test_summary_service.py

**Files Modified:**
- backend/app/main.py (added summary router import and registration)
- backend/app/services/memory/redis_keys.py (added summary_cache_key function)
- frontend/src/hooks/useMatterSummary.ts (replaced mock with real API)
