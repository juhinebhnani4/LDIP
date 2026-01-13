# Story 2B.3: Display OCR Quality Assessment

Status: review
<!-- Code complete, manual steps pending + deferred test tasks - see Tasks 13-14 and "Manual Steps" section -->

## Story

As an **attorney**,
I want **to see OCR quality metrics before relying on extracted text**,
So that **I know if a document needs manual review due to poor scan quality**.

## Acceptance Criteria

1. **Given** OCR completes for a document **When** I view the document in the Documents tab **Then** I see an OCR quality indicator (Good >85%, Fair 70-85%, Poor <70%) **And** the indicator is based on average word confidence across all pages

2. **Given** a document has Poor OCR quality (<70% confidence) **When** processing completes **Then** a warning badge appears on the document row **And** a tooltip explains "Low OCR confidence - some text may be inaccurate"

3. **Given** I click on a Poor quality document **When** the detail view opens **Then** I see a page-by-page breakdown of confidence scores **And** pages with <60% confidence are highlighted **And** I see a "Request Manual Review" button

4. **Given** I click "Request Manual Review" **When** the dialog opens **Then** I can flag specific pages for manual transcription **And** those pages are added to a review queue **And** the document status shows "Partial - awaiting manual review"

## Tasks / Subtasks

- [x] Task 1: Add OCR Confidence Columns to Documents Table (AC: #1)
  - [x] Create migration `supabase/migrations/20260108000002_add_ocr_quality_columns.sql`
  - [x] Add `ocr_confidence_per_page` jsonb column (array of page confidence scores)
  - [x] Add `ocr_quality_status` column ('good', 'fair', 'poor', null)
  - [x] Add index on `ocr_quality_status` for filtering
  - Note: `ocr_confidence` already exists from Story 2b-1, used as the average

- [x] Task 2: Create OCR Confidence Calculator Service (AC: #1)
  - [x] Create `backend/app/services/ocr/confidence_calculator.py`
  - [x] Create `backend/app/models/ocr_confidence.py` for result models
  - [x] Implement `calculate_document_confidence(document_id: str) -> OCRConfidenceResult`
  - [x] Implement `update_document_confidence(document_id: str) -> OCRConfidenceResult`
  - [x] Query bounding_boxes table for all word confidence scores
  - [x] Calculate average confidence per page
  - [x] Calculate overall document average confidence
  - [x] Determine quality status based on thresholds (>85% Good, 70-85% Fair, <70% Poor)
  - [x] Return structured result with page-by-page breakdown

- [x] Task 3: Update Document Processing Pipeline (AC: #1)
  - [x] Update `backend/app/workers/tasks/document_tasks.py`
  - [x] Add `calculate_confidence` Celery task
  - [x] Chain: `process_document -> validate_ocr -> calculate_confidence`
  - [x] Update `backend/app/api/routes/documents.py` to include new task in chain

- [x] Task 4: Create OCR Quality API Endpoints (AC: #1, #3)
  - [x] Add `GET /api/documents/{document_id}/ocr-quality` endpoint
  - [x] Update `GET /api/documents/{document_id}` to include OCR quality fields
  - [x] Return confidence scores, quality status, and page-level details

- [x] Task 5: Create OCRQualityBadge Component (AC: #1, #2)
  - [x] Create `frontend/src/components/features/document/OCRQualityBadge.tsx`
  - [x] Display colored badge: Green (Good >85%), Yellow (Fair 70-85%), Red (Poor <70%)
  - [x] Include optional percentage text
  - [x] Handle null/pending state (OCR not yet complete)

- [x] Task 6: Update DocumentList to Show OCR Quality (AC: #1, #2)
  - [x] Update `frontend/src/components/features/document/DocumentList.tsx`
  - [x] Add OCR Quality column after Status column
  - [x] Display `OCRQualityBadge` for each document

- [x] Task 7: Create OCRQualityDetail Component (AC: #3)
  - [x] Create `frontend/src/components/features/document/OCRQualityDetail.tsx`
  - [x] Display per-page confidence grid
  - [x] Highlight pages with <60% confidence in red
  - [x] Show overall summary statistics

- [x] Task 8: Create ManualReviewDialog Component (AC: #4)
  - [x] Create `frontend/src/components/features/document/ManualReviewDialog.tsx`
  - [x] Show list of pages with checkboxes
  - [x] Pre-select option for pages with <60% confidence
  - [x] Allow user to toggle page selection
  - [x] "Request Review" button submits to API

- [x] Task 9: Create Page Manual Review API Endpoint (AC: #4)
  - [x] Add endpoint `POST /api/documents/{document_id}/request-manual-review`
  - [x] Accept body: `{ pages: number[] }` - array of page numbers
  - [x] Add `add_pages_to_queue` method to `HumanReviewService`
  - [x] Return success response with review queue count

- [x] Task 10: Update Document Types (AC: #1, #3)
  - [x] Update `frontend/src/types/document.ts`
  - [x] Add `OCRQualityStatus` type
  - [x] Add OCR fields to `Document` and `DocumentListItem` interfaces
  - [x] Add `OCRConfidenceResult`, `PageConfidence` types
  - [x] Add `ManualReviewRequest`, `ManualReviewResponse` types

- [x] Task 11: Update Document API Client (AC: #1, #3, #4)
  - [x] Update `frontend/src/lib/api/documents.ts`
  - [x] Add `fetchOCRQuality(documentId: string): Promise<OCRConfidenceResult>`
  - [x] Add `requestManualReview(documentId: string, pages: number[]): Promise<ManualReviewResponse['data']>`

- [x] Task 12: Write Backend Unit Tests
  - [x] Create `backend/tests/services/ocr/test_confidence_calculator.py`
  - [x] Test confidence calculation from bounding boxes
  - [x] Test quality status determination (Good/Fair/Poor thresholds)
  - [x] Test page-level aggregation
  - [x] Test empty/null handling
  - [x] Test error handling

- [ ] Task 13: Write Backend Integration Tests (DEFERRED)
  - Deferred - basic functionality tested via unit tests

- [ ] Task 14: Write Frontend Component Tests (DEFERRED)
  - Deferred - can be added in a follow-up PR

## Dev Notes

### OCR Quality Thresholds (CRITICAL - Per Architecture)

| Quality Level | Confidence Range | UI Display | Action |
|---------------|------------------|------------|--------|
| Good | >85% | Green badge | No action needed |
| Fair | 70-85% | Yellow badge | Optional review |
| Poor | <70% | Red badge + warning | Manual review suggested |

**Configuration (already in `backend/app/core/config.py` from Story 2b-2):**
```python
class Settings(BaseSettings):
    ocr_quality_good_threshold: float = 0.85  # Above this = Good
    ocr_quality_fair_threshold: float = 0.70  # Above this = Fair, below = Poor
    ocr_page_highlight_threshold: float = 0.60  # Pages below this are highlighted
```

### Database Schema Updates

**Documents table additions:**
```sql
-- Migration: YYYYMMDD_add_ocr_quality_columns.sql

ALTER TABLE public.documents
ADD COLUMN ocr_confidence_avg float,
ADD COLUMN ocr_confidence_per_page jsonb DEFAULT '[]',
ADD COLUMN ocr_quality_status text CHECK (ocr_quality_status IN ('good', 'fair', 'poor'));

-- Index for filtering by OCR quality
CREATE INDEX idx_documents_ocr_quality ON public.documents(ocr_quality_status)
WHERE ocr_quality_status IS NOT NULL;

-- No RLS changes needed - documents table already has matter-based RLS
```

### Previous Story Intelligence

**FROM Story 2b-2 (Gemini OCR Validation):**
- `ocr_validation_log` table tracks all corrections made
- `ocr_human_review` table already exists for manual review queue
- `validation_status` column on documents: 'pending', 'validated', 'requires_human_review'
- Celery task chain: `process_document -> validate_ocr`
- Pattern corrections applied before Gemini validation
- Confidence scores stored in `bounding_boxes` table

**Files from 2b-2 to extend:**
- `backend/app/services/ocr/__init__.py` - Add confidence_calculator export
- `backend/app/workers/tasks/document_tasks.py` - Add confidence calculation to chain
- `backend/app/api/routes/ocr_validation.py` - Already has human review endpoints

**FROM Story 2b-1 (Google Document AI OCR):**
- `bounding_boxes` table contains word-level confidence scores
- `OCRBoundingBox` model has `confidence_score: float` field
- Each bounding box represents a word/text block with position and confidence

### Git Intelligence

Recent commits from previous OCR stories:
```
6affc45 fix(ocr): address code review issues for Story 2b-2
1aff844 feat(ocr): implement Gemini-based OCR validation (Story 2b-2)
200ff41 fix(ocr): address code review issues for Story 2b-1
7321212 feat(ocr): implement Google Document AI OCR integration (Story 2b-1)
```

**Recommended commit message:** `feat(ocr): implement OCR quality assessment display (Story 2b-3)`

### Confidence Calculation Logic

```python
# backend/app/services/ocr/confidence_calculator.py
from app.models.ocr import OCRConfidenceResult, PageConfidence
from app.services.supabase.client import get_supabase_client
from app.core.config import get_settings

async def calculate_document_confidence(document_id: str) -> OCRConfidenceResult:
    """
    Calculate OCR confidence metrics for a document.

    Queries bounding_boxes table, aggregates confidence per page,
    then calculates overall document confidence.
    """
    settings = get_settings()
    supabase = get_supabase_client()

    # Get all bounding boxes for document with confidence scores
    response = await supabase.from_("bounding_boxes") \
        .select("page_number, confidence_score") \
        .eq("document_id", document_id) \
        .execute()

    if not response.data:
        return OCRConfidenceResult(
            document_id=document_id,
            overall_confidence=None,
            page_confidences=[],
            quality_status=None,
            total_words=0
        )

    # Group by page and calculate averages
    page_scores: dict[int, list[float]] = {}
    for bbox in response.data:
        page = bbox["page_number"]
        conf = bbox["confidence_score"]
        if page not in page_scores:
            page_scores[page] = []
        page_scores[page].append(conf)

    # Calculate per-page averages
    page_confidences = [
        PageConfidence(
            page_number=page,
            confidence=sum(scores) / len(scores),
            word_count=len(scores)
        )
        for page, scores in sorted(page_scores.items())
    ]

    # Calculate overall average
    all_scores = [s for scores in page_scores.values() for s in scores]
    overall_confidence = sum(all_scores) / len(all_scores)

    # Determine quality status
    if overall_confidence >= settings.ocr_quality_good_threshold:
        quality_status = "good"
    elif overall_confidence >= settings.ocr_quality_fair_threshold:
        quality_status = "fair"
    else:
        quality_status = "poor"

    return OCRConfidenceResult(
        document_id=document_id,
        overall_confidence=overall_confidence,
        page_confidences=page_confidences,
        quality_status=quality_status,
        total_words=len(all_scores)
    )
```

### Frontend Component Patterns

**OCRQualityBadge component:**
```typescript
// frontend/src/components/features/document/OCRQualityBadge.tsx
'use client';

import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { AlertTriangle, CheckCircle, AlertCircle } from 'lucide-react';

type QualityStatus = 'good' | 'fair' | 'poor' | null;

interface OCRQualityBadgeProps {
  confidence: number | null;
  qualityStatus: QualityStatus;
  showPercentage?: boolean;
}

const QUALITY_CONFIG: Record<NonNullable<QualityStatus>, {
  label: string;
  variant: 'default' | 'secondary' | 'destructive' | 'outline';
  className: string;
  icon: React.ComponentType<{ className?: string }>;
  tooltip: string;
}> = {
  good: {
    label: 'Good',
    variant: 'default',
    className: 'bg-green-100 text-green-800 hover:bg-green-100',
    icon: CheckCircle,
    tooltip: 'High OCR accuracy (>85%). Text extraction is reliable.',
  },
  fair: {
    label: 'Fair',
    variant: 'secondary',
    className: 'bg-yellow-100 text-yellow-800 hover:bg-yellow-100',
    icon: AlertCircle,
    tooltip: 'Moderate OCR accuracy (70-85%). Some words may need verification.',
  },
  poor: {
    label: 'Poor',
    variant: 'destructive',
    className: 'bg-red-100 text-red-800 hover:bg-red-100',
    icon: AlertTriangle,
    tooltip: 'Low OCR accuracy (<70%). Manual review recommended.',
  },
};

export function OCRQualityBadge({
  confidence,
  qualityStatus,
  showPercentage = true,
}: OCRQualityBadgeProps) {
  if (qualityStatus === null || confidence === null) {
    return (
      <Badge variant="outline" className="text-muted-foreground">
        Pending
      </Badge>
    );
  }

  const config = QUALITY_CONFIG[qualityStatus];
  const Icon = config.icon;
  const percentage = Math.round(confidence * 100);

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge variant={config.variant} className={config.className}>
            <Icon className="w-3 h-3 mr-1" />
            {showPercentage ? `${percentage}%` : config.label}
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          <p className="max-w-xs">{config.tooltip}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
```

### Critical Architecture Constraints

**FROM PROJECT-CONTEXT.md - MUST FOLLOW EXACTLY:**

#### Naming Conventions
| Layer | Convention | Example |
|-------|------------|---------|
| Database columns | snake_case | `ocr_confidence_avg`, `ocr_quality_status` |
| TypeScript variables | camelCase | `ocrConfidenceAvg`, `qualityStatus` |
| React components | PascalCase | `OCRQualityBadge`, `ManualReviewDialog` |
| API endpoints | kebab-case in path | `/ocr-quality`, `/request-manual-review` |

#### API Response Format (MANDATORY)
```python
# Success
{
  "data": {
    "document_id": "uuid",
    "overall_confidence": 0.87,
    "quality_status": "good",
    "page_confidences": [0.92, 0.85, 0.88, ...]
  }
}

# Error
{ "error": { "code": "DOCUMENT_NOT_FOUND", "message": "...", "details": {} } }
```

#### Zustand State (NOT needed for this story)
This story uses direct API calls via React Query patterns in the existing DocumentList component. No new Zustand stores required.

### File Organization

```
backend/app/
├── services/
│   └── ocr/
│       ├── __init__.py                    (UPDATE) - Export confidence_calculator
│       └── confidence_calculator.py       (NEW) - Confidence calculation
├── models/
│   └── ocr_confidence.py                  (NEW) - Confidence result models
├── workers/
│   └── tasks/
│       └── document_tasks.py              (UPDATE) - Add calculate_confidence to chain
└── api/
    └── routes/
        └── documents.py                   (UPDATE) - Add OCR quality endpoints

frontend/src/
├── components/
│   └── features/
│       └── document/
│           ├── DocumentList.tsx           (UPDATE) - Add OCR quality column
│           ├── OCRQualityBadge.tsx        (NEW) - Quality indicator badge
│           ├── OCRQualityBadge.test.tsx   (NEW) - Badge tests
│           ├── OCRQualityDetail.tsx       (NEW) - Page breakdown view
│           ├── OCRQualityDetail.test.tsx  (NEW) - Detail tests
│           ├── ManualReviewDialog.tsx     (NEW) - Review request dialog
│           └── ManualReviewDialog.test.tsx (NEW) - Dialog tests
├── types/
│   └── document.ts                        (UPDATE) - Add OCR quality types
└── lib/
    └── api/
        └── documents.ts                   (UPDATE) - Add OCR quality API calls

supabase/migrations/
└── YYYYMMDD_add_ocr_quality_columns.sql   (NEW) - Database migration

backend/tests/
├── services/
│   └── ocr/
│       └── test_confidence_calculator.py  (NEW) - Unit tests
└── integration/
    └── test_ocr_quality_integration.py    (NEW) - Integration tests
```

### Testing Guidance

#### Unit Tests - Backend

```python
# backend/tests/services/ocr/test_confidence_calculator.py
import pytest
from unittest.mock import Mock, patch
from app.services.ocr.confidence_calculator import calculate_document_confidence

@pytest.fixture
def mock_bounding_boxes():
    """Mock bounding box data with various confidence levels."""
    return [
        {"page_number": 1, "confidence_score": 0.95},
        {"page_number": 1, "confidence_score": 0.88},
        {"page_number": 1, "confidence_score": 0.92},
        {"page_number": 2, "confidence_score": 0.75},
        {"page_number": 2, "confidence_score": 0.68},
    ]

@pytest.mark.asyncio
async def test_good_quality_document(mock_bounding_boxes_high):
    """Test document with >85% confidence gets 'good' status."""
    # Mock all confidence scores > 85%
    result = await calculate_document_confidence("doc-id")
    assert result.quality_status == "good"
    assert result.overall_confidence > 0.85

@pytest.mark.asyncio
async def test_fair_quality_document(mock_bounding_boxes_medium):
    """Test document with 70-85% confidence gets 'fair' status."""
    result = await calculate_document_confidence("doc-id")
    assert result.quality_status == "fair"
    assert 0.70 <= result.overall_confidence < 0.85

@pytest.mark.asyncio
async def test_poor_quality_document(mock_bounding_boxes_low):
    """Test document with <70% confidence gets 'poor' status."""
    result = await calculate_document_confidence("doc-id")
    assert result.quality_status == "poor"
    assert result.overall_confidence < 0.70

@pytest.mark.asyncio
async def test_page_level_breakdown():
    """Test that page-level confidence is calculated correctly."""
    result = await calculate_document_confidence("doc-id")
    assert len(result.page_confidences) > 0
    for page in result.page_confidences:
        assert 0 <= page.confidence <= 1
        assert page.word_count > 0

@pytest.mark.asyncio
async def test_empty_document():
    """Test handling of document with no bounding boxes."""
    result = await calculate_document_confidence("empty-doc")
    assert result.overall_confidence is None
    assert result.quality_status is None
```

#### Unit Tests - Frontend

```typescript
// frontend/src/components/features/document/OCRQualityBadge.test.tsx
import { render, screen } from '@testing-library/react';
import { OCRQualityBadge } from './OCRQualityBadge';

describe('OCRQualityBadge', () => {
  test('renders Good badge for >85% confidence', () => {
    render(<OCRQualityBadge confidence={0.92} qualityStatus="good" />);
    expect(screen.getByText('92%')).toBeInTheDocument();
    // Badge should have green styling (implementation-dependent)
  });

  test('renders Fair badge for 70-85% confidence', () => {
    render(<OCRQualityBadge confidence={0.78} qualityStatus="fair" />);
    expect(screen.getByText('78%')).toBeInTheDocument();
  });

  test('renders Poor badge for <70% confidence', () => {
    render(<OCRQualityBadge confidence={0.55} qualityStatus="poor" />);
    expect(screen.getByText('55%')).toBeInTheDocument();
  });

  test('renders Pending for null values', () => {
    render(<OCRQualityBadge confidence={null} qualityStatus={null} />);
    expect(screen.getByText('Pending')).toBeInTheDocument();
  });

  test('shows tooltip on hover', async () => {
    const { user } = render(<OCRQualityBadge confidence={0.55} qualityStatus="poor" />);
    const badge = screen.getByText('55%');
    await user.hover(badge);
    expect(screen.getByText(/Low OCR accuracy/)).toBeInTheDocument();
  });
});
```

### Anti-Patterns to AVOID

```typescript
// WRONG: Calculating confidence on the frontend
const confidence = documents.map(d => {
  const sum = d.boundingBoxes.reduce((a, b) => a + b.confidence, 0);
  return sum / d.boundingBoxes.length;
}); // This should be done on backend!

// CORRECT: Use pre-calculated backend value
const confidence = document.ocrConfidenceAvg;

// WRONG: Inline badge styling without semantic meaning
<span className="text-red-500">Poor</span>

// CORRECT: Use semantic Badge component with accessibility
<Badge variant="destructive" role="status" aria-label="Poor OCR quality: 55%">
  <AlertTriangle className="w-3 h-3 mr-1" />
  55%
</Badge>

// WRONG: Not handling loading/pending states
{document.ocrConfidenceAvg && <OCRQualityBadge ... />}

// CORRECT: Explicit null handling
<OCRQualityBadge
  confidence={document.ocrConfidenceAvg}
  qualityStatus={document.ocrQualityStatus}
/>
```

### Performance Considerations

- **Pre-calculate on backend:** Confidence is calculated once during processing, not on every API call
- **Indexed queries:** `ocr_quality_status` column is indexed for fast filtering
- **Pagination:** DocumentList already implements pagination, quality column adds minimal overhead
- **Lazy load detail:** OCRQualityDetail only fetches page breakdown when user opens document detail

### Environment Variables Required

No new environment variables required. Uses existing thresholds from Story 2b-2:
```bash
# Already in backend/.env from Story 2b-2
OCR_VALIDATION_GEMINI_THRESHOLD=0.85
OCR_VALIDATION_HUMAN_THRESHOLD=0.50

# Optional: Override default quality thresholds
OCR_QUALITY_GOOD_THRESHOLD=0.85
OCR_QUALITY_FAIR_THRESHOLD=0.70
OCR_PAGE_HIGHLIGHT_THRESHOLD=0.60
```

### Manual Steps Required After Implementation

**⚠️ NOTE: Manual steps still pending - complete before marking story truly "done"**

#### Migrations
- [ ] Run: `supabase db push` or apply `YYYYMMDD_add_ocr_quality_columns.sql`
- [ ] Verify new columns exist on documents table
- [ ] Verify index created for ocr_quality_status

#### Manual Tests
- [ ] Upload a clear, high-quality PDF - verify "Good" (green) badge appears
- [ ] Upload a low-quality scanned PDF - verify "Poor" (red) badge appears
- [ ] Click on a Poor quality document - verify page breakdown displays
- [ ] Click "Request Manual Review" - verify dialog opens with page selection
- [ ] Submit manual review request - verify pages added to human review queue
- [ ] Filter document list by OCR quality - verify filtering works
- [ ] Sort document list by OCR quality - verify sorting works

### Downstream Dependencies

This story enables:
- **Epic 3 (Citation Engine):** Quality indicator helps attorneys trust citation verification
- **Epic 10D (Documents Tab):** OCR quality column in workspace documents view
- **Export Builder:** Can filter/exclude low-quality documents from exports

### Project Structure Notes

- OCR quality is calculated as part of document processing pipeline
- Quality is per-document, with page-level breakdown available on demand
- Human review queue (from 2b-2) is reused for manual review requests
- Badge component follows existing DocumentTypeBadge pattern

### References

- [Source: _bmad-output/architecture.md#OCR-Quality-Routing] - Quality thresholds
- [Source: _bmad-output/project-context.md#Confidence-Thresholds] - Confidence tiers
- [Source: _bmad-output/project-planning-artifacts/epics.md#Story-2.5.1] - Acceptance criteria
- [Source: _bmad-output/implementation-artifacts/2b-2-gemini-ocr-validation.md] - Previous story patterns
- [Source: frontend/src/components/features/document/DocumentList.tsx] - Existing document list
- [Source: frontend/src/components/features/document/DocumentTypeBadge.tsx] - Badge pattern reference
- [Source: backend/app/services/ocr/human_review_service.py] - Human review queue (from 2b-2)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- All 12 core tasks completed successfully
- Backend integration tests (Task 13) and Frontend component tests (Task 14) deferred to follow-up PR
- Migration file created at `supabase/migrations/20260108000002_add_ocr_quality_columns.sql`
- Existing `ocr_confidence` column from Story 2b-1 reused as the average confidence
- Task chain updated: `process_document -> validate_ocr -> calculate_confidence`
- Three new frontend components created: OCRQualityBadge, OCRQualityDetail, ManualReviewDialog
- DocumentList updated to show OCR Quality column with badge
- Human review service extended with `add_pages_to_queue` method for page-level review requests

### File List

**Backend (New):**
- `supabase/migrations/20260108000002_add_ocr_quality_columns.sql`
- `backend/app/models/ocr_confidence.py`
- `backend/app/services/ocr/confidence_calculator.py`
- `backend/tests/services/ocr/test_confidence_calculator.py`

**Backend (Modified):**
- `backend/app/core/config.py` - Added OCR quality thresholds
- `backend/app/models/document.py` - Added ocr_confidence_per_page, ocr_quality_status fields
- `backend/app/services/document_service.py` - Updated _parse_document and _parse_list_item
- `backend/app/services/ocr/__init__.py` - Export confidence calculator
- `backend/app/services/ocr/human_review_service.py` - Added add_pages_to_queue method
- `backend/app/workers/tasks/document_tasks.py` - Added calculate_confidence task
- `backend/app/api/routes/documents.py` - Added ocr-quality and request-manual-review endpoints

**Frontend (New):**
- `frontend/src/components/features/document/OCRQualityBadge.tsx`
- `frontend/src/components/features/document/OCRQualityDetail.tsx`
- `frontend/src/components/features/document/ManualReviewDialog.tsx`

**Frontend (Modified):**
- `frontend/src/types/document.ts` - Added OCR quality types
- `frontend/src/lib/api/documents.ts` - Added fetchOCRQuality and requestManualReview
- `frontend/src/components/features/document/DocumentList.tsx` - Added OCR Quality column
