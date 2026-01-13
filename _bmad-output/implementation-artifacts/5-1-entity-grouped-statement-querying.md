# Story 5.1: Implement Entity-Grouped Statement Querying

Status: complete

## Story

As an **attorney**,
I want **all statements about an entity grouped together**,
So that **I can compare what different documents say about the same person or organization**.

## Acceptance Criteria

1. **Given** an entity exists in the MIG
   **When** I request statements about that entity
   **Then** all chunks mentioning the entity's canonical_id or aliases are retrieved
   **And** statements are grouped by document source

2. **Given** an entity has multiple aliases
   **When** statement querying runs
   **Then** mentions of any alias are included
   **And** all are attributed to the canonical entity

3. **Given** a statement mentions dates or amounts related to an entity
   **When** it is retrieved
   **Then** the specific values are extracted and structured
   **And** they can be compared across statements

4. **Given** no statements exist for an entity
   **When** querying runs
   **Then** an empty result is returned
   **And** no error occurs

## Tasks / Subtasks

- [x] Task 1: Create statement querying models (AC: #1, #3)
  - [x] 1.1: Create `Statement` Pydantic model with entity_id, chunk_id, document_id, content, dates, amounts, page_number, confidence
  - [x] 1.2: Create `EntityStatements` response model grouping statements by document
  - [x] 1.3: Create `StatementValue` model for extracted dates/amounts with type (DATE, AMOUNT, QUANTITY)
  - [x] 1.4: Add models to `backend/app/models/contradiction.py`

- [x] Task 2: Implement statement query service (AC: #1, #2, #4)
  - [x] 2.1: Create `StatementQueryService` in `backend/app/services/contradiction/statement_query.py`
  - [x] 2.2: Implement `get_statements_for_entity()` - retrieve chunks by entity_id using chunks.entity_ids array
  - [x] 2.3: Implement `get_statements_for_canonical_entity()` - include aliases via EntityResolver
  - [x] 2.4: Implement `get_all_aliases_for_entity()` helper using MIGGraphService
  - [x] 2.5: Add matter_id validation for 4-layer isolation (CRITICAL)

- [x] Task 3: Implement value extraction (AC: #3)
  - [x] 3.1: Create `ValueExtractor` class for extracting dates/amounts from statement text
  - [x] 3.2: Implement date extraction supporting Indian formats (DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, legal format)
  - [x] 3.3: Implement amount extraction (rupees, lakhs, crores, USD, percentages)
  - [x] 3.4: Use regex patterns (NOT LLM) per cost optimization rules - rule-based is sufficient
  - [x] 3.5: Store extracted values in `StatementValue` objects

- [x] Task 4: Create API endpoints (AC: #1, #2, #4)
  - [x] 4.1: Create `backend/app/api/routes/contradiction.py` router
  - [x] 4.2: Implement `GET /api/matters/{matter_id}/contradictions/entities/{entity_id}/statements` endpoint
  - [x] 4.3: Add query params: include_aliases (bool), document_ids (list[uuid]), page, per_page
  - [x] 4.4: Return `{ data: EntityStatements, meta: PaginationMeta }` response format
  - [x] 4.5: Register router in main.py

- [x] Task 5: Write comprehensive tests (AC: #1, #2, #3, #4)
  - [x] 5.1: Unit tests for `StatementQueryService` (mock Supabase)
  - [x] 5.2: Unit tests for `ValueExtractor` (date/amount patterns)
  - [x] 5.3: API route tests with httpx.AsyncClient
  - [x] 5.4: Test empty results scenario
  - [x] 5.5: Test alias resolution integration
  - [x] 5.6: Test matter isolation (CRITICAL - security test)

## Dev Notes

### Architecture Compliance

This story implements the first stage of the **Contradiction Engine** (Epic 5) pipeline:
```
STATEMENT QUERYING (5-1) → PAIR COMPARISON (5-2) → CLASSIFICATION (5-3) → SCORING (5-4)
```

Follow the 4-stage pipeline pattern established in Epic 3 (Citation) and Epic 4 (Timeline).

### Critical Implementation Details

1. **Entity Resolution via MIG**
   - Use existing `EntityResolver` from `app/services/mig/entity_resolver.py` for alias matching
   - Use `MIGGraphService.get_all_aliases()` to retrieve linked aliases
   - Entity lookup uses `canonical_entity_id` from `identity_nodes` table
   - Confidence threshold for alias matching: 0.7 (per existing code)

2. **Statement Retrieval via Chunks**
   - Chunks table has `entity_ids uuid[]` column with GIN index (`idx_chunks_entities`)
   - Query pattern: `WHERE :entity_id = ANY(entity_ids) AND matter_id = :matter_id`
   - Include parent chunks for context (chunk_type = 'parent')
   - Return child chunks for precision (chunk_type = 'child')

3. **4-Layer Matter Isolation (CRITICAL)**
   - Layer 1 (RLS): Chunks table has RLS policies enforced
   - Layer 2 (Vector namespace): Not used in this story (no embedding search)
   - Layer 3 (Redis): Not used in this story (no caching yet)
   - Layer 4 (API middleware): Validate matter_id on every request

4. **Date/Amount Extraction Patterns**
   - Use regex-based extraction (NOT Gemini) per cost optimization rules
   - Indian date formats: `DD/MM/YYYY`, `DD-MM-YYYY`, `DD.MM.YYYY`, `"dated X of Y, 20XX"`
   - Indian amounts: `Rs. X`, `X lakhs`, `X crores`, `X rupees`
   - Amounts with variations: `1,00,000` (Indian comma style), `100000`, `1 lakh`

### LLM Routing Rules (CRITICAL)

**DO NOT USE LLM** for this story. Statement querying and value extraction are:
- Pattern matching tasks (regex is sufficient)
- Verifiable downstream in Story 5-2
- Cost-sensitive (would be 30x more expensive with GPT-4)

The LLM will be used in Story 5-2 for semantic comparison, which is a reasoning task.

### Existing Code to Reuse

| Component | Location | Purpose |
|-----------|----------|---------|
| `EntityResolver` | `app/services/mig/entity_resolver.py` | Alias resolution, name similarity |
| `MIGGraphService` | `app/services/mig/graph.py` | Entity CRUD, alias edge queries |
| `EntityNode` model | `app/models/entity.py` | Entity data structure |
| `chunks` table | `supabase/migrations/20260106000002_create_chunks_table.sql` | Statement storage |
| `entity_mentions` table | `supabase/migrations/20260112000001_create_entity_mentions_table.sql` | Mention locations |

### File Structure for Contradiction Engine

Create the following structure (mirror Timeline engine pattern):

```
backend/app/
├── engines/
│   └── contradiction/          # NEW - Epic 5
│       ├── __init__.py
│       ├── statement_query.py  # Story 5-1 (this story)
│       ├── comparator.py       # Story 5-2
│       ├── classifier.py       # Story 5-3
│       ├── scorer.py           # Story 5-4
│       └── prompts.py          # LLM prompts (Story 5-2+)
├── models/
│   └── contradiction.py        # NEW - Contradiction models
├── services/
│   └── contradiction/          # NEW - Contradiction services
│       ├── __init__.py
│       └── statement_query.py  # Service layer
└── api/
    └── routes/
        └── contradiction.py    # NEW - API routes
```

### Testing Requirements

Per project-context.md:
- Backend: `tests/` directory with `api/`, `engines/`, `services/`, `security/`
- Use pytest-asyncio for async tests
- Use httpx.AsyncClient for API testing
- Mock Supabase client (never call real DB in tests)
- **CRITICAL**: Include matter isolation test in `tests/security/test_cross_matter_isolation.py`

### Project Structure Notes

- Follows backend structure from architecture.md: domain-driven with engines/, services/, api/ separation
- Contradiction engine goes in `engines/contradiction/` (not services)
- Models in `models/contradiction.py`
- API routes in `api/routes/contradiction.py`

### Previous Epic Learnings (from Epic 3-4 Retrospective)

1. **Rule-based extraction saves cost** - Anomaly detection used rules, not LLM. Same applies here for date/amount extraction.
2. **Reuse EntityResolver** - Successfully used in Timeline engine for entity linking.
3. **Pipeline stages should be independent** - Each stage testable without full pipeline integration.
4. **Indian formats matter** - Date formats (DD/MM/YYYY), legal terminology require explicit handling.

### References

- [Architecture: Contradiction Engine](../_bmad-output/architecture.md) - ADR-003: Why 3 MVP Engines
- [MIG Entity Resolver](../backend/app/services/mig/entity_resolver.py) - Alias resolution logic
- [Chunks Table Schema](../supabase/migrations/20260106000002_create_chunks_table.sql) - entity_ids column
- [Epic 3-4 Retrospective](../_bmad-output/implementation-artifacts/epic-3-4-retro-2026-01-14.md) - Lessons learned
- [Project Context](../_bmad-output/project-context.md) - Implementation rules

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

- Implemented StatementQueryEngine with ValueExtractor for regex-based date/amount extraction
- Created Pydantic models in `contradiction.py` with proper camelCase serialization
- Service layer validates matter_id before any DB queries (Layer 4 isolation)
- API endpoint follows existing patterns from entities.py route
- 39 tests pass covering value extraction, service logic, API routes, and security isolation
- Used GIN-indexed `entity_ids` array for efficient chunk queries with `overlaps` operator for alias matching

### Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.5
**Date:** 2026-01-14
**Verdict:** PASS

#### Summary

Story 5-1 implementation is complete and follows all architectural patterns and security requirements.

#### Checklist

- [x] All acceptance criteria met
- [x] 4-layer matter isolation enforced
- [x] No LLM used (regex-based extraction per cost optimization)
- [x] Follows existing engine/service/route patterns
- [x] Tests cover all scenarios including security
- [x] Indian date/amount formats supported

#### Files Changed

| File | Change Type | Lines |
|------|-------------|-------|
| backend/app/models/contradiction.py | Added | ~175 |
| backend/app/engines/contradiction/__init__.py | Added | ~20 |
| backend/app/engines/contradiction/statement_query.py | Added | ~380 |
| backend/app/services/contradiction/__init__.py | Added | ~10 |
| backend/app/services/contradiction/statement_query.py | Added | ~140 |
| backend/app/api/routes/contradiction.py | Added | ~130 |
| backend/app/main.py | Modified | +2 |
| tests/engines/contradiction/__init__.py | Added | ~3 |
| tests/engines/contradiction/test_statement_query.py | Added | ~290 |
| tests/services/contradiction/__init__.py | Added | ~3 |
| tests/services/contradiction/test_statement_query.py | Added | ~165 |
| tests/api/routes/test_contradiction.py | Added | ~195 |
| tests/security/test_contradiction_isolation.py | Added | ~120 |

## File List

**Files Created:**
- `backend/app/engines/contradiction/__init__.py`
- `backend/app/engines/contradiction/statement_query.py`
- `backend/app/models/contradiction.py`
- `backend/app/services/contradiction/__init__.py`
- `backend/app/services/contradiction/statement_query.py`
- `backend/app/api/routes/contradiction.py`
- `backend/tests/engines/contradiction/__init__.py`
- `backend/tests/engines/contradiction/test_statement_query.py`
- `backend/tests/services/contradiction/__init__.py`
- `backend/tests/services/contradiction/test_statement_query.py`
- `backend/tests/api/routes/test_contradiction.py`
- `backend/tests/security/test_contradiction_isolation.py`

**Files Modified:**
- `backend/app/main.py` - Register contradiction router
