# Story 4.4: Implement Timeline Anomaly Detection

Status: dev-complete

## Story

As an **attorney**,
I want **unusual timeline patterns flagged automatically**,
So that **I notice potential issues like "9 months between notice and filing"**.

## Acceptance Criteria

1. **Given** a timeline is constructed **When** anomaly detection runs **Then** logical sequence violations are flagged (e.g., hearing before filing)

2. **Given** a notice period appears unusually long **When** detection runs **Then** a warning is generated: "Notice dated 9 months after borrower default - verify" **And** the anomaly appears in the attention banner

3. **Given** events are out of expected order **When** detection runs **Then** sequence violations are flagged with severity **And** explanations suggest possible causes (date error, exceptional circumstances)

4. **Given** an anomaly is detected **When** it is stored **Then** anomalies table contains: anomaly_id, matter_id, event_ids involved, anomaly_type, severity, explanation, verified

## Tasks / Subtasks

- [x] Task 1: Create Anomalies Database Table and Models (AC: #4)
  - [x] Create migration `supabase/migrations/20260114000003_create_anomalies_table.sql`
    - Table: `public.anomalies`
    - Columns:
      - `id` uuid PRIMARY KEY DEFAULT gen_random_uuid()
      - `matter_id` uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE
      - `anomaly_type` text NOT NULL (gap, sequence_violation, duplicate, outlier)
      - `severity` text NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical'))
      - `title` text NOT NULL (short description for UI)
      - `explanation` text NOT NULL (detailed explanation with suggested causes)
      - `event_ids` uuid[] NOT NULL (array of involved event UUIDs)
      - `expected_order` text[] (for sequence violations - expected event type order)
      - `actual_order` text[] (for sequence violations - actual event type order)
      - `gap_days` integer (for gap anomalies - number of days in gap)
      - `confidence` float DEFAULT 0.8 (confidence in anomaly detection)
      - `verified` boolean DEFAULT false (attorney verified)
      - `dismissed` boolean DEFAULT false (attorney dismissed as not an issue)
      - `verified_by` uuid REFERENCES auth.users(id)
      - `verified_at` timestamptz
      - `created_at` timestamptz DEFAULT now()
      - `updated_at` timestamptz DEFAULT now()
    - Indexes:
      - `idx_anomalies_matter_id` on `matter_id`
      - `idx_anomalies_severity` on `severity`
      - `idx_anomalies_type` on `anomaly_type`
    - RLS policy: Users can only access anomalies in their matters
  - [x] Create Pydantic models in `backend/app/models/anomaly.py`:
    - `AnomalyType` enum: GAP, SEQUENCE_VIOLATION, DUPLICATE, OUTLIER
    - `AnomalySeverity` enum: LOW, MEDIUM, HIGH, CRITICAL
    - `AnomalyBase`: Common fields
    - `AnomalyCreate`: For creating anomalies
    - `Anomaly`: Full model with id, timestamps
    - `AnomalyListItem`: For list responses
    - `AnomaliesListResponse`: API response with pagination
    - `AnomalyUpdateRequest`: For dismissing/verifying

- [x] Task 2: Create Anomaly Detection Engine (AC: #1, #2, #3)
  - [x] Create `backend/app/engines/timeline/anomaly_detector.py`
    - Class: `TimelineAnomalyDetector`
    - Method: `detect_anomalies(matter_id: str) -> list[AnomalyCreate]`
      - Load all classified events for matter
      - Run sequence validation
      - Run gap detection
      - Run duplicate detection
      - Run outlier detection
      - Return list of detected anomalies
    - Method: `detect_sequence_violations(events: list[TimelineEvent]) -> list[AnomalyCreate]`
      - Define expected legal workflow sequences:
        - FILING must come before HEARING
        - NOTICE should precede FILING (in SARFAESI cases)
        - ORDER follows HEARING
        - TRANSACTION typically before FILING (loan disbursement)
      - Compare actual event order against expected
      - Flag violations with severity based on impact
      - Generate explanation with possible causes
    - Method: `detect_gaps(events: list[TimelineEvent]) -> list[AnomalyCreate]`
      - Identify unusual time gaps between related events
      - Gap thresholds by event type pair:
        - NOTICE → FILING: >180 days is unusual, >365 days is high severity
        - FILING → HEARING: >90 days may indicate delays
        - HEARING → ORDER: >60 days is unusual
      - Calculate gap_days between consecutive events
      - Flag gaps exceeding thresholds
    - Method: `detect_duplicates(events: list[TimelineEvent]) -> list[AnomalyCreate]`
      - Find events on same date with similar descriptions
      - Use text similarity (Levenshtein) for description matching
      - Flag potential duplicates for review
    - Method: `detect_outliers(events: list[TimelineEvent]) -> list[AnomalyCreate]`
      - Find dates that seem statistically anomalous
      - Events far in the past or future relative to case timeline
      - Very old dates (>10 years before earliest filing)
      - Future dates (after current date)
    - Method: `_calculate_severity(anomaly_type: str, context: dict) -> AnomalySeverity`
      - GAP: based on gap_days and event types involved
      - SEQUENCE_VIOLATION: based on which events are out of order
      - DUPLICATE: typically LOW unless same event type
      - OUTLIER: based on how far out of range

- [x] Task 3: Create Anomaly Service for Database Operations (AC: #4)
  - [x] Create `backend/app/services/anomaly_service.py`
    - Class: `AnomalyService`
    - Method: `save_anomalies(anomalies: list[AnomalyCreate], matter_id: str) -> list[str]`
      - Insert anomalies to database
      - Return list of created anomaly IDs
    - Method: `get_anomalies_for_matter(matter_id: str, page: int, per_page: int) -> AnomaliesListResponse`
      - Get paginated anomalies for matter
      - Order by severity DESC, then created_at DESC
    - Method: `get_anomaly_by_id(anomaly_id: str, matter_id: str) -> Anomaly | None`
    - Method: `dismiss_anomaly(anomaly_id: str, matter_id: str, user_id: str) -> bool`
      - Set dismissed=true, verified_by, verified_at
    - Method: `verify_anomaly(anomaly_id: str, matter_id: str, user_id: str) -> bool`
      - Set verified=true, verified_by, verified_at
    - Method: `delete_anomalies_for_matter(matter_id: str) -> int`
      - Delete all anomalies (for reprocessing)
    - Method: `get_anomaly_summary(matter_id: str) -> dict`
      - Return counts by severity and type
      - For attention banner display

- [x] Task 4: Create Background Task for Anomaly Detection (AC: #1, #2, #3)
  - [x] Add to `backend/app/workers/tasks/engine_tasks.py`
    - Task: `detect_timeline_anomalies_task(matter_id: str, force_redetect: bool = False)`
      - Delete existing anomalies if force_redetect
      - Load timeline via TimelineBuilder
      - Run TimelineAnomalyDetector.detect_anomalies()
      - Save detected anomalies via AnomalyService
      - Update processing_jobs table
      - Invalidate timeline cache (anomalies affect display)
    - Task: `detect_anomalies_for_document_task(document_id: str, matter_id: str)`
      - Detect anomalies related to events from specific document
      - For incremental detection after new document upload
  - [ ] Integrate with timeline pipeline (DEFERRED - requires orchestration work):
    - After entity linking completes, queue anomaly detection
    - Pipeline: extraction → classification → entity linking → anomaly detection
    - NOTE: Currently anomaly detection is triggered manually via POST /api/matters/{matter_id}/anomalies/detect

- [x] Task 5: Create API Endpoints for Anomalies (AC: #1, #2, #3, #4)
  - [x] Create `backend/app/api/routes/anomalies.py`
    - `GET /api/matters/{matter_id}/anomalies`
      - List all anomalies for matter with pagination
      - Query params: severity, anomaly_type, dismissed, page, per_page
    - `GET /api/matters/{matter_id}/anomalies/{anomaly_id}`
      - Get single anomaly with full details
      - Include linked events with their details
    - `GET /api/matters/{matter_id}/anomalies/summary`
      - Return summary counts for attention banner
      - { high_count: 2, medium_count: 5, total: 10, unreviewed: 7 }
    - `POST /api/matters/{matter_id}/anomalies/detect`
      - Trigger anomaly detection job
      - Query param: force_redetect (default false)
      - Return job_id for progress tracking
    - `PATCH /api/matters/{matter_id}/anomalies/{anomaly_id}/dismiss`
      - Dismiss anomaly as not an issue
      - Attorney decision - not a real problem
    - `PATCH /api/matters/{matter_id}/anomalies/{anomaly_id}/verify`
      - Verify anomaly is a real issue
      - Marks for follow-up action
  - [x] Register routes in `backend/app/main.py` (anomalies router imported and registered)

- [x] Task 6: Define Legal Workflow Sequence Rules (AC: #1, #3)
  - [x] Create `backend/app/engines/timeline/legal_sequences.py`
    - Define legal workflow templates for different case types:
      - SARFAESI proceedings sequence
      - General civil suit sequence
      - Arbitration proceedings sequence
    - Class: `LegalSequenceValidator`
    - Method: `get_expected_sequence(case_type: str) -> list[EventType]`
      - Return expected event type order for case type
    - Method: `validate_sequence(events: list[TimelineEvent], case_type: str) -> list[SequenceViolation]`
      - Compare actual vs expected
      - Return violations with positions
    - SARFAESI expected sequence:
      1. TRANSACTION (loan disbursement/agreement)
      2. NOTICE (demand notice, 13(2) notice)
      3. FILING (possession application, DRAT appeal)
      4. HEARING (hearing dates)
      5. ORDER (possession order, tribunal order)
    - Gap thresholds as constants:
      ```python
      GAP_THRESHOLDS = {
          ("notice", "filing"): {"warning": 180, "critical": 365},
          ("filing", "hearing"): {"warning": 90, "critical": 180},
          ("hearing", "order"): {"warning": 60, "critical": 120},
          ("transaction", "notice"): {"warning": 365, "critical": 730},
      }
      ```

- [x] Task 7: Write Unit Tests for Anomaly Detector (AC: #1, #2, #3)
  - [x] Create `backend/tests/engines/timeline/test_anomaly_detector.py`
    - Test sequence violation detection
    - Test gap detection with various thresholds
    - Test duplicate detection
    - Test outlier detection
    - Test severity calculation
    - Test edge cases:
      - Empty timeline
      - Single event
      - All events on same date
      - Events with no classified type

- [x] Task 8: Write Service and API Tests (AC: #4)
  - [x] Create `backend/tests/services/test_anomaly_service.py`
    - Test CRUD operations
    - Test dismiss/verify functionality
    - Test summary generation
  - [x] Create `backend/tests/api/routes/test_anomalies.py`
    - Test all endpoints
    - Test pagination
    - Test filtering by severity/type
    - Test authorization (matter isolation)

- [x] Task 9: Write Integration Tests (AC: #1, #2, #3, #4)
  - [x] Create `backend/tests/integration/test_anomaly_detection_pipeline.py`
    - Test full pipeline: events → anomaly detection → storage
    - Test cache invalidation
    - Test incremental detection after new document
    - Verify anomaly-event relationships

## Dev Notes

### CRITICAL: Architecture Requirements

**From [architecture.md](../_bmad-output/architecture.md):**

This is **Story 4.4** of the **Timeline Construction Engine** (Epic 4). The complete engine flow is:

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
EVENTS TABLE + MIG INTEGRATION (Story 4-3) ✓ COMPLETED
  | Link events to canonical entities from MIG
  | Build timeline with entity context
  | Cache timeline for fast retrieval
  v
TIMELINE ANOMALY DETECTION (THIS STORY)
  | Flag sequence violations, gaps, duplicates
  | Calculate severity and suggest causes
  | Store anomalies for attorney review
```

### Timeline Builder Integration (CRITICAL)

**From [backend/app/engines/timeline/timeline_builder.py](../../backend/app/engines/timeline/timeline_builder.py):**

The `TimelineBuilder` class already provides:
- `build_timeline(matter_id)` → `ConstructedTimeline` with events, segments, entity_views, statistics
- `TimelineEvent` dataclass with: event_id, event_date, event_type, description, entities, confidence
- `TimelineStatistics` with: total_events, events_by_type, date_range_start, date_range_end

**Use TimelineBuilder to get events for anomaly detection:**

```python
from app.engines.timeline.timeline_builder import get_timeline_builder, TimelineEvent

builder = get_timeline_builder()
timeline = await builder.build_timeline(
    matter_id=matter_id,
    include_entities=True,
    include_raw_dates=False,  # Only classified events
    page=1,
    per_page=10000,  # Get all events
)

events = timeline.events  # list[TimelineEvent]
```

### Event Types (From Story 4-2)

**From [backend/app/models/timeline.py](../../backend/app/models/timeline.py):**

```python
class EventType(str, Enum):
    FILING = "filing"        # Court filings, petitions, appeals
    NOTICE = "notice"        # Demand notices, legal notices
    HEARING = "hearing"      # Court hearings, tribunal hearings
    ORDER = "order"          # Court orders, tribunal orders
    TRANSACTION = "transaction"  # Financial transactions, loan events
    DOCUMENT = "document"    # Document signing, submissions
    DEADLINE = "deadline"    # Statutory deadlines, limitation periods
    UNCLASSIFIED = "unclassified"  # Needs manual classification
    RAW_DATE = "raw_date"    # Pre-classification
```

### Anomaly Types to Detect

1. **SEQUENCE_VIOLATION**: Events out of expected legal workflow order
   - Example: "Hearing dated 2024-01-15 but Filing dated 2024-03-20"
   - Severity: HIGH if HEARING before FILING, MEDIUM if minor reordering

2. **GAP**: Unusual time gaps between related events
   - Example: "9 months between Demand Notice and Filing - verify if intentional"
   - Severity: Based on gap length and event types

3. **DUPLICATE**: Potential duplicate events
   - Example: "Two 'Filing' events on 2024-01-15 with similar descriptions"
   - Severity: LOW unless critical event type

4. **OUTLIER**: Statistically anomalous dates
   - Example: "Transaction dated 1990-01-01 appears 30 years before other events"
   - Severity: HIGH if date seems erroneous

### Severity Calculation Rules

```python
def calculate_severity(anomaly_type: AnomalyType, context: dict) -> AnomalySeverity:
    match anomaly_type:
        case AnomalyType.SEQUENCE_VIOLATION:
            # Critical legal workflow violations
            if context.get("events_swapped") in [
                ("hearing", "filing"),
                ("order", "filing"),
            ]:
                return AnomalySeverity.HIGH
            return AnomalySeverity.MEDIUM

        case AnomalyType.GAP:
            gap_days = context.get("gap_days", 0)
            if gap_days > 365:
                return AnomalySeverity.HIGH
            elif gap_days > 180:
                return AnomalySeverity.MEDIUM
            return AnomalySeverity.LOW

        case AnomalyType.DUPLICATE:
            if context.get("event_type") in ["filing", "order"]:
                return AnomalySeverity.MEDIUM
            return AnomalySeverity.LOW

        case AnomalyType.OUTLIER:
            years_off = context.get("years_off", 0)
            if years_off > 10:
                return AnomalySeverity.HIGH
            return AnomalySeverity.MEDIUM
```

### SARFAESI Legal Sequence (Indian Law Context)

For SARFAESI (Securitisation and Reconstruction of Financial Assets and Enforcement of Security Interest Act) proceedings:

1. **TRANSACTION**: Loan agreement, disbursement
2. **DEFAULT**: Borrower defaults (may not be an event)
3. **NOTICE**: 13(2) notice to borrower (60 days statutory period)
4. **NOTICE**: Reply from borrower (optional)
5. **FILING**: Possession application under 13(4)
6. **HEARING**: DRT/DRAT hearing
7. **ORDER**: Tribunal order

**Key statutory periods to check:**
- 13(2) notice must give 60 days minimum
- Appeal to DRAT within 30 days of DRT order
- Limitation period for recovery: 3 years from NPA date

### LLM Usage (NOT Required for Basic Detection)

**From [project-context.md](../_bmad-output/project-context.md):**

Anomaly detection should primarily use **rule-based algorithms**, NOT LLM:
- Sequence validation: Compare against predefined legal sequences
- Gap detection: Simple date arithmetic
- Duplicate detection: Text similarity (rapidfuzz)
- Outlier detection: Statistical analysis

LLM (Gemini Flash) may be used ONLY if needed for:
- Generating natural language explanations
- Identifying case type from document content

```python
# CORRECT - Rule-based detection
if event_a.event_type == "hearing" and event_b.event_type == "filing":
    if event_a.event_date < event_b.event_date:
        # This is a sequence violation

# WRONG - Don't use LLM for basic comparisons
response = await gemini.generate("Is hearing before filing a problem?")
```

### API Response Format (MANDATORY)

**From [project-context.md](../_bmad-output/project-context.md):**

```python
# GET /api/matters/{matter_id}/anomalies
{
  "data": [
    {
      "id": "uuid",
      "anomaly_type": "gap",
      "severity": "high",
      "title": "Unusual gap between Notice and Filing",
      "explanation": "274 days between Demand Notice (2023-05-10) and Filing (2024-02-10). This exceeds the typical 180-day threshold. Possible causes: negotiation period, borrower response pending, strategic delay.",
      "event_ids": ["event-uuid-1", "event-uuid-2"],
      "gap_days": 274,
      "confidence": 0.95,
      "verified": false,
      "dismissed": false,
      "created_at": "2026-01-13T10:00:00Z"
    }
  ],
  "meta": {
    "total": 7,
    "page": 1,
    "per_page": 20,
    "total_pages": 1
  }
}

# GET /api/matters/{matter_id}/anomalies/summary
{
  "data": {
    "total": 7,
    "by_severity": {
      "critical": 0,
      "high": 2,
      "medium": 3,
      "low": 2
    },
    "by_type": {
      "gap": 3,
      "sequence_violation": 2,
      "duplicate": 1,
      "outlier": 1
    },
    "unreviewed": 5,
    "verified": 1,
    "dismissed": 1
  }
}

# POST /api/matters/{matter_id}/anomalies/detect
{
  "data": {
    "job_id": "uuid",
    "status": "queued",
    "events_to_analyze": 45
  }
}
```

### Git Intelligence

Recent commits in timeline engine:
```
5a32ea3 fix(review): address code review issues for Story 4-3
55b2a61 feat(timeline): implement entity linking and timeline construction (Story 4-3)
7ea16a8 fix(review): address code review issues for Story 4-2
0533aff feat(timeline): implement event classification with Gemini (Story 4-2)
fb04eff feat(timeline): implement date extraction with Gemini (Story 4-1)
```

**Recommended commit message:** `feat(timeline): implement anomaly detection with sequence and gap validation (Story 4-4)`

### File Organization

```
backend/app/
|-- engines/
|   |-- timeline/
|   |   |-- __init__.py                      (UPDATE - add anomaly_detector, legal_sequences)
|   |   |-- date_extractor.py                (EXISTING)
|   |   |-- event_classifier.py              (EXISTING)
|   |   |-- entity_linker.py                 (EXISTING)
|   |   |-- timeline_builder.py              (EXISTING)
|   |   |-- anomaly_detector.py              (NEW)
|   |   |-- legal_sequences.py               (NEW)
|   |   |-- prompts.py                       (EXISTING)
|   |   +-- classification_prompts.py        (EXISTING)
|-- models/
|   |-- timeline.py                          (EXISTING)
|   +-- anomaly.py                           (NEW)
|-- services/
|   |-- timeline_service.py                  (EXISTING)
|   |-- timeline_cache.py                    (EXISTING)
|   +-- anomaly_service.py                   (NEW)
|-- api/
|   +-- routes/
|       |-- timeline.py                      (EXISTING)
|       +-- anomalies.py                     (NEW)
|-- workers/
|   +-- tasks/
|       +-- engine_tasks.py                  (UPDATE - add anomaly detection tasks)

supabase/migrations/
+-- 20260113000001_create_anomalies_table.sql (NEW)

backend/tests/
|-- engines/
|   +-- timeline/
|       |-- test_date_extractor.py           (EXISTING)
|       |-- test_event_classifier.py         (EXISTING)
|       |-- test_entity_linker.py            (EXISTING)
|       |-- test_timeline_builder.py         (EXISTING)
|       +-- test_anomaly_detector.py         (NEW)
|-- services/
|   |-- test_timeline_service.py             (EXISTING)
|   |-- test_timeline_cache.py               (EXISTING)
|   +-- test_anomaly_service.py              (NEW)
|-- api/
|   +-- routes/
|       |-- test_timeline.py                 (EXISTING)
|       +-- test_anomalies.py                (NEW)
+-- integration/
    |-- test_classification_pipeline.py      (EXISTING)
    |-- test_entity_linking_pipeline.py      (EXISTING)
    +-- test_anomaly_detection_pipeline.py   (NEW)
```

### Dependencies

**Backend:**
```bash
# Already installed - no new dependencies needed
# Uses existing:
# - rapidfuzz (text similarity for duplicate detection)
# - supabase (database access)
# - structlog (logging)
```

### Manual Steps Required After Implementation

#### Migrations
- [ ] Run: `supabase migration up` to create anomalies table
- [ ] Verify RLS policy is applied correctly

#### Environment Variables
- [ ] None - uses existing configuration

#### Dashboard Configuration
- [ ] None - no dashboard changes needed

#### Manual Tests
- [ ] Create a matter with timeline events from Stories 4-1, 4-2, 4-3
- [ ] Ensure events include intentional anomalies:
  - A HEARING event dated before FILING event
  - A large gap (>180 days) between NOTICE and FILING
  - Two events with similar descriptions on same date
- [ ] Trigger anomaly detection via POST /api/matters/{matter_id}/anomalies/detect
- [ ] Verify GET /api/matters/{matter_id}/anomalies returns detected anomalies
- [ ] Verify GET /api/matters/{matter_id}/anomalies/summary returns correct counts
- [ ] Test dismiss and verify actions
- [ ] Verify matter isolation - cannot view other matter's anomalies

### Downstream Dependencies

This story enables:
- **Epic 9 (Dashboard):** Anomaly count in matter cards
- **Epic 10B (Timeline Tab):** Anomaly indicators on timeline events
- **Epic 11 (Q&A Panel):** AI can reference anomalies in responses
- **Export Builder:** Include anomaly summary in reports

### Edge Cases to Handle

1. **No classified events:** Return empty anomalies list, not error
2. **Single event:** Cannot detect gaps or sequences
3. **All events unclassified:** Skip sequence validation, still check for duplicates/outliers
4. **Future dates:** Flag as OUTLIER with HIGH severity
5. **Very old dates (>30 years):** Flag as OUTLIER - likely OCR error
6. **Reprocessing:** When force_redetect=true, delete existing and re-detect all
7. **Incremental detection:** After new document, detect anomalies involving new events only

### Algorithm for Sequence Validation

```
1. LOAD expected sequence for case type (default: SARFAESI)
   - [transaction, notice, filing, hearing, order]

2. FILTER events to only sequenceable types (filing, notice, hearing, order, transaction)

3. SORT events by event_date ASC

4. FOR each pair of consecutive events (event_a, event_b):
   a. GET expected_position(event_a.event_type)
   b. GET expected_position(event_b.event_type)

   c. IF expected_position(event_b) < expected_position(event_a):
      - This is a sequence violation
      - Create anomaly with:
        - event_ids: [event_a.id, event_b.id]
        - expected_order: [event_b.event_type, event_a.event_type]
        - actual_order: [event_a.event_type, event_b.event_type]
        - explanation: "Event_B should occur before Event_A in standard legal workflow"
        - severity: calculate based on violation severity
```

### Algorithm for Gap Detection

```
1. SORT events by event_date ASC

2. DEFINE gap_thresholds for event type pairs:
   {
     ("notice", "filing"): {"warning": 180, "critical": 365},
     ("filing", "hearing"): {"warning": 90, "critical": 180},
     ("hearing", "order"): {"warning": 60, "critical": 120},
   }

3. FOR each pair of consecutive events (event_a, event_b):
   a. CALCULATE gap_days = (event_b.event_date - event_a.event_date).days

   b. LOOKUP threshold for (event_a.event_type, event_b.event_type)

   c. IF gap_days > threshold.critical:
      - Create HIGH severity gap anomaly
   ELIF gap_days > threshold.warning:
      - Create MEDIUM severity gap anomaly
```

### References

- [Source: architecture.md#Timeline-Construction-Engine] - Engine architecture
- [Source: epics.md#Story-4.4] - Story requirements and acceptance criteria
- [Source: Requirements-Baseline-v1.0.md#Timeline-Construction-Engine] - Business requirements
- [Source: project-context.md#LLM-Routing] - Rule-based preferred over LLM
- [Source: backend/app/engines/timeline/timeline_builder.py] - Timeline construction patterns
- [Source: backend/app/models/timeline.py] - EventType enum and models
- [Source: backend/app/services/timeline_service.py] - Database operation patterns
- [Source: supabase/migrations/20260106000008_create_events_table.sql] - Events table schema

### Project Structure Notes

- Anomaly detector in `engines/timeline/anomaly_detector.py` per existing engine pattern
- Legal sequence rules in `engines/timeline/legal_sequences.py` for maintainability
- Anomaly models in `models/anomaly.py` (new file, separate from timeline.py)
- Anomaly service in `services/anomaly_service.py` for database operations
- New API routes in `api/routes/anomalies.py` (not extending timeline.py)
- Tests follow existing pattern in `tests/engines/timeline/`

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

1. Implemented rule-based anomaly detection for timeline events
2. Created four detection algorithms: sequence violations, gap detection, duplicate detection, outlier detection
3. Legal workflow sequences defined for SARFAESI, civil suit, and arbitration proceedings
4. All 68 tests passing (31 unit, 10 service, 19 API, 8 integration) - NOTE: Increased from original 62 with code review fixes
5. Fixed deprecation warning for datetime.utcnow()
6. **Code Review Fixes (2026-01-14):**
   - Fixed route order conflict: moved `/summary` endpoint before `/{anomaly_id}` to avoid FastAPI path matching issue
   - Fixed datetime.now(tz=None) to use datetime.now(timezone.utc) for proper timezone-aware timestamps
   - Fixed deprecated asyncio.get_event_loop() pattern with asyncio.run() for sync wrappers
   - Added authenticated API tests with mocked auth for better coverage
   - Added edge case tests for UNCLASSIFIED event type handling
   - Fixed: Updated project-context.md to use correct `matter_attorneys` table name (was incorrectly `matter_members`)
   - Note: Pipeline integration (auto-trigger after entity linking) deferred - requires orchestration work

### File List

New files created:
- `supabase/migrations/20260114000003_create_anomalies_table.sql` - Database table and RLS policies
- `backend/app/models/anomaly.py` - Pydantic models for anomalies
- `backend/app/engines/timeline/anomaly_detector.py` - TimelineAnomalyDetector class
- `backend/app/engines/timeline/legal_sequences.py` - LegalSequenceValidator and rules
- `backend/app/services/anomaly_service.py` - AnomalyService for CRUD operations
- `backend/app/api/routes/anomalies.py` - API endpoints for anomalies
- `backend/tests/engines/timeline/test_anomaly_detector.py` - Unit tests
- `backend/tests/services/test_anomaly_service.py` - Service tests
- `backend/tests/api/routes/test_anomalies.py` - API tests
- `backend/tests/integration/test_anomaly_detection_pipeline.py` - Integration tests

Modified files:
- `backend/app/engines/timeline/__init__.py` - Export new classes
- `backend/app/workers/tasks/engine_tasks.py` - Added detect_timeline_anomalies task
- `backend/app/models/job.py` - Added ANOMALY_DETECTION job type
- `backend/app/main.py` - Registered anomalies router
