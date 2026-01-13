# Story 4.3: Implement Events Table with MIG Integration

Status: dev-complete

## Story

As a **developer**,
I want **events stored with entity links and chronological ordering**,
So that **timelines can show who was involved in each event**.

## Acceptance Criteria

1. **Given** an event is created **When** it is stored **Then** the events table contains: event_id, matter_id, document_id, event_date, event_type, title, description, entity_ids (array), bbox_ids, source_text, confidence, verified

2. **Given** an event mentions "Nirav Jobalia filed a petition" **When** entity linking runs **Then** the event's entity_ids includes the canonical entity_id for Nirav Jobalia

3. **Given** multiple events exist for a matter **When** timeline is constructed **Then** events are ordered by event_date ascending **And** events on the same date maintain document order

4. **Given** timeline data is needed frequently **When** timeline is generated **Then** it is cached in Matter Memory at /matter-{id}/timeline_cache.jsonb **And** cache is invalidated when new documents are uploaded

## Tasks / Subtasks

- [ ] Task 1: Create Entity Linking Service (AC: #2)
  - [ ] Create `backend/app/engines/timeline/entity_linker.py`
    - Class: `EventEntityLinker`
    - Method: `link_entities_to_event(event_id: str, description: str, matter_id: str) -> list[str]`
      - Parse description text to identify entity mentions
      - Search `identity_nodes` table for matching canonical names or aliases
      - Use MIGGraphService.get_entities_by_matter() for entity lookup
      - Use EntityResolver for fuzzy name matching (existing from Story 2c-2)
      - Return list of matched entity_id UUIDs
    - Method: `link_entities_batch(events: list[RawEvent], matter_id: str) -> dict[str, list[str]]`
      - Batch entity linking for multiple events
      - Efficient - load all matter entities once, then match against each event
      - Return dict mapping event_id to list of entity_ids
    - Use Gemini for complex entity mention extraction if names ambiguous
    - Confidence threshold: only link if match confidence >= 0.7
  - [ ] Handle Indian legal name patterns:
    - Titles: "Shri", "Smt", "Adv", "Hon'ble"
    - Patronymics: "Nirav Dineshbhai Jobalia"
    - Initials: "N.D. Jobalia"

- [ ] Task 2: Create Timeline Service Methods for Entity Linking (AC: #1, #2)
  - [ ] Update `backend/app/services/timeline_service.py`
    - Method: `update_event_entities(event_id: str, matter_id: str, entity_ids: list[str]) -> bool`
      - Update events.entities_involved array
      - Validate all entity_ids exist in identity_nodes for this matter
      - Update event.updated_at timestamp
    - Method: `get_events_with_entities(matter_id: str, entity_id: str | None = None) -> list[RawEvent]`
      - If entity_id provided, filter by events containing that entity
      - Use GIN index on entities_involved for efficient queries
    - Method: `link_entities_for_document(document_id: str, matter_id: str) -> int`
      - Get all events for document
      - Run entity linking on each event
      - Return count of events updated

- [ ] Task 3: Create Timeline Construction Service (AC: #3, #4)
  - [ ] Create `backend/app/engines/timeline/timeline_builder.py`
    - Class: `TimelineBuilder`
    - Method: `build_timeline(matter_id: str, filters: TimelineFilters | None = None) -> Timeline`
      - Load all classified events for matter (event_type != 'raw_date')
      - Order by event_date ASC, then document order
      - Group by date for UI rendering
      - Apply optional filters (event_type, date range, entity_id)
    - Method: `get_timeline_for_entity(matter_id: str, entity_id: str) -> Timeline`
      - Build timeline filtered to events involving specific entity
      - Useful for "Show me everything about Nirav Jobalia"
    - Method: `get_events_between_dates(matter_id: str, start: date, end: date) -> list[ClassifiedEvent]`
      - Efficient date range queries using idx_events_matter_date index
  - [ ] Create Pydantic models in `backend/app/models/timeline.py`:
    - `TimelineFilters`: event_types, start_date, end_date, entity_ids, verified_only
    - `TimelineEvent`: extends ClassifiedEvent with entity names resolved
    - `Timeline`: events list, date_range, entity_summary

- [ ] Task 4: Implement Timeline Cache in Matter Memory (AC: #4)
  - [ ] Create `backend/app/services/memory/timeline_cache.py`
    - Method: `get_timeline_cache(matter_id: str) -> Timeline | None`
      - Check matter_memory table for timeline_cache key
      - Return cached Timeline if exists and not stale
    - Method: `set_timeline_cache(matter_id: str, timeline: Timeline) -> None`
      - Store timeline as JSONB in matter_memory
      - Key: `timeline_cache`
      - Include cache_timestamp for staleness detection
    - Method: `invalidate_timeline_cache(matter_id: str) -> None`
      - Delete timeline_cache from matter_memory
      - Called when new documents uploaded or events modified
  - [ ] Integrate with document upload flow:
    - After OCR/date extraction complete, invalidate timeline cache
    - After event classification complete, invalidate timeline cache
  - [ ] Cache structure:
    ```json
    {
      "matter_id": "uuid",
      "timeline_cache": {
        "events": [...],
        "date_range": {"start": "2020-01-01", "end": "2024-12-31"},
        "entity_summary": {"count": 15, "top_entities": [...]},
        "cache_timestamp": "2026-01-13T10:00:00Z"
      }
    }
    ```

- [ ] Task 5: Create Background Task for Entity Linking (AC: #2)
  - [ ] Add to `backend/app/workers/tasks/engine_tasks.py`
    - Task: `link_entities_for_document_task(document_id: str, matter_id: str)`
      - Load classified events for document
      - Run EventEntityLinker.link_entities_batch()
      - Update events table with entity_ids
      - Update processing_jobs table
    - Task: `link_entities_for_matter_task(matter_id: str)`
      - Link entities for all events in matter
      - Useful for backfill after MIG entity extraction
    - Task: `rebuild_timeline_cache_task(matter_id: str)`
      - Build and cache timeline for matter
  - [ ] Integrate with classification pipeline:
    - After classification completes, queue entity linking task
    - Pipeline: extraction → classification → entity linking → cache rebuild

- [ ] Task 6: Create API Endpoints for Timeline with Entities (AC: #1, #2, #3)
  - [ ] Update `backend/app/api/routes/timeline.py`
    - `GET /api/matters/{matter_id}/timeline`
      - Return full chronological timeline with entity information
      - Parameters: event_type, start_date, end_date, entity_id, page, per_page
      - Use cache if available, rebuild if stale
    - `GET /api/matters/{matter_id}/timeline/entity/{entity_id}`
      - Return timeline filtered to specific entity
      - Shows all events where entity is involved
    - `POST /api/matters/{matter_id}/timeline/link-entities`
      - Trigger entity linking for matter
      - Parameters: document_ids (optional), force_relink (default false)
      - Return job_id for progress tracking
    - `GET /api/matters/{matter_id}/events/{event_id}/entities`
      - Return entities linked to specific event
      - Include entity details (canonical_name, type, aliases)
    - `PATCH /api/matters/{matter_id}/events/{event_id}/entities`
      - Manual entity linking by attorney
      - Add/remove entity_ids from event
      - Set verified = true for manual links

- [ ] Task 7: Write Unit Tests for Entity Linker (AC: #2)
  - [ ] Create `backend/tests/engines/timeline/test_entity_linker.py`
    - Test entity name matching against MIG
    - Test alias resolution (N.D. → Nirav D.)
    - Test Indian name patterns
    - Test confidence thresholds
    - Test batch processing
    - Mock MIG graph service calls

- [ ] Task 8: Write Service and API Tests (AC: #1, #2, #3, #4)
  - [ ] Update `backend/tests/services/test_timeline_service.py`
    - Test update_event_entities
    - Test get_events_with_entities
    - Test link_entities_for_document
  - [ ] Create `backend/tests/services/memory/test_timeline_cache.py`
    - Test cache get/set/invalidate
    - Test cache staleness detection
  - [ ] Update `backend/tests/api/routes/test_timeline.py`
    - Test GET timeline endpoint with entity data
    - Test entity filtering
    - Test entity linking endpoints
    - Test manual entity link/unlink

- [ ] Task 9: Write Integration Tests (AC: #1, #2, #3, #4)
  - [ ] Create `backend/tests/integration/test_entity_linking_pipeline.py`
    - Test full pipeline: extraction → classification → entity linking
    - Test timeline cache invalidation on new documents
    - Test entity filtering accuracy
    - Verify entity_ids reference valid identity_nodes

## Dev Notes

### CRITICAL: Architecture Requirements

**From [architecture.md](../_bmad-output/architecture.md):**

This is **Story 4.3** of the **Timeline Construction Engine** (Epic 4). The engine flow is:

```
DATE EXTRACTION (Story 4-1) ✓ COMPLETED
  | Extract dates with context from all case files
  | Store as "raw_date" events for classification
  v
EVENT CLASSIFICATION (Story 4-2) ✓ COMPLETED
  | Classify dates by type (filing, notice, hearing, etc.)
  | Update event_type from "raw_date" to classified type
  | Flag low-confidence events for manual review
  v
EVENTS TABLE + MIG INTEGRATION (THIS STORY)
  | Link events to canonical entities from MIG
  | Build timeline with entity context
  | Cache timeline for fast retrieval
  v
TIMELINE ANOMALY DETECTION (Story 4-4)
  | Flag sequence violations, gaps, etc.
```

### MIG Integration Pattern (CRITICAL)

**From [MIG Graph Service](../../backend/app/services/mig/graph.py):**

The Matter Identity Graph (MIG) stores entities in `identity_nodes` table with:
- `canonical_name`: Primary entity name (e.g., "Nirav Dineshbhai Jobalia")
- `entity_type`: PERSON, ORG, INSTITUTION, ASSET
- `aliases`: Array of name variants (e.g., ["N.D. Jobalia", "Mr. Jobalia"])
- `mention_count`: How often entity appears

**Entity Linking Strategy:**
1. Parse event description for potential entity mentions
2. Query `identity_nodes` for matter with matching canonical_name or aliases
3. Use `EntityResolver.calculate_name_similarity()` for fuzzy matching
4. Link if similarity >= 0.7 confidence threshold

```python
# CORRECT - Use existing MIG services
from app.services.mig.graph import get_mig_graph_service
from app.services.mig.entity_resolver import get_entity_resolver

mig_service = get_mig_graph_service()
resolver = get_entity_resolver()

# Get all entities for matter
entities, _ = await mig_service.get_entities_by_matter(matter_id)

# Match entity mentions in event text
for entity in entities:
    similarity = resolver.calculate_name_similarity(
        mention_text, entity.canonical_name
    )
    if similarity >= 0.7:
        matched_entity_ids.append(entity.id)
```

### Events Table Schema (Already Exists)

**From [supabase/migrations/20260106000008_create_events_table.sql](../../supabase/migrations/20260106000008_create_events_table.sql):**

```sql
CREATE TABLE public.events (
  id uuid PRIMARY KEY,
  matter_id uuid NOT NULL REFERENCES public.matters(id),
  document_id uuid REFERENCES public.documents(id),
  event_date date NOT NULL,
  event_date_precision text NOT NULL DEFAULT 'day',
  event_date_text text,
  event_type text NOT NULL,
  description text NOT NULL,
  entities_involved uuid[], -- ← THIS IS THE TARGET FOR ENTITY LINKING
  source_page integer,
  source_bbox_ids uuid[],
  confidence float,
  is_manual boolean DEFAULT false,
  created_by uuid REFERENCES auth.users(id),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- GIN index for efficient entity filtering
CREATE INDEX idx_events_entities ON public.events USING GIN (entities_involved);
```

**Key insight:** The `entities_involved` column is a UUID array that references `identity_nodes.id`. Entity linking populates this array.

### LLM Routing (CRITICAL - Cost & Quality)

**From [project-context.md](../_bmad-output/project-context.md):**

| Task Type | Model | Reason |
|-----------|-------|--------|
| Entity extraction from text | **Gemini 3 Flash** | Pattern matching, ingestion task |
| Entity linking | **Gemini 3 Flash** | Only if names ambiguous, otherwise string matching |
| NOT GPT-4 | - | Would be 30x more expensive |

```python
# CORRECT - Use Gemini for entity extraction if needed
from google.generativeai import GenerativeModel
model = GenerativeModel("gemini-1.5-flash-latest")

# WRONG - Don't use GPT-4 for entity linking
from openai import OpenAI
client.chat.completions.create(model="gpt-4", ...)
```

### Previous Story Intelligence (Story 4-2)

**From Story 4-2 (Event Classification):**

Key patterns to follow:
1. **Service class pattern**: `EventClassifier` class with async methods - follow same for `EventEntityLinker`
2. **Batch processing**: Process events in batches for efficiency (20 events per batch)
3. **Confidence scoring**: 0-1 range, threshold at 0.7 for automation
4. **Job tracking integration**: Create job, update progress via processing_jobs

**Files from Story 4-2 to reference:**
- `backend/app/engines/timeline/event_classifier.py` - Service pattern to follow
- `backend/app/engines/timeline/classification_prompts.py` - Prompt structure reference
- `backend/app/models/timeline.py` - Models to extend (add Timeline, TimelineFilters)
- `backend/app/services/timeline_service.py` - Service to extend with entity methods

### Entity Resolver (Existing - Reuse!)

**From [backend/app/services/mig/entity_resolver.py](../../backend/app/services/mig/entity_resolver.py):**

The `EntityResolver` class already handles:
- Name similarity calculation (Jaro-Winkler + component matching)
- Indian name patterns (titles, patronymics, initials)
- Alias matching (N.D. → Nirav D.)
- Confidence thresholds

**CRITICAL: Do NOT reinvent name matching. Use existing EntityResolver:**

```python
from app.services.mig.entity_resolver import get_entity_resolver

resolver = get_entity_resolver()

# Compare mention to canonical name
similarity = resolver.calculate_name_similarity(
    mention_text,
    entity.canonical_name
)

# Also check aliases
for alias in entity.aliases:
    alias_similarity = resolver.calculate_name_similarity(mention_text, alias)
    similarity = max(similarity, alias_similarity)
```

### Matter Memory Pattern (For Cache)

**From [architecture.md](../_bmad-output/architecture.md):**

Matter Memory uses PostgreSQL JSONB in `matter_memory` table:
- Key: `/matter-{id}/{key}` or just `{key}` per matter
- TTL: Persistent (no expiration)
- Invalidation: Manual via API or on document upload

```python
# Cache structure for timeline
{
    "events": [...],  # List of ClassifiedEvent objects
    "date_range": {"start": "2020-01-01", "end": "2024-12-31"},
    "entity_summary": {
        "count": 15,
        "top_entities": [
            {"id": "uuid", "name": "Nirav Jobalia", "event_count": 12},
            ...
        ]
    },
    "cache_timestamp": "2026-01-13T10:00:00Z"
}
```

### API Response Format (MANDATORY)

```python
# GET /api/matters/{matter_id}/timeline
{
  "data": {
    "events": [
      {
        "id": "uuid",
        "event_date": "2024-01-15",
        "event_type": "filing",
        "description": "The petitioner filed this writ petition...",
        "entities_involved": [
          {
            "id": "uuid",
            "canonical_name": "Nirav Dineshbhai Jobalia",
            "entity_type": "PERSON"
          }
        ],
        "source_page": 1,
        "verified": false
      }
    ],
    "date_range": {"start": "2020-01-01", "end": "2024-12-31"},
    "total_events": 45,
    "from_cache": true
  },
  "meta": {
    "total": 45,
    "page": 1,
    "per_page": 50,
    "total_pages": 1
  }
}

# GET /api/matters/{matter_id}/timeline/entity/{entity_id}
{
  "data": {
    "entity": {
      "id": "uuid",
      "canonical_name": "Nirav Dineshbhai Jobalia",
      "entity_type": "PERSON",
      "aliases": ["N.D. Jobalia", "Mr. Jobalia"]
    },
    "events": [...],  # Events filtered to this entity
    "total_events": 12
  }
}

# POST /api/matters/{matter_id}/timeline/link-entities
{
  "data": {
    "job_id": "uuid",
    "status": "queued",
    "events_to_link": 150
  }
}
```

### Git Intelligence

Recent commits:
```
7ea16a8 fix(review): address code review issues for Story 4-2
0533aff feat(timeline): implement event classification with Gemini (Story 4-2)
fb04eff feat(timeline): implement date extraction with Gemini (Story 4-1)
```

**Recommended commit message:** `feat(timeline): implement entity linking and timeline construction (Story 4-3)`

### File Organization

```
backend/app/
|-- engines/
|   |-- timeline/
|   |   |-- __init__.py                      (UPDATE - add entity_linker, timeline_builder)
|   |   |-- date_extractor.py                (EXISTING)
|   |   |-- event_classifier.py              (EXISTING)
|   |   |-- entity_linker.py                 (NEW)
|   |   |-- timeline_builder.py              (NEW)
|   |   |-- prompts.py                       (EXISTING)
|   |   +-- classification_prompts.py        (EXISTING)
|-- models/
|   +-- timeline.py                          (UPDATE - add Timeline, TimelineFilters, TimelineEvent)
|-- services/
|   |-- memory/
|   |   +-- timeline_cache.py                (NEW)
|   +-- timeline_service.py                  (UPDATE - add entity linking methods)
|-- api/
|   +-- routes/
|       +-- timeline.py                      (UPDATE - add timeline/entity endpoints)
|-- workers/
|   +-- tasks/
|       +-- engine_tasks.py                  (UPDATE - add entity linking tasks)

backend/tests/
|-- engines/
|   +-- timeline/
|       |-- test_date_extractor.py           (EXISTING)
|       |-- test_event_classifier.py         (EXISTING)
|       +-- test_entity_linker.py            (NEW)
|-- services/
|   |-- memory/
|   |   +-- test_timeline_cache.py           (NEW)
|   +-- test_timeline_service.py             (UPDATE - add entity linking tests)
|-- api/
|   +-- routes/
|       +-- test_timeline.py                 (UPDATE - add timeline/entity tests)
+-- integration/
    |-- test_classification_pipeline.py      (EXISTING)
    +-- test_entity_linking_pipeline.py      (NEW)
```

### Dependencies

**Backend:**
```bash
# Already installed - no new dependencies needed
# Uses existing:
# - google-generativeai (Gemini)
# - rapidfuzz (name matching via EntityResolver)
# - supabase (database access)
```

### Manual Steps Required After Implementation

#### Migrations
- [ ] None - events table already has entities_involved column (20260106000008_create_events_table.sql)
- [ ] Verify matter_memory table exists for timeline cache (check migrations)

#### Environment Variables
- [ ] Verify `GEMINI_API_KEY` is set (should exist from Story 4-1)

#### Dashboard Configuration
- [ ] None - no dashboard changes needed

#### Manual Tests
- [ ] Upload test documents with entity mentions in date context
- [ ] Run date extraction (Story 4-1) and classification (Story 4-2) first
- [ ] Verify MIG has entities extracted (Epic 2C) before testing entity linking
- [ ] Trigger entity linking via POST /api/matters/{matter_id}/timeline/link-entities
- [ ] Verify GET /api/matters/{matter_id}/timeline returns events with entities
- [ ] Test entity filtering via GET /api/matters/{matter_id}/timeline/entity/{entity_id}
- [ ] Verify timeline cache is populated and returned on subsequent requests
- [ ] Test cache invalidation when new document is uploaded
- [ ] Test manual entity linking via PATCH endpoint
- [ ] Verify matter isolation - cannot view other matter's timeline

### Downstream Dependencies

This story enables:
- **Story 4-4 (Anomaly Detection):** Will use entity-linked events for sequence validation
- **Epic 5 (Contradiction Engine):** Will use entity-grouped events for contradiction detection
- **Epic 10B (Timeline Tab):** Will display timeline with entity avatars/badges
- **Epic 10C (Entities Tab):** Will show entity timeline view

### Entity Linking Algorithm

**Algorithm for matching entity mentions in event descriptions:**

```
1. LOAD all entities for matter (identity_nodes)
   - Include canonical_name, aliases, entity_type

2. FOR each event:
   a. EXTRACT potential entity mentions from description
      - Look for capitalized phrases (proper nouns)
      - Look for title + name patterns ("Shri", "Hon'ble", etc.)
      - Look for known entity patterns (ORG indicators: "Ltd", "Bank", etc.)

   b. FOR each potential mention:
      - MATCH against all entities using EntityResolver.calculate_name_similarity()
      - CHECK canonical_name AND all aliases
      - THRESHOLD: similarity >= 0.7 to link

   c. DEDUPLICATE matched entity_ids (avoid duplicates in array)

   d. UPDATE event.entities_involved with matched entity_ids

3. TRACK statistics:
   - Events processed
   - Entities linked
   - High-confidence links vs uncertain
```

### Edge Cases to Handle

1. **No MIG entities yet:** If matter has no entities in identity_nodes, entity linking returns empty arrays (graceful degradation)
2. **Ambiguous names:** "Mr. Singh" could match multiple entities - link to all if confidence >= 0.7, flag for manual review if ambiguous
3. **Organization variations:** "HDFC Bank Ltd" should match "HDFC Bank Limited" using similarity
4. **Already linked events:** If event already has entity_ids and force_relink=false, skip
5. **Cache staleness:** If cache_timestamp > 24 hours old, rebuild on access

### References

- [Source: architecture.md#Timeline-Construction-Engine] - Engine architecture
- [Source: architecture.md#MIG-Integration] - Matter Identity Graph patterns
- [Source: epics.md#Story-4.3] - Story requirements and acceptance criteria
- [Source: Requirements-Baseline-v1.0.md#Timeline-Construction-Engine] - Business requirements
- [Source: project-context.md#LLM-Routing] - Gemini usage for ingestion tasks
- [Source: backend/app/services/mig/graph.py] - MIG Graph Service (entity CRUD)
- [Source: backend/app/services/mig/entity_resolver.py] - Name matching algorithms
- [Source: backend/app/engines/timeline/event_classifier.py] - Pattern for service class
- [Source: supabase/migrations/20260106000008_create_events_table.sql] - Events table schema

### Project Structure Notes

- Entity linker in `engines/timeline/entity_linker.py` per existing pattern
- Timeline builder in `engines/timeline/timeline_builder.py`
- Extended models in `models/timeline.py`
- Cache service in `services/memory/timeline_cache.py`
- Extended timeline service in `services/timeline_service.py`
- Extended API routes in `api/routes/timeline.py`
- Tests follow existing pattern in `tests/engines/timeline/`

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

