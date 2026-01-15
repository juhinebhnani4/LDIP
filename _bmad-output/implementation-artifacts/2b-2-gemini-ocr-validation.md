# Story 2B.2: Implement Gemini-Based OCR Validation

Status: done

## Story

As an **attorney**,
I want **low-confidence OCR results to be validated and corrected**,
So that **critical information like dates and amounts is accurate**.

## Acceptance Criteria

1. **Given** a word has confidence score < 85% **When** validation runs **Then** the word is flagged for Gemini validation **And** surrounding context is sent to Gemini for correction

2. **Given** a date or amount has low confidence **When** Gemini validates it **Then** pattern-based auto-correction is applied (e.g., "1O" → "10") **And** the corrected value replaces the original

3. **Given** a word has confidence score < 50% **When** validation runs **Then** the word is routed to a human review queue **And** marked as "requires_human_review"

4. **Given** Gemini validation completes **When** results are saved **Then** the validated text replaces the original **And** a validation_log records original, corrected, and confidence

## Tasks / Subtasks

- [x] Task 1: Create OCR Validation Models (AC: #1, #4)
  - [x] Create `backend/app/models/ocr_validation.py` with Pydantic models
  - [x] `LowConfidenceWord`: word, confidence, page, bbox_id, context_before, context_after
  - [x] `ValidationResult`: original, corrected, new_confidence, correction_type (gemini/pattern/human_required)
  - [x] `ValidationLog`: document_id, word_id, original, corrected, old_confidence, new_confidence, validation_type, timestamp
  - [x] `OCRValidationStatus`: pending_validation, validated, requires_human_review

- [x] Task 2: Create Low-Confidence Word Extractor (AC: #1, #3)
  - [x] Create `backend/app/services/ocr/validation_extractor.py`
  - [x] Implement `extract_low_confidence_words()` from bounding boxes table
  - [x] Configure confidence thresholds: `<85%` = needs_gemini, `<50%` = needs_human
  - [x] Extract surrounding context (50 characters) for each low-confidence word
  - [x] Group words by page for batch processing

- [x] Task 3: Implement Pattern-Based Auto-Correction (AC: #2)
  - [x] Create `backend/app/services/ocr/pattern_corrector.py`
  - [x] Implement common OCR error patterns:
    - "1O", "10" confusions (letter O vs zero)
    - "l" vs "1" in numeric contexts
    - "S" vs "5" in numeric contexts
    - "B" vs "8" in numeric contexts
    - Date format corrections (01/O2/2024 -> 01/02/2024)
    - Indian currency format (Rs. 1O,OOO -> Rs. 10,000)
  - [x] Implement `apply_pattern_corrections()` for date and amount patterns
  - [x] Return correction with type="pattern" when applied

- [x] Task 4: Create Gemini Validation Service (AC: #1, #2)
  - [x] Create `backend/app/services/ocr/gemini_validator.py`
  - [x] Implement `GeminiOCRValidator` class using Gemini 3 Flash
  - [x] Build validation prompt with:
    - Word to validate
    - Surrounding context
    - Document type hint (if available)
    - Legal document context
  - [x] Parse Gemini response for corrected text and confidence
  - [x] Implement batch validation for efficiency (up to 20 words per request)
  - [x] Handle rate limits and errors with retry logic

- [x] Task 5: Create Human Review Queue Service (AC: #3)
  - [x] Create `backend/app/services/ocr/human_review_service.py`
  - [x] Implement `HumanReviewService` for managing review queue
  - [x] Create methods: `add_to_queue()`, `get_pending_reviews()`, `submit_correction()`
  - [x] Store review items in `ocr_human_review` table (to be created)

- [x] Task 6: Create Database Migration for Validation Tables (AC: #3, #4)
  - [x] Create `supabase/migrations/20260108000001_create_ocr_validation_tables.sql`
  - [x] Create `ocr_validation_log` table with: id, document_id, bbox_id, original_text, corrected_text, old_confidence, new_confidence, validation_type, created_at
  - [x] Create `ocr_human_review` table with: id, document_id, matter_id, bbox_id, original_text, context, status (pending/completed/skipped), corrected_text, reviewed_by, reviewed_at
  - [x] Add RLS policies for matter isolation
  - [x] Add `validation_status` column to documents table

- [x] Task 7: Create OCR Validation Celery Task (AC: #1, #2, #3, #4)
  - [x] Update `backend/app/workers/tasks/document_tasks.py`
  - [x] Add `validate_ocr` Celery task that runs after `process_document`
  - [x] Task flow:
    1. Extract low-confidence words from bounding_boxes
    2. Apply pattern corrections first
    3. Send remaining < 85% words to Gemini
    4. Queue < 50% words for human review
    5. Update bounding_boxes with corrected text
    6. Log all validations to ocr_validation_log
    7. Update document validation_status
  - [x] Chain task: `process_document.s() | validate_ocr.s()`

- [x] Task 8: Update Document Upload to Chain Validation (AC: #1)
  - [x] Update `backend/app/api/routes/documents.py`
  - [x] Chain OCR + Validation tasks on upload
  - [x] Use Celery chain for: `process_document -> validate_ocr`

- [x] Task 9: Create Validation API Endpoints (AC: #3, #4)
  - [x] Create `backend/app/api/routes/ocr_validation.py`
  - [x] `GET /api/documents/{document_id}/validation-status` - Get validation status
  - [x] `GET /api/documents/{document_id}/validation-log` - Get validation history
  - [x] `GET /api/matters/{matter_id}/human-review` - Get pending human reviews
  - [x] `POST /api/matters/{matter_id}/human-review/{review_id}` - Submit human correction

- [x] Task 10: Write Backend Unit Tests
  - [x] Create `backend/tests/services/ocr/test_validation_extractor.py`
  - [x] Create `backend/tests/services/ocr/test_pattern_corrector.py`
  - [x] Create `backend/tests/services/ocr/test_gemini_validator.py` (mocked)
  - [x] Test confidence threshold logic
  - [x] Test pattern corrections for common OCR errors
  - [x] Test batch processing grouping

- [x] Task 11: Write Backend Integration Tests
  - [x] Create `backend/tests/integration/test_ocr_validation_integration.py`
  - [x] Test full validation pipeline: OCR -> Pattern -> Gemini -> Human Queue
  - [x] Test validation log creation
  - [x] Test chained task execution
  - [x] Mock Gemini API calls

## Dev Notes

### LLM Routing (CRITICAL - Per Architecture)

| Task | Model | Reason |
|------|-------|--------|
| OCR Validation | **Gemini 3 Flash** | Bulk, low-stakes, verifiable |
| Pattern Correction | None (regex) | No LLM needed |

**NEVER use GPT-4 for OCR post-processing** - it's 30x more expensive and overkill for this task.

### Gemini 3 Flash Configuration

**Python SDK:**
```python
import google.generativeai as genai
from app.core.config import get_settings

settings = get_settings()
genai.configure(api_key=settings.gemini_api_key)

model = genai.GenerativeModel('gemini-1.5-flash')  # or 'gemini-2.0-flash' when available

# Batch validation prompt
prompt = f"""You are an OCR validation assistant for legal documents.
Review these low-confidence OCR results and provide corrections.

Document context: Legal document (petition/appeal/annexure)
Language context: English with possible Hindi/Gujarati

Words to validate:
{words_with_context}

For each word, respond in JSON format:
[
  {{
    "index": 0,
    "original": "Rs. 1O,OOO",
    "corrected": "Rs. 10,000",
    "confidence": 0.95,
    "reasoning": "Common OCR error: O confused with 0"
  }}
]

Only correct if confident. If unsure, return original with lower confidence.
"""
```

**Batch Processing Strategy:**
- Group up to 20 words per Gemini request
- Include 50 chars context before and after each word
- Process pages in parallel using asyncio.gather

### Pattern Correction Rules

```python
# backend/app/services/ocr/pattern_corrector.py
COMMON_OCR_PATTERNS = [
    # Letter O vs Zero in numbers
    (r'(\d+)O(\d+)', r'\g<1>0\g<2>'),  # "1O0" -> "100"
    (r'O(\d)', r'0\g<1>'),              # "O5" -> "05"
    (r'(\d)O', r'\g<1>0'),              # "5O" -> "50"

    # Letter l vs digit 1
    (r'(\d)l(\d)', r'\g<1>1\g<2>'),    # "2l5" -> "215"

    # S vs 5 in amounts
    (r'Rs\.\s*S', r'Rs. 5'),            # "Rs. S" -> "Rs. 5"

    # Date patterns
    (r'(\d{1,2})[/\-]O(\d)', r'\g<1>/0\g<2>'),  # "12/O3" -> "12/03"

    # Indian currency patterns
    (r'Rs\.\s*([lI1])(\d)', r'Rs. 1\g<2>'),  # "Rs. l0" -> "Rs. 10"

    # Section references
    (r'Section\s+(\d+)\s*[O]', r'Section \g<1>('),  # "Section 13 O" -> "Section 13("
]

CRITICAL_PATTERNS = {
    'date': r'\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}',
    'amount': r'Rs\.?\s*[\d,lIO]+',
    'section': r'Section\s+\d+',
}
```

### Confidence Threshold Configuration

```python
# backend/app/core/config.py
class Settings(BaseSettings):
    # OCR Validation thresholds
    ocr_validation_gemini_threshold: float = 0.85  # Below this -> Gemini
    ocr_validation_human_threshold: float = 0.50   # Below this -> Human review
    ocr_validation_batch_size: int = 20            # Words per Gemini request

    # Gemini configuration
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
```

### Database Schema

**ocr_validation_log table:**
```sql
CREATE TABLE public.ocr_validation_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  bbox_id uuid REFERENCES public.bounding_boxes(id) ON DELETE SET NULL,
  original_text text NOT NULL,
  corrected_text text NOT NULL,
  old_confidence float,
  new_confidence float,
  validation_type text NOT NULL CHECK (validation_type IN ('pattern', 'gemini', 'human')),
  reasoning text,
  created_at timestamptz DEFAULT now()
);

-- Index for document lookups
CREATE INDEX idx_validation_log_document ON public.ocr_validation_log(document_id);

-- RLS Policy
ALTER TABLE public.ocr_validation_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users access own matter validation logs"
ON public.ocr_validation_log FOR ALL
USING (
  document_id IN (
    SELECT id FROM public.documents
    WHERE matter_id IN (
      SELECT matter_id FROM public.matter_members
      WHERE user_id = auth.uid()
    )
  )
);
```

**ocr_human_review table:**
```sql
CREATE TABLE public.ocr_human_review (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
  bbox_id uuid REFERENCES public.bounding_boxes(id) ON DELETE SET NULL,
  original_text text NOT NULL,
  context_before text,
  context_after text,
  page_number int NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'skipped')),
  corrected_text text,
  reviewed_by uuid REFERENCES auth.users(id),
  reviewed_at timestamptz,
  created_at timestamptz DEFAULT now()
);

-- Indexes
CREATE INDEX idx_human_review_matter_status ON public.ocr_human_review(matter_id, status);
CREATE INDEX idx_human_review_document ON public.ocr_human_review(document_id);

-- RLS Policy
ALTER TABLE public.ocr_human_review ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users access own matter human reviews"
ON public.ocr_human_review FOR ALL
USING (
  matter_id IN (
    SELECT matter_id FROM public.matter_members
    WHERE user_id = auth.uid()
  )
);
```

**Documents table addition:**
```sql
ALTER TABLE public.documents
ADD COLUMN validation_status text DEFAULT 'pending'
CHECK (validation_status IN ('pending', 'validated', 'requires_human_review'));
```

### Previous Story Intelligence

**FROM Story 2b-1 (Google Document AI OCR):**
- `OCRProcessor` in `backend/app/services/ocr/processor.py` - provides raw OCR results
- `OCRBoundingBox` model with confidence scores already extracted
- `bounding_boxes` table populated with text and confidence per block
- Celery task pattern with retry logic in `document_tasks.py`
- `DocumentStatus` enum includes `OCR_COMPLETE` which triggers validation

**Existing Code to Extend:**
- `backend/app/services/ocr/__init__.py` - add validation exports
- `backend/app/workers/tasks/document_tasks.py` - add validate_ocr task
- `backend/app/models/ocr.py` - validation models can extend these

**Pattern from 2b-1:**
```python
# Task chaining pattern (from 2b-1)
@celery_app.task(bind=True, autoretry_for=(...))
def process_document(self, document_id: str) -> dict:
    # ... process ...
    return {"status": "ocr_complete", "document_id": document_id}

# New pattern for chaining:
@celery_app.task(bind=True)
def validate_ocr(self, prev_result: dict, document_id: str | None = None) -> dict:
    doc_id = document_id or prev_result.get("document_id")
    # ... validate ...
```

### Git Intelligence

Recent commits from Story 2b-1:
```
200ff41 fix(ocr): address code review issues for Story 2b-1
7321212 feat(ocr): implement Google Document AI OCR integration (Story 2b-1)
```

**Files created in 2b-1 to reference:**
- `backend/app/services/ocr/processor.py` - OCRProcessor pattern
- `backend/app/services/ocr/bbox_extractor.py` - Bounding box handling
- `backend/app/models/ocr.py` - OCR models
- `backend/tests/services/ocr/` - Test patterns

**Recommended commit:** `feat(ocr): implement Gemini-based OCR validation (Story 2b-2)`

### Critical Architecture Constraints

**FROM PROJECT-CONTEXT.md - MUST FOLLOW EXACTLY:**

#### Backend Technology Stack
- **Python 3.12+** - use modern syntax (match statements, type hints)
- **FastAPI 0.115+** - async endpoints where beneficial
- **Pydantic v2** - use model_validator, not validator (v1 syntax)
- **structlog** for logging - NOT standard logging library
- **Celery + Redis** - for background tasks

#### API Response Format (MANDATORY)
```python
# Success
{ "data": { "document_id": "uuid", "validation_status": "validated" } }

# Error
{ "error": { "code": "VALIDATION_FAILED", "message": "...", "details": {} } }
```

#### Naming Conventions
| Layer | Convention | Example |
|-------|------------|---------|
| Python functions | snake_case | `validate_ocr_results`, `extract_low_confidence` |
| Python classes | PascalCase | `GeminiOCRValidator`, `ValidationResult` |
| Database columns | snake_case | `corrected_text`, `validation_type` |
| API endpoints | kebab-case in path | `/validation-log`, `/human-review` |

### File Organization

```
backend/app/
├── services/
│   └── ocr/
│       ├── __init__.py                    (UPDATE) - Export validation
│       ├── processor.py                   (EXISTING)
│       ├── bbox_extractor.py              (EXISTING)
│       ├── validation_extractor.py        (NEW) - Low-confidence extraction
│       ├── pattern_corrector.py           (NEW) - Pattern-based fixes
│       ├── gemini_validator.py            (NEW) - Gemini validation
│       └── human_review_service.py        (NEW) - Human review queue
├── models/
│   ├── ocr.py                             (EXISTING)
│   └── ocr_validation.py                  (NEW) - Validation models
├── workers/
│   └── tasks/
│       └── document_tasks.py              (UPDATE) - Add validate_ocr task
└── api/
    └── routes/
        ├── documents.py                   (UPDATE) - Chain validation
        └── ocr_validation.py              (NEW) - Validation endpoints

supabase/migrations/
└── YYYYMMDD_create_ocr_validation_tables.sql  (NEW)

backend/tests/
├── services/
│   └── ocr/
│       ├── test_validation_extractor.py   (NEW)
│       ├── test_pattern_corrector.py      (NEW)
│       └── test_gemini_validator.py       (NEW)
└── integration/
    └── test_ocr_validation_integration.py (NEW)
```

### Testing Guidance

#### Unit Tests (Mocked)

```python
# test_pattern_corrector.py
import pytest
from app.services.ocr.pattern_corrector import PatternCorrector, apply_pattern_corrections

def test_zero_o_confusion_in_amount():
    """Test O -> 0 correction in currency."""
    corrector = PatternCorrector()
    result = corrector.correct("Rs. 1O,OOO")
    assert result.corrected == "Rs. 10,000"
    assert result.correction_type == "pattern"

def test_date_format_correction():
    """Test date O -> 0 correction."""
    result = apply_pattern_corrections("O1/O2/2024")
    assert result.corrected == "01/02/2024"

def test_no_correction_when_valid():
    """Test no change for valid text."""
    result = apply_pattern_corrections("Rs. 10,000")
    assert result.corrected == "Rs. 10,000"
    assert result.correction_type is None

# test_gemini_validator.py
import pytest
from unittest.mock import Mock, patch
from app.services.ocr.gemini_validator import GeminiOCRValidator

@pytest.fixture
def mock_genai():
    with patch('google.generativeai.GenerativeModel') as mock:
        yield mock

@pytest.mark.asyncio
async def test_batch_validation(mock_genai):
    """Test Gemini batch validation."""
    mock_response = Mock()
    mock_response.text = '''[
        {"index": 0, "original": "1O", "corrected": "10", "confidence": 0.95}
    ]'''
    mock_genai.return_value.generate_content_async.return_value = mock_response

    validator = GeminiOCRValidator()
    words = [{"text": "1O", "confidence": 0.7, "context": "Amount: 1O lakhs"}]

    results = await validator.validate_batch(words)
    assert results[0].corrected == "10"
```

#### Integration Tests

```python
# test_ocr_validation_integration.py
@pytest.mark.asyncio
async def test_full_validation_pipeline(test_document_with_low_confidence):
    """Test OCR -> Pattern -> Gemini -> Human Queue pipeline."""
    # 1. Create document with known low-confidence text
    # 2. Run validation task
    # 3. Verify pattern corrections applied
    # 4. Verify Gemini was called for remaining
    # 5. Verify human queue populated for <50% confidence
    pass

@pytest.mark.asyncio
async def test_validation_log_created(test_document):
    """Test validation log entries created."""
    # Run validation
    # Check ocr_validation_log table
    pass
```

### Anti-Patterns to AVOID

```python
# WRONG: Using GPT-4 for OCR validation
model = openai.ChatCompletion.create(model="gpt-4", ...)

# CORRECT: Use Gemini Flash for bulk validation
model = genai.GenerativeModel('gemini-1.5-flash')

# WRONG: Processing one word at a time
for word in low_confidence_words:
    result = await gemini.validate(word)

# CORRECT: Batch processing
batches = chunk(low_confidence_words, size=20)
results = await asyncio.gather(*[gemini.validate_batch(b) for b in batches])

# WRONG: Not applying pattern corrections first
words = extract_low_confidence_words(document)
for word in words:
    result = await gemini.validate(word)  # Wasteful!

# CORRECT: Pattern first, then Gemini for remainder
words = extract_low_confidence_words(document)
pattern_corrected, remaining = apply_pattern_corrections(words)
if remaining:
    gemini_corrected = await gemini.validate_batch(remaining)

# WRONG: Blocking async in Celery
async def validate_ocr(document_id: str):
    ...  # Celery doesn't handle async directly

# CORRECT: Use sync wrapper or Celery-asyncio extension
def validate_ocr(document_id: str):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(_validate_ocr_async(document_id))
```

### Performance Considerations

- **Pattern corrections first:** O(1) regex vs O(n) API calls
- **Batch Gemini requests:** 20 words/request reduces API overhead
- **Parallel page processing:** Use asyncio.gather for multiple pages
- **Skip validation for high-confidence docs:** If overall_confidence > 95%, skip
- **Cache Gemini responses:** Same context patterns may repeat across documents

### Environment Variables Required

```bash
# backend/.env
GEMINI_API_KEY=your-gemini-api-key

# Optional tuning
OCR_VALIDATION_GEMINI_THRESHOLD=0.85
OCR_VALIDATION_HUMAN_THRESHOLD=0.50
OCR_VALIDATION_BATCH_SIZE=20
```

### Manual Steps Required After Implementation

#### Migrations
- [ ] Run: `supabase db push` or apply `YYYYMMDD_create_ocr_validation_tables.sql`

#### Environment Variables
- [ ] Add to `backend/.env`: `GEMINI_API_KEY=your-key` (from Google AI Studio)
- [ ] Optional: Add validation threshold overrides

#### Manual Tests
- [ ] Upload a PDF with low-quality scan (poor OCR confidence)
- [ ] Verify pattern corrections applied (check amounts like "Rs. 1O,OOO")
- [ ] Verify Gemini validation runs for <85% confidence words
- [ ] Verify human review queue populated for <50% confidence words
- [ ] Check validation log entries created

### Downstream Dependencies

This story creates the foundation for:
- **Story 2b-3 (OCR Quality Assessment):** Uses validation_status for quality display
- **Story 2b-5 (Parent-Child Chunking):** Uses validated text for chunking
- **Epic 3 (Citation Engine):** Uses validated text for accurate citation extraction

### Project Structure Notes

- Validation runs automatically after OCR via Celery task chain
- Human review queue is per-matter (attorneys only see their matters)
- Validation log provides audit trail for court-defensible accuracy
- Pattern corrections are deterministic and auditable

### References

- [Source: _bmad-output/architecture.md#LLM-Routing] - Gemini 3 Flash for OCR post-processing
- [Source: _bmad-output/project-context.md#LLM-Routing] - Never use GPT-4 for ingestion
- [Source: _bmad-output/project-planning-artifacts/epics.md#Story-2.5] - Acceptance criteria
- [Source: _bmad-output/implementation-artifacts/2b-1-google-document-ai-ocr.md] - Previous story patterns
- [Source: backend/app/services/ocr/processor.py] - OCRProcessor implementation
- [Source: backend/app/models/ocr.py] - OCR models to extend

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- All 11 tasks completed successfully
- Pattern corrections applied before Gemini validation to reduce API costs
- Celery task chaining implemented: process_document → validate_ocr
- Confidence thresholds: <85% → Gemini validation, <50% → Human review queue
- Uses Gemini 1.5 Flash per architecture LLM routing rules (NOT GPT-4)
- RLS policies added for matter isolation on all new tables
- Comprehensive unit and integration tests with mocked external services

### File List

**New Files Created:**
- `backend/app/models/ocr_validation.py` - Pydantic models for validation
- `backend/app/services/ocr/validation_extractor.py` - Low-confidence word extraction
- `backend/app/services/ocr/pattern_corrector.py` - Pattern-based auto-correction
- `backend/app/services/ocr/gemini_validator.py` - Gemini validation service
- `backend/app/services/ocr/human_review_service.py` - Human review queue
- `backend/app/api/routes/ocr_validation.py` - Validation API endpoints
- `supabase/migrations/20260108000001_create_ocr_validation_tables.sql` - Database migration
- `backend/tests/services/ocr/test_validation_extractor.py` - Unit tests
- `backend/tests/services/ocr/test_pattern_corrector.py` - Unit tests
- `backend/tests/services/ocr/test_gemini_validator.py` - Unit tests (mocked)
- `backend/tests/integration/test_ocr_validation_integration.py` - Integration tests

**Modified Files:**
- `backend/app/workers/tasks/document_tasks.py` - Added validate_ocr Celery task
- `backend/app/api/routes/documents.py` - Added Celery task chaining
- `backend/app/core/config.py` - Added Gemini and validation threshold settings
- `backend/app/services/ocr/__init__.py` - Exported validation components

