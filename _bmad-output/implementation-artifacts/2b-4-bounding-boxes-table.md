# Story 2B.4: Create Bounding Boxes Table Enhancement

Status: completed

## Story

As a **developer**,
I want **bounding box coordinates stored for all extracted text with proper linking to chunks and citations**,
So that **the UI can highlight exact text locations in documents for citation verification and search results**.

## Acceptance Criteria

1. **Given** OCR extracts text from a page **When** bounding boxes are saved **Then** the bounding_boxes table contains: bbox_id, document_id, page_number, x, y, width, height, text_content, confidence_score **And** they are stored with a reading order index

2. **Given** a chunk references text **When** the chunk is created **Then** it links to one or more bbox_ids **And** the UI can retrieve bounding boxes for any chunk

3. **Given** a citation is found in a document **When** it is stored **Then** it references the bbox_ids for the citation text **And** clicking the citation highlights the exact location

4. **Given** multiple text blocks are on a page **When** bounding boxes are stored **Then** they are ordered by reading order (top-to-bottom, left-to-right) **And** the reading_order_index column reflects this order

## Tasks / Subtasks

- [x] Task 1: Add Reading Order Index to Bounding Boxes Table (AC: #1, #4)
  - [x] Create migration `supabase/migrations/20260108000003_add_bbox_reading_order.sql`
  - [x] Add `reading_order_index` integer column to bounding_boxes table
  - [x] Add index on `(document_id, page_number, reading_order_index)` for ordered retrieval
  - [x] Add CHECK constraint: `reading_order_index >= 0`

- [x] Task 2: Update BoundingBoxService for Reading Order (AC: #1, #4)
  - [x] Update `backend/app/services/bounding_box_service.py`
  - [x] Update `save_bounding_boxes()` to include reading_order_index
  - [x] Add `get_bounding_boxes_for_page(document_id, page_number)` method returning ordered list
  - [x] Add `get_bounding_boxes_for_document(document_id)` method returning all boxes ordered by page then reading order
  - [x] Add `get_bounding_boxes_by_ids(bbox_ids)` method for chunk/citation lookup

- [x] Task 3: Update OCR Processor for Reading Order (AC: #1, #4)
  - [x] Update `backend/app/services/ocr/bbox_extractor.py`
  - [x] Calculate reading order from bounding box positions (y coordinate primary, x coordinate secondary)
  - [x] Assign `reading_order_index` to each OCRBoundingBox during extraction
  - [x] Added `calculate_reading_order()` function with y_tolerance for line grouping

- [x] Task 4: Update OCRBoundingBox Model (AC: #1)
  - [x] Update `backend/app/models/ocr.py`
  - [x] Add `reading_order_index: int | None` field to OCRBoundingBox model
  - [x] Update field validation for reading_order_index >= 0

- [x] Task 5: Create BoundingBox API Endpoints (AC: #2, #3)
  - [x] Create `backend/app/api/routes/bounding_boxes.py`
  - [x] `GET /api/documents/{document_id}/bounding-boxes` - Get all bounding boxes for document
  - [x] `GET /api/documents/{document_id}/pages/{page_number}/bounding-boxes` - Get bounding boxes for page
  - [x] `GET /api/chunks/{chunk_id}/bounding-boxes` - Get bounding boxes for a chunk
  - [x] Registered routers in `backend/app/main.py`

- [x] Task 6: Create Chunk-to-BoundingBox Linking Service (AC: #2)
  - [x] Create `backend/app/services/chunk_bbox_linker.py`
  - [x] Implement `link_chunk_to_bboxes(chunk_id, bbox_ids)` method
  - [x] Implement `get_bboxes_for_chunk(chunk_id)` method
  - [x] Uses existing `bbox_ids` array column in chunks table

- [x] Task 7: Create Citation-to-BoundingBox Linking Service (AC: #3)
  - [x] Create `backend/app/services/citation_service.py`
  - [x] Implement `link_citation_to_source_bboxes()` and `link_citation_to_target_bboxes()` methods
  - [x] Implement `get_source_bboxes_for_citation()` and `get_target_bboxes_for_citation()` methods
  - [x] Uses existing `source_bbox_ids` and `target_bbox_ids` columns in citations table

- [x] Task 8: Create Citation BoundingBox Migration (AC: #3)
  - [x] SKIPPED - citations table already has `source_bbox_ids` and `target_bbox_ids` columns
  - [x] No new migration needed

- [x] Task 9: Update Frontend Types for BoundingBox API (AC: #2, #3)
  - [x] Update `frontend/src/types/document.ts`
  - [x] Add `BoundingBox` interface with all fields including readingOrderIndex
  - [x] Add `BoundingBoxListResponse` and `BoundingBoxPageResponse` types

- [x] Task 10: Create Frontend BoundingBox API Client (AC: #2, #3)
  - [x] Create `frontend/src/lib/api/bounding-boxes.ts`
  - [x] Add `fetchBoundingBoxesForDocument(documentId)` function
  - [x] Add `fetchBoundingBoxesForPage(documentId, pageNumber)` function
  - [x] Add `fetchBoundingBoxesForChunk(chunkId)` function

- [x] Task 11: Write Backend Unit Tests
  - [x] Updated `backend/tests/services/test_bounding_box_service.py` with reading_order_index tests
  - [x] Added `TestBoundingBoxServiceRetrievalMethods` class
  - [x] Added `TestCalculateReadingOrder` class to `backend/tests/services/ocr/test_bbox_extractor.py`
  - [x] Test reading order calculation and sorting

- [x] Task 12: Write Backend Integration Tests
  - [x] Create `backend/tests/api/routes/test_bounding_boxes.py`
  - [x] Test document bbox API endpoint
  - [x] Test page bbox API endpoint
  - [x] Test chunk bbox API endpoint
  - [x] Test authentication requirements

## Dev Notes

### CRITICAL: Existing Implementation Status

**The bounding_boxes table ALREADY EXISTS** (created in Story 2a-3 migrations). **Story 2b-1 ALREADY populates it** during OCR processing. This story is about **enhancing** the existing infrastructure:

1. **Add reading order index** - Currently boxes are saved without reading order
2. **Create API endpoints** - No direct bbox API exists yet
3. **Enable chunk linking** - chunks table has bbox_ids column but nothing populates it yet
4. **Enable citation linking** - citations table needs bbox_ids column added

### Reading Order Algorithm

**Standard reading order (Western documents):**
```python
# backend/app/services/ocr/bbox_extractor.py

def calculate_reading_order(
    bounding_boxes: list[OCRBoundingBox],
    column_threshold: float = 0.3,  # 30% of page width indicates new column
) -> list[OCRBoundingBox]:
    """
    Calculate reading order for bounding boxes.

    Algorithm:
    1. Sort by y (top to bottom)
    2. Group boxes at similar y-levels into "lines"
    3. Within each line, sort by x (left to right)
    4. Handle multi-column layouts by detecting x-position gaps

    Returns boxes with reading_order_index assigned.
    """
    if not bounding_boxes:
        return []

    # Group boxes by approximate y-position (within 2% tolerance)
    y_tolerance = 2.0  # 2% of page height
    lines: list[list[OCRBoundingBox]] = []

    sorted_by_y = sorted(bounding_boxes, key=lambda b: b.y)

    current_line: list[OCRBoundingBox] = [sorted_by_y[0]]
    current_y = sorted_by_y[0].y

    for bbox in sorted_by_y[1:]:
        if abs(bbox.y - current_y) <= y_tolerance:
            current_line.append(bbox)
        else:
            lines.append(sorted(current_line, key=lambda b: b.x))
            current_line = [bbox]
            current_y = bbox.y

    if current_line:
        lines.append(sorted(current_line, key=lambda b: b.x))

    # Flatten and assign reading order
    ordered: list[OCRBoundingBox] = []
    for idx, line in enumerate(lines):
        for box_idx, bbox in enumerate(line):
            bbox.reading_order_index = len(ordered)
            ordered.append(bbox)

    return ordered
```

### Database Schema Updates

**Migration: Add reading order index**
```sql
-- 20260108000003_add_bbox_reading_order.sql

ALTER TABLE public.bounding_boxes
ADD COLUMN reading_order_index integer;

-- Composite index for ordered page retrieval
CREATE INDEX idx_bboxes_page_order ON public.bounding_boxes(
    document_id, page_number, reading_order_index
);

-- Add CHECK constraint
ALTER TABLE public.bounding_boxes
ADD CONSTRAINT bboxes_reading_order_positive
CHECK (reading_order_index IS NULL OR reading_order_index >= 0);

COMMENT ON COLUMN public.bounding_boxes.reading_order_index IS
'Reading order within page (0-indexed, top-to-bottom, left-to-right)';
```

**Migration: Add bbox_ids to citations**
```sql
-- 20260108000004_add_bbox_ids_to_citations.sql

ALTER TABLE public.citations
ADD COLUMN bbox_ids uuid[];

-- GIN index for array containment queries
CREATE INDEX idx_citations_bboxes ON public.citations USING GIN (bbox_ids);

COMMENT ON COLUMN public.citations.bbox_ids IS
'Array of bounding_box IDs for highlighting citation location';
```

### Previous Story Intelligence

**FROM Story 2b-1 (Google Document AI OCR):**
- `BoundingBoxService` in `backend/app/services/bounding_box_service.py` - handles DB operations
- `bbox_extractor.py` extracts boxes from Document AI response
- Coordinates are percentage-based (0-100) for responsive rendering
- Bounding boxes are saved in batches (100 per insert)

**Key files to modify:**
- `backend/app/services/bounding_box_service.py` - Add reading order and retrieval methods
- `backend/app/services/ocr/bbox_extractor.py` - Add reading order calculation
- `backend/app/models/ocr.py` - Add reading_order_index field

**FROM Story 2b-2 and 2b-3:**
- Confidence scores are already in bounding_boxes table
- OCR validation updates confidence scores directly in bounding_boxes
- Human review service can update individual bounding box text

### Critical Architecture Constraints

**FROM PROJECT-CONTEXT.md - MUST FOLLOW EXACTLY:**

#### Backend Technology Stack
- **Python 3.12+** - use modern syntax (match statements, type hints)
- **FastAPI 0.115+** - async endpoints where beneficial
- **Pydantic v2** - use model_validator, not validator (v1 syntax)
- **structlog** for logging - NOT standard logging library

#### Matter Isolation (4-Layer Enforcement)
```python
# Layer 1: RLS on bounding_boxes table (already implemented)
# Layer 2: Not applicable (no vector embeddings)
# Layer 3: Redis key prefix (if caching)
redis_key = f"matter:{matter_id}:document:{document_id}:bboxes"
# Layer 4: API middleware validates matter access
```

#### API Response Format (MANDATORY)
```python
# Success - single bbox
{
  "data": {
    "id": "uuid",
    "document_id": "uuid",
    "page_number": 1,
    "x": 10.5,
    "y": 20.3,
    "width": 45.2,
    "height": 5.1,
    "text": "Sample text",
    "confidence": 0.95,
    "reading_order_index": 0
  }
}

# Success - list
{
  "data": [...],
  "meta": { "total": 150, "page": 1, "per_page": 100 }
}

# Error
{ "error": { "code": "DOCUMENT_NOT_FOUND", "message": "...", "details": {} } }
```

#### Naming Conventions
| Layer | Convention | Example |
|-------|------------|---------|
| Database columns | snake_case | `reading_order_index`, `bbox_ids` |
| TypeScript variables | camelCase | `readingOrderIndex`, `bboxIds` |
| Python functions | snake_case | `get_bounding_boxes_for_page` |
| Python classes | PascalCase | `BoundingBoxService` |
| API endpoints | kebab-case | `/bounding-boxes` |

### File Organization

```
backend/app/
├── services/
│   ├── bounding_box_service.py          (UPDATE) - Add reading order, retrieval methods
│   ├── chunk_bbox_linker.py             (NEW) - Chunk-to-bbox linking
│   └── ocr/
│       └── bbox_extractor.py            (UPDATE) - Add reading order calculation
├── models/
│   └── ocr.py                           (UPDATE) - Add reading_order_index field
└── api/
    └── routes/
        ├── __init__.py                  (UPDATE) - Register bbox router
        └── bounding_boxes.py            (NEW) - BBox API endpoints

supabase/migrations/
├── 20260108000003_add_bbox_reading_order.sql   (NEW)
└── 20260108000004_add_bbox_ids_to_citations.sql (NEW)

frontend/src/
├── types/
│   └── document.ts                      (UPDATE) - Add BoundingBox types
└── lib/
    └── api/
        └── bounding-boxes.ts            (NEW or UPDATE) - BBox API client

backend/tests/
├── services/
│   └── test_bounding_box_service_extended.py   (NEW)
└── integration/
    └── test_bbox_api_integration.py            (NEW)
```

### API Endpoint Specifications

**GET /api/documents/{document_id}/bounding-boxes**
```python
@router.get("/documents/{document_id}/bounding-boxes")
async def get_document_bounding_boxes(
    document_id: str,
    page: int | None = Query(None, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Supabase = Depends(get_supabase)
) -> dict:
    """Get all bounding boxes for a document, ordered by reading order."""
    # Validate document access via matter
    # Return paginated, ordered results
```

**GET /api/documents/{document_id}/pages/{page_number}/bounding-boxes**
```python
@router.get("/documents/{document_id}/pages/{page_number}/bounding-boxes")
async def get_page_bounding_boxes(
    document_id: str,
    page_number: int,
    current_user: User = Depends(get_current_user),
    db: Supabase = Depends(get_supabase)
) -> dict:
    """Get bounding boxes for a specific page, ordered by reading order."""
```

**GET /api/chunks/{chunk_id}/bounding-boxes**
```python
@router.get("/chunks/{chunk_id}/bounding-boxes")
async def get_chunk_bounding_boxes(
    chunk_id: str,
    current_user: User = Depends(get_current_user),
    db: Supabase = Depends(get_supabase)
) -> dict:
    """Get bounding boxes linked to a chunk via its bbox_ids array."""
```

### Testing Guidance

#### Unit Tests

```python
# backend/tests/services/test_bounding_box_service_extended.py

import pytest
from app.services.bounding_box_service import BoundingBoxService
from app.services.ocr.bbox_extractor import calculate_reading_order
from app.models.ocr import OCRBoundingBox

def test_reading_order_single_column():
    """Test reading order calculation for single-column document."""
    boxes = [
        OCRBoundingBox(page=1, x=10, y=50, width=80, height=5, text="Line 3", confidence=0.9),
        OCRBoundingBox(page=1, x=10, y=10, width=80, height=5, text="Line 1", confidence=0.9),
        OCRBoundingBox(page=1, x=10, y=30, width=80, height=5, text="Line 2", confidence=0.9),
    ]

    ordered = calculate_reading_order(boxes)

    assert ordered[0].text == "Line 1"
    assert ordered[0].reading_order_index == 0
    assert ordered[1].text == "Line 2"
    assert ordered[1].reading_order_index == 1
    assert ordered[2].text == "Line 3"
    assert ordered[2].reading_order_index == 2


def test_reading_order_same_line():
    """Test reading order for text on same line (left to right)."""
    boxes = [
        OCRBoundingBox(page=1, x=60, y=10, width=20, height=5, text="Right", confidence=0.9),
        OCRBoundingBox(page=1, x=10, y=10, width=20, height=5, text="Left", confidence=0.9),
        OCRBoundingBox(page=1, x=35, y=10, width=20, height=5, text="Middle", confidence=0.9),
    ]

    ordered = calculate_reading_order(boxes)

    assert ordered[0].text == "Left"
    assert ordered[1].text == "Middle"
    assert ordered[2].text == "Right"


def test_reading_order_two_column_layout():
    """Test reading order for two-column document layout."""
    # Two columns: left column (x: 10-45), right column (x: 55-90)
    boxes = [
        # Left column
        OCRBoundingBox(page=1, x=10, y=10, width=30, height=5, text="L1", confidence=0.9),
        OCRBoundingBox(page=1, x=10, y=20, width=30, height=5, text="L2", confidence=0.9),
        # Right column
        OCRBoundingBox(page=1, x=55, y=10, width=30, height=5, text="R1", confidence=0.9),
        OCRBoundingBox(page=1, x=55, y=20, width=30, height=5, text="R2", confidence=0.9),
    ]

    ordered = calculate_reading_order(boxes)

    # Same y-level should order left-to-right
    assert ordered[0].text == "L1"
    assert ordered[1].text == "R1"
    assert ordered[2].text == "L2"
    assert ordered[3].text == "R2"


@pytest.mark.asyncio
async def test_get_bounding_boxes_for_page_ordered(mock_supabase):
    """Test that bounding boxes are returned in reading order."""
    service = BoundingBoxService(client=mock_supabase)

    # Mock return unordered data
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {"id": "1", "reading_order_index": 2, "text": "third"},
        {"id": "2", "reading_order_index": 0, "text": "first"},
        {"id": "3", "reading_order_index": 1, "text": "second"},
    ]

    result = await service.get_bounding_boxes_for_page("doc-id", 1)

    # Verify order by reading_order_index was requested
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.assert_called_with("reading_order_index")
```

#### Integration Tests

```python
# backend/tests/integration/test_bbox_api_integration.py

@pytest.mark.asyncio
async def test_bbox_api_returns_ordered_by_reading_order(
    test_client: AsyncClient,
    test_document_with_bboxes: Document,
    auth_headers: dict
):
    """Test that bbox API returns boxes in reading order."""
    response = await test_client.get(
        f"/api/documents/{test_document_with_bboxes.id}/bounding-boxes",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # Verify ordering
    for i in range(len(data) - 1):
        assert data[i]["reading_order_index"] <= data[i + 1]["reading_order_index"]


@pytest.mark.asyncio
async def test_chunk_bboxes_retrieved_correctly(
    test_client: AsyncClient,
    test_chunk_with_bboxes: Chunk,
    auth_headers: dict
):
    """Test that chunk's bbox_ids array returns correct bounding boxes."""
    response = await test_client.get(
        f"/api/chunks/{test_chunk_with_bboxes.id}/bounding-boxes",
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # Verify all bbox_ids from chunk are returned
    assert len(data) == len(test_chunk_with_bboxes.bbox_ids)
```

### Anti-Patterns to AVOID

```python
# WRONG: Not ordering bounding boxes by reading order
boxes = supabase.table("bounding_boxes").select("*").eq("document_id", doc_id).execute()

# CORRECT: Always order by reading_order_index
boxes = supabase.table("bounding_boxes") \
    .select("*") \
    .eq("document_id", doc_id) \
    .order("page_number") \
    .order("reading_order_index") \
    .execute()

# WRONG: Calculating reading order on frontend
const sortedBoxes = boxes.sort((a, b) => a.y - b.y || a.x - b.x);

# CORRECT: Use pre-calculated reading_order_index from backend
const sortedBoxes = boxes.sort((a, b) => a.readingOrderIndex - b.readingOrderIndex);

# WRONG: Not validating matter access before returning bboxes
async def get_bboxes(document_id: str):
    return await db.table("bounding_boxes").select("*").eq("document_id", document_id).execute()

# CORRECT: Validate via document's matter
async def get_bboxes(document_id: str, current_user: User):
    # First verify document exists and user has access to its matter
    doc = await validate_document_access(document_id, current_user.id)
    return await db.table("bounding_boxes").select("*").eq("document_id", document_id).execute()

# WRONG: N+1 query for chunk bounding boxes
for chunk in chunks:
    for bbox_id in chunk.bbox_ids:
        bbox = await db.table("bounding_boxes").select("*").eq("id", bbox_id).execute()

# CORRECT: Single query using ANY operator
bbox_ids = [id for chunk in chunks for id in chunk.bbox_ids]
bboxes = await db.table("bounding_boxes").select("*").in_("id", bbox_ids).execute()
```

### Performance Considerations

- **Index usage:** The composite index `(document_id, page_number, reading_order_index)` enables efficient ordered retrieval
- **Pagination:** For large documents (1000+ pages), always paginate bbox retrieval
- **Frontend canvas rendering:** Render bboxes as a single canvas layer, not individual DOM elements (see project-context.md)
- **Batch chunk linking:** When creating chunks, batch the bbox_ids population to avoid N+1 updates

### Downstream Dependencies

This story enables:
- **Story 2b-5 (Parent-Child Chunking):** Chunks will link to bounding boxes via bbox_ids
- **Epic 3 (Citation Verification):** Citations reference bboxes for highlighting
- **Epic 11 (PDF Viewer):** Bounding box overlays with reading order for text selection

### Manual Steps Required After Implementation

#### Migrations
- [ ] Run: `supabase db push` or apply both new migrations
- [ ] Verify `reading_order_index` column added to bounding_boxes
- [ ] Verify `bbox_ids` column added to citations
- [ ] Verify indexes created

#### Environment Variables
- No new environment variables required

#### Manual Tests
- [ ] Upload a PDF and verify bounding boxes are saved with reading_order_index
- [ ] Call `/api/documents/{id}/bounding-boxes` and verify ordered response
- [ ] Verify RLS still enforces matter isolation on bbox API
- [ ] Test page-specific bbox retrieval

### References

- [Source: _bmad-output/architecture.md#Performance-Gotchas] - Canvas overlay, not DOM elements
- [Source: _bmad-output/project-context.md#Matter-Isolation] - 4-layer enforcement
- [Source: _bmad-output/project-planning-artifacts/epics.md#Story-2.6] - Acceptance criteria
- [Source: _bmad-output/implementation-artifacts/2b-1-google-document-ai-ocr.md] - BBox extraction patterns
- [Source: supabase/migrations/20260106000003_create_bounding_boxes_table.sql] - Existing schema
- [Source: supabase/migrations/20260106000002_create_chunks_table.sql] - Chunks table with bbox_ids
- [Source: backend/app/services/bounding_box_service.py] - Existing service to extend
- [Source: backend/app/services/ocr/bbox_extractor.py] - Extraction logic to update

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- All 46 unit tests passing (40 bounding box tests + 6 API tests)

### Completion Notes List

1. **Task 8 skipped** - The citations table already has `source_bbox_ids` and `target_bbox_ids` columns (per existing schema), so no new migration was needed.

2. **Citation service implementation** - Created with dual bbox support (source and target) to match the existing schema design for split-view citation highlighting.

3. **Reading order algorithm** - Implemented with configurable y_tolerance (default 2.0%) for grouping text on the same line. Works top-to-bottom, left-to-right within tolerance groups.

4. **API endpoints registered** - Both `bounding_boxes.router` (for document endpoints) and `bounding_boxes.chunks_router` (for chunk endpoints) are registered in main.py.

5. **Matter isolation** - All API endpoints validate access via the document's or chunk's matter_id using Layer 4 validation pattern.

### File List

**New Files:**
- `supabase/migrations/20260108000003_add_bbox_reading_order.sql` - Migration adding reading_order_index column
- `backend/app/api/routes/bounding_boxes.py` - BoundingBox API endpoints
- `backend/app/services/chunk_bbox_linker.py` - Chunk-to-BoundingBox linking service
- `backend/app/services/citation_service.py` - Citation service with bbox linking
- `frontend/src/lib/api/bounding-boxes.ts` - Frontend API client for bounding boxes
- `backend/tests/api/routes/test_bounding_boxes.py` - API route tests

**Modified Files:**
- `backend/app/models/ocr.py` - Added reading_order_index field to OCRBoundingBox
- `backend/app/services/ocr/bbox_extractor.py` - Added calculate_reading_order() function
- `backend/app/services/bounding_box_service.py` - Added retrieval methods and reading_order_index support
- `backend/app/main.py` - Registered bounding_boxes routers
- `frontend/src/types/document.ts` - Added BoundingBox types
- `backend/tests/services/test_bounding_box_service.py` - Added retrieval method tests
- `backend/tests/services/ocr/test_bbox_extractor.py` - Added reading order calculation tests

