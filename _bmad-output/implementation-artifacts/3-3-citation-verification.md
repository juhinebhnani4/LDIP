# Story 3.3: Implement Citation Verification

Status: done

## Story

As an **attorney**,
I want **citations verified against the actual Act text**,
So that **I know if sections exist and quoted text is accurate**.

## Acceptance Criteria

1. **Given** a citation references Section 138 of NI Act **When** the NI Act is uploaded and indexed **Then** the system checks if Section 138 exists in the Act **And** verification_status is set to: verified, mismatch, section_not_found, or act_unavailable

2. **Given** a citation includes quoted text from the Act **When** verification runs **Then** the quoted text is compared against the actual Act text **And** mismatches are flagged with explanation

3. **Given** a citation references a section that doesn't exist **When** verification runs **Then** the citation is marked as "section_not_found" **And** a confidence score is assigned based on fuzzy matching

4. **Given** an Act is not uploaded **When** verification runs **Then** the citation is marked "Unverified - Act not provided" **And** verification can be completed later when Act is uploaded

## Tasks / Subtasks

- [x] Task 1: Create Citation Verification Service (AC: #1, #2, #3)
  - [x] Create `backend/app/engines/citation/verifier.py`
    - Implement `CitationVerifier` class
    - Method: `verify_citation(citation: Citation, act_document_id: str) -> VerificationResult`
      - Load Act document chunks from database
      - Find section in Act text using semantic + keyword search
      - Compare citation text against Act text
      - Calculate similarity score and confidence
      - Return verification result with status and explanation
    - Method: `find_section_in_act(act_name: str, section: str, chunks: list[Chunk]) -> SectionMatch | None`
      - Search Act chunks for section header/reference
      - Use regex patterns for section identification: `Section \d+`, `\d+\.`, etc.
      - Return matched text and location or None
    - Method: `compare_quoted_text(citation_quote: str, act_text: str) -> QuoteComparison`
      - Use sentence-level semantic similarity
      - Identify exact matches vs paraphrases vs mismatches
      - Return match percentage and diff explanation
    - Use Gemini 3 Flash for semantic comparison (per architecture - verification is extraction-adjacent)

- [x] Task 2: Create Verification Result Models (AC: #1, #2, #3)
  - [x] Update `backend/app/models/citation.py`
    - Add `VerificationResult` model:
      - `status: VerificationStatus` - verified, mismatch, section_not_found
      - `section_found: bool` - whether section was located in Act
      - `section_text: str | None` - matched section text from Act
      - `target_page: int | None` - page in Act document
      - `target_bbox_ids: list[str]` - bounding boxes in Act
      - `similarity_score: float` - semantic similarity (0-100)
      - `explanation: str` - human-readable verification explanation
      - `diff_details: DiffDetail | None` - specific text differences
    - Add `DiffDetail` model:
      - `citation_text: str` - text from case document
      - `act_text: str` - text from Act document
      - `match_type: str` - exact, paraphrase, mismatch
      - `differences: list[str]` - specific differences found
    - Add `SectionMatch` model:
      - `section_number: str`
      - `section_text: str`
      - `chunk_id: str`
      - `page_number: int`
      - `bbox_ids: list[str]`
      - `confidence: float`
    - Add `QuoteComparison` model:
      - `similarity_score: float`
      - `match_type: str`
      - `explanation: str`

- [x] Task 3: Create Act Text Indexing Service (AC: #1)
  - [x] Create `backend/app/engines/citation/act_indexer.py`
    - Implement `ActIndexer` class
    - Method: `index_act_document(document_id: str, matter_id: str) -> ActIndex`
      - Load all chunks from Act document
      - Build section index: { section_number: chunk_ids }
      - Extract section headers and boundaries
      - Store index in act_resolutions metadata
    - Method: `get_section_chunks(act_document_id: str, section: str) -> list[Chunk]`
      - Retrieve chunks containing the specified section
      - Order by page and position
    - Method: `extract_section_boundaries(chunks: list[Chunk]) -> list[SectionBoundary]`
      - Use regex to identify section numbers
      - Map section numbers to chunk IDs and page numbers
    - Cache section index per Act document

- [x] Task 4: Create Verification Prompts (AC: #2, #3)
  - [x] Create `backend/app/engines/citation/verification_prompts.py`
    - Define `SECTION_MATCHING_PROMPT` for finding sections
      - Input: section reference, Act chunks
      - Output: matched section text, confidence
    - Define `TEXT_COMPARISON_PROMPT` for quote verification
      - Input: citation quote, Act section text
      - Output: match type, similarity, explanation
    - Define `VERIFICATION_EXPLANATION_PROMPT` for generating explanations
      - Input: verification result
      - Output: human-readable explanation
    - Include few-shot examples for legal text comparison

- [x] Task 5: Implement Batch Verification Task (AC: #1, #4)
  - [x] Add `verify_citations` Celery task in `backend/app/workers/tasks/verification_tasks.py` (NEW FILE)
    - Task triggered when Act document is uploaded and marked as reference material
    - Method: `verify_citations_for_act(act_document_id: str, matter_id: str)`
      - Load all citations for the matter referencing this Act
      - Index the Act document sections
      - For each citation:
        - Find section in Act
        - Verify quoted text if present
        - Update citation record with verification result
      - Broadcast progress via `citations:{matter_id}` channel
    - Use job tracking pattern from Story 2c-3
    - Add to PIPELINE_STAGES: `citation_verification`

- [x] Task 6: Create Verification API Endpoints (AC: #1, #2, #3, #4)
  - [x] Update `backend/app/api/routes/citations.py`
    - `POST /api/matters/{matter_id}/citations/{citation_id}/verify` - Manually verify single citation
      - Request body: `{ actDocumentId: string }`
      - Triggers verification against specified Act
      - Returns VerificationResult
    - `POST /api/matters/{matter_id}/citations/verify-all` - Verify all citations for matter
      - Triggers batch verification for all available Acts
      - Returns task_id for progress tracking
    - `GET /api/matters/{matter_id}/citations/{citation_id}/verification` - Get verification details
      - Returns full verification result with explanation
    - Add `trigger_verification_for_act(act_name: str)` - Called when Act is uploaded

- [x] Task 7: Implement Act Upload Trigger (AC: #4)
  - [x] Update `backend/app/api/routes/citations.py`
    - Hook into `mark_act_uploaded` endpoint from Story 3-2
    - When Act is marked as uploaded:
      - Queue `verify_citations_for_act` task
      - Update citations from "act_unavailable" to "pending"
      - Broadcast status update via Realtime
  - [x] Update `backend/app/engines/citation/discovery.py`
    - Method: `trigger_verification_on_upload(matter_id: str, act_name: str, act_document_id: str)`
      - Queue verification task
      - Return task_id for tracking

- [x] Task 8: Create Frontend Verification Types (AC: #1, #2, #3)
  - [x] Update `frontend/src/types/citation.ts`
    - Add `VerificationResult` interface:
      - `status: VerificationStatus`
      - `sectionFound: boolean`
      - `sectionText: string | null`
      - `targetPage: number | null`
      - `targetBboxIds: string[]`
      - `similarityScore: number`
      - `explanation: string`
      - `diffDetails: DiffDetail | null`
    - Add `DiffDetail` interface:
      - `citationText: string`
      - `actText: string`
      - `matchType: 'exact' | 'paraphrase' | 'mismatch'`
      - `differences: string[]`
    - Add `VerifyCitationRequest` interface:
      - `actDocumentId: string`
    - Add `VerifyAllRequest` interface:
      - (empty - verifies all available Acts)

- [x] Task 9: Create Frontend Verification API Client (AC: #1, #2, #3)
  - [x] Update `frontend/src/lib/api/citations.ts`
    - `verifyCitation(matterId: string, citationId: string, actDocumentId: string): Promise<VerificationResult>`
    - `verifyAllCitations(matterId: string): Promise<{ taskId: string }>`
    - `getVerificationDetails(matterId: string, citationId: string): Promise<VerificationResult>`
    - `getCitationsForVerification(matterId: string, options?: { status?: VerificationStatus }): Promise<CitationsListResponse>`

- [x] Task 10: Create Real-Time Verification Updates (AC: #1, #4)
  - [x] Update `backend/app/services/pubsub_service.py`
    - Add `broadcast_verification_progress(matter_id, act_name, verified_count, total_count)`
    - Add `broadcast_citation_verified(matter_id, citation_id, status, explanation)`
  - [x] Update channel: `citations:{matter_id}`
    - Event: `verification_progress` - progress during batch verification
    - Event: `citation_verified` - single citation verification complete

- [x] Task 11: Write Backend Unit Tests
  - [x] Create `backend/tests/engines/citation/test_verifier.py`
    - Test section finding in Act text
    - Test quote comparison logic
    - Test verification status assignment
    - Test similarity scoring
    - Test edge cases: missing sections, partial matches
  - [x] Create `backend/tests/engines/citation/test_act_indexer.py`
    - Test section boundary extraction
    - Test section index building
    - Test chunk retrieval by section
  - [x] Update `backend/tests/api/routes/test_citations.py`
    - Test verify single citation endpoint
    - Test verify all citations endpoint
    - Test verification details endpoint

- [x] Task 12: Write Integration Tests
  - [x] Create `backend/tests/integration/test_citation_verification.py`
    - Test full verification pipeline
    - Test verification triggered by Act upload
    - Test status updates during verification
    - Test matter isolation for verification

## Dev Notes

### CRITICAL: Architecture Requirements (ADR-005)

**From [architecture.md#ADR-005](../_bmad-output/architecture.md):**

Citation Verification is the third stage of the Citation Engine flow:

```
CITATION EXTRACTION (Automatic) <- Story 3-1 DONE
  |
  v
ACT DISCOVERY REPORT (System -> User) <- Story 3-2 DONE
  |
  v
CITATION VERIFICATION (For Available Acts Only) <- THIS STORY
  | For each citation where Act is available:
  |   * Does section exist in Act?
  |   * Does quoted text match Act text?
  |   * Any misattribution detected?
  | For citations without Act:
  |   * Mark as "Unverified - Act not provided"
  v
CITATION FINDINGS
```

**Verification Depth (from architecture):**
- Level 1: Section exists in cited Act
- Level 2: Quoted text matches Act text (semantic comparison)
- Level 3: Proviso/exception correctly included (future enhancement)

### LLM Routing (MANDATORY per Architecture)

**Citation verification uses Gemini 3 Flash:**
- Verification is extraction-adjacent, downstream from initial extraction
- Errors are verifiable (attorney can review in split view)

From [project-context.md](../_bmad-output/project-context.md):
```
| Task | Model | Reason |
| Citation extraction | Gemini 3 Flash | Regex-augmented, errors caught in verification |
```

### Previous Story Intelligence

#### Story 3-1: Act Citation Extraction
**Key patterns from [3-1-act-citation-extraction.md](3-1-act-citation-extraction.md):**

1. **Database Schema (Already exists):**
   - `citations` table with `verification_status`, `target_act_document_id`, `target_page`, `target_bbox_ids`
   - `act_resolutions` table with `act_document_id` linking to uploaded Acts
   - Indexes on `verification_status` for filtering

2. **Existing Enums:**
   ```python
   class VerificationStatus(str, Enum):
       PENDING = "pending"
       VERIFIED = "verified"
       MISMATCH = "mismatch"
       SECTION_NOT_FOUND = "section_not_found"
       ACT_UNAVAILABLE = "act_unavailable"
   ```

3. **Citation Model Fields:**
   ```python
   target_act_document_id: str | None  # Linked Act document
   target_page: int | None             # Page in Act
   target_bbox_ids: list[str]          # Bounding boxes in Act
   confidence: float                   # Verification confidence
   ```

4. **Async/Sync Pattern:**
   ```python
   def _run_async(coro):
       loop = asyncio.new_event_loop()
       asyncio.set_event_loop(loop)
       try:
           return loop.run_until_complete(coro)
       finally:
           loop.close()
   ```

#### Story 3-2: Act Discovery Report UI
**Key patterns from [3-2-act-discovery-report-ui.md](3-2-act-discovery-report-ui.md):**

1. **Act Upload Flow:**
   - `markActUploaded(matterId, actName, documentId)` marks Act available
   - Triggers should queue verification for affected citations

2. **Real-Time Channel:**
   - Channel: `citations:{matter_id}`
   - Events: `citation_extraction_complete`, `act_discovery_update`
   - Add: `verification_progress`, `citation_verified`

3. **Frontend Types (Already exist in `types/citation.ts`):**
   ```typescript
   interface Citation {
     targetActDocumentId: string | null;
     targetPage: number | null;
     targetBboxIds: string[];
     verificationStatus: VerificationStatus;
   }
   ```

### Git Intelligence

Recent commits:
```
eb10100 feat(citation): implement Act Discovery Report UI (Story 3-2)
1fcf660 fix(async): use asyncio.to_thread for sync Supabase calls in async methods
d543898 feat(citation): implement Act citation extraction from case files (Story 3-1)
```

**Recommended commit message:** `feat(citation): implement citation verification against Act text (Story 3-3)`

### Section Finding Algorithm

**Strategy: Hybrid Regex + Semantic Search**

1. **Regex Patterns for Section Headers:**
   ```python
   SECTION_HEADER_PATTERNS = [
       r"^Section\s+(\d+(?:\([a-zA-Z0-9]+\))?)",  # "Section 138", "Section 138(1)"
       r"^(\d+)\.\s+",                             # "138. " at line start
       r"^\[Section\s+(\d+)\]",                    # "[Section 138]"
       r"^Sec\.\s*(\d+)",                          # "Sec. 138"
   ]
   ```

2. **Section Boundary Detection:**
   - Identify where sections start/end in Act text
   - Build index: `{ "138": { start_chunk, end_chunk, pages } }`

3. **Semantic Fallback:**
   - If regex fails, use embedding similarity to find relevant chunks
   - Query: "Section {number} of {act_name}"

### Quote Comparison Algorithm

**Strategy: Multi-Level Matching**

1. **Exact Match (100%):**
   - Normalize whitespace and punctuation
   - Direct string comparison

2. **Paraphrase Match (70-99%):**
   - Sentence embeddings comparison
   - Threshold: >85% similarity = paraphrase

3. **Semantic Match (50-69%):**
   - Key concepts present but different wording
   - Flag for manual review

4. **Mismatch (<50%):**
   - Significant differences in meaning
   - Mark as `mismatch` with explanation

### Verification Explanation Format

```json
{
  "status": "verified",
  "explanation": "Section 138 found on page 45 of Negotiable Instruments Act, 1881. The quoted text matches exactly with the Act text.",
  "diff_details": null
}

{
  "status": "mismatch",
  "explanation": "Section 138 found but quoted text differs from Act text. The citation quotes 'shall be punished with imprisonment' but the Act states 'shall be punished with imprisonment for a term'.",
  "diff_details": {
    "citation_text": "shall be punished with imprisonment",
    "act_text": "shall be punished with imprisonment for a term",
    "match_type": "mismatch",
    "differences": ["Missing phrase: 'for a term'"]
  }
}

{
  "status": "section_not_found",
  "explanation": "Section 138(5) not found in Negotiable Instruments Act, 1881. The Act contains Sections 1-147. Closest match: Section 138(1).",
  "diff_details": null
}
```

### API Response Format (MANDATORY)

```python
# Success - verification result
{
  "data": {
    "status": "verified",
    "section_found": true,
    "section_text": "Dishonour of cheque for insufficiency...",
    "target_page": 45,
    "target_bbox_ids": ["uuid1", "uuid2"],
    "similarity_score": 98.5,
    "explanation": "Section 138 verified. Quoted text matches Act text.",
    "diff_details": null
  }
}

# Success - batch verification task
{
  "data": {
    "task_id": "celery-task-uuid",
    "status": "processing",
    "total_citations": 23,
    "act_name": "Negotiable Instruments Act, 1881"
  }
}

# Error
{ "error": { "code": "ACT_NOT_UPLOADED", "message": "...", "details": {} } }
```

### Performance Considerations

- **Batch Processing:** Verify citations in batches of 10 (like extraction)
- **Section Index Caching:** Cache Act section indices in act_resolutions metadata
- **Rate Limiting:** 0.5s delay between Gemini API calls
- **Progress Updates:** Broadcast every 5 citations verified
- **Partial Recovery:** Track verified citations for failure recovery

### File Organization

```
backend/app/
├── engines/
│   └── citation/
│       ├── __init__.py                     (UPDATE - export verifier)
│       ├── verifier.py                     (NEW) - Citation verification
│       ├── act_indexer.py                  (NEW) - Act section indexing
│       ├── verification_prompts.py         (NEW) - Verification LLM prompts
│       ├── extractor.py                    (EXISTS)
│       ├── storage.py                      (UPDATE - verification methods)
│       ├── discovery.py                    (UPDATE - trigger verification)
│       └── prompts.py                      (EXISTS)
├── api/
│   └── routes/
│       └── citations.py                    (UPDATE - verification endpoints)
├── models/
│   └── citation.py                         (UPDATE - verification models)
├── workers/
│   └── tasks/
│       └── document_tasks.py               (UPDATE - verification task)
├── services/
│   └── pubsub_service.py                   (UPDATE - verification events)

frontend/src/
├── types/
│   └── citation.ts                         (UPDATE - verification types)
├── lib/
│   └── api/
│       └── citations.ts                    (UPDATE - verification API)

backend/tests/
├── engines/
│   └── citation/
│       ├── test_verifier.py                (NEW)
│       └── test_act_indexer.py             (NEW)
├── api/
│   └── test_citations.py                   (UPDATE)
└── integration/
    └── test_citation_verification.py       (NEW)
```

### Integration with Split-View (Story 3-4)

This story provides:
- `target_page` - Page in Act document for split view
- `target_bbox_ids` - Bounding boxes to highlight in Act
- `diff_details` - Text differences to show in UI

Story 3-4 will consume these to display:
- Left panel: Case document at `source_page` with `source_bbox_ids` highlighted
- Right panel: Act document at `target_page` with `target_bbox_ids` highlighted
- Diff overlay if `diff_details` present

### Error Handling

```python
class CitationVerificationError(Exception):
    """Base exception for verification errors."""
    pass

class ActNotIndexedError(CitationVerificationError):
    """Act document not yet indexed."""
    pass

class SectionNotFoundError(CitationVerificationError):
    """Section not found in Act document."""
    pass

class QuoteComparisonError(CitationVerificationError):
    """Error comparing quoted text."""
    pass
```

### Environment Variables

```bash
# Optional - tune verification behavior
VERIFICATION_BATCH_SIZE=10
VERIFICATION_RATE_LIMIT_DELAY=0.5
VERIFICATION_MIN_SIMILARITY=70
SECTION_SEARCH_TOP_K=5
```

### Dependencies

```bash
# No new dependencies - uses existing infrastructure
# - google-generativeai (Gemini)
# - sentence-transformers (optional, for local embeddings)
```

### Manual Steps Required After Implementation

#### Migrations
- [ ] None - schema already supports verification fields from Story 3-1

#### Environment Variables
- [ ] Optionally add verification tuning variables to backend `.env`

#### Dashboard Configuration
- [ ] None - no dashboard changes

#### Manual Tests
- [ ] Upload a case document with Act citations
- [ ] Upload the referenced Act document
- [ ] Mark Act as uploaded via Act Discovery modal
- [ ] Verify citations are automatically verified
- [ ] Test GET /api/matters/{id}/citations/{id}/verification endpoint
- [ ] Test manual verification via POST endpoint
- [ ] Verify "section_not_found" status for invalid sections
- [ ] Verify "mismatch" status for incorrect quotes
- [ ] Test batch verification via verify-all endpoint
- [ ] Verify matter isolation for verification results

### Downstream Dependencies

This story enables:
- **Story 3-4 (Split-View Highlighting):** Uses target_page and target_bbox_ids for split view
- **Citations Tab (Epic 10):** Shows verification status with visual indicators
- **Export Builder (Epic 12):** Includes verification confidence in exports

### References

- [Source: architecture.md#ADR-005] - Act Discovery architecture and verification depth
- [Source: architecture.md#Citation-Engine-Flow] - Verification pipeline
- [Source: project-context.md#LLM-Routing] - Gemini for verification
- [Source: epics.md#Story-3.3] - Story requirements
- [Source: 3-1-act-citation-extraction.md] - Extraction patterns and schema
- [Source: 3-2-act-discovery-report-ui.md] - Act upload trigger
- [Source: backend/app/models/citation.py] - Existing citation models
- [Source: frontend/src/types/citation.ts] - Frontend citation types
- [Source: backend/app/engines/citation/] - Existing citation engine code

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None

### Completion Notes List

1. **Verification Service**: Created `CitationVerifier` class using Gemini 3 Flash for semantic text comparison between citations and Act documents
2. **Act Indexing**: Created `ActIndexer` class with regex-based section boundary detection and in-memory caching
3. **Verification Prompts**: Created structured LLM prompts for section matching, text comparison, and explanation generation
4. **Celery Tasks**: Implemented batch verification with progress broadcasting and retry logic
5. **API Endpoints**: Added verification endpoints including batch verify, single verify, and mark-uploaded-and-verify
6. **Real-Time Updates**: Added pub/sub broadcasting for verification progress, individual citation verification, and completion events
7. **Frontend Types**: Added TypeScript interfaces for verification results, diff details, and events
8. **Frontend API Client**: Added API functions for triggering and monitoring verification
9. **Tests**: Created unit tests for verifier and act indexer, plus integration tests for full verification flow

### File List

**Created:**
- `backend/app/engines/citation/verification_prompts.py` - LLM prompts for verification
- `backend/app/engines/citation/act_indexer.py` - Act document section indexing service
- `backend/app/engines/citation/verifier.py` - Main citation verification service
- `backend/app/workers/tasks/verification_tasks.py` - Celery verification tasks
- `backend/tests/engines/citation/test_verifier.py` - Verifier unit tests
- `backend/tests/engines/citation/test_act_indexer.py` - Act indexer unit tests
- `backend/tests/engines/citation/test_verification_integration.py` - Integration tests

**Modified:**
- `backend/app/models/citation.py` - Added VerificationResult, DiffDetail, SectionMatch, QuoteComparison, BatchVerificationResponse models
- `backend/app/engines/citation/__init__.py` - Updated exports for new classes
- `backend/app/engines/citation/storage.py` - Added verification storage methods
- `backend/app/api/routes/citations.py` - Added verification API endpoints
- `backend/app/services/pubsub_service.py` - Added verification broadcasting functions
- `frontend/src/types/citation.ts` - Added verification types and events
- `frontend/src/lib/api/citations.ts` - Added verification API functions
- `frontend/src/types/index.ts` - Updated exports

### Code Review Fixes Applied (2026-01-13)

**HIGH Priority Issues Fixed:**
1. **HIGH-1**: Added missing API tests for verification endpoints in `test_citations.py`:
   - `TestVerifyCitationsBatchEndpoint` - batch verification tests
   - `TestVerifySingleCitationEndpoint` - single citation verification tests
   - `TestGetVerificationDetailsEndpoint` - GET /verification endpoint tests
   - `TestMarkActUploadedAndVerifyEndpoint` - combined upload+verify tests

2. **HIGH-2**: Added `GET /api/matters/{matter_id}/citations/{citation_id}/verification` endpoint in `citations.py` and `getVerificationDetails()` function in frontend `citations.ts`

3. **HIGH-3**: The `mark_act_uploaded_and_verify` endpoint properly triggers verification via `trigger_verification_on_act_upload.delay()`

4. **HIGH-4**: Added `trigger_verification_on_upload()` method to `discovery.py` per story spec

**MEDIUM Priority Issues Fixed:**
1. **MEDIUM-1**: Added `getCitationsForVerification()` convenience function to frontend API client
2. **MEDIUM-2**: Verified `VerificationResultResponse` is properly exported from `types/index.ts`
3. **MEDIUM-3**: Improved docstrings for `_run_async()` helper in both `document_tasks.py` and `verification_tasks.py` with proper documentation of asyncio pattern caveats
4. **MEDIUM-4**: Added `citation_verification` to `PIPELINE_STAGES` in `document_tasks.py`
5. **MEDIUM-5**: Added environment variable configuration in `config.py`:
   - `verification_batch_size` (default: 10)
   - `verification_rate_limit_delay` (default: 0.5s)
   - `verification_min_similarity` (default: 70.0)
   - `verification_section_search_top_k` (default: 5)

**LOW Priority Issues Fixed:**
1. **LOW-1**: Fixed deprecated `asyncio.get_event_loop()` pattern in `test_act_indexer.py` - converted to `@pytest.mark.asyncio` async tests
2. **LOW-2**: Added clarifying comment for similarity_score default (100.0) explaining it's intentional for section-only verification
3. **LOW-3**: Enhanced `_run_async()` docstrings with Args, Returns, Example, and Note sections

**Files Modified in Review:**
- `backend/tests/api/routes/test_citations.py` - Added verification endpoint tests
- `backend/app/api/routes/citations.py` - Added GET verification details endpoint
- `backend/app/engines/citation/discovery.py` - Added trigger_verification_on_upload method
- `backend/app/workers/tasks/document_tasks.py` - Added citation_verification to PIPELINE_STAGES, improved docstring
- `backend/app/workers/tasks/verification_tasks.py` - Improved _run_async docstring
- `backend/app/engines/citation/verifier.py` - Added config helper functions, improved similarity score comment
- `backend/app/core/config.py` - Added verification configuration settings
- `backend/tests/engines/citation/test_act_indexer.py` - Fixed deprecated asyncio patterns
- `frontend/src/lib/api/citations.ts` - Added getVerificationDetails and getCitationsForVerification functions
