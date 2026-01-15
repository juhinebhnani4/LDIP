# Story 14.2: Contradictions List API Endpoint

Status: review-passed

## Story

As a **legal attorney using LDIP**,
I want **to retrieve ALL contradictions for a matter in a single API call**,
so that **I can view the Contradictions Tab with all entity-based conflicts grouped by entity, without needing to query each entity individually**.

## Acceptance Criteria

1. **AC1: GET /api/matters/{matter_id}/contradictions endpoint exists**
   - Returns HTTP 200 with paginated contradictions list
   - Returns HTTP 404 if matter not found or user lacks access
   - Returns HTTP 401 if user not authenticated
   - Validates matter access via RLS (user must be matter member)

2. **AC2: Response structure matches FR23 requirements**
   - Contradictions grouped by entity (canonical_name header, contradiction cards below)
   - Each contradiction includes:
     - `contradictionType`: badge (semantic/factual/date_mismatch/amount_mismatch)
     - `severity`: indicator (high/medium/low)
     - `entityId` and `entityName`: canonical entity info
     - Statement 1: document + page + excerpt + date
     - Statement 2: document + page + excerpt + date
     - `explanation`: natural language explanation
     - `evidenceLinks`: click to view in PDF (document_id, page, bbox_ids)
   - Meta includes pagination info (total, page, perPage, totalPages)

3. **AC3: Filtering support for attorney workflow**
   - `severity`: Filter by HIGH/MEDIUM/LOW
   - `contradictionType`: Filter by semantic_contradiction/factual_contradiction/date_mismatch/amount_mismatch
   - `entityId`: Filter to specific entity
   - `documentId`: Filter by source document

4. **AC4: Pagination with configurable page size**
   - Default `page=1`, `perPage=20`
   - Maximum `perPage=100`
   - Return actual total count for UI pagination

5. **AC5: Data sourced from statement_comparisons table**
   - Query `statement_comparisons` WHERE `result = 'contradiction'`
   - Join with `identity_nodes` for entity canonical_name
   - Join with `chunks` for statement content and page numbers
   - Join with `documents` for document names

6. **AC6: Sort options for attorney prioritization**
   - Default sort: severity DESC (HIGH first), then created_at DESC
   - Optional `sortBy`: severity, createdAt, entityName
   - Optional `sortOrder`: asc, desc

## Tasks / Subtasks

