# Story 2C.1: Implement MIG Entity Extraction

Status: complete

## Story

As an **attorney**,
I want **people, organizations, and assets automatically extracted from documents**,
So that **I can see all parties and their relationships in my matter**.

## Acceptance Criteria

1. **Given** a document is processed **When** entity extraction runs via Gemini **Then** entities are extracted with types: PERSON, ORG, INSTITUTION, ASSET **And** each entity is stored in `identity_nodes` table

2. **Given** an entity is extracted **When** it is stored **Then** `identity_nodes` contains: entity_id, matter_id, canonical_name, entity_type, metadata (roles, aliases found, first_mention_doc)

3. **Given** relationships between entities are detected **When** they are stored **Then** `identity_edges` contains: source_entity_id, target_entity_id, relationship_type (ALIAS_OF, HAS_ROLE, RELATED_TO), confidence

4. **Given** an entity appears in multiple documents **When** extraction runs **Then** document references are stored in `entity_mentions` **And** mention count is tracked per entity

## Tasks / Subtasks

- [x] Task 1: Create Database Schema for MIG Tables (AC: #1, #2, #3)
  - [x] Create Supabase migration for `identity_nodes` table
    - Columns: `id` (UUID PK), `matter_id` (FK), `canonical_name` (text), `entity_type` (enum: PERSON, ORG, INSTITUTION, ASSET), `metadata` (JSONB), `mention_count` (int default 0), `created_at`, `updated_at`
    - Add GIN index on `metadata` for alias searching
    - Add composite index on `(matter_id, entity_type)` for filtering
  - [x] Create Supabase migration for `identity_edges` table
    - Columns: `id` (UUID PK), `matter_id` (FK), `source_entity_id` (FK), `target_entity_id` (FK), `relationship_type` (enum: ALIAS_OF, HAS_ROLE, RELATED_TO), `confidence` (float 0-1), `metadata` (JSONB), `created_at`
    - Add composite index on `(source_entity_id, relationship_type)`
    - Add index on `(matter_id, relationship_type)` for matter-wide queries
  - [x] Create Supabase migration for `entity_mentions` table
    - Columns: `id` (UUID PK), `entity_id` (FK), `document_id` (FK), `chunk_id` (FK nullable), `page_number` (int), `bbox_ids` (UUID array), `mention_text` (text), `context` (text), `confidence` (float), `created_at`
    - Add composite index on `(entity_id, document_id)`
    - Links entities to source locations for highlighting
  - [x] Implement RLS policies for all three tables (matter isolation)

- [x] Task 2: Create MIG Pydantic Models (AC: #1, #2, #3)
  - [x] Create `backend/app/models/entity.py`
    - Define `EntityType` enum: PERSON, ORG, INSTITUTION, ASSET
    - Define `RelationshipType` enum: ALIAS_OF, HAS_ROLE, RELATED_TO
    - Define `EntityNodeCreate` Pydantic model for insertion
    - Define `EntityNode` model for API responses
    - Define `EntityEdgeCreate` and `EntityEdge` models
    - Define `EntityMentionCreate` and `EntityMention` models
    - Define `EntityExtractionResult` for Gemini response parsing
  - [x] Update `backend/app/models/__init__.py` with exports

- [x] Task 3: Create Gemini Entity Extraction Prompt and Service (AC: #1, #4)
  - [x] Create `backend/app/services/mig/__init__.py`
  - [x] Create `backend/app/services/mig/extractor.py`
    - Implement `MIGEntityExtractor` class
    - Method: `extract_entities(text: str, document_id: str, matter_id: str) -> EntityExtractionResult`
    - Use Gemini 3 Flash (ingestion task per LLM routing rules)
    - Design prompt to extract: entity names, types, roles, relationships
    - Parse structured JSON response from Gemini
    - Handle edge cases: ambiguous names, titles vs names
  - [x] Create `backend/app/services/mig/prompts.py`
    - Define entity extraction prompt template
    - Include examples for each entity type
    - Request structured JSON output format

- [x] Task 4: Create MIG Graph Service (AC: #2, #3, #4)
  - [x] Create `backend/app/services/mig/graph.py`
    - Implement `MIGGraphService` class
    - Method: `save_entities(matter_id: str, extraction_result: EntityExtractionResult) -> list[EntityNode]`
    - Method: `save_edges(matter_id: str, edges: list[EntityEdgeCreate]) -> list[EntityEdge]`
    - Method: `save_mentions(entity_id: str, mentions: list[EntityMentionCreate]) -> list[EntityMention]`
    - Method: `get_entity(entity_id: str, matter_id: str) -> EntityNode | None`
    - Method: `get_entities_by_matter(matter_id: str, entity_type: EntityType | None = None) -> list[EntityNode]`
    - Method: `increment_mention_count(entity_id: str) -> None`
    - Implement deduplication: check if canonical_name+type already exists in matter
    - Use Supabase client with RLS enforcement

- [x] Task 5: Integrate Entity Extraction into Document Processing Pipeline (AC: #1, #4)
  - [x] Update `backend/app/workers/tasks/document_tasks.py`
    - Add `extract_entities_task` Celery task
    - Called after chunking completes
    - Process all chunks for a document, extract entities from each
    - Aggregate entities across chunks (deduplicate within document)
    - Save to MIG tables
  - [x] Update document processing orchestration
    - Chain: OCR -> chunking -> embedding -> entity extraction
    - Emit progress events for entity extraction stage
  - [x] Add structlog logging for entity extraction

- [x] Task 6: Create MIG API Endpoints (AC: #2, #3, #4)
  - [x] Create `backend/app/api/routes/entities.py`
    - `GET /api/matters/{matter_id}/entities` - List all entities in matter
      - Query params: `entity_type`, `page`, `per_page`
      - Response: paginated list with mention counts
    - `GET /api/matters/{matter_id}/entities/{entity_id}` - Get single entity with details
      - Include: aliases, relationships, mentions
    - `GET /api/matters/{matter_id}/entities/{entity_id}/mentions` - Get all mentions
      - Include: document info, page, bbox for highlighting
  - [x] Register routes in `backend/app/main.py`
  - [x] Add auth dependency (matter access validation)

- [x] Task 7: Create Frontend Types and API Client (AC: #2, #4)
  - [x] Create `frontend/src/types/entity.ts`
    - Define `EntityType` enum
    - Define `RelationshipType` enum
    - Define `Entity` interface with mention_count, aliases
    - Define `EntityMention` interface with document/page/bbox refs
    - Define `EntitiesResponse` paginated response type
  - [x] Create `frontend/src/lib/api/entities.ts`
    - `getEntities(matterId, options): Promise<EntitiesResponse>`
    - `getEntity(matterId, entityId): Promise<Entity>`
    - `getEntityMentions(matterId, entityId): Promise<EntityMention[]>`

- [x] Task 8: Write Backend Unit Tests
  - [x] Create `backend/tests/services/mig/test_extractor.py`
    - Test entity extraction from sample text
    - Test parsing of different entity types
    - Test handling of malformed Gemini responses
    - Mock Gemini API calls
  - [x] Create `backend/tests/services/mig/test_graph.py`
    - Test entity deduplication
    - Test edge creation
    - Test mention count increment
    - Test matter isolation
  - [x] Create `backend/tests/api/routes/test_entities.py`
    - Test list entities endpoint
    - Test single entity endpoint
    - Test mentions endpoint
    - Test authorization (matter membership)

- [x] Task 9: Write Integration Tests
  - [x] Create `backend/tests/integration/test_mig_integration.py`
    - Test full pipeline: document -> chunks -> entities -> MIG
    - Test entity deduplication across multiple documents
    - Test matter isolation (cross-matter entities should not leak)
    - Test entity mention linking to bbox

## Dev Notes

### CRITICAL: Existing Infrastructure to Use

**From Story 2b-5 (Chunking):**
- `ChunkingService` in `backend/app/services/rag/chunker.py` - Provides chunked text
- `Chunk` dataclass has: id, document_id, content, chunk_type, page_number, token_count
- Document processing pipeline in `backend/app/workers/tasks/document_tasks.py`
- Celery task orchestration pattern

**From Story 2b-4 (Bounding Boxes):**
- `bounding_boxes` table with page coordinates
- Can link entity mentions to bbox for highlighting
- `BoundingBox` model in `backend/app/models/bbox.py`

**Key integration point:** Entity extraction runs AFTER chunking, uses chunk content for extraction, and links mentions back to chunks/bboxes.

### Architecture Requirements (MANDATORY)

**From [architecture.md](../_bmad-output/architecture.md):**

#### MIG (Matter Identity Graph) Design
From architecture Project Structure section:
```
backend/app/services/mig/
├── __init__.py
├── graph.py              # Matter Intelligence Graph operations
├── entity_resolver.py    # Name variant resolution (Story 2C.2)
└── linker.py            # Entity-document linking
```

From architecture ADR-001:
> **PostgreSQL only (no Neo4j for MIG)** - simpler security, adequate for our query patterns.
> MIG queries are simple lookups ("Get all aliases for entity X"), not complex 6-hop graph traversals.

#### Database Schema (from architecture)
```sql
-- identity_nodes table
entity_id, matter_id, canonical_name, entity_type, metadata

-- identity_edges table
source_entity_id, target_entity_id, relationship_type, confidence
```

#### LLM Routing Rules (MUST FOLLOW)
```
| Task | Model | Rationale |
|------|-------|-----------|
| Entity extraction | Gemini 3 Flash | Pattern matching, verifiable downstream |
```

**CRITICAL:** Use Gemini for entity extraction - it's an ingestion task, NOT user-facing reasoning.

#### 4-Layer Matter Isolation (MUST IMPLEMENT)
```
Layer 1: RLS policies on identity_nodes, identity_edges, entity_mentions
Layer 2: N/A (no vectors in MIG)
Layer 3: N/A (no Redis caching for MIG)
Layer 4: API middleware validates matter access
```

### Entity Extraction Prompt Design

**System Prompt for Gemini:**
```
You are a legal document entity extractor. Extract all mentioned entities from the provided text.

ENTITY TYPES:
- PERSON: Individual people (parties, witnesses, attorneys, judges)
- ORG: Companies, corporations, partnerships, LLPs, trusts
- INSTITUTION: Government bodies, courts, tribunals, regulatory agencies
- ASSET: Properties, bank accounts, financial instruments, disputed items

OUTPUT FORMAT (JSON):
{
  "entities": [
    {
      "name": "Exact name as appears in text",
      "canonical_name": "Normalized form (e.g., 'Nirav D. Jobalia' -> 'Nirav Jobalia')",
      "type": "PERSON|ORG|INSTITUTION|ASSET",
      "roles": ["plaintiff", "defendant", "witness", etc.],
      "mentions": [
        {"text": "Mr. Jobalia", "context": "±50 chars around mention"}
      ]
    }
  ],
  "relationships": [
    {
      "source": "Entity Name 1",
      "target": "Entity Name 2",
      "type": "HAS_ROLE|RELATED_TO",
      "description": "Director of"
    }
  ]
}

RULES:
1. Extract ALL entity mentions, even duplicates with different forms
2. Include titles (Mr., Dr., Hon.) in mentions but normalize canonical_name without them
3. For ORG entities, include suffixes (Pvt. Ltd., LLP) in canonical_name
4. Mark confidence as "high" or "low" based on clarity
5. Extract relationships only when explicitly stated
```

### Deduplication Strategy

**Within Document:**
- Same canonical_name + type = same entity
- Collect all mention variants

**Across Documents (handled in Story 2C.2 - Alias Resolution):**
- This story only handles within-document deduplication
- Cross-document alias linking is Story 2C.2

### Previous Story Intelligence

**FROM Story 2b-7 (Cohere Rerank):**
- Pattern for adding new service to `services/` folder
- API endpoint pattern with proper response format
- Graceful fallback design when external API fails
- structlog logging patterns

**FROM Story 2b-5 (Chunking):**
- Celery task integration into document processing pipeline
- Task chaining pattern
- Progress event emission

**Key files to reference:**
- [backend/app/services/rag/reranker.py](backend/app/services/rag/reranker.py) - Service structure pattern
- [backend/app/workers/tasks/document_tasks.py](backend/app/workers/tasks/document_tasks.py) - Where to integrate
- [backend/app/services/llm/gemini.py](backend/app/services/llm/gemini.py) - Gemini client to use

### Git Intelligence

Recent commits:
```
2274652 fix(search): address code review issues for Story 2b-7
1c36bc0 feat(search): integrate Cohere Rerank v3.5 for improved search precision (Story 2b-7)
39cf4cc fix(search): address code review issues for Story 2b-6
5d4d398 feat(search): implement hybrid BM25+pgvector search with RRF fusion (Story 2b-6)
```

**Recommended commit message:** `feat(mig): implement entity extraction and identity_nodes/identity_edges tables (Story 2c-1)`

### Critical Architecture Constraints

**FROM PROJECT-CONTEXT.md - MUST FOLLOW EXACTLY:**

#### Backend Technology Stack
- **Python 3.12+** - use modern syntax (match statements, type hints)
- **FastAPI 0.115+** - async endpoints where beneficial
- **Pydantic v2** - use model_validator, not validator (v1 syntax)
- **structlog** for logging - NOT standard logging library
- **Gemini 3 Flash** for entity extraction (ingestion task)

#### API Response Format (MANDATORY)
```python
# Success - entity list
{
  "data": [
    {
      "id": "uuid",
      "canonical_name": "Nirav Jobalia",
      "entity_type": "PERSON",
      "mention_count": 15,
      "metadata": {
        "roles": ["plaintiff"],
        "aliases": ["N.D. Jobalia", "Mr. Jobalia"]
      }
    }
  ],
  "meta": {
    "total": 45,
    "page": 1,
    "per_page": 20
  }
}

# Error
{ "error": { "code": "ENTITY_NOT_FOUND", "message": "...", "details": {} } }
```

#### Naming Conventions
| Layer | Convention | Example |
|-------|------------|---------|
| Database tables | snake_case | `identity_nodes`, `entity_mentions` |
| Database columns | snake_case | `canonical_name`, `entity_type` |
| TypeScript variables | camelCase | `entityType`, `mentionCount` |
| Python functions | snake_case | `extract_entities`, `save_entity` |
| Python classes | PascalCase | `MIGEntityExtractor`, `EntityNode` |
| API endpoints | plural nouns | `/api/matters/{matter_id}/entities` |

#### RLS Policy Template (MANDATORY)
```sql
CREATE POLICY "Users can only access entities in their matters"
ON identity_nodes FOR ALL
USING (
  matter_id IN (
    SELECT matter_id FROM matter_members
    WHERE user_id = auth.uid()
  )
);
```

### File Organization

```
backend/app/
├── services/
│   └── mig/
│       ├── __init__.py                     (NEW) - Module exports
│       ├── extractor.py                    (NEW) - Gemini entity extraction
│       ├── graph.py                        (NEW) - MIG CRUD operations
│       └── prompts.py                      (NEW) - Extraction prompts
├── api/
│   └── routes/
│       ├── __init__.py                     (UPDATE - add entities router)
│       └── entities.py                     (NEW) - Entity API endpoints
├── models/
│   ├── __init__.py                         (UPDATE - export entity models)
│   └── entity.py                           (NEW) - Entity Pydantic models
├── workers/
│   └── tasks/
│       └── document_tasks.py               (UPDATE - add entity extraction task)

frontend/src/
├── types/
│   └── entity.ts                           (NEW) - Entity TypeScript types
└── lib/
    └── api/
        └── entities.ts                     (NEW) - Entity API client

supabase/migrations/
├── xxx_create_identity_nodes.sql           (NEW)
├── xxx_create_identity_edges.sql           (NEW)
├── xxx_create_entity_mentions.sql          (NEW)
└── xxx_enable_rls_mig.sql                  (NEW)

backend/tests/
├── services/
│   └── mig/
│       ├── test_extractor.py               (NEW)
│       └── test_graph.py                   (NEW)
├── api/
│   └── test_entities.py                    (NEW)
└── integration/
    └── test_mig_integration.py             (NEW)
```

### Testing Guidance

#### Unit Tests - Entity Extraction

```python
# backend/tests/services/mig/test_extractor.py

import pytest
from unittest.mock import MagicMock, patch

from app.services.mig.extractor import MIGEntityExtractor
from app.models.entity import EntityType


@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response with entities."""
    return {
        "entities": [
            {
                "name": "Nirav D. Jobalia",
                "canonical_name": "Nirav Jobalia",
                "type": "PERSON",
                "roles": ["plaintiff"],
                "mentions": [
                    {"text": "Mr. Jobalia", "context": "...plaintiff Mr. Jobalia filed..."}
                ]
            },
            {
                "name": "State Bank of India",
                "canonical_name": "State Bank of India",
                "type": "ORG",
                "roles": ["defendant"],
                "mentions": [
                    {"text": "SBI", "context": "...the respondent SBI failed to..."}
                ]
            }
        ],
        "relationships": [
            {
                "source": "Nirav Jobalia",
                "target": "ABC Corp",
                "type": "HAS_ROLE",
                "description": "Director"
            }
        ]
    }


@pytest.mark.asyncio
async def test_extract_entities_returns_valid_entities(mock_gemini_response):
    """Test entity extraction parses Gemini response correctly."""
    extractor = MIGEntityExtractor()

    with patch.object(extractor, '_call_gemini', return_value=mock_gemini_response):
        result = await extractor.extract_entities(
            text="Plaintiff Mr. Jobalia filed against SBI...",
            document_id="doc-123",
            matter_id="matter-456"
        )

    assert len(result.entities) == 2
    assert result.entities[0].canonical_name == "Nirav Jobalia"
    assert result.entities[0].entity_type == EntityType.PERSON
    assert "plaintiff" in result.entities[0].roles


@pytest.mark.asyncio
async def test_extract_entities_handles_empty_text():
    """Test extraction handles empty or minimal text gracefully."""
    extractor = MIGEntityExtractor()

    result = await extractor.extract_entities(
        text="",
        document_id="doc-123",
        matter_id="matter-456"
    )

    assert len(result.entities) == 0
```

#### Integration Tests

```python
# backend/tests/integration/test_mig_integration.py

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_entity_extraction_pipeline(
    client: AsyncClient,
    test_matter_with_documents: Matter,
    auth_headers: dict,
):
    """Test entities are extracted from processed documents."""
    # Trigger document processing (or use pre-processed test data)
    # ...

    # Verify entities were extracted
    response = await client.get(
        f"/api/matters/{test_matter_with_documents.id}/entities",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert "data" in data
    assert len(data["data"]) > 0

    # Verify entity structure
    entity = data["data"][0]
    assert "id" in entity
    assert "canonical_name" in entity
    assert "entity_type" in entity
    assert "mention_count" in entity


@pytest.mark.asyncio
async def test_matter_isolation_for_entities(
    client: AsyncClient,
    test_matter_a: Matter,
    test_matter_b: Matter,
    user_a_headers: dict,
    user_b_headers: dict,
):
    """Test entities from one matter cannot be accessed from another."""
    # User A should see matter A entities
    response = await client.get(
        f"/api/matters/{test_matter_a.id}/entities",
        headers=user_a_headers,
    )
    assert response.status_code == 200

    # User B should NOT see matter A entities
    response = await client.get(
        f"/api/matters/{test_matter_a.id}/entities",
        headers=user_b_headers,
    )
    assert response.status_code == 403  # Forbidden
```

### Anti-Patterns to AVOID

```python
# WRONG: Using GPT-4 for entity extraction
model = "gpt-4"  # Too expensive for ingestion task

# CORRECT: Use Gemini for ingestion tasks
model = "gemini-3-flash"

# WRONG: Not validating matter_id on every operation
def get_entity(entity_id):
    return db.query(Entity).filter_by(id=entity_id).first()  # No matter check!

# CORRECT: Always filter by matter_id
def get_entity(entity_id: str, matter_id: str):
    return db.query(Entity).filter_by(id=entity_id, matter_id=matter_id).first()

# WRONG: Storing raw Gemini response without parsing
entities = gemini_response  # Unvalidated data

# CORRECT: Parse and validate with Pydantic
entities = EntityExtractionResult.model_validate(gemini_response)

# WRONG: Not handling Gemini API failures
result = await gemini.generate(prompt)  # Could throw

# CORRECT: Wrap with try-catch and retry logic
try:
    result = await gemini.generate(prompt)
except GeminiError as e:
    logger.warning("gemini_extraction_failed", error=str(e))
    return EntityExtractionResult(entities=[], relationships=[])
```

### Performance Considerations

- **Batch Processing:** Extract entities from multiple chunks in parallel
- **Caching:** Cache extracted entities within same document (avoid re-extraction)
- **Deduplication:** Use hash of (canonical_name, entity_type) for fast dedup
- **Mention Limiting:** Store max 100 mentions per entity (oldest first)
- **Gemini Token Limits:** Chunk text to fit within context window

### Dependencies to Add

```bash
# No new dependencies needed - uses existing Gemini service
```

### Environment Variables Required

```bash
# Already configured in previous stories
GOOGLE_AI_API_KEY=...   # For Gemini (configured in Story 2b-2)
```

### Manual Steps Required After Implementation

#### Migrations
- [ ] Run: `supabase migration up` for identity_nodes, identity_edges, entity_mentions tables

#### Environment Variables
- [ ] No new environment variables required (Gemini API key already configured)

#### Dashboard Configuration
- [ ] No dashboard changes required

#### Manual Tests
- [ ] Upload a test document and verify entities are extracted
- [ ] Check identity_nodes table has entries after document processing
- [ ] Test entity API endpoint returns extracted entities
- [ ] Verify entity mentions link to correct documents/pages
- [ ] Test matter isolation: ensure entities from one matter are not visible in another
- [ ] Test entity deduplication: same entity mentioned multiple times should be one entry

### Downstream Dependencies

This story enables:
- **Story 2C.2 (Alias Resolution):** Uses identity_nodes to link aliases across documents
- **Epic 4 (Timeline Engine):** Links events to entities via entity_ids
- **Epic 5 (Contradiction Engine):** Groups statements by canonical_entity_id
- **Epic 10C (Entities Tab):** Displays MIG graph visualization

### Project Structure Notes

- MIG is PostgreSQL-only (per ADR-001) - no Neo4j
- Simple graph operations (lookup, filter) - not complex traversals
- RLS enforces matter isolation at database level
- Entity extraction is part of document ingestion pipeline

### References

- [Source: architecture.md#ADR-001] - PostgreSQL for MIG decision
- [Source: architecture.md#MIG-Service] - Service structure
- [Source: architecture.md#Database-Schema] - Table definitions
- [Source: project-context.md#LLM-Routing] - Gemini for entity extraction
- [Source: epics.md#Story-2.10] - Story requirements
- [Source: 2b-7-cohere-rerank-integration.md] - Service pattern reference
- [Source: FR14] - MIG functional requirement

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A - No significant debugging issues encountered.

### Completion Notes List

1. **Task 1 (Database Schema)**: Found existing `identity_nodes` and `identity_edges` tables in migration `20260106000009_create_mig_tables.sql`. Created new migration `20260112000001_create_entity_mentions_table.sql` for the `entity_mentions` table with proper indexes and RLS policies enforcing matter isolation.

2. **Task 2 (Pydantic Models)**: Created comprehensive entity models in `backend/app/models/entity.py` including EntityType/RelationshipType enums, EntityNode, EntityEdge, EntityMention models, and EntityExtractionResult for Gemini response parsing. Updated `__init__.py` with exports.

3. **Task 3 (Gemini Extraction Service)**: Created `backend/app/services/mig/` module with `extractor.py` containing MIGEntityExtractor class using Gemini Flash for entity extraction. Added `prompts.py` with detailed extraction prompts for Indian legal documents.

4. **Task 4 (Graph Service)**: Created `backend/app/services/mig/graph.py` with MIGGraphService class implementing full CRUD operations including entity deduplication within matter, mention tracking, and relationship storage.

5. **Task 5 (Pipeline Integration)**: Updated `backend/app/workers/tasks/document_tasks.py` to add `extract_entities` Celery task that runs after `embed_chunks`, processing child chunks for entity extraction.

6. **Task 6 (API Endpoints)**: Created `backend/app/api/routes/entities.py` with three endpoints: list entities, get entity detail, and get entity mentions. All endpoints enforce matter access authorization.

7. **Task 7 (Frontend Types)**: Created `frontend/src/types/entity.ts` with TypeScript types and `frontend/src/lib/api/entities.ts` with API client functions.

8. **Task 8 (Unit Tests)**: Created comprehensive unit tests in `backend/tests/services/mig/test_extractor.py`, `backend/tests/services/mig/test_graph.py`, and `backend/tests/api/routes/test_entities.py`.

9. **Task 9 (Integration Tests)**: Created `backend/tests/integration/test_mig_integration.py` testing the complete extraction pipeline, entity deduplication, matter isolation, entity type handling, and relationship extraction.

### File List

**New Files Created:**
- `supabase/migrations/20260112000001_create_entity_mentions_table.sql` - Migration for entity_mentions table with RLS
- `backend/app/models/entity.py` - MIG Pydantic models
- `backend/app/services/mig/__init__.py` - MIG service module exports
- `backend/app/services/mig/prompts.py` - Entity extraction prompts for Gemini
- `backend/app/services/mig/extractor.py` - MIGEntityExtractor class
- `backend/app/services/mig/graph.py` - MIGGraphService class
- `backend/app/api/routes/entities.py` - Entity API endpoints
- `frontend/src/types/entity.ts` - TypeScript entity types
- `frontend/src/lib/api/entities.ts` - Frontend API client for entities
- `backend/tests/services/mig/__init__.py` - Test module init
- `backend/tests/services/mig/test_extractor.py` - Extractor unit tests
- `backend/tests/services/mig/test_graph.py` - Graph service unit tests
- `backend/tests/api/routes/test_entities.py` - API endpoint tests
- `backend/tests/integration/test_mig_integration.py` - Integration tests

**Modified Files:**
- `backend/app/models/__init__.py` - Added entity model exports
- `backend/app/main.py` - Registered entities router
- `backend/app/workers/tasks/document_tasks.py` - Added extract_entities task
- `backend/app/api/routes/documents.py` - Added extract_entities to pipeline chain
- `frontend/src/types/index.ts` - Added entity type exports (including PaginationMeta)
- `backend/tests/workers/test_document_tasks.py` - Added TestExtractEntitiesTask tests

## Code Review Fixes Applied

**Date:** 2026-01-12
**Reviewer:** Claude Opus 4.5 (Adversarial Code Review)

### Issues Found and Fixed:

1. **[HIGH] Entity Type Constraint** - Added CHECK constraint for entity_type enum values
   - Created migration `20260112000002_add_entity_type_constraint.sql`
   - Enforces: PERSON, ORG, INSTITUTION, ASSET for entity_type
   - Enforces: ALIAS_OF, HAS_ROLE, RELATED_TO for relationship_type

2. **[HIGH] AC #4 Clarification** - Updated AC text from `pre_linked_relationships` to `entity_mentions`
   - The `entity_mentions` table correctly stores document references
   - No `pre_linked_relationships` table was ever needed

3. **[MEDIUM] Pipeline Chain Missing** - Added extract_entities to document processing chain
   - Updated `backend/app/api/routes/documents.py`
   - Chain now: OCR -> Validation -> Confidence -> Chunking -> Embedding -> Entity Extraction

4. **[MEDIUM] PaginationMeta Not Exported** - Added to frontend/src/types/index.ts exports

5. **[LOW] Extract Entities Task Tests** - Added comprehensive tests
   - `TestExtractEntitiesTask` class in `backend/tests/workers/test_document_tasks.py`
   - Tests: successful extraction, skip on failed prev task, no document_id, no chunks

6. **[MEDIUM] Async-Safe Supabase Calls** - Refactored graph.py to use asyncio.to_thread()
   - All database operations now run in thread pool to avoid blocking event loop
   - Added `asyncio.gather()` for concurrent queries in `get_entity_relationships()`
   - Pattern can be applied to other services (chunk_service.py etc.) as needed

