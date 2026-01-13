# Story 4.2: Implement Event Classification

Status: dev-complete

## Story

As an **attorney**,
I want **dates classified by event type (filing, notice, hearing, etc.)**,
So that **I can filter and understand the timeline by event category**.

## Acceptance Criteria

1. **Given** a date with context is extracted **When** classification runs **Then** the event is assigned a type: filing, notice, hearing, order, transaction, document, deadline **And** classification confidence is recorded

2. **Given** context mentions "filed on" **When** classification runs **Then** the event is classified as "filing"

3. **Given** context mentions "next hearing" **When** classification runs **Then** the event is classified as "hearing"

4. **Given** classification is uncertain **When** confidence < 0.7 **Then** the event type is marked as "unclassified" **And** it appears in verification queue for manual classification

## Tasks / Subtasks

- [x] Task 1: Create Event Classification Prompts (AC: #1, #2, #3)
  - [ ] Create `backend/app/engines/timeline/classification_prompts.py`
    - EVENT_CLASSIFICATION_SYSTEM_PROMPT: Define classification requirements
      - Define all event types with clear descriptions:
        - `filing`: Petition, complaint, appeal, application filed
        - `notice`: Notice issued, served, received
        - `hearing`: Court hearing, arguments, proceedings
        - `order`: Court orders, judgments, decrees
        - `transaction`: Payment, transfer, contract execution
        - `document`: Document creation, execution, signing
        - `deadline`: Time limits, limitation periods, due dates
        - `unclassified`: Cannot determine with confidence
      - Require confidence score based on keyword matches and context
      - Specify output JSON schema
    - EVENT_CLASSIFICATION_USER_PROMPT: Template for event text
    - Include examples of expected classifications
  - [ ] Handle edge cases:
    - Multiple possible types (return highest confidence)
    - Indian legal terminology (e.g., "vakalatnama", "rejoinder")
    - Combined events (e.g., "filed and served")

- [x] Task 2: Create Event Classifier Service (AC: #1, #2, #3, #4)
  - [ ] Create `backend/app/engines/timeline/event_classifier.py`
    - Class: `EventClassifier`
    - Method: `classify_event(event_id: str, context_text: str, date_text: str) -> EventClassificationResult`
      - Use Gemini 3 Flash (per LLM routing rules - ingestion task, NOT user-facing)
      - Implement retry logic with exponential backoff (MAX_RETRIES=3)
      - Handle rate limits gracefully
      - Parse LLM JSON response into structured data
    - Method: `classify_events_batch(events: list[dict]) -> list[EventClassificationResult]`
      - Batch classify multiple events in single LLM call for efficiency
      - Process up to 20 events per batch to stay within token limits
    - Calculate confidence scores based on:
      - Keyword presence (exact matches: 0.95+)
      - Context analysis (patterns: 0.85-0.95)
      - Ambiguous context (0.5-0.7)
      - Flag as unclassified if < 0.7

- [x] Task 3: Create Pydantic Models for Event Classification (AC: #1, #4)
  - [ ] Update `backend/app/models/timeline.py`
    - `EventType` enum: filing, notice, hearing, order, transaction, document, deadline, unclassified, raw_date
    - `EventClassificationResult` model:
      - event_id: str
      - event_type: EventType
      - classification_confidence: float
      - secondary_types: list[tuple[EventType, float]] (alternative classifications)
      - keywords_matched: list[str]
      - classification_reasoning: str | None
    - `ClassifiedEvent` model (extends RawEvent):
      - event_type: EventType (not raw_date)
      - classification_confidence: float
      - verified: bool = False
    - `EventClassificationResponse` model for API

- [x] Task 4: Add Service Methods for Classification (AC: #1, #4)
  - [ ] Update `backend/app/services/timeline_service.py`
    - Method: `update_event_classification(event_id: str, matter_id: str, event_type: str, confidence: float) -> bool`
      - Update events table with new event_type and confidence
      - Preserve original raw_date type in metadata if needed
    - Method: `get_unclassified_events(matter_id: str) -> list[RawEvent]`
      - Return events where event_type = 'raw_date' OR classification confidence < 0.7
    - Method: `get_events_for_classification(matter_id: str, limit: int = 100) -> list[RawEvent]`
      - Return raw_date events ready for classification
    - Method: `bulk_update_classifications(classifications: list[EventClassificationResult]) -> int`
      - Update multiple events in single transaction

- [x] Task 5: Create Background Task for Event Classification (AC: #1)
  - [ ] Add to `backend/app/workers/tasks/engine_tasks.py`
    - Task: `classify_events_for_document(document_id: str, matter_id: str)`
      - Load all raw_date events for document
      - Call EventClassifier.classify_events_batch
      - Save classifications via timeline_service
      - Update processing_jobs table with status
    - Task: `classify_events_for_matter(matter_id: str)`
      - Queue classification for all documents with raw_date events
      - Track overall progress
    - Integrate with job tracking pattern from Story 2c-3

- [x] Task 6: Create API Endpoints for Event Classification (AC: #1, #4)
  - [ ] Add to `backend/app/api/routes/timeline.py`
    - `POST /api/matters/{matter_id}/timeline/classify`
      - Trigger classification for raw_date events
      - Return job_id for progress tracking
      - Parameters: document_ids (optional), force_reclassify (default false)
    - `GET /api/matters/{matter_id}/timeline/events`
      - Return classified events (event_type != raw_date)
      - Support filtering: ?event_type=filing&confidence_min=0.7
      - Use pagination (page, per_page)
    - `GET /api/matters/{matter_id}/timeline/unclassified`
      - Return events needing manual classification
      - Filter by confidence < 0.7 OR event_type = 'unclassified'
    - `PATCH /api/matters/{matter_id}/timeline/events/{event_id}`
      - Manual event type update by attorney
      - Set is_manual = true, verified = true
      - Update confidence to 1.0 (human verified)
    - All endpoints require matter membership (RLS + API middleware)

- [x] Task 7: Integrate with Date Extraction Pipeline (AC: #1)
  - [ ] Update date extraction to optionally trigger classification
    - After date extraction completes, queue classification job
    - Add parameter `auto_classify: bool = True` to extraction endpoints
  - [ ] Update processing flow:
    - Date Extraction → Classification → Ready for Timeline View
  - [ ] Add job type `EVENT_CLASSIFICATION` to job tracking

- [x] Task 8: Write Unit Tests for Event Classification (AC: #1, #2, #3, #4)
  - [ ] Create `backend/tests/engines/timeline/test_event_classifier.py`
    - Test classification of different event types
    - Test keyword matching for each type
    - Test confidence thresholds
    - Test unclassified fallback
    - Test Indian legal terminology
    - Mock Gemini API calls

- [x] Task 9: Write Service and API Tests (AC: #1, #4)
  - [ ] Update `backend/tests/services/test_timeline_service.py`
    - Test update_event_classification
    - Test get_unclassified_events
    - Test bulk_update_classifications
  - [ ] Update `backend/tests/api/routes/test_timeline.py`
    - Test POST classify endpoint
    - Test GET events endpoint with filters
    - Test GET unclassified endpoint
    - Test PATCH manual classification

- [x] Task 10: Write Integration Tests
  - [ ] Test full pipeline: extraction → classification → retrieval
  - [ ] Test classification accuracy on sample legal text
  - [ ] Verify confidence thresholds work correctly

## Dev Notes

### CRITICAL: Architecture Requirements

**From [architecture.md](../_bmad-output/architecture.md):**

This is **Story 4.2** of the **Timeline Construction Engine** (Epic 4). The engine flow is:

```
DATE EXTRACTION (Story 4-1) ✓ COMPLETED
  | Extract dates with context from all case files
  | Store as "raw_date" events for classification
  v
EVENT CLASSIFICATION (THIS STORY)
  | Classify dates by type (filing, notice, hearing, etc.)
  | Update event_type from "raw_date" to classified type
  | Flag low-confidence events for manual review
  v
EVENTS TABLE + MIG INTEGRATION (Story 4-3)
  | Link events to canonical entities
  | Build timeline cache
  v
TIMELINE ANOMALY DETECTION (Story 4-4)
  | Flag sequence violations, gaps, etc.
```

### LLM Routing (CRITICAL - Cost & Quality)

**From [project-context.md](../_bmad-output/project-context.md):**

| Task Type | Model | Reason |
|-----------|-------|--------|
| Event classification | **Gemini 3 Flash** | Ingestion task, verifiable downstream |
| NOT GPT-4 | - | Would be 30x more expensive |

```python
# CORRECT - Use Gemini for event classification
from google.generativeai import GenerativeModel
model = GenerativeModel("gemini-1.5-flash-latest")

# WRONG - Don't use GPT-4 for ingestion tasks
from openai import OpenAI
client.chat.completions.create(model="gpt-4", ...)
```

### Existing Events Table Schema (Already Created)

**From [supabase/migrations/20260106000008_create_events_table.sql](../../supabase/migrations/20260106000008_create_events_table.sql):**

```sql
CREATE TABLE public.events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  document_id uuid REFERENCES public.documents(id) ON DELETE SET NULL,

  -- Event timing
  event_date date NOT NULL,
  event_date_precision text NOT NULL DEFAULT 'day'
    CHECK (event_date_precision IN ('day', 'month', 'year', 'approximate')),
  event_date_text text, -- Original date text from document

  -- Event details
  event_type text NOT NULL,  -- ← CLASSIFICATION TARGET
  description text NOT NULL,
  entities_involved uuid[], -- References to identity_nodes

  -- Source references
  source_page integer,
  source_bbox_ids uuid[],

  -- Confidence and metadata
  confidence float CHECK (confidence >= 0 AND confidence <= 1),
  is_manual boolean DEFAULT false,
  created_by uuid REFERENCES auth.users(id),

  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);
```

**Key insight:** Classification updates `event_type` from "raw_date" to classified types. Confidence field already exists for classification confidence.

### Previous Story Intelligence (Story 4-1)

**From Story 4-1 (Date Extraction with Gemini):**

Key patterns to follow:
1. **Service class pattern**: `DateExtractor` class with async/sync methods
2. **Prompt structure**: System prompt + user prompt template
3. **Retry logic**: MAX_RETRIES=3, exponential backoff
4. **Confidence scoring**: 0-1 range based on multiple factors
5. **Graceful degradation**: Return empty results on failure
6. **Job tracking integration**: Create job, update progress

**File created in Story 4-1:**
- `backend/app/engines/timeline/date_extractor.py` - Pattern to follow
- `backend/app/engines/timeline/prompts.py` - Prompt structure to follow
- `backend/app/models/timeline.py` - Models to extend
- `backend/app/services/timeline_service.py` - Service to extend

### Event Type Definitions (CRITICAL)

Define clear event types for Indian legal context:

| Type | Keywords | Examples |
|------|----------|----------|
| `filing` | filed, submitted, lodged, petition, complaint, appeal, application | "The petitioner filed this writ petition on..." |
| `notice` | notice, served, issued, received, demand notice, legal notice | "A demand notice was issued on..." |
| `hearing` | hearing, arguments, submissions, appearance, trial, proceedings | "The next date of hearing is..." |
| `order` | order, judgment, decree, ruling, decision, disposed | "The Hon'ble Court passed an order on..." |
| `transaction` | paid, received, transferred, executed, loan, payment | "The borrower paid Rs. 5,00,000 on..." |
| `document` | executed, signed, registered, notarized, agreement | "The agreement was executed on..." |
| `deadline` | limitation, deadline, due date, expiry, within | "The limitation period expired on..." |
| `unclassified` | N/A | Events with confidence < 0.7 |

### Indian Legal Terminology

Common terms to recognize:
- **Vakalatnama**: Power of attorney (filing)
- **Rejoinder**: Response to reply (filing)
- **Affidavit**: Sworn statement (document)
- **Lok Adalat**: People's court (hearing)
- **Stay**: Court stay order (order)
- **SARFAESI**: Recovery act provisions (various)
- **Section 138**: Cheque bounce cases (filing)
- **Limitation Act**: Time limit provisions (deadline)

### Classification Confidence Algorithm

**Factors:**
- Keyword presence: 0.5 weight
  - Exact match (e.g., "filed", "hearing"): +0.5
  - Related term: +0.3
  - No match: +0.0
- Context strength: 0.3 weight
  - Clear legal context: +0.3
  - Ambiguous context: +0.15
  - No context: +0.0
- Pattern recognition: 0.2 weight
  - Standard legal phrase: +0.2
  - Partial match: +0.1
  - No pattern: +0.0

**Thresholds:**
- confidence >= 0.7: Classified as detected type
- confidence < 0.7: Set to "unclassified", flag for review

### API Response Format (MANDATORY)

```python
# GET /api/matters/{matter_id}/timeline/events
{
  "data": [
    {
      "id": "uuid",
      "event_date": "2024-01-15",
      "event_date_precision": "day",
      "event_date_text": "15th January, 2024",
      "event_type": "filing",
      "description": "The petitioner filed this writ petition before the Hon'ble Court",
      "classification_confidence": 0.95,
      "document_id": "uuid",
      "source_page": 1,
      "verified": false
    }
  ],
  "meta": {
    "total": 45,
    "page": 1,
    "per_page": 20,
    "total_pages": 3
  }
}

# POST /api/matters/{matter_id}/timeline/classify
{
  "data": {
    "job_id": "uuid",
    "status": "queued",
    "events_to_classify": 150
  }
}

# GET /api/matters/{matter_id}/timeline/unclassified
{
  "data": [
    {
      "id": "uuid",
      "event_date": "2024-03-01",
      "event_type": "unclassified",
      "description": "Context that couldn't be classified",
      "classification_confidence": 0.45,
      "suggested_types": [
        {"type": "hearing", "confidence": 0.45},
        {"type": "filing", "confidence": 0.42}
      ]
    }
  ],
  "meta": {...}
}
```

### Git Intelligence

Recent commits:
```
fb04eff feat(timeline): implement date extraction with Gemini (Story 4-1)
9603017 fix(review): address cross-epic code review issues
68634fd fix(citation): address code review issues for Story 3-4
```

**Recommended commit message:** `feat(timeline): implement event classification with Gemini (Story 4-2)`

### File Organization

```
backend/app/
|-- engines/
|   |-- timeline/
|   |   |-- __init__.py                      (UPDATE - add classifier exports)
|   |   |-- date_extractor.py                (EXISTING)
|   |   |-- event_classifier.py              (NEW)
|   |   |-- prompts.py                       (EXISTING)
|   |   +-- classification_prompts.py        (NEW)
|-- models/
|   +-- timeline.py                          (UPDATE - add classification models)
|-- services/
|   +-- timeline_service.py                  (UPDATE - add classification methods)
|-- api/
|   +-- routes/
|       +-- timeline.py                      (UPDATE - add classification endpoints)
|-- workers/
|   +-- tasks/
|       +-- engine_tasks.py                  (UPDATE - add classification tasks)

backend/tests/
|-- engines/
|   +-- timeline/
|       |-- test_date_extractor.py           (EXISTING)
|       +-- test_event_classifier.py         (NEW)
|-- services/
|   +-- test_timeline_service.py             (UPDATE - add classification tests)
|-- api/
|   +-- test_timeline_routes.py              (UPDATE - add classification tests)
+-- integration/
    +-- test_classification_pipeline.py      (NEW)
```

### Dependencies

**Backend:**
```bash
# Already installed - uses existing google-generativeai package
# No new dependencies needed
```

### Manual Steps Required After Implementation

#### Migrations
- [ ] None - events table already has event_type column (20260106000008_create_events_table.sql)
- [ ] Add job type enum value if not using string job types:
  - Check if JobType enum needs EVENT_CLASSIFICATION added

#### Environment Variables
- [ ] Verify `GEMINI_API_KEY` is set (should already exist from Story 4-1)

#### Dashboard Configuration
- [ ] None - no dashboard changes needed

#### Manual Tests
- [ ] Upload test documents with various event types
- [ ] Run date extraction first (Story 4-1)
- [ ] Trigger classification via POST /api/matters/{matter_id}/timeline/classify
- [ ] Monitor job progress via processing_jobs table
- [ ] Verify GET /api/matters/{matter_id}/timeline/events returns classified events
- [ ] Check events table has updated event_type values:
  - Filing events correctly identified
  - Hearing events correctly identified
  - Low confidence events marked as unclassified
- [ ] Test manual classification via PATCH endpoint
- [ ] Verify unclassified events appear in /unclassified endpoint
- [ ] Test matter isolation - cannot view other matter's events

### Downstream Dependencies

This story enables:
- **Story 4-3 (Events Table + MIG):** Will link classified events to entities
- **Story 4-4 (Anomaly Detection):** Will use event types for sequence validation
- **Epic 10B (Timeline Tab):** Will display events by type with icons

### References

- [Source: architecture.md#Timeline-Construction-Engine] - Engine architecture
- [Source: epics.md#Story-4.2] - Story requirements and acceptance criteria
- [Source: Requirements-Baseline-v1.0.md#Timeline-Construction-Engine] - Business requirements
- [Source: project-context.md#LLM-Routing] - Gemini usage for ingestion
- [Source: backend/app/engines/timeline/date_extractor.py] - Pattern for Gemini service
- [Source: backend/app/engines/timeline/prompts.py] - Pattern for prompt structure
- [Source: supabase/migrations/20260106000008_create_events_table.sql] - Events table schema
- [Source: backend/app/services/timeline_service.py] - Existing service to extend
- [Source: backend/app/api/routes/timeline.py] - Existing routes to extend

### Project Structure Notes

- Event classifier in `engines/timeline/event_classifier.py` per existing pattern
- Classification prompts in `engines/timeline/classification_prompts.py`
- Extended models in `models/timeline.py`
- Extended service in `services/timeline_service.py`
- Extended API routes in `api/routes/timeline.py`
- Tests follow existing pattern in `tests/engines/timeline/`

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

1. Created comprehensive event classification system using Gemini 3 Flash for Indian legal documents
2. Implemented 8 event types: filing, notice, hearing, order, transaction, document, deadline, unclassified (+ raw_date)
3. Classification uses confidence threshold of 0.7 - events below are marked as unclassified
4. Added Indian legal terminology support (vakalatnama, rejoinder, Lok Adalat, SARFAESI, Section 138)
5. Integrated with date extraction pipeline via auto_classify parameter
6. Created comprehensive test suites for classifier, service, and API endpoints

### File List

**New Files Created:**
- `backend/app/engines/timeline/classification_prompts.py` - Classification prompt templates
- `backend/app/engines/timeline/event_classifier.py` - EventClassifier service with Gemini integration
- `backend/tests/engines/timeline/test_event_classifier.py` - Unit tests for classifier

**Files Modified:**
- `backend/app/engines/timeline/__init__.py` - Added classifier exports
- `backend/app/models/timeline.py` - Added EventType enum and classification models
- `backend/app/models/job.py` - Added EVENT_CLASSIFICATION job type
- `backend/app/services/timeline_service.py` - Added classification service methods
- `backend/app/workers/tasks/engine_tasks.py` - Added classification Celery tasks
- `backend/app/api/routes/timeline.py` - Added classification API endpoints
- `backend/tests/services/test_timeline_service.py` - Added classification service tests
- `backend/tests/api/routes/test_timeline.py` - Added classification API tests