- [x] **Task 1: Create backend Pydantic response models** (AC: #2) ✅
  - [x] 1.1 Create `backend/app/models/contradiction_list.py` with:
    - `StatementInfo`: documentId, documentName, page, excerpt, date (nullable)
    - `ContradictionItem`: contradictionType, severity, entityId, entityName, statementA, statementB, explanation, evidenceLinks, confidence, createdAt
    - `EntityContradictions`: entityId, entityName, contradictions list, count
    - `ContradictionsListResponse`: data (list of EntityContradictions), meta (pagination)
  - [x] 1.2 Use camelCase aliases to match frontend TypeScript conventions

- [x] **Task 2: Create Contradictions List Service** (AC: #5) ✅
  - [x] 2.1 Create `backend/app/services/contradiction_list_service.py`
  - [x] 2.2 Implement `get_all_contradictions(matter_id, filters, pagination, sort)`
  - [x] 2.3 Query statement_comparisons with result='contradiction'
  - [x] 2.4 Join identity_nodes for entity names
  - [x] 2.5 Join chunks (via statement_a_id/statement_b_id) for content and page
  - [x] 2.6 Join documents for document names
  - [x] 2.7 Group results by entity_id (canonical_name header)
  - [x] 2.8 Apply filters (severity, contradictionType, entityId, documentId)
  - [x] 2.9 Apply sorting (default: severity DESC, created_at DESC)
  - [x] 2.10 Apply pagination with total count

- [x] **Task 3: Create API Route** (AC: #1, #3, #4, #6) ✅
  - [x] 3.1 Add GET endpoint to `backend/app/api/routes/contradiction.py`
  - [x] 3.2 Path: `/api/matters/{matter_id}/contradictions` (at matter level, not entity level)
  - [x] 3.3 Add matter access validation via `require_matter_role` dependency
  - [x] 3.4 Add query parameters: severity, contradictionType, entityId, documentId, page, perPage, sortBy, sortOrder
  - [x] 3.5 Return ContradictionsListResponse with data and meta

- [x] **Task 4: Write tests** (AC: all) ✅
  - [x] 4.1 Create `backend/tests/api/routes/test_contradiction_list.py`
  - [x] 4.2 Test successful response with mock data
  - [x] 4.3 Test filtering by severity (HIGH only)
  - [x] 4.4 Test filtering by contradiction type (date_mismatch)
  - [x] 4.5 Test filtering by entity ID
  - [x] 4.6 Test pagination (page 2 with perPage=10)
  - [x] 4.7 Test sorting by severity DESC
  - [x] 4.8 Test sorting by createdAt ASC
  - [x] 4.9 Test 404 for non-existent matter
  - [x] 4.10 Test 401 for unauthenticated request
  - [x] 4.11 Test empty result (no contradictions) returns empty list, not error
  - [x] 4.12 Create `backend/tests/services/test_contradiction_list_service.py`
  - [x] 4.13 Test service methods with mocked Supabase client

## Dev Notes

### FR Reference (from MVP Gap Analysis)

> **FR3: Consistency & Contradiction Engine** - Query all chunks mentioning a canonical entity_id from MIG, group statements by entity (e.g., "Nirav Jobalia" = "N.D. Jobalia" = "Mr. Jobalia"), compare statement pairs using GPT-4 chain-of-thought reasoning, detect contradiction types: semantic_contradiction, factual_contradiction, date_mismatch, amount_mismatch, provide contradiction_explanation in natural language, assign severity (high/medium/low)...

> **FR23: Contradictions Tab** - Display contradictions grouped by entity (canonical name header, contradiction cards below), show contradiction cards with: contradiction type badge (semantic/factual/date_mismatch/amount_mismatch), severity indicator (high/medium/low), entity name, Statement 1 with document+page+excerpt+date, Statement 2 with document+page+excerpt+date, contradiction explanation in natural language, evidence links (click to view in PDF), implement inline verification on each contradiction...

### Architecture Compliance

**API Response Format (MANDATORY):**
```python
# Success response - list with pagination
{
  "data": [
    {
      "entityId": "uuid",
      "entityName": "Nirav Jobalia",
      "contradictions": [...],
      "count": 3
    }
  ],
  "meta": {
    "total": 45,
    "page": 1,
    "perPage": 20,
    "totalPages": 3
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
- statement_comparisons table has RLS enabled - queries automatically scoped by matter
- Never return data from matters the user doesn't have access to

**LLM Routing:** N/A - This is a database query endpoint, no LLM calls required.

### Database Schema Reference

**statement_comparisons table columns used:**
```sql
id                  UUID          -- Primary key
matter_id           UUID          -- Foreign key to matters (RLS scope)
entity_id           UUID          -- Entity the statements are about
statement_a_id      UUID          -- References chunks.chunk_id
statement_b_id      UUID          -- References chunks.chunk_id
result              VARCHAR(20)   -- 'contradiction' (we filter on this)
confidence          NUMERIC(3,2)  -- 0-1 confidence score
reasoning           TEXT          -- GPT-4 chain-of-thought
evidence            JSONB         -- {type, value_a, value_b, page_refs}
contradiction_type  VARCHAR(30)   -- semantic_contradiction/factual_contradiction/date_mismatch/amount_mismatch
severity            VARCHAR(10)   -- high/medium/low
explanation         TEXT          -- Attorney-ready explanation
created_at          TIMESTAMPTZ   -- For sorting
```

**Required JOINs:**
```sql
-- Get entity name
identity_nodes.canonical_name WHERE identity_nodes.id = statement_comparisons.entity_id

-- Get statement A content and page
chunks.content, chunks.page_number WHERE chunks.chunk_id = statement_comparisons.statement_a_id

-- Get statement B content and page
chunks.content, chunks.page_number WHERE chunks.chunk_id = statement_comparisons.statement_b_id

-- Get document names
documents.filename WHERE documents.id = chunks.document_id
```

### SQL Query Pattern

```sql
SELECT
  sc.id,
  sc.entity_id,
  sc.contradiction_type,
  sc.severity,
  sc.explanation,
  sc.confidence,
  sc.evidence,
  sc.created_at,
  in_node.canonical_name as entity_name,
  chunk_a.content as statement_a_content,
  chunk_a.page_number as statement_a_page,
  doc_a.id as document_a_id,
  doc_a.filename as document_a_name,
  chunk_b.content as statement_b_content,
  chunk_b.page_number as statement_b_page,
  doc_b.id as document_b_id,
  doc_b.filename as document_b_name
FROM statement_comparisons sc
JOIN identity_nodes in_node ON sc.entity_id = in_node.id
JOIN chunks chunk_a ON sc.statement_a_id = chunk_a.chunk_id
JOIN chunks chunk_b ON sc.statement_b_id = chunk_b.chunk_id
JOIN documents doc_a ON chunk_a.document_id = doc_a.id
JOIN documents doc_b ON chunk_b.document_id = doc_b.id
WHERE sc.matter_id = :matter_id
  AND sc.result = 'contradiction'
  -- Optional filters
  AND (:severity IS NULL OR sc.severity = :severity)
  AND (:type IS NULL OR sc.contradiction_type = :type)
  AND (:entity_id IS NULL OR sc.entity_id = :entity_id)
ORDER BY
  CASE sc.severity
    WHEN 'high' THEN 1
    WHEN 'medium' THEN 2
    WHEN 'low' THEN 3
  END,
  sc.created_at DESC
LIMIT :per_page OFFSET :offset
```

### Existing Code Patterns to Follow

**Route location:** Add to `backend/app/api/routes/contradiction.py` (existing file)

**Existing endpoints in same file:**
- `GET /matters/{matter_id}/contradictions/entities/{entity_id}/statements`
- `POST /matters/{matter_id}/contradictions/entities/{entity_id}/compare`

**New endpoint pattern:** `GET /matters/{matter_id}/contradictions` (at matter level)

**Service pattern from summary_service.py:**
```python
class ContradictionListService:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    async def get_all_contradictions(
        self,
        matter_id: str,
        severity: str | None = None,
        contradiction_type: str | None = None,
        entity_id: str | None = None,
        document_id: str | None = None,
        page: int = 1,
        per_page: int = 20,
        sort_by: str = "severity",
        sort_order: str = "desc"
    ) -> ContradictionsListResponse:
        ...
```

**Dependency injection pattern:**
```python
def get_contradiction_list_service() -> ContradictionListService:
    from app.core.supabase import get_supabase_client
    return ContradictionListService(get_supabase_client())
```

### Project Structure Notes

**Files to create:**
- `backend/app/models/contradiction_list.py` - Response models
- `backend/app/services/contradiction_list_service.py` - Business logic
- `backend/tests/api/routes/test_contradiction_list.py` - API tests
- `backend/tests/services/test_contradiction_list_service.py` - Service tests

**Files to modify:**
- `backend/app/api/routes/contradiction.py` - Add new GET endpoint at matter level

### Previous Story Intelligence (Story 14.1)

**Learnings from 14-1-summary-api-endpoint:**
1. Use camelCase aliases in Pydantic models with `model_config = ConfigDict(populate_by_name=True)`
2. Follow `{ data: ..., meta: ... }` response wrapper pattern
3. Wrap service calls in try/except with proper error response format
4. Use structlog for logging with context (matter_id, user_id)
5. Test both happy path and error cases (404, 401)
6. Mock Supabase client in service tests using pytest fixtures

**Code review fixes applied in 14.1 to avoid:**
1. Use correct case for enum values in queries (e.g., `"verified"` not `"VERIFIED"`)
2. Extract hardcoded limits to named constants
3. Include cache invalidation if applicable (not needed for this read-only endpoint)

### TypeScript Interface (Frontend Reference)

The frontend will expect this structure (to be created in a future story):

```typescript
interface ContradictionItem {
  id: string;
  contradictionType: 'semantic_contradiction' | 'factual_contradiction' | 'date_mismatch' | 'amount_mismatch';
  severity: 'high' | 'medium' | 'low';
  entityId: string;
  entityName: string;
  statementA: {
    documentId: string;
    documentName: string;
    page: number | null;
    excerpt: string;
    date: string | null;
  };
  statementB: {
    documentId: string;
    documentName: string;
    page: number | null;
    excerpt: string;
    date: string | null;
  };
  explanation: string;
  evidenceLinks: {
    statementId: string;
    documentId: string;
    documentName: string;
    page: number | null;
    bboxIds: string[];
  }[];
  confidence: number;
  createdAt: string;
}

interface EntityContradictions {
  entityId: string;
  entityName: string;
  contradictions: ContradictionItem[];
  count: number;
}

interface ContradictionsListResponse {
  data: EntityContradictions[];
  meta: {
    total: number;
    page: number;
    perPage: number;
    totalPages: number;
  };
}
```

### Constants to Define

```python
# In contradiction_list_service.py
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAX_EXCERPT_LENGTH = 200  # Truncate statement content for response
```

### References

- [Source: _bmad-output/implementation-artifacts/mvp-gap-analysis-2026-01-16.md#GAP-API-2]
- [Source: backend/app/api/routes/contradiction.py] - Existing entity-specific endpoints
- [Source: backend/app/models/contradiction.py] - Existing models (ScoredContradiction, EvidenceLink)
- [Source: supabase/migrations/20260114000004_create_statement_comparisons_table.sql] - Table schema
- [Source: supabase/migrations/20260114000005_add_contradiction_classification.sql] - Type column
- [Source: supabase/migrations/20260114000006_add_severity_scoring.sql] - Severity column
- [Source: project-context.md#API-Response-Format] - { data, meta } wrapper requirement

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

1. **Task 1 Complete:** Created `backend/app/models/contradiction_list.py` with all required Pydantic models:
   - `StatementInfo` - document/page/excerpt info
   - `ContradictionEvidenceLink` - PDF navigation links
   - `ContradictionItem` - full contradiction details
   - `EntityContradictions` - contradictions grouped by entity
   - `ContradictionsListResponse` - paginated response wrapper
   - All models use camelCase aliases via `ConfigDict(populate_by_name=True)`

2. **Task 2 Complete:** Created `backend/app/services/contradiction_list_service.py`:
   - `ContradictionListService` class with Supabase integration
   - `get_all_contradictions()` method with filters, pagination, and sorting
   - Entity grouping logic with `_group_by_entity()`
   - Excerpt truncation with `_truncate_excerpt()`
   - Type-safe parsing of contradiction types and severity
   - Proper error handling with `ContradictionListServiceError`

3. **Task 3 Complete:** Added GET endpoint to `backend/app/api/routes/contradiction.py`:
   - Path: `GET /api/matters/{matter_id}/contradictions`
   - All query parameters: severity, contradictionType, entityId, documentId, page, perPage, sortBy, sortOrder
   - Matter access validation via `require_matter_role`
   - Proper error handling with structured error responses

4. **Task 4 Complete:** Created comprehensive test suites:
   - `backend/tests/api/routes/test_contradiction_list.py` (20 tests)
   - `backend/tests/services/test_contradiction_list_service.py` (16 tests)
   - All 36 new tests pass
   - Full backend suite: 2175 tests pass, 0 failures

### File List

**Files Created:**
- `backend/app/models/contradiction_list.py`
- `backend/app/services/contradiction_list_service.py`
- `backend/tests/api/routes/test_contradiction_list.py`
- `backend/tests/services/test_contradiction_list_service.py`

**Files Modified:**
- `backend/app/api/routes/contradiction.py` - Added new GET endpoint and imports
