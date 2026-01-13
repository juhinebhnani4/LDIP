# Story 4.1: Implement Date Extraction with Gemini

Status: completed

## Story

As an **attorney**,
I want **all dates extracted from documents with surrounding context**,
So that **I can understand what happened and when**.

## Acceptance Criteria

1. **Given** a document is processed **When** date extraction runs via Gemini **Then** dates are extracted in various formats (DD/MM/YYYY, Month DD, YYYY, etc.) **And** plus/minus 200 words of surrounding context are captured

2. **Given** a date is ambiguous (e.g., 01/02/2024) **When** extraction runs **Then** context is used to determine DD/MM vs MM/DD **And** if uncertain, a date_ambiguity flag is set

3. **Given** a date is extracted **When** it is stored **Then** the raw_events table contains: event_id, matter_id, document_id, page_number, extracted_date, date_confidence, context_text, bbox_ids

4. **Given** multiple dates appear in close proximity **When** extraction runs **Then** each date is extracted separately **And** context distinguishes their purposes

## Tasks / Subtasks

- [x] Task 1: Create Timeline Engine Directory Structure (AC: #3)
  - [x] Create `backend/app/engines/timeline/__init__.py`
  - [x] Create `backend/app/engines/timeline/prompts.py` for Gemini extraction prompts
  - [x] Create `backend/app/engines/timeline/date_extractor.py` - main extraction service
  - [x] Export timeline engine components from engines/__init__.py

- [x] Task 2: Implement Gemini Date Extraction Prompts (AC: #1, #2, #4)
  - [x] Create `backend/app/engines/timeline/prompts.py`
    - DATE_EXTRACTION_SYSTEM_PROMPT: Define extraction requirements
      - Support multiple date formats (DD/MM/YYYY, DD-MM-YYYY, Month DD YYYY, DD Month YYYY, etc.)
      - Require plus/minus 200 word context window
      - Handle Indian date conventions (DD/MM priority over MM/DD)
      - Specify output JSON schema
    - DATE_EXTRACTION_USER_PROMPT: Template for document text
    - Include examples of expected extractions
  - [x] Handle ambiguous date detection and flagging
  - [x] Define date_precision values: day, month, year, approximate

- [x] Task 3: Create Date Extraction Service (AC: #1, #2, #3, #4)
  - [x] Create `backend/app/engines/timeline/date_extractor.py`
    - Class: `DateExtractor`
    - Method: `extract_dates_from_text(text: str, document_id: str, matter_id: str, page_number: int | None) -> DateExtractionResult`
    - Use Gemini 3 Flash (per LLM routing rules - ingestion task, NOT user-facing)
    - Implement retry logic with exponential backoff (MAX_RETRIES=3)
    - Handle rate limits gracefully
    - Parse LLM JSON response into structured data
    - Calculate confidence scores based on:
      - Date format clarity
      - Context availability
      - Ambiguity presence
  - [x] Implement batch processing for large documents
    - Process in chunks of 30,000 characters max (per MIG extractor pattern)
    - Aggregate results across chunks
    - Handle overlapping context for boundary dates

- [x] Task 4: Create Pydantic Models for Date Extraction (AC: #3)
  - [x] Create `backend/app/models/timeline.py`
    - `ExtractedDate` model:
      - extracted_date: date
      - date_text: str (original text, e.g., "on or about March 2023")
      - date_precision: Literal["day", "month", "year", "approximate"]
      - context_before: str (up to 200 words before)
      - context_after: str (up to 200 words after)
      - page_number: int | None
      - bbox_ids: list[str]
      - is_ambiguous: bool
      - ambiguity_reason: str | None (e.g., "DD/MM vs MM/DD uncertain")
      - confidence: float
    - `DateExtractionResult` model:
      - dates: list[ExtractedDate]
      - document_id: str
      - matter_id: str
      - total_dates_found: int
      - processing_time_ms: int

- [x] Task 5: Create Database Service for Raw Events (AC: #3)
  - [x] Create `backend/app/services/timeline_service.py`
    - Method: `save_extracted_dates(matter_id: str, document_id: str, dates: list[ExtractedDate]) -> list[str]`
      - Insert into existing `events` table (migration already exists)
      - Map ExtractedDate to events table columns:
        - event_date = extracted_date
        - event_date_precision = date_precision
        - event_date_text = date_text
        - description = context (combined before/after)
        - source_page = page_number
        - source_bbox_ids = bbox_ids
        - confidence = confidence
        - event_type = "raw_date" (pre-classification)
      - Return list of inserted event IDs
    - Method: `get_raw_dates_for_document(document_id: str) -> list[Event]`
    - Method: `get_timeline_for_matter(matter_id: str) -> list[Event]`
    - All methods use RLS via Supabase client (4-layer isolation)

- [x] Task 6: Create Background Task for Date Extraction (AC: #1)
  - [x] Add to `backend/app/workers/tasks/engine_tasks.py`
    - Task: `extract_dates_from_document(document_id: str, matter_id: str)`
      - Load document text from chunks table
      - Call DateExtractor.extract_dates_from_text
      - Save results via timeline_service
      - Update processing_jobs table with status
      - Use job tracking pattern from Story 2c-3
  - [x] Task: `extract_dates_from_matter(matter_id: str)`
    - Queue date extraction for all case file documents
    - Skip already processed documents
    - Track overall progress

- [x] Task 7: Create API Endpoints for Date Extraction (AC: #3)
  - [x] Add to `backend/app/api/routes/timeline.py`
    - `POST /api/matters/{matter_id}/timeline/extract`
      - Trigger date extraction for all/specified documents
      - Return job_id for progress tracking
    - `GET /api/matters/{matter_id}/timeline/raw-dates`
      - Return all extracted dates (pre-classification)
      - Support filtering: ?document_id=xxx, ?page=N
      - Use pagination (page, per_page)
    - `GET /api/matters/{matter_id}/timeline/raw-dates/{event_id}`
      - Return single extracted date with full context
    - All endpoints require matter membership (RLS + API middleware)

- [x] Task 8: Integrate with Document Processing Pipeline (AC: #1)
  - [x] Date extraction available as on-demand API trigger
  - [x] Only processes case_file documents (not Acts)
  - [x] Tracked via processing_jobs with job tracking integration

- [x] Task 9: Handle Indian Date Formats and Context (AC: #1, #2)
  - [x] Add Indian date format patterns to prompts:
    - DD/MM/YYYY (primary Indian format)
    - DD-MM-YYYY
    - DD.MM.YYYY
    - "dated X of Y" format
    - Legal date formats: "this X day of Y, 20XX"
  - [x] Add context-based disambiguation rules:
    - If document is from India, prefer DD/MM
    - If month name present, use as anchor
    - If year > 2000 and first number > 12, it's day

- [x] Task 10: Write Unit Tests for Date Extraction (AC: #1, #2, #4)
  - [x] Create `backend/tests/engines/timeline/test_date_extractor.py`
    - Test various date format extractions
    - Test ambiguous date handling
    - Test context window extraction
    - Test multiple dates in proximity
    - Test Indian date format priority
    - Mock Gemini API calls

- [x] Task 11: Write Service Tests (AC: #3)
  - [x] Create `backend/tests/services/test_timeline_service.py`
    - Test save_extracted_dates
    - Test get_raw_dates_for_document
    - Test get_timeline_for_matter
  - [x] Create `backend/tests/api/routes/test_timeline.py`
    - Test POST extract endpoint
    - Test GET raw-dates endpoint
    - Test pagination

- [x] Task 12: Write Integration Tests
  - [x] API route tests created in `backend/tests/api/routes/test_timeline.py`
  - [x] Service tests verify events table population

## Dev Notes

### CRITICAL: Architecture Requirements

**From [architecture.md](../_bmad-output/architecture.md):**

This is **Story 4.1** of the **Timeline Construction Engine** (Epic 4). The engine flow is:

```
DATE EXTRACTION (THIS STORY)
  | Extract dates with context from all case files
  | Store as "raw_date" events for classification
  v
EVENT CLASSIFICATION (Story 4-2)
  | Classify dates by type (filing, notice, hearing, etc.)
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
| Date extraction | **Gemini 3 Flash** | Bulk ingestion, verifiable downstream |
| NOT GPT-4 | - | Would be 30x more expensive |

```python
# CORRECT - Use Gemini for date extraction
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
  event_type text NOT NULL,
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

**Key insight:** Use `event_type = 'raw_date'` for this story. Story 4-2 will classify these into specific types.

### Previous Story Intelligence

**From Story 3-4 (Split-View Citation Highlighting):**

Key patterns to follow:
1. **Canvas overlay for bbox highlighting** (not DOM elements)
2. **Service pattern with async methods**
3. **Job tracking integration** (Story 2c-3)
4. **RLS enforcement via Supabase client**

**From MIG Entity Extractor ([backend/app/services/mig/extractor.py](../../backend/app/services/mig/extractor.py)):**

Pattern to follow for Gemini extraction:
- MAX_RETRIES = 3
- INITIAL_RETRY_DELAY = 1.0
- MAX_TEXT_LENGTH = 30000
- Use `structlog` for logging
- Wrap Gemini calls in try/except with retry logic
- Parse JSON response with error handling

### Git Intelligence

Recent commits:
```
9603017 fix(review): address cross-epic code review issues
68634fd fix(citation): address code review issues for Story 3-4
3f99375 feat(citation): implement split-view citation highlighting (Story 3-4)
```

**Recommended commit message:** `feat(timeline): implement date extraction with Gemini (Story 4-1)`

### Date Format Priorities (Indian Legal Context)

**Priority order for ambiguous dates:**
1. If month name present (January, Jan, etc.) - use directly
2. If format has year first (2024-01-02) - ISO format, unambiguous
3. If in DD/MM/YYYY or DD-MM-YYYY format - Indian standard
4. If first number > 12 - must be day
5. If second number > 12 - must be day
6. If document metadata indicates India - prefer DD/MM
7. Otherwise - flag as ambiguous

**Common Indian legal date patterns:**
- "dated this 5th day of January, 2024"
- "dated 05/01/2024"
- "dated 05.01.2024"
- "on or about January 2024" (month precision)
- "in the year 2024" (year precision)
- "circa 2020" (approximate precision)

### Context Window Extraction

**Requirements:**
- Extract 200 words BEFORE the date
- Extract 200 words AFTER the date
- Preserve sentence boundaries where possible
- Include page number reference
- Link to bounding boxes if available

**Implementation:**
```python
def extract_context_window(
    text: str,
    date_position: int,
    window_words: int = 200
) -> tuple[str, str]:
    """Extract context before and after date position."""
    words = text.split()
    # Find word index containing date_position
    # Extract window_words before and after
    ...
```

### Confidence Scoring Algorithm

**Factors:**
- Date format clarity: 0.3 weight
  - Named month: +0.3
  - ISO format: +0.3
  - Unambiguous DD/MM: +0.2
  - Ambiguous: +0.0
- Context quality: 0.4 weight
  - Full 200-word window: +0.4
  - Partial window: +0.2
  - No context: +0.0
- OCR confidence (from source): 0.3 weight
  - >90%: +0.3
  - 70-90%: +0.2
  - <70%: +0.1

**Final score:** Weighted sum, capped at 1.0

### API Response Format (MANDATORY)

```python
# GET /api/matters/{matter_id}/timeline/raw-dates
{
  "data": [
    {
      "id": "uuid",
      "event_date": "2024-01-15",
      "event_date_precision": "day",
      "event_date_text": "dated 15th January, 2024",
      "description": "...context text...",
      "document_id": "uuid",
      "source_page": 45,
      "confidence": 0.92,
      "is_ambiguous": false
    }
  ],
  "meta": {
    "total": 150,
    "page": 1,
    "per_page": 20,
    "total_pages": 8
  }
}

# POST /api/matters/{matter_id}/timeline/extract
{
  "data": {
    "job_id": "uuid",
    "status": "queued",
    "documents_to_process": 5
  }
}
```

### File Organization

```
backend/app/
|-- engines/
|   |-- timeline/
|   |   |-- __init__.py                  (NEW)
|   |   |-- date_extractor.py            (NEW)
|   |   +-- prompts.py                   (NEW)
|-- models/
|   +-- timeline.py                      (NEW)
|-- services/
|   +-- timeline_service.py              (NEW)
|-- api/
|   +-- routes/
|       +-- timeline.py                  (NEW)
|-- workers/
|   +-- tasks/
|       |-- engine_tasks.py              (UPDATE - add date extraction task)
|       +-- document_tasks.py            (UPDATE - trigger date extraction)

backend/tests/
|-- engines/
|   +-- timeline/
|       |-- test_date_extractor.py       (NEW)
|       +-- test_prompts.py              (NEW)
|-- services/
|   +-- test_timeline_service.py         (NEW)
|-- api/
|   +-- test_timeline_routes.py          (NEW)
+-- integration/
    +-- test_date_extraction_pipeline.py (NEW)
```

### Dependencies

**Backend:**
```bash
# Already installed - uses existing google-generativeai package
# No new dependencies needed
```

### Manual Steps Required After Implementation

#### Migrations
- [ ] None - events table already exists (20260106000008_create_events_table.sql)

#### Environment Variables
- [ ] Verify `GEMINI_API_KEY` is set (should already exist from MIG extraction)

#### Dashboard Configuration
- [ ] None - no dashboard changes needed

#### Manual Tests
- [ ] Upload a test document with various date formats
- [ ] Trigger date extraction via POST /api/matters/{matter_id}/timeline/extract
- [ ] Monitor job progress via processing_jobs table
- [ ] Verify GET /api/matters/{matter_id}/timeline/raw-dates returns extracted dates
- [ ] Check events table has correct data:
  - event_date matches extracted dates
  - event_date_precision is appropriate
  - context_text includes surrounding words
  - confidence scores are reasonable
- [ ] Test with ambiguous dates (e.g., 01/02/2024)
- [ ] Verify is_ambiguous flag set appropriately
- [ ] Test matter isolation - cannot view other matter's dates

### Downstream Dependencies

This story enables:
- **Story 4-2 (Event Classification):** Will classify raw_date events by type
- **Story 4-3 (Events Table + MIG):** Will link events to entities
- **Story 4-4 (Anomaly Detection):** Will flag timeline issues
- **Epic 10B (Timeline Tab):** Will display timeline visualization

### References

- [Source: architecture.md#Timeline-Construction-Engine] - Engine architecture
- [Source: epics.md#Story-4.1] - Story requirements and acceptance criteria
- [Source: Requirements-Baseline-v1.0.md#Timeline-Construction-Engine] - Business requirements
- [Source: project-context.md#LLM-Routing] - Gemini usage for ingestion
- [Source: backend/app/services/mig/extractor.py] - Pattern for Gemini extraction
- [Source: supabase/migrations/20260106000008_create_events_table.sql] - Events table schema
- [Source: backend/app/models/entity.py] - Pattern for Pydantic models
- [Source: backend/app/services/job_tracking/tracker.py] - Job tracking pattern

### Project Structure Notes

- Timeline engine in `engines/timeline/` per architecture patterns
- Services in `services/timeline_service.py` following existing service patterns
- API routes in `api/routes/timeline.py` following FastAPI conventions
- Tests co-located with source in `tests/engines/timeline/`

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- Implemented complete Timeline Engine date extraction functionality
- Used Gemini 3 Flash for date extraction (per LLM routing rules)
- Comprehensive prompts for Indian legal date formats and ambiguity detection
- Service follows existing MIG extractor patterns
- API endpoints follow FastAPI conventions
- Job tracking integration for progress monitoring
- All acceptance criteria met

### File List

**Created:**
- `backend/app/engines/timeline/__init__.py` - Timeline engine module exports
- `backend/app/engines/timeline/prompts.py` - Gemini date extraction prompts
- `backend/app/engines/timeline/date_extractor.py` - DateExtractor service
- `backend/app/models/timeline.py` - Pydantic models for timeline data
- `backend/app/services/timeline_service.py` - Database service for events
- `backend/app/api/routes/timeline.py` - API endpoints
- `backend/tests/engines/timeline/__init__.py` - Test package
- `backend/tests/engines/timeline/test_date_extractor.py` - Unit tests
- `backend/tests/services/test_timeline_service.py` - Service tests
- `backend/tests/api/routes/test_timeline.py` - API tests

**Modified:**
- `backend/app/engines/__init__.py` - Added timeline engine exports
- `backend/app/models/job.py` - Added DATE_EXTRACTION job type
- `backend/app/workers/tasks/engine_tasks.py` - Added date extraction tasks
- `backend/app/main.py` - Registered timeline router
