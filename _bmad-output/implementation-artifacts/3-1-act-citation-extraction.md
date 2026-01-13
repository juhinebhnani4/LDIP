# Story 3.1: Implement Act Citation Extraction

Status: done

## Story

As an **attorney**,
I want **all Act citations automatically extracted from case documents**,
So that **I know which laws are referenced without reading everything**.

## Acceptance Criteria

1. **Given** a case document is processed **When** citation extraction runs **Then** citations like "Section 138 of the Negotiable Instruments Act, 1881" are identified **And** each citation is parsed into: act_name, section_number, subsection, clause

2. **Given** a citation uses abbreviations **When** extraction runs **Then** common abbreviations are recognized (e.g., "NI Act" = "Negotiable Instruments Act") **And** the full Act name is stored

3. **Given** citations are extracted **When** they are stored **Then** the citations table contains: citation_id, matter_id, document_id, page_number, bbox_ids, act_name, section_number, raw_text, verification_status

4. **Given** a document references multiple Acts **When** extraction completes **Then** all unique Acts are identified **And** a count of citations per Act is available

## Tasks / Subtasks

- [x] Task 1: Create Database Schema for Citations (AC: #3)
  - [x] Create Supabase migration for `citations` table
    - Columns: `id` (UUID PK), `matter_id` (FK), `document_id` (FK), `source_page` (int), `source_bbox_ids` (UUID[] - array of bounding box references), `act_name` (text - full normalized name), `act_name_original` (text - as extracted), `section_number` (text), `subsection` (text nullable), `clause` (text nullable), `raw_citation_text` (text - exact text from document), `quoted_text` (text nullable - any quoted text from Act), `verification_status` (enum: 'pending', 'verified', 'mismatch', 'section_not_found', 'act_unavailable'), `target_act_document_id` (UUID FK nullable - links to uploaded Act), `target_page` (int nullable), `target_bbox_ids` (UUID[] nullable), `confidence` (numeric 0-100), `extraction_metadata` (JSONB), `created_at`, `updated_at`
    - Add index on `(matter_id, act_name)` for Act Discovery queries
    - Add index on `(document_id, source_page)` for page-level queries
    - Add index on `verification_status` for filtering
  - [x] Create Supabase migration for `act_resolutions` table
    - Columns: `id` (UUID PK), `matter_id` (FK), `act_name_normalized` (text - e.g., "negotiable_instruments_act_1881"), `act_name_display` (text - "Negotiable Instruments Act, 1881"), `act_document_id` (UUID FK nullable - user uploaded Act), `resolution_status` (enum: 'available', 'missing', 'skipped'), `user_action` (enum: 'uploaded', 'skipped', 'pending'), `citation_count` (int - count of citations for this Act), `created_at`, `updated_at`
    - Unique constraint on `(matter_id, act_name_normalized)`
  - [x] Implement RLS policies for both tables (matter isolation per architecture)

- [x] Task 2: Create Citation Pydantic Models (AC: #1, #3)
  - [x] Create `backend/app/models/citation.py`
    - Define `VerificationStatus` enum: PENDING, VERIFIED, MISMATCH, SECTION_NOT_FOUND, ACT_UNAVAILABLE
    - Define `ActResolutionStatus` enum: AVAILABLE, MISSING, SKIPPED
    - Define `UserAction` enum: UPLOADED, SKIPPED, PENDING
    - Define `Citation` Pydantic model for API responses
    - Define `CitationCreate`, `CitationUpdate` models
    - Define `ActResolution` model for Act Discovery Report
    - Define `CitationExtractionResult` model for extraction output
    - Define `ActDiscoverySummary` model (act_name, citation_count, status)
  - [x] Update `backend/app/models/__init__.py` with exports

- [x] Task 3: Create Act Abbreviation Dictionary (AC: #2)
  - [x] Create `backend/app/engines/citation/abbreviations.py`
    - Comprehensive dictionary of Indian legal Act abbreviations
    - Include common variations and their canonical forms:
      - "NI Act" / "N.I. Act" -> "Negotiable Instruments Act"
      - "SARFAESI Act" / "SARFAESI" -> "Securitisation and Reconstruction of Financial Assets and Enforcement of Security Interest Act"
      - "IPC" -> "Indian Penal Code"
      - "BNS" -> "Bharatiya Nyaya Sanhita"
      - "BNSS" -> "Bharatiya Nagarik Suraksha Sanhita"
      - "CrPC" / "Cr.P.C." -> "Code of Criminal Procedure"
      - "CPC" / "C.P.C." -> "Code of Civil Procedure"
      - "IT Act" -> "Information Technology Act"
      - "Companies Act" -> "Companies Act"
      - "FEMA" -> "Foreign Exchange Management Act"
      - "GST Act" -> "Goods and Services Tax Act"
      - "Income Tax Act" / "I.T. Act" -> "Income Tax Act"
      - And 50+ more common Acts
    - Method: `normalize_act_name(raw_name: str) -> str`
    - Method: `get_canonical_name(abbreviated: str) -> str | None`
    - Method: `extract_year_from_name(act_name: str) -> int | None`

- [x] Task 4: Create Citation Extraction Prompts (AC: #1, #2)
  - [x] Create `backend/app/engines/citation/prompts.py`
    - Define `CITATION_EXTRACTION_PROMPT` for Gemini
    - Prompt should instruct LLM to:
      - Find ALL Act/statute citations in legal text
      - Extract: act_name, section, subsection, clause, quoted_text
      - Handle variations: "Section 138", "S. 138", "sec. 138", "u/s 138"
      - Handle ranges: "Sections 138-141", "Section 138 read with Section 139"
      - Handle provisos: "Proviso to Section 138"
      - Handle amendments: "Section 138 (as amended in 2018)"
      - Return structured JSON output
    - Include few-shot examples for common Indian legal citations

- [x] Task 5: Create Citation Extractor Service (AC: #1, #2, #4)
  - [x] Create `backend/app/engines/citation/__init__.py`
  - [x] Create `backend/app/engines/citation/extractor.py`
    - Implement `CitationExtractor` class
    - Method: `extract_from_text(text: str, document_id: str, matter_id: str, page_number: int) -> list[Citation]`
      - Uses Gemini 3 Flash (per architecture - ingestion tasks use Gemini)
      - Combines LLM extraction with regex patterns for reliability
      - Normalizes act names using abbreviation dictionary
      - Returns structured Citation objects
    - Method: `extract_from_chunk(chunk_id: str, content: str, ...) -> list[Citation]`
    - Method: `extract_from_document(document_id: str, matter_id: str) -> CitationExtractionResult`
      - Processes all chunks from a document
      - Deduplicates citations (same section, same act)
      - Aggregates unique Acts for discovery report
    - Include regex patterns for common citation formats:
      - `Section \d+(\(\d+\))?`
      - `u/s \d+`
      - `S\. \d+`
      - Act names with years: `[A-Z][a-z]+ Act,? \d{4}`

- [x] Task 6: Create Citation Storage Service (AC: #3, #4)
  - [x] Create `backend/app/engines/citation/storage.py`
    - Implement `CitationStorageService` class
    - Method: `save_citations(matter_id: str, citations: list[Citation]) -> int`
      - Saves extracted citations to database
      - Links to bounding boxes via source_bbox_ids
      - Returns count of saved citations
    - Method: `get_citations_by_document(document_id: str) -> list[Citation]`
    - Method: `get_citations_by_matter(matter_id: str) -> list[Citation]`
    - Method: `get_citation(citation_id: str) -> Citation | None`
    - Method: `update_act_resolution_counts(matter_id: str) -> None`
      - Updates citation_count in act_resolutions table
    - Method: `create_or_update_act_resolution(matter_id: str, act_name: str) -> ActResolution`
      - Creates act_resolution record if doesn't exist
      - Updates citation count if exists
    - Use RLS-enforced Supabase client

- [x] Task 7: Create Act Discovery Service (AC: #4)
  - [x] Create `backend/app/engines/citation/discovery.py`
    - Implement `ActDiscoveryService` class
    - Method: `get_discovery_report(matter_id: str) -> list[ActDiscoverySummary]`
      - Returns all Acts referenced in matter with counts and availability
      - Ordered by citation count (most referenced first)
    - Method: `mark_act_available(matter_id: str, act_name: str, document_id: str) -> ActResolution`
      - Called when user uploads an Act document
    - Method: `mark_act_skipped(matter_id: str, act_name: str) -> ActResolution`
      - Called when user chooses to skip an Act
    - Method: `get_missing_acts(matter_id: str) -> list[ActResolution]`
      - Returns Acts that are still missing

- [x] Task 8: Integrate Citation Extraction into Document Pipeline (AC: #1, #2, #3, #4)
  - [x] Create `backend/app/workers/tasks/citation_tasks.py`
    - Celery task: `extract_citations`
      - Runs after alias_resolution in pipeline (or parallel with it)
      - Processes all chunks from document
      - Extracts and stores citations
      - Updates act_resolutions with discovered Acts
      - Uses job tracking pattern from Story 2c-3
    - Add `citation_extraction` to PIPELINE_STAGES in document_tasks.py
    - Chain task after resolve_aliases (or configure parallel execution)
  - [x] Update `backend/app/workers/tasks/document_tasks.py`
    - Add citation extraction to pipeline chain
    - Option A: Chain after resolve_aliases (sequential)
    - Option B: Group with resolve_aliases (parallel) - recommended for performance

- [x] Task 9: Create Citation API Endpoints (AC: #3, #4)
  - [x] Create `backend/app/api/routes/citations.py`
    - `GET /api/matters/{matter_id}/citations` - List all citations for matter
      - Query params: `document_id`, `act_name`, `verification_status`, `page`, `per_page`
      - Response: paginated citation list
    - `GET /api/matters/{matter_id}/citations/{citation_id}` - Get single citation
      - Include: source location, raw text, verification status
    - `GET /api/matters/{matter_id}/citations/summary` - Get citation counts by Act
      - Response: list of {act_name, citation_count, verification_status}
    - `GET /api/matters/{matter_id}/act-discovery` - Get Act Discovery Report
      - Response: list of ActDiscoverySummary (for UI display)
  - [x] Register routes in `backend/app/main.py`
  - [x] Add auth dependency (matter access validation)

- [x] Task 10: Create Real-Time Citation Status Broadcasting (AC: #4)
  - [x] Update `backend/app/services/pubsub_service.py`
    - Add `broadcast_citation_extraction_progress(matter_id, document_id, progress)` function
    - Add `broadcast_act_discovery_update(matter_id, act_summary)` function
  - [x] Create citation progress channel: `citations:{matter_id}`
    - Sends: document_id, citations_found, unique_acts, progress_pct

- [x] Task 11: Create Frontend Types and API Client (AC: #3, #4)
  - [x] Create `frontend/src/types/citation.ts`
    - Define `VerificationStatus`, `ActResolutionStatus` enums
    - Define `Citation` interface with all fields
    - Define `ActDiscoverySummary` interface
    - Define `CitationSummary` interface (for list views)
    - Define `CitationsResponse` paginated response type
  - [x] Create `frontend/src/lib/api/citations.ts`
    - `getCitations(matterId, options): Promise<CitationsResponse>`
    - `getCitation(matterId, citationId): Promise<Citation>`
    - `getCitationSummary(matterId): Promise<CitationSummary[]>`
    - `getActDiscoveryReport(matterId): Promise<ActDiscoverySummary[]>`

- [x] Task 12: Write Backend Unit Tests
  - [x] Create `backend/tests/engines/citation/test_extractor.py`
    - Test citation pattern recognition
    - Test abbreviation expansion
    - Test section/subsection parsing
    - Test multi-Act extraction from single document
    - Test edge cases: ranges, provisos, amendments
  - [x] Create `backend/tests/engines/citation/test_abbreviations.py`
    - Test canonical name lookup
    - Test normalization
    - Test year extraction
  - [x] Create `backend/tests/engines/citation/test_storage.py`
    - Test citation save and retrieve
    - Test act resolution creation
    - Test matter isolation
  - [x] Create `backend/tests/api/routes/test_citations.py`
    - Test list citations endpoint
    - Test citation summary endpoint
    - Test act discovery endpoint
    - Test authorization

- [x] Task 13: Write Integration Tests
  - [x] Create `backend/tests/integration/test_citation_extraction.py`
    - Test full extraction pipeline with sample legal document
    - Test citation linking to bounding boxes
    - Test act discovery report generation
    - Test matter isolation for citations

## Dev Notes

### CRITICAL: Architecture Requirements (ADR-005)

**From [architecture.md](../_bmad-output/architecture.md#ADR-005):**

The Citation Engine uses "Act Discovery with User-Driven Resolution" pattern:

```
DOCUMENT UPLOAD
  │ User uploads case files (petition, reply, rejoinder, annexures)
  ▼
CITATION EXTRACTION (Automatic) ← THIS STORY
  │ System scans all case files for Act citations
  │ Output: List of {Act Name, Section, Page, BBox}
  ▼
ACT DISCOVERY REPORT (System → User) ← Story 3.2
  │ "Your case references 6 Acts. 2 available, 4 missing."
  ▼
CITATION VERIFICATION (For Available Acts Only) ← Story 3.3
```

**Data Model (from architecture):**
```sql
documents table:
  - document_type: 'case_file' | 'act' | 'annexure' | 'other'
  - is_reference_material: boolean (true for Acts)

citations table:
  - citation_id, matter_id
  - source_document_id (case file where citation found)
  - act_name (extracted: "SARFAESI Act")
  - section (extracted: "13(2)")
  - quoted_text (if quote exists in case file)
  - source_page, source_bbox_ids
  - verification_status: 'verified' | 'mismatch' | 'not_found' | 'act_unavailable'
  - target_act_document_id (nullable - links to uploaded Act)
  - target_page, target_bbox_ids (location in Act file)
  - confidence: 0-100

act_resolutions table:
  - matter_id
  - act_name_normalized (e.g., "sarfaesi_act_2002")
  - act_document_id (nullable - user uploaded)
  - resolution_status: 'available' | 'missing' | 'skipped'
  - user_action: 'uploaded' | 'skipped' | 'pending'
```

### LLM Routing (MANDATORY per Architecture)

**Citation extraction uses Gemini 3 Flash:**
- Ingestion/extraction tasks use Gemini (bulk, verifiable downstream)
- Never use GPT-4 for extraction (30x more expensive)

From [project-context.md](../_bmad-output/project-context.md):
```
| Task | Model | Reason |
| Citation extraction | Gemini 3 Flash | Regex-augmented, errors caught in verification |
```

### Previous Story Intelligence (Story 2c-3)

**Key patterns to follow from [2c-3-background-job-tracking.md](2c-3-background-job-tracking.md):**

1. **Job Tracking Integration:**
   - Add `citation_extraction` to PIPELINE_STAGES
   - Use `_update_job_stage_start()`, `_update_job_stage_complete()` helpers
   - Preserve partial progress for failure recovery

2. **Celery Task Pattern:**
   ```python
   @celery_app.task(
       name="app.workers.tasks.citation_tasks.extract_citations",
       bind=True,
       autoretry_for=(CitationExtractionError, ConnectionError),
       retry_backoff=True,
       retry_backoff_max=120,
       max_retries=3,
       retry_jitter=True,
   )
   def extract_citations(self, prev_result, document_id=None, ...):
       # Follow pattern from document_tasks.py
   ```

3. **Async-to-Sync Wrapper:**
   ```python
   def _run_async(coro):
       loop = asyncio.new_event_loop()
       asyncio.set_event_loop(loop)
       try:
           return loop.run_until_complete(coro)
       finally:
           loop.close()
   ```

### Git Intelligence

Recent commits:
```
ee2471e feat(jobs): implement background job status tracking and retry (Story 2c-3)
7685652 feat(mig): implement alias resolution for entity name variants (Story 2c-2)
f48a00e fix(mig): address code review issues for Story 2c-1
```

**Recommended commit message:** `feat(citation): implement Act citation extraction from case files (Story 3-1)`

### Indian Legal Citation Patterns

**Common formats to handle:**

1. **Standard section references:**
   - "Section 138 of the Negotiable Instruments Act, 1881"
   - "Section 138 N.I. Act"
   - "S. 138 NI Act"
   - "u/s 138 of NI Act"
   - "under Section 138"

2. **With subsections/clauses:**
   - "Section 138(1)(a)"
   - "Section 13(2) of SARFAESI Act"
   - "Section 2(h) of the Contract Act"

3. **Ranges and multiple sections:**
   - "Sections 138-141 of NI Act"
   - "Section 138 read with Section 139"
   - "Sections 138, 139 and 141"

4. **Provisos and explanations:**
   - "Proviso to Section 138"
   - "Explanation to Section 138(1)"

5. **With amendments:**
   - "Section 138 (as amended in 2018)"
   - "Section 138 (substituted by Act 20 of 2002)"

### Regex Patterns for Extraction

```python
CITATION_PATTERNS = [
    # Section X of Act Name, Year
    r"[Ss]ection\s+(\d+(?:\(\d+\))?(?:\([a-z]\))?)\s+(?:of\s+(?:the\s+)?)?([A-Z][A-Za-z\s]+(?:Act|Code|Rules)),?\s*(\d{4})?",

    # S. X / Sec. X patterns
    r"[Ss](?:ec)?\.?\s*(\d+(?:\(\d+\))?)\s+(?:of\s+)?([A-Z][A-Za-z\s]+(?:Act|Code))",

    # u/s X patterns
    r"u/s\s*\.?\s*(\d+(?:\(\d+\))?)\s+(?:of\s+)?([A-Z][A-Za-z\s]+)",

    # Section ranges
    r"[Ss]ections?\s+(\d+)\s*[-–to]\s*(\d+)\s+(?:of\s+)?([A-Z][A-Za-z\s]+)",

    # Read with patterns
    r"[Ss]ection\s+(\d+)\s+read\s+with\s+[Ss]ection\s+(\d+)",
]
```

### NFR Compliance

**From architecture - NFR8:** Citation extraction recall > 95%

To achieve this:
1. Combine LLM extraction with regex patterns
2. Use multiple passes if needed
3. Log extraction confidence for monitoring
4. Include comprehensive test cases

### File Organization

```
backend/app/
├── engines/
│   └── citation/                           (NEW)
│       ├── __init__.py                     (NEW) - Module exports
│       ├── extractor.py                    (NEW) - Citation extraction
│       ├── storage.py                      (NEW) - Database operations
│       ├── discovery.py                    (NEW) - Act Discovery service
│       ├── abbreviations.py                (NEW) - Abbreviation dictionary
│       └── prompts.py                      (NEW) - LLM prompts
├── api/
│   └── routes/
│       ├── __init__.py                     (UPDATE - add citations router)
│       └── citations.py                    (NEW) - Citation API endpoints
├── models/
│   ├── __init__.py                         (UPDATE - export citation models)
│   └── citation.py                         (NEW) - Citation Pydantic models
├── workers/
│   └── tasks/
│       ├── document_tasks.py               (UPDATE - add citation stage)
│       └── citation_tasks.py               (NEW) - Citation extraction task

frontend/src/
├── types/
│   ├── citation.ts                         (NEW) - Citation TypeScript types
│   └── index.ts                            (UPDATE - export citation types)
├── lib/
│   └── api/
│       └── citations.ts                    (NEW) - Citation API client

supabase/migrations/
├── xxx_create_citations_table.sql          (NEW)
└── xxx_create_act_resolutions_table.sql    (NEW)

backend/tests/
├── engines/
│   └── citation/
│       ├── test_extractor.py               (NEW)
│       ├── test_abbreviations.py           (NEW)
│       └── test_storage.py                 (NEW)
├── api/
│   └── test_citations.py                   (NEW)
└── integration/
    └── test_citation_extraction.py         (NEW)
```

### API Response Format (MANDATORY)

```python
# Success - citation list
{
  "data": [
    {
      "id": "uuid",
      "matter_id": "uuid",
      "document_id": "uuid",
      "act_name": "Negotiable Instruments Act, 1881",
      "section_number": "138",
      "subsection": "1",
      "raw_citation_text": "Section 138(1) of the NI Act",
      "source_page": 15,
      "source_bbox_ids": ["uuid1", "uuid2"],
      "verification_status": "pending",
      "confidence": 95
    }
  ],
  "meta": {
    "total": 45,
    "page": 1,
    "per_page": 20
  }
}

# Success - act discovery report
{
  "data": [
    {
      "act_name": "Negotiable Instruments Act, 1881",
      "act_name_normalized": "negotiable_instruments_act_1881",
      "citation_count": 23,
      "resolution_status": "missing",
      "user_action": "pending"
    }
  ]
}

# Error
{ "error": { "code": "CITATION_NOT_FOUND", "message": "...", "details": {} } }
```

### RLS Policy Template (MANDATORY)

```sql
CREATE POLICY "Users can only access citations in their matters"
ON citations FOR ALL
USING (
  matter_id IN (
    SELECT matter_id FROM matter_members
    WHERE user_id = auth.uid()
  )
);

CREATE POLICY "Users can only access act_resolutions in their matters"
ON act_resolutions FOR ALL
USING (
  matter_id IN (
    SELECT matter_id FROM matter_members
    WHERE user_id = auth.uid()
  )
);
```

### Performance Considerations

- **Batch processing:** Extract citations in batches of 10 chunks (like entity extraction)
- **Rate limiting:** 0.5s delay between Gemini API calls
- **Caching:** Cache abbreviation dictionary in memory
- **Parallel extraction:** Consider running citation extraction parallel with alias resolution
- **Partial progress:** Track processed chunks for failure recovery

### Dependencies

```bash
# No new dependencies - uses existing Gemini/LLM infrastructure
```

### Environment Variables

```bash
# Optional - tune extraction behavior
CITATION_EXTRACTION_BATCH_SIZE=10
CITATION_EXTRACTION_RATE_LIMIT_DELAY=0.5
CITATION_MIN_CONFIDENCE=70
```

### Manual Steps Required After Implementation

#### Migrations
- [ ] Run: `supabase migration up` for citations and act_resolutions tables

#### Environment Variables
- [ ] Optionally add citation extraction tuning variables to backend `.env`

#### Dashboard Configuration
- [ ] No dashboard changes required

#### Manual Tests
- [ ] Upload a case document with known citations
- [ ] Verify citations are extracted and stored
- [ ] Verify all unique Acts appear in act_resolutions table
- [ ] Test GET /api/matters/{id}/citations endpoint
- [ ] Test GET /api/matters/{id}/act-discovery endpoint
- [ ] Verify citation counts match expectations
- [ ] Test abbreviation expansion (NI Act -> Negotiable Instruments Act)
- [ ] Test section/subsection parsing
- [ ] Verify matter isolation for citations

### Downstream Dependencies

This story enables:
- **Story 3.2 (Act Discovery Report UI):** Displays extracted Acts and their status
- **Story 3.3 (Citation Verification):** Verifies extracted citations against Acts
- **Story 3.4 (Split-View Highlighting):** Links citations to source locations
- **Story 9.4 (Upload Flow):** Shows Act Discovery modal after upload

### Project Structure Notes

- Citation Engine is one of 3 MVP AI engines (per architecture)
- Uses Gemini 3 Flash for extraction (cost optimization)
- Citations are per-matter (RLS enforced)
- Integrates with existing document processing pipeline
- Bounding box linking enables click-to-highlight in UI

### References

- [Source: architecture.md#ADR-005] - Act Discovery architecture
- [Source: architecture.md#Citation-Engine-Flow] - Extraction pipeline
- [Source: project-context.md#LLM-Routing] - Gemini for citation extraction
- [Source: epics.md#Story-3.1] - Story requirements
- [Source: 2c-3-background-job-tracking.md] - Job tracking patterns
- [Source: document_tasks.py] - Pipeline integration pattern

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List
